# EQO 15-minute technical demo

## Summary

Create one caption-led, 16:9 screen recording for technical evaluators. The story is:

**install EQO Local → discover admitted tools → compose and run a typed multi-tool workflow → inspect provenance → use the same control plane from CLI and Jupyter.**

The hero workflow is **Evolution to hardware readiness**:

`Pauli Hamiltonian → OpenQEvo → QASMTrans → STABSim + NWQEC`

This shows four tools, typed artifact handoffs, worker selection, run state, and reproducible outputs without implying HPC production or quantum-hardware execution.

## Recording plan

| Time | Screen | Demonstration |
|---|---:|---|
| 0:00–0:35 | Workbench Overview | EQO’s purpose: an orchestration layer connecting independent quantum/HPC tools through typed workflows and recorded provenance. |
| 0:35–2:15 | VS Code terminal | Show prerequisites, virtual environment, `pip install -e ".[local,jupyter]"`, then `eqo local up --open`. Use an edited/time-compressed segment for first-run image preparation; retain the final ready summary. |
| 2:15–3:15 | Terminal + browser | Show `eqo local status`, then Overview with healthy API, Workbench, assistant, and workers. State that this is a local development profile using admitted containerized runtimes. |
| 3:15–4:45 | Workbench Tools / Knowledge | Find OpenQEvo, QASMTrans, STABSim, and NWQEC. Show that operations have declared inputs, outputs, targets, and runtime identity. Use Knowledge Explorer only to establish connected ecosystem context. |
| 4:45–7:15 | Compose | Select **Evolution to hardware readiness**, explain the four-step graph and its fan-out, load the provided two-qubit Pauli Hamiltonian, review the typed input and worker readiness, then submit. |
| 7:15–9:15 | Runs / Artifacts | Follow the live run to completion. Inspect the synthesis report, OpenQASM output, mapped circuit metrics, and Clifford/T count. Highlight run ID, workflow version, artifact checksums, and runtime/provenance—not scientific-performance claims. |
| 9:15–11:00 | Terminal / CLI | Show the same control plane from CLI: `eqo workflow list`, run listing/info, and run export. Use the run created in the Workbench; do not submit a duplicate run. |
| 11:00–13:40 | Jupyter in VS Code | Open `examples/notebooks/eqo_evolution_readiness.ipynb`. Execute or reveal the cells that connect with `EQOClient`, create the typed Hamiltonian artifact, locate the published workflow, submit it, wait, and render artifacts. For timing, use the already-completed Workbench run when showing results. |
| 13:40–15:00 | Workbench results | Return to the completed run and summarize: the workflow is versioned, the tools remain independent, handoffs are typed, and outputs retain inspectable evidence. End on Runs/Artifacts rather than a marketing screen. |

## Complete demo workflow and preparation

- Use the published `showcase-evolution-readiness@0.1.1` workflow and `examples/inputs/openqevo-two-qubit-hamiltonian.json`; do not create a new scientific workflow for the video.
- Before recording, verify Docker access, the optional admitted OpenQEvo runtime, worker health, and workflow publication with:
  - `docker version`
  - `eqo local runtime list`
  - `eqo local up --open`
  - `eqo local status`
  - `eqo local diagnose`
  - `eqo workflow list`
- Run one complete rehearsal end-to-end. Confirm the four expected outputs: synthesis report, source circuit, transpiled circuit/metrics, and Clifford/T counts.
- Capture a clean successful run before the main recording as a recovery asset. During the main take, show real submission and real status transitions; if execution exceeds the allotted time, cut to the pre-captured completed run with a caption identifying it as the same workflow/input profile.
- Keep ChatQEC out of the main path. Its current local profile is direct Stim/Tsim circuit tooling, not a general model-backed QEC assistant; it would distract from the workflow story.
- Prepare VS Code in a three-pane sequence: terminal, browser Workbench, and Jupyter notebook. Use readable 125–140% zoom, a clean terminal, and only the files needed for the demo.

## Captions and claims

- No narration. Add concise captions in Claude during editing; use `.development/eqo-video-caption-context.md` as factual context.
- Use captions such as: “Typed Pauli-Hamiltonian input,” “Pinned runtime and compatible worker required,” “One circuit fans out to independent analyses,” and “Artifacts preserve the workflow version, input, runtime, and output evidence.”
- State “local development execution” and “containerized admitted runtime.” Do not say production HPC, QPU execution, scientific validation, or fault-tolerant advantage.
- Show long installation/image-download time as a short accelerated sequence, clearly labeled “first-run runtime preparation.”

## Acceptance checks

- A viewer can see an installation command, ready local services, a runnable multi-tool workflow, a submitted run, completed artifacts, CLI inspection, and notebook use within 15 minutes.
- The hero run succeeds during rehearsal using the recorded input and available local workers.
- Every visible result is traceable to the EQO run/artifact views; no output is manually edited or represented as hardware/HPC evidence.
- The final edit remains understandable with captions alone and without audio.

## Assumptions

- The video is 1920×1080 landscape and caption-led, with no voice-over.
- The optional OpenQEvo runtime already installed for this workspace remains available; if it is not, repair that before recording rather than including runtime-admission troubleshooting in the main demo.
- The “complete workflow” deliverable is the complete timed recording runbook above, not a new repository workflow artifact.
