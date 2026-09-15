#!/usr/bin/env python3
"""Constrained, credential-free FTQC C API operation entrypoint."""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import re
import sys
from pathlib import Path
from typing import Any


SOURCE_REVISION = "779216de8805ea0c1d473c640eaf17d6cbfa04e8"
INPUT = Path("/inputs/circuit.qasm")
OUTPUT_DIRECTORY = Path("/outputs")
QASM_HEADER = re.compile(r"^\s*OPENQASM\s+(?:2(?:\.0)?|3(?:\.0)?)\s*;", re.I | re.M)
FUNCTION_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
IQM_JSON_ATTRIBUTE = re.compile(
    r'ftqc\.iqm_json\s*=\s*"((?:[^"\\]|\\.)*)"'
)


class FTQCConfiguration(ctypes.Structure):
    """Pinned FTQC C API configuration layout."""

    _fields_ = [
        ("ecc_kind", ctypes.c_char * 64),
        ("ecc_dist", ctypes.c_int),
        ("func_name", ctypes.c_char * 64),
        ("run_steane_pipeline", ctypes.c_int),
        ("run_surface_pipeline", ctypes.c_int),
        ("run_distill_pipeline", ctypes.c_int),
        ("steane_encode", ctypes.c_int),
        ("surface_encode", ctypes.c_int),
        ("use_lattice", ctypes.c_int),
        ("color_encode", ctypes.c_int),
        ("insert_syndrome", ctypes.c_int),
        ("syndrome_method", ctypes.c_char * 32),
        ("syndrome_rounds", ctypes.c_int),
        ("insert_correction", ctypes.c_int),
        ("pauli_frame_opt", ctypes.c_int),
        ("magic_distill", ctypes.c_int),
        ("distill_protocol", ctypes.c_char * 32),
        ("distill_levels", ctypes.c_int),
        ("distill_target_error", ctypes.c_double),
        ("transversal_gates", ctypes.c_int),
        ("decompose_non_transversal", ctypes.c_int),
        ("lower_to_quantum", ctypes.c_int),
        ("lower_to_stim", ctypes.c_int),
        ("lower_to_qir", ctypes.c_int),
        ("lower_to_qasm3", ctypes.c_int),
        ("lower_to_iqm_json", ctypes.c_int),
        ("lower_to_lattice_surgery", ctypes.c_int),
        ("lower_to_iqs", ctypes.c_int),
        ("resource_estimate", ctypes.c_int),
        ("print_report", ctypes.c_int),
        ("fault_path", ctypes.c_int),
        ("fault_path_max_order", ctypes.c_int),
        ("threshold_analysis", ctypes.c_int),
        ("physical_error_rate", ctypes.c_double),
        ("target_error_rate", ctypes.c_double),
        ("lower_to_iqm_json_radians", ctypes.c_int),
        ("lower_to_iqm_json_physical", ctypes.c_int),
    ]


class OperationError(RuntimeError):
    """A controlled operation input, runtime, or output error."""


def parse_arguments(arguments: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="qhpc-ftqc-prepare-iqm")
    parser.add_argument(
        "--preparation",
        choices=("device", "steane-logical"),
        default="device",
    )
    parser.add_argument("--function-name", default="circuit")
    parsed = parser.parse_args(arguments)
    if (
        FUNCTION_NAME.fullmatch(parsed.function_name) is None
        or len(parsed.function_name.encode("ascii", "ignore")) > 63
    ):
        parser.error("--function-name must be an MLIR identifier of at most 63 bytes")
    return parsed


def read_input() -> bytes:
    if not INPUT.is_file():
        raise OperationError("missing input: /inputs/circuit.qasm")
    if INPUT.stat().st_size > 1_000_000:
        raise OperationError("FTQC circuit input exceeds the 1 MB limit")
    try:
        payload = INPUT.read_bytes()
        text = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise OperationError("input circuit must be UTF-8 text") from error
    if QASM_HEADER.search(text) is None:
        raise OperationError("input circuit must declare OPENQASM 2.0 or 3.0")
    return payload


def compile_program(circuit: bytes, preparation: str, function_name: str) -> str:
    try:
        library = ctypes.CDLL("/opt/qhpc/lib/libftqc.so.1")
        compiler = library.ftqc_qasm_opt
        compiler.argtypes = [
            ctypes.c_void_p,
            ctypes.c_size_t,
            ctypes.POINTER(FTQCConfiguration),
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(ctypes.c_size_t),
        ]
        compiler.restype = ctypes.c_int
        release = library.ftqc_free
        release.argtypes = [ctypes.c_void_p]
        release.restype = None
    except (AttributeError, OSError) as error:
        raise OperationError("FTQC compiler library could not be loaded") from error

    configuration = FTQCConfiguration()
    configuration.ecc_kind = b"steane"
    configuration.ecc_dist = 3
    configuration.func_name = function_name.encode("ascii")
    configuration.lower_to_iqm_json = 1
    configuration.lower_to_iqm_json_radians = 1
    configuration.lower_to_iqm_json_physical = int(preparation == "steane-logical")
    output = ctypes.c_void_p()
    output_size = ctypes.c_size_t()
    source = ctypes.create_string_buffer(circuit)
    status = compiler(
        source,
        len(circuit),
        ctypes.byref(configuration),
        ctypes.byref(output),
        ctypes.byref(output_size),
    )
    if status != 0 or not output.value or output_size.value < 1:
        if output.value:
            release(output)
        raise OperationError(f"FTQC compilation exited with status {status}")
    try:
        return (
            ctypes.string_at(output, output_size.value).decode("utf-8").rstrip()
            + "\n"
        )
    except UnicodeDecodeError as error:
        raise OperationError("FTQC compiler output must be UTF-8 text") from error
    finally:
        release(output)


def decode_mlir_string(value: str) -> str:
    output = bytearray()
    index = 0
    while index < len(value):
        if value[index] != "\\":
            output.extend(value[index].encode("utf-8"))
            index += 1
        elif index + 2 < len(value) and re.fullmatch(
            r"[0-9A-Fa-f]{2}", value[index + 1 : index + 3]
        ):
            output.append(int(value[index + 1 : index + 3], 16))
            index += 3
        elif index + 1 < len(value) and value[index + 1] in {'"', "\\"}:
            output.extend(value[index + 1].encode("utf-8"))
            index += 2
        else:
            raise OperationError("FTQC returned an invalid MLIR string escape")
    try:
        return output.decode("utf-8")
    except UnicodeDecodeError as error:
        raise OperationError("FTQC returned a non-UTF-8 MLIR string") from error


def validated_circuit(program: str) -> dict[str, Any]:
    match = IQM_JSON_ATTRIBUTE.search(program)
    if match is None:
        raise OperationError("FTQC output lacks its IQM JSON module attribute")
    try:
        circuit = json.loads(decode_mlir_string(match.group(1)))
    except json.JSONDecodeError as error:
        raise OperationError("FTQC emitted invalid IQM JSON") from error
    if not isinstance(circuit, dict) or set(circuit) != {"name", "instructions"}:
        raise OperationError("FTQC IQM output must contain name and instructions")
    if not isinstance(circuit["name"], str) or not circuit["name"]:
        raise OperationError("FTQC IQM circuit name is invalid")
    instructions = circuit["instructions"]
    if not isinstance(instructions, list) or not 1 <= len(instructions) <= 100_000:
        raise OperationError("FTQC IQM circuit must contain 1 to 100000 instructions")
    for index, instruction in enumerate(instructions):
        if not isinstance(instruction, dict) or set(instruction) != {
            "name",
            "locus",
            "args",
        }:
            raise OperationError(f"FTQC IQM instruction {index} is malformed")
        if instruction["name"] not in {"prx", "cz", "measure"}:
            raise OperationError(f"FTQC IQM instruction {index} uses an unsupported gate")
        if not isinstance(instruction["args"], dict):
            raise OperationError(f"FTQC IQM instruction {index} has invalid arguments")
        locus = instruction["locus"]
        if (
            not isinstance(locus, list)
            or not locus
            or any(
                not isinstance(value, str)
                or re.fullmatch(r"QB[1-9][0-9]*", value) is None
                for value in locus
            )
        ):
            raise OperationError(f"FTQC IQM instruction {index} has an invalid locus")
    return circuit


def preparation_report(circuit: dict[str, Any], preparation: str) -> dict[str, Any]:
    gate_counts: dict[str, int] = {}
    loci: set[str] = set()
    for instruction in circuit["instructions"]:
        name = instruction["name"]
        gate_counts[name] = gate_counts.get(name, 0) + 1
        loci.update(instruction["locus"])
    if preparation == "device":
        if loci != {"QB1", "QB2"} or gate_counts.get("measure") != 2:
            raise OperationError(
                "device preparation is restricted to a measured two-qubit circuit"
            )
        logical_qubits: int | None = None
        routing_requirement = "calibration-check-required"
        claim_boundary = (
            "Direct two-device-qubit lowering; FTQC's intermediate retains ECC type "
            "metadata, but no Steane block expansion is performed."
        )
    else:
        if (
            loci != {f"QB{index}" for index in range(1, 8)}
            or gate_counts.get("measure") != 7
        ):
            raise OperationError(
                "Steane logical preparation is restricted to one seven-data-qubit block"
            )
        logical_qubits = 1
        routing_requirement = "required-before-hardware"
        claim_boundary = (
            "One Steane [[7,1,3]] logical qubit expanded to seven data qubits; "
            "this preparation alone is not evidence of error suppression."
        )
    return {
        "schema": "qhpc.ftqc-iqm-preparation-report.v1",
        "preparation": preparation,
        "compiler_interface": "ftqc_qasm_opt",
        "source_revision": SOURCE_REVISION,
        "ecc": {"kind": "steane", "distance": 3},
        "logical_qubits": logical_qubits,
        "device_qubits": len(loci),
        "instruction_count": len(circuit["instructions"]),
        "gate_counts": dict(sorted(gate_counts.items())),
        "loci": sorted(loci, key=lambda value: int(value[2:])),
        "angle_units": "radians",
        "routing": {
            "status": "not-performed",
            "requirement": routing_requirement,
            "reason": (
                "Topology routing needs qiskit-iqm and current device calibration; "
                "it is outside this credential-free local stage."
            ),
        },
        "submission": {
            "status": "not-submitted",
            "execution_class": "quantum-backend",
        },
        "claim_boundary": claim_boundary,
    }


def write_output(name: str, payload: str) -> None:
    if not OUTPUT_DIRECTORY.is_dir() or not os.access(OUTPUT_DIRECTORY, os.W_OK):
        raise OperationError("output mount is not writable: /outputs")
    destination = OUTPUT_DIRECTORY / name
    temporary = OUTPUT_DIRECTORY / f".{name}.tmp"
    temporary.write_text(payload, encoding="utf-8")
    os.replace(temporary, destination)


def main(arguments: list[str]) -> int:
    parsed = parse_arguments(arguments)
    circuit_data = read_input()
    program = compile_program(circuit_data, parsed.preparation, parsed.function_name)
    circuit = validated_circuit(program)
    report = preparation_report(circuit, parsed.preparation)
    write_output("program.mlir", program)
    write_output(
        "iqm-circuit.json", json.dumps(circuit, indent=2, sort_keys=True) + "\n"
    )
    write_output(
        "preparation-report.json", json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    print(
        f"FTQC prepared {report['device_qubits']} IQM loci; "
        "routing and hardware submission were not performed"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except OperationError as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(65)
