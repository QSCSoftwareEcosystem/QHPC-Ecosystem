"""Storage-aware asynchronous Slurm and Apptainer operation runner."""

from __future__ import annotations

import json
import os
import re
import shutil
import time
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterable
from urllib.parse import unquote, urlparse

from .contract import load_document, validate_contract_data
from .engine import ArtifactResult, TaskRequest, TaskResult
from .operation_runtime import file_digest
from .slurm import (
    ApptainerBind,
    NodeLocalStaging,
    SlurmClient,
    SlurmResources,
    render_apptainer_job,
)
from .worker import TargetStatus, TargetSubmission


class SlurmApptainerError(RuntimeError):
    """A target, storage, runtime, or staged artifact violates admission policy."""


def load_execution_target(path: str | Path) -> dict[str, Any]:
    document = load_document(path)
    validate_contract_data("execution-target", document)
    return document


def load_storage_profile(path: str | Path) -> dict[str, Any]:
    document = load_document(path)
    validate_contract_data("storage-profile", document)
    return document


def _elapsed_ms(started: float) -> int:
    return max(0, round((time.perf_counter() - started) * 1000))


def _local_uri(value: str, label: str) -> Path:
    if value.startswith("file://"):
        parsed = urlparse(value)
        if parsed.netloc not in {"", "localhost"}:
            raise SlurmApptainerError(f"{label} must use a local file URI")
        value = unquote(parsed.path)
    elif "://" in value:
        raise SlurmApptainerError(f"{label} must be a local file or absolute path")
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        raise SlurmApptainerError(f"{label} must be absolute")
    path = candidate.resolve()
    return path


def _within(path: Path, root: Path, label: str) -> Path:
    try:
        path.relative_to(root)
    except ValueError as error:
        raise SlurmApptainerError(f"{label} is outside approved root {root}") from error
    return path


def _safe_identifier(value: str, label: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", value):
        raise SlurmApptainerError(f"invalid {label}: {value}")
    return value


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="ascii",
    )
    os.replace(temporary, path)


class SlurmApptainerRunner:
    """Submit one admitted operation runtime through a reviewed storage profile."""

    def __init__(
        self,
        execution_target: dict[str, Any],
        storage_profile: dict[str, Any],
        runtimes: Iterable[dict[str, Any]],
        *,
        client: SlurmClient | None = None,
        scheduler_path_mapper: Callable[[Path], str] = str,
    ) -> None:
        runtime_documents = tuple(runtimes)
        for runtime in runtime_documents:
            validate_contract_data("operation-runtime", runtime)
        self._initialize_target(
            execution_target,
            storage_profile,
            client=client,
            scheduler_path_mapper=scheduler_path_mapper,
        )

        self.runtimes: dict[tuple[str, str], dict[str, Any]] = {}
        for runtime in runtime_documents:
            metadata = runtime["metadata"]
            release = runtime["spec"]["release"]
            if metadata["status"] != "target-accepted":
                raise SlurmApptainerError(
                    f"runtime is not target-accepted: {metadata['id']}"
                )
            if release["status"] != "target-accepted":
                raise SlurmApptainerError(
                    f"runtime release is not target-accepted: {metadata['id']}"
                )
            key = (metadata["capability"], metadata["operation"])
            if key in self.runtimes:
                raise SlurmApptainerError(
                    f"duplicate operation runtime: {key[0]}/{key[1]}"
                )
            self.runtimes[key] = runtime

    def _initialize_target(
        self,
        execution_target: dict[str, Any],
        storage_profile: dict[str, Any],
        *,
        client: SlurmClient | None,
        scheduler_path_mapper: Callable[[Path], str],
    ) -> None:
        validate_contract_data("execution-target", execution_target)
        validate_contract_data("storage-profile", storage_profile)
        target_metadata = execution_target["metadata"]
        target_spec = execution_target["spec"]
        storage_metadata = storage_profile["metadata"]
        storage_spec = storage_profile["spec"]
        if target_metadata["status"] != "active":
            raise SlurmApptainerError("execution target must be active")
        if target_spec["runner"] != "slurm":
            raise SlurmApptainerError("execution target runner must be slurm")
        if "apptainer" not in target_spec["container_runtimes"]:
            raise SlurmApptainerError("execution target must admit Apptainer")
        if "batch-hpc" not in target_spec["execution_classes"]:
            raise SlurmApptainerError("execution target must admit the batch-hpc class")
        if storage_metadata["status"] != "active":
            raise SlurmApptainerError("storage profile must be active")
        if target_spec["storage_profile"] != storage_metadata["id"]:
            raise SlurmApptainerError(
                "execution target does not reference this storage profile"
            )
        if storage_spec["execution_target"] != target_metadata["id"]:
            raise SlurmApptainerError(
                "storage profile does not reference this execution target"
            )

        self.execution_target = execution_target
        self.storage_profile = storage_profile
        self.client = client or SlurmClient()
        self.scheduler_path_mapper = scheduler_path_mapper
        self.target_id = target_metadata["id"]
        self.execution_targets = frozenset({self.target_id})
        self.execution_classes = frozenset({"batch-hpc"})
        policies = target_spec["policies"]
        if not policies["approved_images_only"]:
            raise SlurmApptainerError(
                "Slurm/Apptainer runner requires approved-images-only policy"
            )
        if policies["network_access"] != "none":
            raise SlurmApptainerError(
                "operation-container target must disable network access"
            )
        roots = storage_spec["roots"]
        self.image_cache = Path(roots["image_cache"]).resolve()
        self.task_staging = Path(roots["task_staging"]).resolve()
        self.task_staging.mkdir(parents=True, exist_ok=True)
        if not self.image_cache.is_dir():
            raise SlurmApptainerError(
                f"approved image cache does not exist: {self.image_cache}"
            )

    def _scheduler_path(self, path: Path, label: str) -> str:
        try:
            value = self.scheduler_path_mapper(path.resolve())
        except (OSError, TypeError, ValueError) as error:
            raise SlurmApptainerError(
                f"cannot map {label} into scheduler storage"
            ) from error
        if not isinstance(value, str):
            raise SlurmApptainerError(f"scheduler {label} path must be text")
        parsed = PurePosixPath(value)
        if (
            not parsed.is_absolute()
            or ".." in parsed.parts
            or "\x00" in value
            or "\n" in value
            or "\r" in value
        ):
            raise SlurmApptainerError(f"invalid scheduler {label} path: {value}")
        return str(parsed)

    def _runtime(self, request: TaskRequest) -> dict[str, Any]:
        if request.execution_target != self.target_id:
            raise SlurmApptainerError(
                f"request target is not admitted: {request.execution_target}"
            )
        if request.execution_class not in self.execution_classes:
            raise SlurmApptainerError(
                f"request execution class is not admitted: {request.execution_class}"
            )
        allowed_projects = self.execution_target["spec"]["policies"].get(
            "allowed_projects"
        )
        if allowed_projects is not None and request.project not in allowed_projects:
            raise SlurmApptainerError(
                f"request project is not admitted: {request.project}"
            )
        runtime = self.runtimes.get((request.capability_id, request.operation_id))
        if runtime is None:
            raise SlurmApptainerError(
                "no target-accepted runtime for "
                f"{request.capability_id}/{request.operation_id}"
            )
        release = runtime["spec"]["release"]
        if request.runtime_type != "apptainer":
            raise SlurmApptainerError("registry runtime type must be apptainer")
        if (
            request.runtime_reference != release["apptainer_reference"]
            or request.runtime_digest != release["apptainer_digest"]
        ):
            raise SlurmApptainerError(
                "registry runtime does not match the accepted Apptainer release"
            )
        ports = runtime["spec"]["execution"]["ports"]
        if set(request.inputs) != set(ports["inputs"]):
            raise SlurmApptainerError("request input ports do not match runtime ports")
        if set(request.output_types) != set(ports["outputs"]):
            raise SlurmApptainerError("request output ports do not match runtime ports")
        if set(request.parameters) != set(runtime["spec"]["execution"]["parameters"]):
            raise SlurmApptainerError(
                "request parameters do not match runtime parameter policy"
            )
        return runtime

    @staticmethod
    def _arguments(runtime: dict[str, Any], request: TaskRequest) -> tuple[str, ...]:
        arguments: list[str] = []
        bindings = runtime["spec"]["execution"]["parameters"]
        for name, binding in bindings.items():
            value = request.parameters[name]
            if "fixed" in binding:
                if value != binding["fixed"]:
                    raise SlurmApptainerError(
                        f"parameter {name} must equal its fixed runtime value"
                    )
                continue
            parameter_type = binding["type"]
            valid = {
                "string": isinstance(value, str),
                "integer": (isinstance(value, int) and not isinstance(value, bool)),
                "number": (
                    isinstance(value, (int, float)) and not isinstance(value, bool)
                ),
                "boolean": isinstance(value, bool),
            }[parameter_type]
            if not valid:
                raise SlurmApptainerError(
                    f"parameter {name} does not match runtime binding type"
                )
            rendered = str(value).lower() if isinstance(value, bool) else str(value)
            arguments.extend((binding["argument"], rendered))
        return tuple(arguments)

    def _attempt_directory(self, request: TaskRequest) -> Path:
        parts = [
            _safe_identifier(request.run_id, "run ID"),
            _safe_identifier(request.node_id, "node ID"),
            _safe_identifier(request.attempt_id, "attempt ID"),
        ]
        directory = self.task_staging.joinpath(*parts).resolve()
        _within(directory, self.task_staging, "attempt staging directory")
        return directory

    def _image(self, runtime: dict[str, Any]) -> Path:
        release = runtime["spec"]["release"]
        image = _local_uri(release["apptainer_reference"], "Apptainer image")
        _within(image, self.image_cache, "Apptainer image")
        if not image.is_file() or image.is_symlink():
            raise SlurmApptainerError(f"accepted Apptainer image not found: {image}")
        actual = file_digest(image)
        if actual != release["apptainer_digest"]:
            raise SlurmApptainerError(
                "Apptainer image digest mismatch: "
                f"expected {release['apptainer_digest']}, found {actual}"
            )
        return image

    @staticmethod
    def _mounts(runtime: dict[str, Any]) -> dict[str, str]:
        return {
            mount["kind"]: mount["path"]
            for mount in runtime["spec"]["execution"]["mounts"]
        }

    def _validate_mounts(self, runtime: dict[str, Any]) -> dict[str, str]:
        runtime_mounts = self._mounts(runtime)
        profile_mounts = self.storage_profile["spec"]["mounts"]
        for kind, path in runtime_mounts.items():
            if profile_mounts[kind] != path:
                raise SlurmApptainerError(
                    f"runtime {kind} mount does not match storage profile"
                )
        return runtime_mounts

    @staticmethod
    def _relative_port(path: str, mount: str, label: str) -> Path:
        try:
            relative = PurePosixPath(path).relative_to(PurePosixPath(mount))
        except ValueError as error:
            raise SlurmApptainerError(
                f"{label} is outside its declared container mount"
            ) from error
        if not relative.parts or ".." in relative.parts:
            raise SlurmApptainerError(f"invalid {label}")
        return Path(*relative.parts)

    def _stage_inputs(
        self,
        request: TaskRequest,
        runtime: dict[str, Any],
        inputs_directory: Path,
    ) -> None:
        execution = runtime["spec"]["execution"]
        mounts = self._mounts(runtime)
        maximum = self.storage_profile["spec"]["policies"]["max_task_input_bytes"]
        total = 0
        for port, container_path in execution["ports"]["inputs"].items():
            artifact = request.inputs[port]
            source = _local_uri(artifact["uri"], f"input artifact {port}")
            if not source.is_file() or source.is_symlink():
                raise SlurmApptainerError(
                    f"input artifact is not a regular file: {source}"
                )
            content_size = source.stat().st_size
            total += content_size
            if total > maximum:
                raise SlurmApptainerError("task inputs exceed storage profile limit")
            actual = file_digest(source)
            if actual != artifact["checksum"]:
                raise SlurmApptainerError(
                    f"input artifact checksum mismatch for port {port}"
                )
            if content_size != artifact["size_bytes"]:
                raise SlurmApptainerError(
                    f"input artifact size mismatch for port {port}"
                )
            relative = self._relative_port(
                container_path, mounts["input"], f"input port {port}"
            )
            destination = (inputs_directory / relative).resolve()
            _within(destination, inputs_directory, f"input port {port}")
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                if file_digest(destination) != actual:
                    raise SlurmApptainerError(
                        f"staged input conflicts with port {port}"
                    )
                continue
            temporary = destination.with_name(f".{destination.name}.tmp")
            shutil.copyfile(source, temporary)
            os.replace(temporary, destination)

    def _resources(self, request: TaskRequest) -> SlurmResources:
        limits = self.execution_target["spec"]["resource_limits"]
        values = {
            "cpu": int(request.resources.get("cpu", 1)),
            "memory_mb": int(request.resources.get("memory_mb", 1024)),
            "gpu": int(request.resources.get("gpu", 0)),
            "walltime_seconds": int(request.resources.get("walltime_seconds", 600)),
        }
        limit_fields = {
            "cpu": "max_cpu",
            "memory_mb": "max_memory_mb",
            "gpu": "max_gpu",
            "walltime_seconds": "max_walltime_seconds",
        }
        for name, value in values.items():
            maximum = limits.get(limit_fields[name])
            if value < (0 if name == "gpu" else 1):
                raise SlurmApptainerError(f"invalid requested resource: {name}")
            if maximum is not None and value > maximum:
                raise SlurmApptainerError(
                    f"requested {name} exceeds execution-target limit"
                )
        scheduler = self.execution_target["spec"]["scheduler"]
        return SlurmResources(
            **values,
            partition=scheduler.get("partition"),
            account=scheduler.get("account"),
            qos=scheduler.get("qos"),
        )

    def _paths(self, request: TaskRequest) -> dict[str, Path]:
        root = self._attempt_directory(request)
        paths = {
            "root": root,
            "inputs": root / "inputs",
            "outputs": root / "outputs",
            "scratch": root / "scratch",
            "logs": root / "logs",
            "script": root / "job.sh",
            "receipt": root / "submission.json",
            "telemetry": root / "stage-timing.tsv",
        }
        for name in ("inputs", "outputs", "scratch", "logs"):
            paths[name].mkdir(parents=True, exist_ok=True)
            if paths[name].is_symlink() or not paths[name].is_dir():
                raise SlurmApptainerError(
                    f"invalid attempt staging directory: {paths[name]}"
                )
            paths[name].chmod(0o700)
        return paths

    @staticmethod
    def _job_name(request: TaskRequest) -> str:
        digest = sha256(request.attempt_id.encode("ascii")).hexdigest()[:24]
        return "qhpc-" + digest

    def _read_receipt(self, path: Path, request: TaskRequest) -> dict[str, Any] | None:
        if not path.exists():
            return None
        try:
            receipt = json.loads(path.read_text(encoding="ascii"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise SlurmApptainerError(
                f"invalid Slurm submission receipt: {path}"
            ) from error
        if receipt.get("attempt_id") != request.attempt_id:
            raise SlurmApptainerError("Slurm receipt attempt ID mismatch")
        handle = receipt.get("handle")
        if not isinstance(handle, str):
            raise SlurmApptainerError("Slurm receipt has no target handle")
        return receipt

    def submit(self, request: TaskRequest) -> TargetSubmission:
        runtime = self._runtime(request)
        paths = self._paths(request)
        receipt = self._read_receipt(paths["receipt"], request)
        if receipt:
            return TargetSubmission(
                receipt["handle"],
                self.client.status(receipt["handle"]),
                {"recovered_from": "submission-receipt"},
            )

        durations: dict[str, int] = {}
        started = time.perf_counter()
        image = self._image(runtime)
        durations["target.image-verify"] = _elapsed_ms(started)
        self._validate_mounts(runtime)

        started = time.perf_counter()
        self._stage_inputs(request, runtime, paths["inputs"])
        durations["target.input-stage"] = _elapsed_ms(started)

        job_name = self._job_name(request)
        recovered = self.client.find_by_name(job_name)
        if recovered:
            receipt = {
                "attempt_id": request.attempt_id,
                "handle": recovered,
                "job_name": job_name,
                "submitted_at_epoch_ms": round(time.time() * 1000),
                "recovered": True,
            }
            _atomic_json(paths["receipt"], receipt)
            return TargetSubmission(
                recovered,
                self.client.status(recovered),
                {
                    "recovered_from": "scheduler-job-name",
                    "stage_durations_ms": durations,
                },
            )

        execution = runtime["spec"]["execution"]
        mounts = self._mounts(runtime)
        binds = [
            ApptainerBind(
                self._scheduler_path(paths["outputs"], "output bind"),
                mounts["output"],
                read_only=False,
            )
        ]
        if "input" in mounts:
            binds.insert(
                0,
                ApptainerBind(
                    self._scheduler_path(paths["inputs"], "input bind"),
                    mounts["input"],
                    read_only=True,
                ),
            )
        if "scratch" in mounts:
            binds.append(
                ApptainerBind(
                    self._scheduler_path(paths["scratch"], "scratch bind"),
                    mounts["scratch"],
                    read_only=False,
                )
            )
        node_policy = self.storage_profile["spec"]["node_local"]
        node_local = None
        if node_policy["mode"] == "slurm-tmpdir":
            node_local = NodeLocalStaging(
                namespace=request.attempt_id[-32:],
                stage_image=node_policy["stage_image"],
                stage_read_only_binds=node_policy["stage_inputs"],
                minimum_free_mb=node_policy.get("minimum_free_mb"),
            )
        scheduler = self.execution_target["spec"]["scheduler"]
        started = time.perf_counter()
        script = render_apptainer_job(
            image=self._scheduler_path(image, "image"),
            entrypoint=execution["entrypoint"],
            arguments=self._arguments(runtime, request),
            resources=self._resources(request),
            job_name=job_name,
            binds=binds,
            working_directory=execution["working_directory"],
            stdout_path=self._scheduler_path(
                paths["logs"] / "stdout.log", "stdout"
            ),
            stderr_path=self._scheduler_path(
                paths["logs"] / "stderr.log", "stderr"
            ),
            telemetry_path=self._scheduler_path(paths["telemetry"], "telemetry"),
            apptainer_executable=scheduler["apptainer_executable"],
            node_local=node_local,
        )
        paths["script"].write_text(script, encoding="utf-8")
        paths["script"].chmod(0o700)
        durations["target.job-render"] = _elapsed_ms(started)

        started = time.perf_counter()
        handle = self.client.submit(paths["script"])
        durations["target.scheduler-submit"] = _elapsed_ms(started)
        receipt = {
            "attempt_id": request.attempt_id,
            "handle": handle,
            "job_name": job_name,
            "submitted_at_epoch_ms": round(time.time() * 1000),
            "recovered": False,
        }
        _atomic_json(paths["receipt"], receipt)
        return TargetSubmission(
            handle,
            "queued",
            {
                "job_name": job_name,
                "stage_durations_ms": durations,
            },
        )

    def _checked_receipt(
        self, request: TaskRequest, handle: str
    ) -> tuple[dict[str, Path], dict[str, Any]]:
        paths = self._paths(request)
        receipt = self._read_receipt(paths["receipt"], request)
        if receipt is None or receipt["handle"] != handle:
            raise SlurmApptainerError("target handle does not match submission receipt")
        return paths, receipt

    def poll(self, request: TaskRequest, handle: str) -> TargetStatus:
        _runtime = self._runtime(request)
        _paths, receipt = self._checked_receipt(request, handle)
        state = self.client.status(handle)
        metadata: dict[str, Any] = {}
        if state in {"succeeded", "failed", "canceled"}:
            submitted = receipt.get("submitted_at_epoch_ms")
            if isinstance(submitted, int):
                metadata["stage_durations_ms"] = {
                    "target.scheduler-total": max(
                        0, round(time.time() * 1000) - submitted
                    )
                }
        return TargetStatus(state, metadata)

    @staticmethod
    def _telemetry(path: Path) -> dict[str, int]:
        durations: dict[str, int] = {}
        if not path.is_file():
            return durations
        for line in path.read_text(encoding="ascii", errors="replace").splitlines():
            stage, separator, timing = line.partition("\t")
            start, second, end = timing.partition("\t")
            if (
                not separator
                or not second
                or not re.fullmatch(r"[a-z][a-z0-9-]*", stage)
            ):
                continue
            try:
                durations[f"target.{stage}"] = max(0, int(end) - int(start))
            except ValueError:
                continue
        return durations

    def collect(self, request: TaskRequest, handle: str) -> TaskResult:
        runtime = self._runtime(request)
        paths, _receipt = self._checked_receipt(request, handle)
        execution = runtime["spec"]["execution"]
        mounts = self._mounts(runtime)
        outputs: dict[str, ArtifactResult] = {}
        started = time.perf_counter()
        for port, container_path in execution["ports"]["outputs"].items():
            relative = self._relative_port(
                container_path, mounts["output"], f"output port {port}"
            )
            source = (paths["outputs"] / relative).resolve()
            _within(source, paths["outputs"], f"output port {port}")
            if not source.is_file() or source.is_symlink():
                raise SlurmApptainerError(
                    f"target omitted output for port {port}: {source}"
                )
            destination = request.work_directory / f"{port}{source.suffix}"
            temporary = destination.with_name(f".{destination.name}.tmp")
            shutil.copyfile(source, temporary)
            os.replace(temporary, destination)
            outputs[port] = ArtifactResult.from_path(
                request.output_types[port], destination
            )
        durations = self._telemetry(paths["telemetry"])
        durations["target.output-stage"] = _elapsed_ms(started)
        logs = []
        for name in ("stdout.log", "stderr.log"):
            log_path = paths["logs"] / name
            if log_path.is_file():
                value = log_path.read_text(encoding="utf-8", errors="replace")
                if value:
                    logs.append(f"[{name}]\n{value}")
        return TaskResult(
            outputs,
            "\n".join(logs),
            {"stage_durations_ms": durations},
        )

    def cancel(self, request: TaskRequest, handle: str) -> None:
        self._runtime(request)
        self._checked_receipt(request, handle)
        self.client.cancel(handle)

    def finalize(self, request: TaskRequest, *, succeeded: bool) -> None:
        policy = self.storage_profile["spec"]["policies"]["cleanup"]
        should_clean = policy == "always" or (policy == "on-success" and succeeded)
        if should_clean:
            directory = self._attempt_directory(request)
            if directory.exists():
                shutil.rmtree(directory)


class SlurmDockerClusterRunner(SlurmApptainerRunner):
    """Run verified local OCI images through the development Slurm fixture."""

    def __init__(
        self,
        execution_target: dict[str, Any],
        storage_profile: dict[str, Any],
        runtimes: Iterable[dict[str, Any]],
        runtime_images: Iterable[dict[str, str]],
        *,
        host_shared_root: str | Path,
        scheduler_shared_root: str,
        client: SlurmClient,
        scheduler_path_mapper: Callable[[Path], str],
    ) -> None:
        if execution_target["metadata"]["id"] != "development-slurm-docker":
            raise SlurmApptainerError(
                "Docker-cluster runner requires the development Slurm target"
            )
        executable = execution_target["spec"]["scheduler"][
            "apptainer_executable"
        ]
        if executable != "/usr/local/bin/qhpc-oci-shim":
            raise SlurmApptainerError(
                "Docker-cluster runner requires the reviewed OCI shim"
            )

        shared_root = Path(host_shared_root).expanduser().resolve()
        scheduler_root = PurePosixPath(scheduler_shared_root)
        if not shared_root.is_dir():
            raise SlurmApptainerError(
                f"development shared directory not found: {shared_root}"
            )
        if not scheduler_root.is_absolute() or ".." in scheduler_root.parts:
            raise SlurmApptainerError("invalid development scheduler shared root")

        runtime_image_documents = tuple(runtime_images)
        bindings = {
            item["runtime_id"]: dict(item) for item in runtime_image_documents
        }
        if len(bindings) != len(runtime_image_documents):
            raise SlurmApptainerError("duplicate development runtime image binding")

        runtime_documents = tuple(runtimes)
        runtime_ids = {runtime["metadata"]["id"] for runtime in runtime_documents}
        if runtime_ids != set(bindings):
            missing = sorted(runtime_ids - set(bindings))
            extra = sorted(set(bindings) - runtime_ids)
            details = []
            if missing:
                details.append("missing bindings: " + ", ".join(missing))
            if extra:
                details.append("unused bindings: " + ", ".join(extra))
            raise SlurmApptainerError(
                "development runtime image set does not match manifests"
                + (": " + "; ".join(details) if details else "")
            )

        image_cache = Path(
            storage_profile["spec"]["roots"]["image_cache"]
        ).resolve()
        task_staging = Path(
            storage_profile["spec"]["roots"]["task_staging"]
        ).resolve()
        for path, label in (
            (image_cache, "image cache"),
            (task_staging, "task staging"),
        ):
            _within(path, shared_root, f"development {label}")
        image_cache.mkdir(parents=True, exist_ok=True)

        self._initialize_target(
            execution_target,
            storage_profile,
            client=client,
            scheduler_path_mapper=scheduler_path_mapper,
        )
        self.runtimes: dict[tuple[str, str], dict[str, Any]] = {}
        self._development_descriptors: dict[str, tuple[Path, str]] = {}
        self._development_runtimes: dict[
            tuple[str, str], tuple[dict[str, Any], dict[str, str]]
        ] = {}
        for runtime in runtime_documents:
            validate_contract_data("operation-runtime", runtime)
            metadata = runtime["metadata"]
            if metadata["status"] != "oci-smoke-tested":
                raise SlurmApptainerError(
                    f"development runtime lacks OCI smoke evidence: {metadata['id']}"
                )
            binding = bindings[metadata["id"]]
            if not binding["registry_reference"].endswith(
                "@" + binding["digest"]
            ):
                raise SlurmApptainerError(
                    f"development registry reference is mutable: {metadata['id']}"
                )
            descriptor = image_cache / f"{metadata['id']}.oci.json"
            _atomic_json(
                descriptor,
                {
                    "kind": "QHPCDevelopmentOCIImage",
                    "image": binding["local_reference"],
                    "digest": binding["digest"],
                    "host_shared_root": str(shared_root),
                    "scheduler_shared_root": str(scheduler_root),
                },
            )
            key = (metadata["capability"], metadata["operation"])
            if key in self.runtimes:
                raise SlurmApptainerError(
                    f"duplicate development operation runtime: {key[0]}/{key[1]}"
                )
            self._development_runtimes[key] = (runtime, binding)
            self._development_descriptors[metadata["id"]] = (
                descriptor,
                file_digest(descriptor),
            )
            self.runtimes[key] = runtime

    def _image(self, runtime: dict[str, Any]) -> Path:
        runtime_id = runtime["metadata"]["id"]
        descriptor, expected_digest = self._development_descriptors[runtime_id]
        _within(descriptor, self.image_cache, "development OCI descriptor")
        if not descriptor.is_file() or descriptor.is_symlink():
            raise SlurmApptainerError(
                f"development OCI descriptor not found: {descriptor}"
            )
        actual = file_digest(descriptor)
        if actual != expected_digest:
            raise SlurmApptainerError(
                "development OCI descriptor digest mismatch: "
                f"expected {expected_digest}, found {actual}"
            )
        return descriptor

    def _runtime(self, request: TaskRequest) -> dict[str, Any]:
        if request.execution_target != self.target_id:
            raise SlurmApptainerError(
                f"request target is not admitted: {request.execution_target}"
            )
        if request.execution_class not in self.execution_classes:
            raise SlurmApptainerError(
                f"request execution class is not admitted: {request.execution_class}"
            )
        allowed_projects = self.execution_target["spec"]["policies"].get(
            "allowed_projects"
        )
        if allowed_projects is not None and request.project not in allowed_projects:
            raise SlurmApptainerError(
                f"request project is not admitted: {request.project}"
            )
        key = (request.capability_id, request.operation_id)
        development = self._development_runtimes.get(key)
        if development is None:
            raise SlurmApptainerError(
                "no development OCI runtime for "
                f"{request.capability_id}/{request.operation_id}"
            )
        runtime, binding = development
        if request.runtime_type != "oci":
            raise SlurmApptainerError("development registry runtime type must be OCI")
        if (
            request.runtime_reference != binding["registry_reference"]
            or request.runtime_digest != binding["digest"]
        ):
            raise SlurmApptainerError(
                "registry runtime does not match the verified local OCI image"
            )
        ports = runtime["spec"]["execution"]["ports"]
        if set(request.inputs) != set(ports["inputs"]):
            raise SlurmApptainerError("request input ports do not match runtime ports")
        if set(request.output_types) != set(ports["outputs"]):
            raise SlurmApptainerError("request output ports do not match runtime ports")
        if set(request.parameters) != set(runtime["spec"]["execution"]["parameters"]):
            raise SlurmApptainerError(
                "request parameters do not match runtime parameter policy"
            )
        return self.runtimes[key]
