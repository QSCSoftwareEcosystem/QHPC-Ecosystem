"""Exercise the runtime-free FTPrimitiveBench to LightStim interface boundary."""

from __future__ import annotations

import argparse
import hashlib
import json

from qhpc_ecosystem.project_adapters import (
    build_ftprimitivebench_memory,
    estimate_lightstim_logical_error,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--physical-error-rate", type=float, default=0.005)
    parser.add_argument("--max-shots", type=int, default=300)
    parser.add_argument("--max-errors", type=int, default=3)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    circuit = build_ftprimitivebench_memory(
        {
            "x_distance": 3,
            "z_distance": 3,
            "rounds": 3,
            "measurement_basis": "Z",
            "physical_error_rate": args.physical_error_rate,
        }
    )
    estimate = estimate_lightstim_logical_error(
        circuit,
        {
            "decoder": "pymatching",
            "max_shots": args.max_shots,
            "max_errors": args.max_errors,
            "batch_size": min(100, args.max_shots),
            "num_workers": 1,
        },
    )
    print(
        json.dumps(
            {
                "circuit_bytes": len(circuit.encode("utf-8")),
                "circuit_sha256": hashlib.sha256(circuit.encode("utf-8")).hexdigest(),
                "estimate": estimate,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
