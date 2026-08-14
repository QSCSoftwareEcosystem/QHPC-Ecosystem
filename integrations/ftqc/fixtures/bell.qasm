OPENQASM 3.0;
include "stdgates.inc";

qubit[2] q;
bit[2] b;

h q[0];
cx q[0], q[1];

b[0] = measure q[0];
b[1] = measure q[1];
