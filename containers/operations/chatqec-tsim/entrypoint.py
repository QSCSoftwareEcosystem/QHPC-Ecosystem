#!/usr/local/bin/python3
"""EQO adapter for the pinned ChatQEC Tsim simulation tool."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from chatqec_mcp_tools.tools.tsim_simulate import TsimSimulateInput, tsim_simulate


def boolean(value: str) -> bool:
    normalized = value.lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise argparse.ArgumentTypeError("must be true or false")


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--shots", required=True, type=int)
    parser.add_argument("--use-reference-sample", required=True, type=boolean)
    return parser.parse_args()


def main() -> None:
    options = arguments()
    circuit = Path("/inputs/circuit.tsim").read_text(encoding="utf-8")
    result = tsim_simulate(
        TsimSimulateInput(
            circuit=circuit,
            shots=options.shots,
            use_reference_sample=options.use_reference_sample,
        )
    )
    if not result.ok:
        raise ValueError(result.error_message or "ChatQEC Tsim simulation failed")
    Path("/outputs/samples.json").write_text(
        json.dumps(
            {
                "schema": "qhpc.tsim-simulation-samples.v1",
                "shots": result.shots,
                "use_reference_sample": options.use_reference_sample,
                "summary": result.summary,
                "samples_preview": result.samples_preview,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
