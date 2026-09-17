"""Container-engine selection shared by EQO's operation-runtime paths.

By default EQO uses Docker, falling back to Podman, exactly as it always has.
Setting ``USE_APPTAINER=1`` opts into Apptainer — the rootless runtime that is
available on HPC systems where a Docker daemon is not — for the operation-runtime
image acquisition and execution paths.

The two runtimes have different models. Docker keeps a content-addressed image in
a daemon store and is verified with ``docker image inspect``. Apptainer has no
daemon: an image is pulled by its immutable ``docker://…@sha256:`` digest into a
single ``.sif`` file. Because a SIF is not byte-reproducible across Apptainer
versions or hosts, the committed release manifest cannot pin a SIF hash. Instead
the immutable source digest remains the identity authority at pull time, and the
resulting SIF's hash is recorded in a cache-side lock (:func:`lock_path`) so a
later reuse can detect local tampering.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .catalog import CatalogError
from .runtime import default_image_dir, find_runtime


APPTAINER_ENV = "USE_APPTAINER"
_SIF_LOCK_API_VERSION = "eqo.sif-locks/v1"
_CHUNK = 1024 * 1024

# Normalizes ``platform.machine()`` spellings onto the OCI/Apptainer ``--arch``
# vocabulary (the same names used in operation-runtime platform contracts).
_MACHINE_TO_OCI_ARCH = {
    "x86_64": "amd64",
    "amd64": "amd64",
    "aarch64": "arm64",
    "arm64": "arm64",
    "ppc64le": "ppc64le",
}


class ContainerEngineError(RuntimeError):
    """Raised when no admitted container engine or verified SIF is available."""


def apptainer_requested() -> bool:
    """Return ``True`` only when ``USE_APPTAINER=1`` is set in the environment."""

    return os.environ.get(APPTAINER_ENV, "").strip() == "1"


def host_oci_arch() -> str:
    """Return this machine's processor as an OCI/Apptainer arch name.

    Apptainer normally selects an image's architecture to match the host it
    runs on. EQO's admitted operation images currently publish only
    ``linux/amd64``, so a caller uses this to detect a mismatch (for example
    an Apple Silicon or other arm64 host) and explain the emulation it needs,
    rather than surfacing a bare "exec format error" mid-workflow.
    """

    machine = platform.machine().lower()
    return _MACHINE_TO_OCI_ARCH.get(machine, machine)


def _apptainer_shares_network() -> bool:
    """Return ``True`` when the user opted out of an isolated network namespace.

    Some Apptainer installs do not let a plain local user create a network
    namespace (no setuid, no ``allow net``). ``EQO_APPTAINER_SHARE_NETWORK=1``
    lets such a user run the tools anyway by sharing the host network.
    """

    return os.environ.get("EQO_APPTAINER_SHARE_NETWORK", "").strip() == "1"


@dataclass(frozen=True)
class ContainerEngine:
    """One resolved container runtime and its executable path."""

    kind: str  # "apptainer" | "docker" | "podman"
    executable: str

    @property
    def is_apptainer(self) -> bool:
        return self.kind == "apptainer"


def select_engine(*, purpose: str = "EQO container operations") -> ContainerEngine:
    """Resolve the container engine, honoring the ``USE_APPTAINER`` opt-in.

    ``USE_APPTAINER=1`` requires Apptainer and never silently falls back to
    Docker; otherwise Docker is preferred and Podman is the fallback, matching
    EQO's historical behavior.
    """

    if apptainer_requested():
        try:
            executable = find_runtime("apptainer")
        except CatalogError as error:
            raise ContainerEngineError(
                f"{purpose} requested Apptainer via {APPTAINER_ENV}=1, "
                "but Apptainer was not found on PATH"
            ) from error
        return ContainerEngine("apptainer", executable)
    docker = shutil.which("docker")
    if docker:
        return ContainerEngine("docker", docker)
    podman = shutil.which("podman")
    if podman:
        return ContainerEngine("podman", podman)
    raise ContainerEngineError(
        f"{purpose} require Docker or Podman; "
        f"install one, or set {APPTAINER_ENV}=1 to use Apptainer"
    )


# --- SIF store -----------------------------------------------------------------


def sif_store_dir() -> Path:
    """Return the directory that holds pulled operation-runtime SIF images."""

    return default_image_dir() / "operations"


def sif_path_for(image_id: str) -> Path:
    """Return the on-disk SIF path for one manifest image id."""

    return sif_store_dir() / f"{image_id}.sif"


def lock_path() -> Path:
    """Return the cache-side lock recording verified SIF identities."""

    return sif_store_dir() / "sif-locks.json"


def sha256_file(path: str | Path) -> str:
    """Return the ``sha256:`` digest of a file's bytes."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def read_locks() -> dict[str, dict[str, str]]:
    """Return the recorded SIF locks keyed by local reference, or an empty map."""

    path = lock_path()
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError) as error:
        raise ContainerEngineError(f"cannot read SIF lock file: {path}") from error
    images = document.get("images") if isinstance(document, dict) else None
    return images if isinstance(images, dict) else {}


def write_lock_entry(
    local_reference: str,
    *,
    image_id: str,
    source: str,
    source_digest: str,
    sif_path: Path,
    sif_sha256: str,
) -> None:
    """Record one verified SIF so a later reuse can detect local tampering."""

    locks = read_locks()
    locks[local_reference] = {
        "image_id": image_id,
        "source": source,
        "source_digest": source_digest,
        "sif_path": str(sif_path),
        "sif_sha256": sif_sha256,
    }
    path = lock_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(
            {"api_version": _SIF_LOCK_API_VERSION, "images": locks},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def verified_sif(local_reference: str, expected_source_digest: str) -> Path:
    """Return the verified SIF for an admitted local reference.

    The SIF must exist, its recorded lock must bind it to ``expected_source_digest``
    (the immutable digest the release admitted), and its current bytes must still
    hash to the value recorded at install time.
    """

    entry = read_locks().get(local_reference)
    if entry is None:
        raise ContainerEngineError(
            f"no Apptainer SIF is installed for {local_reference}; "
            "run `eqo local up` to install the admitted image set"
        )
    if entry.get("source_digest") != expected_source_digest:
        raise ContainerEngineError(
            f"installed SIF for {local_reference} does not match the admitted digest"
        )
    sif = Path(entry.get("sif_path", ""))
    if not sif.is_file():
        raise ContainerEngineError(
            f"the recorded SIF for {local_reference} is missing: {sif}"
        )
    if sha256_file(sif) != entry.get("sif_sha256"):
        raise ContainerEngineError(
            f"the installed SIF for {local_reference} failed its integrity check"
        )
    return sif


# --- run command construction --------------------------------------------------


def run_command(
    engine: ContainerEngine,
    target: str,
    args: Sequence[str] = (),
    *,
    input_bind: tuple[Path, str] | None = None,
    output_bind: tuple[Path, str] | None = None,
    platform: str | None = None,
    network_none: bool = True,
    tmpfs_size_mb: int = 16,
) -> list[str]:
    """Build a locked-down single-shot run command for either runtime.

    ``target`` is the container image reference for Docker/Podman and the SIF path
    for Apptainer (resolve it with :func:`verified_sif`). The Docker/Podman argv is
    unchanged from EQO's original hand-written command so existing behavior is
    byte-for-byte preserved.
    """

    if engine.is_apptainer:
        # A SIF rootfs is read-only (== --read-only); unprivileged Apptainer runs
        # as the caller with no added capabilities (== --cap-drop ALL and
        # no-new-privileges); --containall provides a private /tmp, /dev and home.
        command = [
            engine.executable,
            "run",
            "--containall",
            "--cleanenv",
            "--writable-tmpfs",
        ]
        if network_none and not _apptainer_shares_network():
            # Requires an Apptainer install that permits an isolated network
            # namespace for unprivileged users (setuid or `allow net`). Where a
            # plain local user cannot create one, EQO_APPTAINER_SHARE_NETWORK=1
            # drops the flag so the tool still runs (sharing the host network).
            command += ["--net", "--network", "none"]
        if input_bind is not None:
            host, dest = input_bind
            command += ["--bind", f"{host}:{dest}:ro"]
        if output_bind is not None:
            host, dest = output_bind
            command += ["--bind", f"{host}:{dest}"]
        command.append(target)
        command.extend(args)
        return command

    command = [engine.executable, "run", "--rm"]
    if platform is not None:
        command += ["--platform", platform]
    if network_none:
        command += ["--network", "none"]
    command += [
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--tmpfs",
        f"/tmp:rw,noexec,nosuid,size={tmpfs_size_mb}m",
    ]
    if input_bind is not None:
        host, dest = input_bind
        command += ["--mount", f"type=bind,src={host},dst={dest},readonly"]
    if output_bind is not None:
        host, dest = output_bind
        command += ["--mount", f"type=bind,src={host},dst={dest}"]
    command.append(target)
    command.extend(args)
    return command
