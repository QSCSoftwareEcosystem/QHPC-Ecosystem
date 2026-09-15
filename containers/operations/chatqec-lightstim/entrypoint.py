#!/usr/local/bin/python3
"""EQO adapter for the pinned ChatQEC LightStim circuit-build tool."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from chatqec_mcp_tools.tools.qec_circuit_build import (
    QecCircuitBuildInput,
    qec_circuit_build,
)


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--code-family",
        required=True,
        choices=("toric_code", "color_code_666", "bb_code", "pqrm"),
    )
    parser.add_argument("--distance", required=True, type=int)
    parser.add_argument("--rounds", required=True, type=int)
    parser.add_argument("--protocol", required=True, choices=("memory",))
    return parser.parse_args()


def main() -> None:
    options = arguments()
    result = qec_circuit_build(
        QecCircuitBuildInput(
            code_family=options.code_family,
            distance=options.distance,
            rounds=options.rounds,
            protocol=options.protocol,
        )
    )
    if not result.ok:
        raise ValueError(result.error_message or "ChatQEC LightStim circuit build failed")
    Path("/outputs/circuit.stim").write_text(result.circuit_text, encoding="utf-8")
    Path("/outputs/build-report.json").write_text(
        json.dumps(
            {
                "schema": "qhpc.qec-circuit-build-report.v1",
                "code_family": options.code_family,
                "distance": options.distance,
                "rounds": options.rounds,
                "protocol": options.protocol,
                "num_qubits": result.num_qubits,
                "num_detectors": result.num_detectors,
                "num_observables": result.num_observables,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
