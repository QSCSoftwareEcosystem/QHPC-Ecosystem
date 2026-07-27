#!/bin/sh
set -eu

if [ "$#" -ne 6 ] ||
    [ "$1" != "--keep-ccx" ] ||
    [ "$3" != "--rz-error-policy" ] ||
    [ "$5" != "--epsilon" ]; then
    printf '%s\n' \
        "usage: qhpc-nwqec-counts --keep-ccx BOOLEAN --rz-error-policy POLICY --epsilon NUMBER" >&2
    exit 64
fi
keep_ccx=$2
policy=$4
epsilon=$6
case "$keep_ccx" in
    true|false) ;;
    *)
        printf '%s\n' "keep-ccx must be true or false" >&2
        exit 64
        ;;
esac
case "$policy" in
    per-gate|total|relative) ;;
    *)
        printf '%s\n' "invalid RZ error policy" >&2
        exit 64
        ;;
esac
if ! printf '%s\n' "$epsilon" |
    grep -Eq '^(0(\.[0-9]+)?|[1-9][0-9]*(\.[0-9]+)?)([eE][-+]?[0-9]+)?$' ||
    printf '%s\n' "$epsilon" | grep -Eq '^0(\.0+)?([eE][-+]?[0-9]+)?$'; then
    printf '%s\n' "epsilon must be a positive number" >&2
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

if [ "$keep_ccx" = true ]; then
    report=$(
        /opt/qhpc/libexec/nwqec-cli \
            /inputs/circuit.qasm --ct-counts --keep-ccx \
            --rz-err "$policy" --epsilon "$epsilon"
    )
else
    report=$(
        /opt/qhpc/libexec/nwqec-cli \
            /inputs/circuit.qasm --ct-counts \
            --rz-err "$policy" --epsilon "$epsilon"
    )
fi
source_qubits=$(
    printf '%s\n' "$report" |
        sed -nE 's/^Circuit contains ([0-9]+) qubits,.*$/\1/p' |
        head -n 1
)
pairs=$(mktemp)
printf '%s\n' "$report" |
    sed -nE '/^=== Clifford\+T Gate Counts ===$/,$s/^  ([a-z][a-z0-9_]*): ([0-9]+)$/\1|\2/p' \
    > "$pairs"
if [ -z "$source_qubits" ] || [ ! -s "$pairs" ]; then
    printf '%s\n' "NWQEC returned an unrecognized count report" >&2
    exit 65
fi

umask 077
{
    printf '{\n  "counts": {\n'
    first=true
    total_t=0
    while IFS='|' read -r gate count; do
        if [ "$first" = false ]; then
            printf ',\n'
        fi
        first=false
        printf '    "%s": %s' "$gate" "$count"
        case "$gate" in
            t|tdg) total_t=$((total_t + count)) ;;
        esac
    done < "$pairs"
    printf '\n  },\n'
    printf '  "epsilon": %s,\n' "$epsilon"
    printf '  "rz_error_policy": "%s",\n' "$policy"
    printf '  "source_qubits": %s,\n' "$source_qubits"
    printf '  "total_t_count": %s\n}\n' "$total_t"
} > /outputs/counts.json
printf '%s\n' "$report"
