#!/usr/local/bin/python3
from __future__ import annotations

import argparse
from pathlib import Path

from ft_primitive_bench.noise_models import uniform_depolarizing
from ft_primitive_bench.surface_code.circuits import memory


def bounded_integer(minimum: int, maximum: int):
    def parse(value: str) -> int:
        try:
            parsed = int(value)
        except ValueError as error:
            raise argparse.ArgumentTypeError("must be an integer") from error
        if parsed < minimum or parsed > maximum:
            raise argparse.ArgumentTypeError(
                f"must be between {minimum} and {maximum}"
            )
        return parsed

    return parse


def error_rate(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be a number") from error
    if parsed < 0 or parsed > 0.5:
        raise argparse.ArgumentTypeError("must be between 0 and 0.5")
    return parsed


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--x-distance", required=True, type=bounded_integer(1, 31)
    )
    parser.add_argument(
        "--z-distance", required=True, type=bounded_integer(1, 31)
    )
    parser.add_argument("--rounds", required=True, type=bounded_integer(1, 100))
    parser.add_argument(
        "--measurement-basis", required=True, choices=("X", "Z")
    )
    parser.add_argument(
        "--physical-error-rate", required=True, type=error_rate
    )
    return parser.parse_args()


def main() -> None:
    options = arguments()
    clean = memory(
        x_distance=options.x_distance,
        z_distance=options.z_distance,
        rounds=options.rounds,
        meas_basis=options.measurement_basis,
    )
    noisy = uniform_depolarizing(
        p=options.physical_error_rate
    ).noisy_circuit(clean)
    serialized = str(noisy).strip() + "\n"
    if "DETECTOR" not in serialized or "OBSERVABLE_INCLUDE" not in serialized:
        raise RuntimeError(
            "FTPrimitiveBench output lacks detector or observable annotations"
        )
    output = Path("/outputs/circuit.stim")
    output.write_text(serialized, encoding="utf-8")


if __name__ == "__main__":
    main()
