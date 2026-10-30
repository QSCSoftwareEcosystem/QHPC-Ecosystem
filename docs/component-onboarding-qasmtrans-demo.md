# Public QASMTrans Onboarding Demonstration

This walkthrough demonstrates EQO's repository-onboarding boundary with the
public [PNNL QASMTrans repository](https://github.com/pnnl/qasmtrans). It is
an inspection demonstration—not an installation or deployment procedure.

## Steps

1. Start EQO Local and open **Components** in the Workbench.
2. Enter `https://github.com/pnnl/qasmtrans` as the repository URL.
3. Enter `refs/heads/master` as the tracked ref and choose the
   **Compiler/transpiler** template.
4. Select **Inspect source**. Review the resolved commit, recognized files,
   detected templates, and proposed typed interface before considering a
   separate isolated build.

On 2026-10-30, this inspection resolved the public `master` ref to
`c745a382a7abcc5e6cce5262361c7c42040dd12f` (commit date
2026-10-05T16:35:33-07:00, subject `Update README.md`). It recognized 204
tracked files, detected both the Python-operation and compiler/transpiler
templates, executed no repository code, and exposed no host credentials.

The observed commit is evidence for this demonstration only. Repeating the
workflow must resolve the ref again and display the then-current immutable
commit; EQO must not silently replace a reviewed source pin.

## Composer relationship

EQO already publishes a separately reviewed QASMTrans capability for its
**Transform a circuit** Basic Composer path. That published operation maps an
OpenQASM 2 circuit to its documented fixed topology and emits a typed
transpiled-circuit artifact for downstream analysis.

The onboarding candidate above is deliberately not attached to that Composer
path. To make an imported revision selectable, a reviewer must complete its
isolated build and smoke test, explicitly admit the immutable image locally,
then publish a versioned capability contract and workflow binding. This keeps a
new public source candidate from changing a working workflow merely because a
branch moved.
