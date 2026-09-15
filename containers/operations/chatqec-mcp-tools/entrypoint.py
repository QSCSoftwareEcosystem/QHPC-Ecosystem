#!/usr/local/bin/python3
"""EQO adapter for pinned ChatQEC QEC tools.

The MCP server is deliberately not started. This narrow entrypoint turns one
reviewed tool invocation into a typed, provenance-carrying EQO artifact.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from xml.etree import ElementTree

from chatqec_mcp_tools.tools.code_params import CodeParamsInput, code_params
from chatqec_mcp_tools.tools.pymatching_decode import (
    PymatchingDecodeInput,
    pymatching_decode,
)
from chatqec_mcp_tools.tools.stim_diagram import StimDiagramInput, stim_diagram
from chatqec_mcp_tools.tools.stim_simulate import StimSimulateInput, stim_simulate
from chatqec_mcp_tools.tools.threshold_sweep import (
    ThresholdSweepInput,
    threshold_sweep,
)
from chatqec_mcp_tools.tools.glcb_visualize import (
    GlcbVisualizeInput,
    glcb_visualize_url,
)

_MAX_SVG_BYTES = 10 * 1024 * 1024
_FORBIDDEN_SVG_ELEMENTS = {
    "animate", "animateMotion", "animateTransform", "embed", "foreignObject",
    "iframe", "object", "script", "set",
}


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    subcommands = parser.add_subparsers(dest="tool", required=True)
    code_parameters = subcommands.add_parser("code-params", add_help=False)
    code_parameters.add_argument(
        "--code-family",
        required=True,
        choices=("surface_code_rotated", "repetition_code", "color_code"),
    )
    code_parameters.add_argument("--distance", required=True, type=int)
    stimulate = subcommands.add_parser("stim-simulate", add_help=False)
    stimulate.add_argument("--shots", required=True, type=int)
    subcommands.add_parser("stim-diagram", add_help=False)
    decode = subcommands.add_parser("pymatching-decode", add_help=False)
    decode.add_argument("--shots", required=True, type=int)
    sweep = subcommands.add_parser("threshold-sweep", add_help=False)
    sweep.add_argument(
        "--code-family",
        required=True,
        choices=("surface_code_rotated", "repetition_code", "color_code"),
    )
    sweep.add_argument("--distances", required=True)
    sweep.add_argument("--p-values", required=True)
    sweep.add_argument("--rounds", type=int)
    sweep.add_argument("--shots", required=True, type=int)
    subcommands.add_parser("glcb-visualize-url", add_help=False)
    return parser.parse_args()


def sanitized_svg(svg: str) -> str:
    """Reject active or externally referenced SVG before artifact persistence."""
    encoded = svg.encode("utf-8")
    if len(encoded) > _MAX_SVG_BYTES:
        raise ValueError("SVG artifact exceeds the 10 MiB artifact limit")
    try:
        root = ElementTree.fromstring(encoded)
    except ElementTree.ParseError as error:
        raise ValueError("SVG artifact is not valid XML") from error
    if root.tag.rsplit("}", 1)[-1] != "svg":
        raise ValueError("SVG artifact did not produce an SVG root element")
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1] in _FORBIDDEN_SVG_ELEMENTS:
            raise ValueError("SVG artifact contains an active SVG element")
        for attribute, value in element.attrib.items():
            if attribute.rsplit("}", 1)[-1] == "href" and ":" in value:
                raise ValueError("SVG artifact contains an external SVG reference")
    return svg


def comma_separated_numbers(value: str, *, kind: str) -> list[int] | list[float]:
    """Parse a compact CLI/UI binding without accepting empty list members."""
    fields = [item.strip() for item in value.split(",")]
    if not fields or any(not item for item in fields):
        raise ValueError(f"{kind} must be a comma-separated, non-empty list")
    try:
        return [int(item) for item in fields] if kind == "distances" else [float(item) for item in fields]
    except ValueError as error:
        raise ValueError(f"{kind} must contain only numeric values") from error


def main() -> None:
    options = arguments()
    if options.tool == "code-params":
        result = code_params(
            CodeParamsInput(code_family=options.code_family, distance=options.distance)
        )
        if not result.ok:
            raise ValueError(result.error_message or "ChatQEC code-parameter calculation failed")
        payload = result.model_dump(
            include={
                "code_family", "distance", "n", "k", "num_stabilizers",
                "stim_code_distance", "num_detectors", "num_observables", "notes",
            }
        )
        payload["schema"] = "qhpc.qec-code-parameters.v1"
        output = Path("/outputs/parameters.json")
    elif options.tool == "stim-simulate":
        circuit = Path("/inputs/circuit.stim").read_text(encoding="utf-8")
        result = stim_simulate(StimSimulateInput(circuit=circuit, shots=options.shots))
        if not result.ok:
            raise ValueError(result.error_message or "ChatQEC Stim simulation failed")
        payload = result.model_dump(include={"shots", "summary", "samples_preview"})
        payload["schema"] = "qhpc.stim-simulation-samples.v1"
        output = Path("/outputs/samples.json")
        output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return
    elif options.tool == "pymatching-decode":
        circuit = Path("/inputs/circuit.stim").read_text(encoding="utf-8")
        result = pymatching_decode(PymatchingDecodeInput(circuit=circuit, shots=options.shots))
        if not result.ok:
            raise ValueError(result.error_message or "ChatQEC PyMatching decode failed")
        payload = result.model_dump(
            include={
                "logical_error_rate", "num_errors", "shots", "num_detectors",
                "num_observables",
            }
        )
        payload["schema"] = "qhpc.qec-decoder-result.v1"
        Path("/outputs/result.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        return
    elif options.tool == "threshold-sweep":
        distances = comma_separated_numbers(options.distances, kind="distances")
        p_values = comma_separated_numbers(options.p_values, kind="p-values")
        result = threshold_sweep(
            ThresholdSweepInput(
                code_family=options.code_family,
                distances=distances,
                p_values=p_values,
                rounds=options.rounds or None,
                shots=options.shots,
            )
        )
        if not result.ok:
            raise ValueError(result.error_message or "ChatQEC threshold sweep failed")
        payload = {
            "schema": "qhpc.qec-threshold-sweep.v1",
            "code_family": options.code_family,
            "distances": distances,
            "p_values": p_values,
            "rounds": options.rounds or None,
            "shots": options.shots,
            "rows": [row.model_dump() for row in result.rows],
        }
        Path("/outputs/results.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        if result.plot_svg:
            Path("/outputs/plot.svg").write_text(
                sanitized_svg(result.plot_svg), encoding="utf-8"
            )
        return
    elif options.tool == "glcb-visualize-url":
        payload = json.loads(Path("/inputs/circuit.json").read_text(encoding="utf-8"))
        result = glcb_visualize_url(GlcbVisualizeInput.model_validate(payload))
        if not result.ok:
            raise ValueError(result.error_message or "GLCB visualization link creation failed")
        Path("/outputs/visualization-link.json").write_text(
            json.dumps(
                {
                    "schema": "qhpc.glcb-visualization-link.v1",
                    "url": result.url,
                    "external_disclosure": (
                        "Opening this URL sends the encoded circuit to the external "
                        "Gemini Logical Circuit Builder service."
                    ),
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        return
    else:
        circuit = Path("/inputs/circuit.stim").read_text(encoding="utf-8")
        result = stim_diagram(StimDiagramInput(circuit=circuit))
        if not result.ok:
            raise ValueError(result.error_message or "ChatQEC Stim diagram rendering failed")
        Path("/outputs/diagram.svg").write_text(sanitized_svg(result.svg), encoding="utf-8")
        return
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
