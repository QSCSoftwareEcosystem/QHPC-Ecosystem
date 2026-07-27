#!/usr/local/bin/python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import stim
from lightstim.simulation.decoder_backend import DecoderConfig, SimulationPipeline


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


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--decoder", required=True, choices=("pymatching",))
    parser.add_argument(
        "--max-shots", required=True, type=bounded_integer(1, 100_000_000)
    )
    parser.add_argument(
        "--max-errors", required=True, type=bounded_integer(1, 1_000_000)
    )
    parser.add_argument(
        "--batch-size", required=True, type=bounded_integer(1, 1_000_000)
    )
    parser.add_argument(
        "--num-workers", required=True, type=bounded_integer(1, 256)
    )
    return parser.parse_args()


def main() -> None:
    options = arguments()
    source = Path("/inputs/circuit.stim")
    if not source.is_file():
        raise FileNotFoundError("missing input: /inputs/circuit.stim")
    circuit = stim.Circuit(source.read_text(encoding="utf-8"))
    if circuit.num_detectors < 1 or circuit.num_observables < 1:
        raise ValueError(
            "Stim circuit requires at least one detector and one observable"
        )

    pipeline = SimulationPipeline(
        decoder_config=DecoderConfig(options.decoder),
        max_errors=options.max_errors,
        max_shots=options.max_shots,
        batch_size=options.batch_size,
        num_workers=options.num_workers,
        print_progress=False,
    )
    stats = pipeline.run(circuit)
    result = {
        "decoder": str(stats.decoder),
        "error_bar": float(stats.ler_error_bar()),
        "errors": int(stats.errors),
        "logical_error_rate": float(stats.logical_error_rate),
        "post_selected_shots": int(stats.post_selected_shots),
        "seconds": float(stats.seconds),
        "shots": int(stats.shots),
    }
    Path("/outputs/estimate.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
