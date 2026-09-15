"""Optional IQM Client/Qiskit adapter for the isolated IQM worker.

The adapter is deliberately separate from :mod:`qhpc_ecosystem.iqm_runner`.
The runner owns the durable EQO contract and secret boundary; this module only
translates that already-validated contract to IQM's optional Python client.
No endpoint, token, or provider option is accepted from an EQO workflow.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse


class IQMProviderUnavailable(RuntimeError):
    """The worker was configured without IQM's optional client dependency."""


class IQMProviderError(RuntimeError):
    """A provider response cannot satisfy the EQO hardware boundary."""


def _timestamp(value: Any) -> str:
    """Return an ISO-8601 UTC timestamp without trusting provider text blindly."""
    if isinstance(value, datetime):
        result = value
    elif isinstance(value, str):
        try:
            result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            result = datetime.now(timezone.utc)
    else:
        result = datetime.now(timezone.utc)
    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _provider_error(action: str, error: Exception) -> IQMProviderError:
    """Do not allow a provider exception to echo a resolved bearer token."""
    del error
    return IQMProviderError(f"IQM provider {action} failed")


class QiskitIQMBackendClient:
    """Adapt one worker-admitted IQM backend to ``IQMBackendClient``.

    IQM's Qiskit integration is an optional worker dependency provided by
    ``iqm-client[qiskit]``. A worker is deliberately configured for exactly one
    device alias so a restart can retrieve a durable job handle without any
    user- or workflow-supplied endpoint selection.
    """

    def __init__(
        self,
        endpoint: str,
        device_alias: str,
        *,
        provider_factory: Callable[..., Any] | None = None,
        transpiler: Callable[[Any, Any], Any] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        parsed = urlparse(endpoint)
        if parsed.scheme != "https" or not parsed.netloc or parsed.query or parsed.fragment:
            raise ValueError("IQM endpoint must be an absolute HTTPS URL without a query")
        if not device_alias or len(device_alias) > 64:
            raise ValueError("IQM device alias must be non-empty text up to 64 characters")
        self.endpoint = endpoint.rstrip("/")
        self.device_alias = device_alias
        self._provider_factory = provider_factory
        self._transpiler = transpiler
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def _dependencies(self) -> tuple[Callable[..., Any], Callable[[Any, Any], Any], Any]:
        if self._provider_factory is not None and self._transpiler is not None:
            try:
                from qiskit import QuantumCircuit
            except ImportError as error:  # pragma: no cover - exercised in worker env
                raise IQMProviderUnavailable(
                    "Qiskit is unavailable; install the iqm optional dependency"
                ) from error
            return self._provider_factory, self._transpiler, QuantumCircuit
        try:
            from iqm.qiskit_iqm import IQMProvider, transpile_to_IQM
            from qiskit import QuantumCircuit
        except ImportError as error:
            raise IQMProviderUnavailable(
                "IQM Client/Qiskit support is unavailable; install 'iqm-client[qiskit]' "
                "in the isolated quantum-worker environment"
            ) from error
        return IQMProvider, transpile_to_IQM, QuantumCircuit

    def validate_environment(self) -> None:
        """Fail worker startup before advertising a backend that cannot run."""
        self._dependencies()

    def _backend(self, token: str) -> Any:
        provider_factory, _transpiler, _circuit = self._dependencies()
        try:
            provider = provider_factory(
                self.endpoint,
                quantum_computer=self.device_alias,
                token=token,
            )
            return provider.get_backend()
        except IQMProviderUnavailable:
            raise
        except Exception as error:
            raise _provider_error("initialization", error) from error

    @staticmethod
    def _loci(circuit: Mapping[str, Any]) -> list[str]:
        loci: list[str] = []
        for instruction in circuit["instructions"]:
            for component in instruction["locus"]:
                if component not in loci:
                    loci.append(component)
        return loci

    def _qiskit_circuit(self, circuit: Mapping[str, Any], quantum_circuit: Any) -> tuple[Any, list[str]]:
        loci = self._loci(circuit)
        measurement_count = sum(
            1 for instruction in circuit["instructions"] if instruction["name"] == "measure"
        )
        if not loci or not measurement_count:
            raise IQMProviderError("IQM input must contain loci and measurements")
        try:
            translated = quantum_circuit(len(loci), measurement_count, name=circuit["name"])
            by_locus = {locus: index for index, locus in enumerate(loci)}
            bit = 0
            for instruction in circuit["instructions"]:
                name = instruction["name"]
                locus = instruction["locus"]
                args = instruction["args"]
                if name == "prx":
                    angle = args.get("angle")
                    phase = args.get("phase")
                    if not isinstance(angle, (int, float)) or not isinstance(phase, (int, float)):
                        raise IQMProviderError("IQM PRX instruction requires numeric angle and phase in radians")
                    translated.r(float(angle), float(phase), by_locus[locus[0]])
                elif name == "cz":
                    translated.cz(by_locus[locus[0]], by_locus[locus[1]])
                elif name == "measure":
                    translated.measure(by_locus[locus[0]], bit)
                    bit += 1
                else:  # The durable runner already enforces this allowlist.
                    raise IQMProviderError(f"unsupported IQM instruction: {name}")
        except IQMProviderError:
            raise
        except Exception as error:
            raise _provider_error("circuit translation", error) from error
        return translated, loci

    @staticmethod
    def _status(value: Any) -> str:
        label = str(getattr(value, "name", value)).lower()
        return {
            "done": "succeeded",
            "succeeded": "succeeded",
            "error": "failed",
            "failed": "failed",
            "cancelled": "canceled",
            "canceled": "canceled",
            "running": "running",
            "processing": "running",
            "queued": "queued",
            "waiting": "queued",
            "initializing": "queued",
        }.get(label, "queued")

    @staticmethod
    def _job_id(job: Any) -> str:
        value = getattr(job, "job_id", None)
        value = value() if callable(value) else value
        if not value:
            raise IQMProviderError("IQM provider did not return a job ID")
        return str(value)

    @staticmethod
    def _device(backend: Any, alias: str) -> dict[str, str]:
        architecture = getattr(backend, "architecture", None)
        calibration = getattr(architecture, "calibration_set_id", None)
        computer = (
            getattr(architecture, "quantum_computer_id", None)
            or getattr(architecture, "quantum_computer_name", None)
            or getattr(backend, "name", None)
        )
        if not calibration or not computer:
            raise IQMProviderError(
                "IQM provider did not expose an exact device and calibration identity"
            )
        return {
            "alias": alias,
            "quantum_computer_id": str(computer),
            "calibration_id": str(calibration),
        }

    @staticmethod
    def _serialized_circuit(backend: Any, circuit: Any) -> dict[str, Any]:
        try:
            serialized = backend.serialize_circuit(circuit)
            instructions = getattr(serialized, "instructions", None)
            if instructions is None and isinstance(serialized, Mapping):
                instructions = serialized.get("instructions")
            converted = []
            for instruction in instructions or ():
                if isinstance(instruction, Mapping):
                    name = instruction["name"]
                    locus = instruction["locus"]
                    args = instruction["args"]
                else:
                    name = instruction.name
                    locus = instruction.locus
                    args = instruction.args
                converted.append({"name": str(name), "locus": list(locus), "args": dict(args)})
            name = getattr(serialized, "name", None) or (
                serialized.get("name") if isinstance(serialized, Mapping) else None
            )
            if not name or not converted:
                raise ValueError("serialized circuit was incomplete")
            return {"name": str(name), "instructions": converted}
        except Exception as error:
            raise _provider_error("routing serialization", error) from error

    @staticmethod
    def _final_layout(backend: Any, circuit: Any, loci: Sequence[str]) -> list[dict[str, str]]:
        try:
            layout = getattr(circuit, "layout", None)
            index_layout = layout.final_index_layout() if layout is not None else None
            if not index_layout:
                index_layout = list(range(len(loci)))
            return [
                {
                    "source": source,
                    "target": str(backend.index_to_qubit_name(index_layout[index])),
                }
                for index, source in enumerate(loci)
            ]
        except Exception as error:
            raise _provider_error("layout extraction", error) from error

    @staticmethod
    def _metrics(circuit: Mapping[str, Any]) -> dict[str, int]:
        instructions = circuit["instructions"]
        return {
            "total_operation_count": len(instructions),
            "two_qubit_gate_count": sum(1 for item in instructions if item["name"] in {"cz", "move", "swap"}),
            "move_count": sum(1 for item in instructions if item["name"] == "move"),
            "explicit_swap_count": sum(1 for item in instructions if item["name"] == "swap"),
        }

    def submit(
        self,
        circuit: Mapping[str, Any],
        *,
        device_alias: str,
        shots: int,
        token: str,
    ) -> Mapping[str, Any]:
        if device_alias != self.device_alias:
            raise IQMProviderError("requested IQM device is not admitted by this worker")
        backend = self._backend(token)
        _provider_factory, transpiler, quantum_circuit = self._dependencies()
        source, loci = self._qiskit_circuit(circuit, quantum_circuit)
        try:
            routed = transpiler(source, backend)
            job = backend.run(routed, shots=shots)
            routed_document = self._serialized_circuit(backend, routed)
            final_layout = self._final_layout(backend, routed, loci)
            return {
                "job_id": self._job_id(job),
                "state": self._status(job.status()),
                "device": self._device(backend, device_alias),
                "submitted_at": _timestamp(self._clock()),
                "routed_circuit": routed_document,
                "initial_layout": [
                    {"source": source_name, "target": source_name}
                    for source_name in loci
                ],
                "final_layout": final_layout,
                "routing_metrics": self._metrics(routed_document),
            }
        except IQMProviderError:
            raise
        except Exception as error:
            raise _provider_error("submission", error) from error

    def _job(self, job_id: str, token: str) -> Any:
        backend = self._backend(token)
        try:
            return backend.retrieve_job(job_id)
        except Exception as error:
            raise _provider_error("job retrieval", error) from error

    def status(self, job_id: str, *, token: str) -> Mapping[str, Any]:
        job = self._job(job_id, token)
        try:
            return {"job_id": job_id, "state": self._status(job.status())}
        except Exception as error:
            raise _provider_error("status query", error) from error

    def result(self, job_id: str, *, token: str) -> Mapping[str, Any]:
        job = self._job(job_id, token)
        try:
            result = job.result()
            counts = result.get_counts()
            if isinstance(counts, list):
                if len(counts) != 1:
                    raise ValueError("IQM worker accepts exactly one circuit per job")
                counts = counts[0]
            if not isinstance(counts, Mapping):
                raise ValueError("IQM result does not contain counts")
            return {
                "job_id": job_id,
                "counts": {str(key): int(value) for key, value in counts.items()},
                "bit_order": "qiskit-little-endian",
                "completed_at": _timestamp(getattr(result, "date", None) or self._clock()),
            }
        except Exception as error:
            raise _provider_error("result collection", error) from error

    def cancel(self, job_id: str, *, token: str) -> None:
        job = self._job(job_id, token)
        try:
            job.cancel()
        except Exception as error:
            raise _provider_error("cancellation", error) from error
