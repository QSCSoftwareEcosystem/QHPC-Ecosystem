"""Exercise the runtime-free NWQEC Clifford and T count interface."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from qhpc_ecosystem.project_adapters import count_nwqec_clifford_t


FIXTURE = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
creg c[3];
h q[0];
cx q[0],q[1];
u1(0.7853981633974483) q[2];
cu1(0.7853981633974483) q[2],q[0];
cu1(1.5707963267948966) q[2],q[1];
h q[2];
measure q -> c;
"""


def main() -> int:
    with TemporaryDirectory(prefix="qhpc-nwqec-") as directory:
        circuit = Path(directory) / "fixture.qasm"
        circuit.write_text(FIXTURE, encoding="utf-8")
        result = count_nwqec_clifford_t(
            circuit,
            {
                "keep_ccx": False,
                "rz_error_policy": "total",
                "epsilon": 0.01,
            },
        )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
