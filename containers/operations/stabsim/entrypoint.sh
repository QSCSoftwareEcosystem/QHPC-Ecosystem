#!/bin/sh
set -eu

if [ "$#" -ne 2 ] || [ "$1" != "--random-seed" ]; then
    printf '%s\n' \
        "usage: qhpc-stabsim-metrics --random-seed NONNEGATIVE_INTEGER" >&2
    exit 64
fi
case "$2" in
    ''|*[!0-9]*)
        printf '%s\n' "random seed must be a nonnegative integer" >&2
        exit 64
        ;;
esac
random_seed=$2
if [ ! -f /inputs/circuit.qasm ]; then
    printf '%s\n' "missing input: /inputs/circuit.qasm" >&2
    exit 66
fi
if [ ! -d /outputs ] || [ ! -w /outputs ]; then
    printf '%s\n' "output mount is not writable: /outputs" >&2
    exit 73
fi

metrics=$(
    /opt/qhpc/libexec/nwq_qasm \
        --qasm_file /inputs/circuit.qasm \
        --metrics \
        --backend cpu \
        --sim stab \
        --random_seed "$random_seed"
)
parsed=$(
    printf '%s\n' "$metrics" |
        sed -nE 's/^Circuit Depth: ([0-9]+); One-qubit Gates: ([0-9]+); Two-qubit Gates: ([0-9]+); Gate Density: ([0-9.]+); Retention Lifespan: ([0-9.]+); Measurement Density: ([0-9.]+); Entanglement Variance: ([0-9.]+)$/\1|\2|\3|\4|\5|\6|\7/p'
)
if [ -z "$parsed" ]; then
    printf '%s\n' "STABSim returned unrecognized metrics" >&2
    exit 65
fi

old_ifs=$IFS
IFS='|'
set -- $parsed
IFS=$old_ifs
umask 077
printf '{\n  "circuit_depth": %s,\n  "entanglement_variance": %s,\n  "gate_density": %s,\n  "measurement_density": %s,\n  "one_qubit_gates": %s,\n  "retention_lifespan": %s,\n  "two_qubit_gates": %s\n}\n' \
    "$1" "$7" "$4" "$6" "$2" "$5" "$3" \
    > /outputs/metrics.json
printf '%s\n' "$metrics"
