#!/bin/sh
set -eu

if [ "$#" -ne 0 ]; then
    printf '%s\n' "qhpc-qasmtrans does not accept command arguments" >&2
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

umask 077
exec /opt/qhpc/libexec/QASMTrans \
    -i /inputs/circuit.qasm \
    -m ibmq \
    -c /opt/qhpc/share/qasmtrans/devices/ibmq_toronto.json \
    -o /outputs/circuit.qasm \
    -v 1
