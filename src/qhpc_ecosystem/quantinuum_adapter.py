"""Offline, evidence-preserving lowering to the reviewed Quantinuum profile.

The adapter deliberately instantiates the pytket Quantinuum backend with
checked-in static backend data.  This makes compilation deterministic with
respect to the published profile and guarantees that the adapter neither
queries a provider nor submits a job.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from typing import Any

from .circuit_exchange import CircuitExchangeError, exchange_to_pytket
from .contract import ContractError, document_digest, validate_contract
from .local_assets import asset_path


PROFILE_ASSET = "transpilation-profile-quantinuum-h2-offline"


def load_quantinuum_h2_profile() -> tuple[dict[str, Any], str]:
    """Load the one reviewed, static Quantinuum compiler profile."""
    try:
        profile = validate_contract(
            "transpilation-target-profile", asset_path(PROFILE_ASSET)
        )
    except (ContractError, OSError, ValueError) as error:
        raise CircuitExchangeError("Quantinuum target profile is unavailable") from error
    compiler = profile["spec"]["compiler"]
    try:
        installed = version(compiler["package"])
    except PackageNotFoundError as error:
        raise CircuitExchangeError(
            "Quantinuum lowering requires the optional pytket-quantinuum runtime"
        ) from error
    if installed != compiler["version"]:
        raise CircuitExchangeError(
            "installed pytket-quantinuum version does not match the published "
            f"profile ({installed} != {compiler['version']})"
        )
    return profile, document_digest(profile)


def _label(value: Any) -> str:
    if (
        not isinstance(value, list)
        or len(value) != 2
        or not isinstance(value[0], str)
        or not isinstance(value[1], list)
        or len(value[1]) != 1
        or not isinstance(value[1][0], int)
    ):
        raise CircuitExchangeError("Quantinuum compiler returned an invalid qubit label")
    return f"{value[0]}[{value[1][0]}]"


def lower_to_quantinuum_h2(document: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Compile a static CircuitExchange artifact with static H2 backend data.

    This is compilation evidence only.  The returned tket JSON is not a
    provider payload, and it has no provider credential or network path.
    """
    profile, profile_digest = load_quantinuum_h2_profile()
    specification = document["spec"]
    if specification["parameters"]:
        raise CircuitExchangeError(
            "Quantinuum lowering accepts only static, non-parameterized circuits"
        )
    if specification["limitations"]:
        raise CircuitExchangeError(
            "CircuitExchange with declared limitations cannot be lowered to Quantinuum"
        )
    if len(specification["qubit_order"]) > profile["spec"]["offline_backend"]["max_qubits"]:
        raise CircuitExchangeError("circuit exceeds the published Quantinuum profile qubit limit")
    if len(specification["classical_bit_order"]) > profile["spec"]["offline_backend"]["max_classical_registers"]:
        raise CircuitExchangeError("circuit exceeds the published Quantinuum profile classical-register limit")

    try:
        from pytket.circuit import OpType
        from pytket.extensions.quantinuum import (
            QuantinuumBackend,
            QuantinuumBackendData,
        )
    except ImportError as error:
        raise CircuitExchangeError(
            "Quantinuum lowering requires the optional pytket-quantinuum runtime"
        ) from error

    backend_data = profile["spec"]["offline_backend"]
    gate_set = frozenset(
        getattr(OpType, name) for name in backend_data["compiler_gate_set"]
    )
    backend = QuantinuumBackend(
        profile["spec"]["device_name"],
        data=QuantinuumBackendData(
            n_qubits=backend_data["max_qubits"],
            n_cl_reg=backend_data["max_classical_registers"],
            gate_set=gate_set,
        ),
    )
    backend.set_compilation_config_allow_implicit_swaps(False)
    try:
        compiled = backend.get_compiled_circuit(
            exchange_to_pytket(document),
            optimisation_level=profile["spec"]["compiler"]["optimisation_level"],
        )
        lowered = compiled.to_dict()
    except CircuitExchangeError:
        raise
    except Exception as error:
        raise CircuitExchangeError("Quantinuum offline compilation failed") from error

    commands = lowered.get("commands")
    if not isinstance(commands, list):
        raise CircuitExchangeError("Quantinuum compiler returned an invalid circuit")
    native_sequence = [
        command.get("op", {}).get("type")
        for command in commands
        if isinstance(command, dict) and isinstance(command.get("op"), dict)
    ]
    if not native_sequence or any(
        not isinstance(gate, str)
        or gate not in backend_data["expected_output_gate_set"]
        for gate in native_sequence
    ):
        raise CircuitExchangeError(
            "Quantinuum compiler emitted a gate outside the published target profile"
        )
    permutation = lowered.get("implicit_permutation", [])
    if not isinstance(permutation, list) or any(
        not isinstance(pair, list) or len(pair) != 2 or _label(pair[0]) != _label(pair[1])
        for pair in permutation
    ):
        raise CircuitExchangeError(
            "Quantinuum compilation introduced an implicit qubit permutation"
        )

    report = {
        "adapter": "circuit-exchange-to-quantinuum-h2-offline",
        "classification": "equivalent-after-lowering",
        "qubit_mapping": [
            {"source": label, "target": label}
            for label in specification["qubit_order"]
        ],
        "implicit_swaps": [],
        "gate_decompositions": [
            {
                "compiler_pass": "QuantinuumBackend.get_compiled_circuit",
                "input_gate_sequence": [
                    operation["gate"] for operation in specification["operations"]
                ],
                "native_gate_sequence": native_sequence,
                "attribution": "whole-circuit lowering; optimiser may combine adjacent gates",
            }
        ],
        "compiler_options": {
            "optimisation_level": profile["spec"]["compiler"]["optimisation_level"],
            "allow_implicit_swaps": False,
            "network": "none",
            "provider_submission": False,
        },
        "target_profile": {
            "id": profile["metadata"]["id"],
            "version": profile["metadata"]["version"],
            "digest": profile_digest,
            "device_name": profile["spec"]["device_name"],
        },
        "equivalence_evidence": {
            "method": "offline Quantinuum compiler pass with a pinned static profile",
            "status": "compiler-lowered",
            "claim_boundary": "The output is compile-only evidence, not hardware admission or execution evidence.",
        },
        "warnings": [
            "No live calibration, routing topology, noise model, provider authentication, or job submission is used.",
        ],
    }
    return lowered, report
