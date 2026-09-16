#!/bin/sh
set -eu

if [ "$#" -ne 6 ] || [ "$1" != "--shots" ] ||
    [ "$3" != "--random-seed" ] || [ "$5" != "--max-qubits" ]; then
    printf '%s\n' \
        "usage: qhpc-nwqsim-simulate --shots POSITIVE_INTEGER --random-seed NONNEGATIVE_INTEGER --max-qubits 1..16" >&2
    exit 64
fi
shots=$2
random_seed=$4
max_qubits=$6
case "$shots" in ''|*[!0-9]*|0) printf '%s\n' "shots must be a positive integer" >&2; exit 64;; esac
case "$random_seed" in ''|*[!0-9]*) printf '%s\n' "random seed must be a nonnegative integer" >&2; exit 64;; esac
case "$max_qubits" in ''|*[!0-9]*|0) printf '%s\n' "max qubits must be an integer from 1 through 16" >&2; exit 64;; esac
if [ "$max_qubits" -gt 16 ]; then
    printf '%s\n' "max qubits must not exceed the 16-qubit development bound" >&2
    exit 64
fi
if [ ! -f /inputs/circuit.qasm ]; then
    printf '%s\n' "missing input: /inputs/circuit.qasm" >&2
    exit 66
fi
if [ ! -d /outputs ] || [ ! -w /outputs ]; then
    printf '%s\n' "output mount is not writable: /outputs" >&2
    exit 73
fi

qubits=$(sed -nE 's/^[[:space:]]*qreg[[:space:]]+[A-Za-z_][A-Za-z0-9_]*\[([0-9]+)\][[:space:]]*;[[:space:]]*$/\1/p' /inputs/circuit.qasm | awk 'NR == 1 { print; exit }')
if [ -z "$qubits" ] || [ "$qubits" -gt "$max_qubits" ]; then
    printf '%s\n' "input must declare one OpenQASM qreg within the requested qubit bound" >&2
    exit 65
fi
if ! grep -Eq '^[[:space:]]*OPENQASM[[:space:]]+2\.0[[:space:]]*;[[:space:]]*$' /inputs/circuit.qasm; then
    printf '%s\n' "input must declare OPENQASM 2.0" >&2
    exit 65
fi

report=$(/opt/qhpc/libexec/nwq_qasm --qasm_file /inputs/circuit.qasm --shots "$shots" --backend cpu --sim sv --random_seed "$random_seed")
pairs=$(printf '%s\n' "$report" | sed -nE 's/^"([01]+)" : ([0-9]+)$/\1|\2/p')
if [ -z "$pairs" ]; then
    printf '%s\n' "NWQ-Sim returned no recognized measurement counts" >&2
    exit 65
fi
total=$(printf '%s\n' "$pairs" | awk -F '|' '{ sum += $2 } END { print sum }')
if [ "$total" != "$shots" ]; then
    printf '%s\n' "NWQ-Sim measurement counts do not match requested shots" >&2
    exit 65
fi

umask 022
{
    printf '{\n  "backend": "CPU",\n  "counts": {\n'
    first=true
    printf '%s\n' "$pairs" | while IFS='|' read -r state count; do
        if [ "$first" = true ]; then first=false; else printf ',\n'; fi
        printf '    "%s": %s' "$state" "$count"
    done
    printf '\n  },\n  "qubits": %s,\n  "random_seed": %s,\n  "shots": %s,\n  "simulation_method": "sv",\n  "source_revision": "b35763d846e6512ed817d3f88ac8ce79a7e82a7e"\n}\n' \
        "$qubits" "$random_seed" "$shots"
} > /outputs/measurements.json
printf '%s\n' "$report"
