"""Credential-isolated asynchronous execution boundary for IQM backends."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol, Sequence
from urllib.parse import unquote, urlparse

from .engine import ArtifactResult, TaskRejectedError, TaskRequest, TaskResult
from .security import validate_secret_reference
from .worker import TargetStatus, TargetSubmission


class IQMAdapterError(RuntimeError):
    """An IQM boundary request or response violated the admitted contract."""


class IQMBackendClient(Protocol):
    """Worker-local provider client; implementations may use qiskit-iqm."""

    def submit(
        self,
        circuit: Mapping[str, Any],
        *,
        device_alias: str,
        shots: int,
        token: str,
    ) -> Mapping[str, Any]: ...

    def status(self, job_id: str, *, token: str) -> Mapping[str, Any]: ...

    def result(self, job_id: str, *, token: str) -> Mapping[str, Any]: ...

    def cancel(self, job_id: str, *, token: str) -> None: ...


SecretResolver = Callable[[str], str]
Clock = Callable[[], datetime]

_ALIAS = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_JOB_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,127}$")
_COMPONENT = re.compile(r"^(?:QB[1-9][0-9]*|COMP_R[1-9][0-9]*)$")
_CHECKSUM = re.compile(r"^sha256:[0-9a-f]{64}$")
_INPUT_GATES = frozenset({"prx", "cz", "measure"})
_ROUTED_GATES = frozenset({"prx", "cz", "measure", "move", "reset", "swap"})
_TARGET_STATES = frozenset({"queued", "running", "succeeded", "failed", "canceled"})
_MAX_INPUT_BYTES = 1_000_000
_MAX_RESPONSE_BYTES = 2_000_000
_MAX_INSTRUCTIONS = 20_000
_MAX_SHOTS = 4096
_RECEIPT_NAME = ".iqm-submission.json"

_STEANE_STABILIZERS = ((1, 2, 3, 4), (0, 2, 3, 5), (0, 1, 3, 6))
_STEANE_DECODE = {
    sum(
        (error in support) << index
        for index, support in enumerate(_STEANE_STABILIZERS)
    ): error
    for error in range(7)
}


@dataclass(frozen=True)
class _RequestPolicy:
    device_alias: str
    shots: int
    credential_reference: str
    max_wait_seconds: int


def resolve_environment_secret(reference: str) -> str:
    """Resolve an ``env`` secret only inside the quantum-backend worker."""
    checked = validate_secret_reference(reference)
    provider, identifier = checked[len("secret://") :].split("/", 1)
    if provider != "env" or "/" in identifier:
        raise IQMAdapterError("the local IQM worker accepts only secret://env/NAME")
    value = os.environ.get(identifier)
    if not value:
        raise IQMAdapterError(f"IQM credential is unavailable: {checked}")
    if len(value) > 16_384:
        raise IQMAdapterError("IQM credential exceeds the worker limit")
    return value


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _object(
    value: Any,
    name: str,
    *,
    required: set[str],
    allowed: set[str],
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise IQMAdapterError(f"{name} must be an object")
    missing = sorted(required - set(value))
    if missing:
        raise IQMAdapterError(f"{name} is missing: {', '.join(missing)}")
    unknown = sorted(str(field) for field in set(value) - allowed)
    if unknown:
        raise IQMAdapterError(
            f"{name} contains unsupported fields: {', '.join(unknown)}"
        )
    return value


def _text(value: Any, name: str, *, maximum: int = 256) -> str:
    if not isinstance(value, str) or not value.strip():
        raise IQMAdapterError(f"{name} must be non-empty text")
    if len(value) > maximum:
        raise IQMAdapterError(f"{name} exceeds {maximum} characters")
    return value


def _timestamp(value: Any, name: str) -> str:
    text = _text(value, name, maximum=64)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as error:
        raise IQMAdapterError(f"{name} must be an ISO-8601 timestamp") from error
    if parsed.tzinfo is None:
        raise IQMAdapterError(f"{name} must include a timezone")
    return text


def _bounded_json(value: Any, name: str) -> bytes:
    try:
        encoded = json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("ascii")
    except (TypeError, ValueError) as error:
        raise IQMAdapterError(f"{name} is not JSON serializable") from error
    if len(encoded) > _MAX_RESPONSE_BYTES:
        raise IQMAdapterError(f"{name} exceeds the 2 MB worker limit")
    return encoded


def _device(value: Any, expected_alias: str) -> dict[str, str]:
    device = _object(
        value,
        "IQM device",
        required={"alias", "quantum_computer_id", "calibration_id"},
        allowed={"alias", "quantum_computer_id", "calibration_id"},
    )
    alias = _text(device["alias"], "IQM device alias", maximum=64)
    if alias != expected_alias:
        raise IQMAdapterError("IQM response device alias does not match the request")
    return {
        "provider": "iqm",
        "alias": alias,
        "quantum_computer_id": _text(
            device["quantum_computer_id"], "IQM quantum computer ID", maximum=128
        ),
        "calibration_id": _text(
            device["calibration_id"], "IQM calibration ID", maximum=128
        ),
    }


def _layout(value: Any, name: str) -> list[dict[str, str]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise IQMAdapterError(f"{name} must be an array")
    if not 1 <= len(value) <= 64:
        raise IQMAdapterError(f"{name} must contain 1 to 64 mappings")
    normalized: list[dict[str, str]] = []
    sources: set[str] = set()
    targets: set[str] = set()
    for index, item in enumerate(value):
        mapping = _object(
            item,
            f"{name}[{index}]",
            required={"source", "target"},
            allowed={"source", "target"},
        )
        source = _text(mapping["source"], f"{name}[{index}].source", maximum=32)
        target = _text(mapping["target"], f"{name}[{index}].target", maximum=32)
        if _COMPONENT.fullmatch(source) is None or _COMPONENT.fullmatch(target) is None:
            raise IQMAdapterError(f"{name}[{index}] has an invalid component")
        if source in sources or target in targets:
            raise IQMAdapterError(f"{name} must be one-to-one")
        sources.add(source)
        targets.add(target)
        normalized.append({"source": source, "target": target})
    return normalized


def _circuit(
    value: Any,
    name: str,
    *,
    gates: frozenset[str],
) -> dict[str, Any]:
    circuit = _object(
        value,
        name,
        required={"name", "instructions"},
        allowed={"name", "instructions"},
    )
    instructions = circuit["instructions"]
    if (
        not isinstance(instructions, list)
        or not 1 <= len(instructions) <= _MAX_INSTRUCTIONS
    ):
        raise IQMAdapterError(
            f"{name}.instructions must contain 1 to {_MAX_INSTRUCTIONS} entries"
        )
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(instructions):
        instruction = _object(
            item,
            f"{name}.instructions[{index}]",
            required={"name", "locus", "args"},
            allowed={"name", "locus", "args"},
        )
        gate = _text(
            instruction["name"], f"{name}.instructions[{index}].name", maximum=16
        ).lower()
        if gate not in gates:
            raise IQMAdapterError(f"{name} contains unsupported IQM gate: {gate}")
        locus = instruction["locus"]
        if not isinstance(locus, list) or not 1 <= len(locus) <= 2:
            raise IQMAdapterError(f"{name}.instructions[{index}].locus is invalid")
        checked_locus: list[str] = []
        for component in locus:
            component_name = _text(component, "IQM component", maximum=32)
            if _COMPONENT.fullmatch(component_name) is None:
                raise IQMAdapterError(f"{name} contains an invalid IQM component")
            checked_locus.append(component_name)
        args = instruction["args"]
        if not isinstance(args, Mapping):
            raise IQMAdapterError(
                f"{name}.instructions[{index}].args must be an object"
            )
        _bounded_json(args, f"{name}.instructions[{index}].args")
        normalized.append({"name": gate, "locus": checked_locus, "args": dict(args)})
    return {
        "name": _text(circuit["name"], f"{name}.name", maximum=128),
        "instructions": normalized,
    }


def _metrics(value: Any) -> dict[str, int]:
    fields = {
        "total_operation_count",
        "two_qubit_gate_count",
        "move_count",
        "explicit_swap_count",
    }
    metrics = _object(value, "IQM routing metrics", required=fields, allowed=fields)
    normalized: dict[str, int] = {}
    for field in sorted(fields):
        number = metrics[field]
        if isinstance(number, bool) or not isinstance(number, int) or number < 0:
            raise IQMAdapterError(f"IQM routing metric {field} must be non-negative")
        normalized[field] = number
    if normalized["total_operation_count"] < 1:
        raise IQMAdapterError("IQM routed circuit must contain an operation")
    return normalized


def _policy(request: TaskRequest) -> _RequestPolicy:
    if request.operation_id != "route-submit-collect":
        raise TaskRejectedError("IQM worker admits only route-submit-collect")
    if request.execution_target != "local-development":
        raise TaskRejectedError("IQM worker admits only local-development")
    if request.execution_class != "quantum-backend":
        raise TaskRejectedError("IQM worker requires execution_class quantum-backend")
    allowed = {
        "device_alias",
        "shots",
        "credential_reference",
        "max_wait_seconds",
    }
    unknown = sorted(set(request.parameters) - allowed)
    if unknown:
        raise TaskRejectedError(
            "unsupported IQM parameters: " + ", ".join(unknown)
        )
    alias = request.parameters.get("device_alias", "default")
    if not isinstance(alias, str) or _ALIAS.fullmatch(alias) is None:
        raise TaskRejectedError("device_alias has an invalid format")
    shots = request.parameters.get("shots", 512)
    if (
        isinstance(shots, bool)
        or not isinstance(shots, int)
        or not 1 <= shots <= _MAX_SHOTS
    ):
        raise TaskRejectedError(f"shots must be an integer from 1 to {_MAX_SHOTS}")
    reference = request.parameters.get("credential_reference", "secret://env/IQM_TOKEN")
    if not isinstance(reference, str):
        raise TaskRejectedError("credential_reference must be text")
    try:
        reference = validate_secret_reference(reference)
    except ValueError as error:
        raise TaskRejectedError(str(error)) from error
    max_wait = request.parameters.get("max_wait_seconds", 1800)
    if (
        isinstance(max_wait, bool)
        or not isinstance(max_wait, int)
        or not 30 <= max_wait <= 7200
    ):
        raise TaskRejectedError("max_wait_seconds must be an integer from 30 to 7200")
    if set(request.inputs) != {"circuit", "report"}:
        raise TaskRejectedError(
            "IQM operation requires exactly the circuit and report inputs"
        )
    expected_outputs = {
        "layout": "qhpc.iqm-routed-layout@1",
        "receipt": "qhpc.iqm-job-receipt@1",
        "counts": "qhpc.iqm-raw-counts@1",
        "logical_result": "qhpc.ftqc-logical-result@1",
    }
    if request.output_types != expected_outputs:
        raise TaskRejectedError(
            "IQM operation output contract does not match the worker"
        )
    return _RequestPolicy(alias, shots, reference, max_wait)


def _input_circuit(request: TaskRequest) -> tuple[dict[str, Any], str]:
    parsed = urlparse(str(request.inputs["circuit"].get("uri", "")))
    if parsed.scheme != "file":
        raise TaskRejectedError("circuit must be a file artifact")
    path = Path(unquote(parsed.path)).resolve()
    if not path.is_file() or path.is_symlink():
        raise TaskRejectedError("circuit artifact is not a regular file")
    content = path.read_bytes()
    if len(content) > _MAX_INPUT_BYTES:
        raise TaskRejectedError("IQM circuit exceeds the 1 MB worker limit")
    try:
        value = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise TaskRejectedError("IQM circuit is not valid UTF-8 JSON") from error
    return _circuit(value, "IQM input circuit", gates=_INPUT_GATES), (
        "sha256:" + sha256(content).hexdigest()
    )


def _preparation(request: TaskRequest, circuit: Mapping[str, Any]) -> str:
    parsed = urlparse(str(request.inputs["report"].get("uri", "")))
    if parsed.scheme != "file":
        raise TaskRejectedError("preparation report must be a file artifact")
    path = Path(unquote(parsed.path)).resolve()
    if not path.is_file() or path.is_symlink():
        raise TaskRejectedError("preparation report is not a regular file")
    content = path.read_bytes()
    if len(content) > _MAX_INPUT_BYTES:
        raise TaskRejectedError("preparation report exceeds the 1 MB worker limit")
    try:
        value = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise TaskRejectedError(
            "preparation report is not valid UTF-8 JSON"
        ) from error
    fields = {
        "schema",
        "preparation",
        "compiler_interface",
        "source_revision",
        "ecc",
        "logical_qubits",
        "device_qubits",
        "instruction_count",
        "gate_counts",
        "loci",
        "angle_units",
        "routing",
        "submission",
        "claim_boundary",
    }
    report = _object(
        value, "FTQC preparation report", required=fields, allowed=fields
    )
    if report["schema"] != "qhpc.ftqc-iqm-preparation-report.v1":
        raise TaskRejectedError("preparation report schema is not supported")
    preparation = report["preparation"]
    if preparation not in {"device", "steane-logical"}:
        raise TaskRejectedError("preparation report has an invalid mode")
    routing = report["routing"]
    submission = report["submission"]
    if (
        not isinstance(routing, Mapping)
        or routing.get("status") != "not-performed"
        or not isinstance(submission, Mapping)
        or submission.get("status") != "not-submitted"
        or submission.get("execution_class") != "quantum-backend"
    ):
        raise TaskRejectedError(
            "preparation report does not preserve the hardware boundary"
        )
    instruction_count = report["instruction_count"]
    device_qubits = report["device_qubits"]
    if instruction_count != len(circuit["instructions"]):
        raise TaskRejectedError(
            "preparation report instruction count does not match the circuit"
        )
    loci = {
        component
        for instruction in circuit["instructions"]
        for component in instruction["locus"]
    }
    if (
        device_qubits != len(loci)
        or not isinstance(report["loci"], list)
        or set(report["loci"]) != loci
    ):
        raise TaskRejectedError(
            "preparation report device width does not match the circuit"
        )
    measurements = sum(
        instruction["name"] == "measure"
        for instruction in circuit["instructions"]
    )
    expected_width = 2 if preparation == "device" else 7
    expected_logical_qubits = None if preparation == "device" else 1
    if (
        measurements != expected_width
        or len(loci) != expected_width
        or report["logical_qubits"] != expected_logical_qubits
    ):
        raise TaskRejectedError(
            "prepared circuit width does not match its reported mode"
        )
    return preparation


def _secret(resolver: SecretResolver, reference: str) -> str:
    try:
        token = resolver(reference)
    except Exception:
        raise IQMAdapterError("IQM credential resolution failed") from None
    if not isinstance(token, str) or not token or len(token) > 16_384:
        raise IQMAdapterError("IQM credential resolution returned an invalid value")
    return token


def _call(action: str, callback: Callable[[], Any]) -> Any:
    try:
        return callback()
    except IQMAdapterError:
        raise
    except Exception:
        raise IQMAdapterError(f"IQM backend {action} failed") from None


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    encoded = _bounded_json(value, path.name) + b"\n"
    path.write_bytes(encoded)


def _steane_correct(bits: list[int]) -> tuple[int, int]:
    raw = sum(bits) & 1
    syndrome = 0
    for index, support in enumerate(_STEANE_STABILIZERS):
        syndrome |= (sum(bits[item] for item in support) & 1) << index
    corrected = list(bits)
    if syndrome:
        corrected[_STEANE_DECODE[syndrome]] ^= 1
    return raw, sum(corrected) & 1


def _logical_result(
    *,
    job_id: str,
    preparation: str,
    shots: int,
    counts: Mapping[str, int],
) -> dict[str, Any]:
    if preparation == "device":
        return {
            "schema": "qhpc.ftqc-logical-result.v1",
            "job_id": job_id,
            "preparation": preparation,
            "shots": shots,
            "status": "not-applicable",
            "decoder": "none",
            "raw_logical_counts": None,
            "corrected_logical_counts": None,
            "claim_boundary": (
                "This direct device-qubit readout is not a logical-qubit result."
            ),
        }

    raw = {"0": 0, "1": 0}
    corrected = {"0": 0, "1": 0}
    for bitstring, count in counts.items():
        data = [int(bit) for bit in reversed(bitstring)]
        raw_bit, corrected_bit = _steane_correct(data)
        raw[str(raw_bit)] += count
        corrected[str(corrected_bit)] += count
    return {
        "schema": "qhpc.ftqc-logical-result.v1",
        "job_id": job_id,
        "preparation": preparation,
        "shots": shots,
        "status": "decoded",
        "decoder": "steane-z-syndrome-pauli-frame-v1",
        "raw_logical_counts": raw,
        "corrected_logical_counts": corrected,
        "claim_boundary": (
            "Classical Steane Z-basis single-X-error correction; this result alone "
            "does not demonstrate error suppression or fault-tolerant advantage."
        ),
    }


class IQMAsyncRunner:
    """Route and run IQM circuits without exposing a credential to EQO clients."""

    execution_targets = frozenset({"local-development"})
    execution_classes = frozenset({"quantum-backend"})

    def __init__(
        self,
        client: IQMBackendClient,
        *,
        secret_resolver: SecretResolver = resolve_environment_secret,
        clock: Clock = _utc_now,
    ) -> None:
        self.client = client
        self.secret_resolver = secret_resolver
        self.clock = clock

    @staticmethod
    def _receipt_path(request: TaskRequest) -> Path:
        return request.work_directory / _RECEIPT_NAME

    def _load_receipt(self, request: TaskRequest, handle: str) -> dict[str, Any]:
        path = self._receipt_path(request)
        if not path.is_file() or path.is_symlink():
            raise IQMAdapterError("IQM submission receipt is unavailable")
        try:
            receipt = json.loads(path.read_text(encoding="ascii"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise IQMAdapterError("IQM submission receipt is invalid") from error
        if not isinstance(receipt, dict) or receipt.get("job_id") != handle:
            raise IQMAdapterError("IQM submission handle does not match its receipt")
        _bounded_json(receipt, "IQM submission receipt")
        return receipt

    def submit(self, request: TaskRequest) -> TargetSubmission:
        policy = _policy(request)
        circuit, source_checksum = _input_circuit(request)
        preparation = _preparation(request, circuit)
        token = _secret(self.secret_resolver, policy.credential_reference)
        response = _call(
            "submission",
            lambda: self.client.submit(
                circuit,
                device_alias=policy.device_alias,
                shots=policy.shots,
                token=token,
            ),
        )
        _bounded_json(response, "IQM submission response")
        fields = {
            "job_id",
            "state",
            "device",
            "submitted_at",
            "routed_circuit",
            "initial_layout",
            "final_layout",
            "routing_metrics",
        }
        value = _object(
            response, "IQM submission response", required=fields, allowed=fields
        )
        job_id = _text(value["job_id"], "IQM job ID", maximum=128)
        if _JOB_ID.fullmatch(job_id) is None:
            raise IQMAdapterError("IQM job ID has an invalid format")
        state = value["state"]
        if state not in _TARGET_STATES:
            raise IQMAdapterError("IQM submission returned an invalid state")
        routed_circuit = _circuit(
            value["routed_circuit"], "IQM routed circuit", gates=_ROUTED_GATES
        )
        routing_metrics = _metrics(value["routing_metrics"])
        if routing_metrics["total_operation_count"] != len(
            routed_circuit["instructions"]
        ):
            raise IQMAdapterError(
                "IQM routing metrics do not match the routed circuit"
            )
        receipt = {
            "job_id": job_id,
            "state": state,
            "device": _device(value["device"], policy.device_alias),
            "shots": policy.shots,
            "preparation": preparation,
            "submitted_at": _timestamp(value["submitted_at"], "submitted_at"),
            "source_circuit_checksum": source_checksum,
            "routed_circuit": routed_circuit,
            "initial_layout": _layout(value["initial_layout"], "initial_layout"),
            "final_layout": _layout(value["final_layout"], "final_layout"),
            "routing_metrics": routing_metrics,
        }
        request.work_directory.mkdir(parents=True, exist_ok=True)
        _write_json(self._receipt_path(request), receipt)
        return TargetSubmission(
            job_id,
            state=state,
            metadata={
                "provider": "iqm",
                "device_alias": policy.device_alias,
                "quantum_computer_id": receipt["device"]["quantum_computer_id"],
                "calibration_id": receipt["device"]["calibration_id"],
                "shots": policy.shots,
            },
        )

    def poll(self, request: TaskRequest, handle: str) -> TargetStatus:
        policy = _policy(request)
        receipt = self._load_receipt(request, handle)
        submitted = datetime.fromisoformat(
            receipt["submitted_at"].replace("Z", "+00:00")
        )
        if (self.clock() - submitted).total_seconds() > policy.max_wait_seconds:
            token = _secret(self.secret_resolver, policy.credential_reference)
            _call(
                "timeout cancellation",
                lambda: self.client.cancel(handle, token=token),
            )
            raise IQMAdapterError("IQM job exceeded the configured wait limit")
        token = _secret(self.secret_resolver, policy.credential_reference)
        response = _call(
            "status polling", lambda: self.client.status(handle, token=token)
        )
        _bounded_json(response, "IQM status response")
        value = _object(
            response,
            "IQM status response",
            required={"job_id", "state"},
            allowed={"job_id", "state"},
        )
        if value["job_id"] != handle:
            raise IQMAdapterError("IQM status job ID does not match the handle")
        state = value["state"]
        if state not in _TARGET_STATES:
            raise IQMAdapterError("IQM status response contains an invalid state")
        return TargetStatus(state, {"provider": "iqm", "job_id": handle})

    def collect(self, request: TaskRequest, handle: str) -> TaskResult:
        policy = _policy(request)
        receipt = self._load_receipt(request, handle)
        token = _secret(self.secret_resolver, policy.credential_reference)
        response = _call(
            "result collection", lambda: self.client.result(handle, token=token)
        )
        _bounded_json(response, "IQM result response")
        value = _object(
            response,
            "IQM result response",
            required={"job_id", "counts", "bit_order", "completed_at"},
            allowed={"job_id", "counts", "bit_order", "completed_at"},
        )
        if value["job_id"] != handle:
            raise IQMAdapterError("IQM result job ID does not match the handle")
        if value["bit_order"] != "qiskit-little-endian":
            raise IQMAdapterError("IQM result uses an unsupported bit order")
        completed_at = _timestamp(value["completed_at"], "completed_at")
        completed_time = datetime.fromisoformat(
            completed_at.replace("Z", "+00:00")
        )
        submitted_time = datetime.fromisoformat(
            receipt["submitted_at"].replace("Z", "+00:00")
        )
        if completed_time < submitted_time:
            raise IQMAdapterError("IQM completion precedes submission")
        raw_counts = value["counts"]
        if (
            not isinstance(raw_counts, Mapping)
            or not 1 <= len(raw_counts) <= _MAX_SHOTS
        ):
            raise IQMAdapterError("IQM counts must contain 1 to 4096 outcomes")
        measurement_count = sum(
            instruction["name"] == "measure"
            for instruction in receipt["routed_circuit"]["instructions"]
        )
        preparation = receipt["preparation"]
        expected_width = 7 if preparation == "steane-logical" else 2
        if measurement_count != expected_width or not 1 <= expected_width <= 64:
            raise IQMAdapterError("IQM measurement width does not match preparation")
        counts: dict[str, int] = {}
        for bitstring, count in raw_counts.items():
            if (
                not isinstance(bitstring, str)
                or len(bitstring) != expected_width
                or re.fullmatch(r"[01]+", bitstring) is None
            ):
                raise IQMAdapterError("IQM result contains an invalid bitstring")
            if isinstance(count, bool) or not isinstance(count, int) or count < 1:
                raise IQMAdapterError("IQM result contains an invalid count")
            counts[bitstring] = count
        if sum(counts.values()) != policy.shots:
            raise IQMAdapterError("IQM counts do not sum to the requested shots")

        route_document = {
            "schema": "qhpc.iqm-routed-layout.v1",
            "source_circuit_checksum": receipt["source_circuit_checksum"],
            "device": receipt["device"],
            "circuit": receipt["routed_circuit"],
            "initial_layout": receipt["initial_layout"],
            "final_layout": receipt["final_layout"],
            "metrics": receipt["routing_metrics"],
        }
        route_path = request.work_directory / "iqm-routed-layout.json"
        _write_json(route_path, route_document)
        route_artifact = ArtifactResult.from_path(
            request.output_types["layout"], route_path
        )
        receipt_document = {
            "schema": "qhpc.iqm-job-receipt.v1",
            "job_id": handle,
            "device": receipt["device"],
            "shots": policy.shots,
            "submitted_at": receipt["submitted_at"],
            "completed_at": completed_at,
            "terminal_state": "succeeded",
            "routed_layout_checksum": route_artifact.checksum,
        }
        counts_document = {
            "schema": "qhpc.iqm-raw-counts.v1",
            "job_id": handle,
            "device": receipt["device"],
            "shots": policy.shots,
            "bit_order": "qiskit-little-endian",
            "counts": dict(sorted(counts.items())),
            "completed_at": completed_at,
        }
        logical_document = _logical_result(
            job_id=handle,
            preparation=preparation,
            shots=policy.shots,
            counts=counts,
        )
        documents = {
            "receipt": ("iqm-job-receipt.json", receipt_document),
            "counts": ("iqm-raw-counts.json", counts_document),
            "logical_result": (
                "ftqc-logical-result.json",
                logical_document,
            ),
        }
        outputs = {"layout": route_artifact}
        for port, (name, document) in documents.items():
            path = request.work_directory / name
            _write_json(path, document)
            outputs[port] = ArtifactResult.from_path(request.output_types[port], path)
        return TaskResult(
            outputs,
            f"Collected IQM job {handle}",
            metadata={
                "provider": "iqm",
                "job_id": handle,
                "device_alias": policy.device_alias,
                "quantum_computer_id": receipt["device"]["quantum_computer_id"],
                "calibration_id": receipt["device"]["calibration_id"],
                "shots": policy.shots,
            },
        )

    def cancel(self, request: TaskRequest, handle: str) -> None:
        policy = _policy(request)
        self._load_receipt(request, handle)
        token = _secret(self.secret_resolver, policy.credential_reference)
        _call("cancellation", lambda: self.client.cancel(handle, token=token))
