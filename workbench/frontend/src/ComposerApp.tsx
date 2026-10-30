import {
  Background,
  BackgroundVariant,
  ReactFlow,
  ReactFlowProvider,
  applyEdgeChanges,
  applyNodeChanges,
  type Connection,
  type EdgeChange,
  type NodeChange,
  type OnSelectionChangeParams,
  useReactFlow,
} from "@xyflow/react";
import {
  Braces,
  Check,
  ChevronRight,
  CircleAlert,
  CloudUpload,
  FileCode2,
  FilePlus2,
  FileUp,
  FlaskConical,
  FolderOpen,
  GitFork,
  LoaderCircle,
  Maximize2,
  PanelLeft,
  PanelRight,
  Play,
  Redo2,
  Save,
  Search,
  Trash2,
  Undo2,
  Unplug,
  X,
} from "lucide-react";
import {
  Fragment,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { composerApi } from "./api";
import {
  type PreflightDisplay,
  workflowPreflightDisplay,
} from "./preflight";
import {
  canvasToWorkflow,
  capabilityOperationIndex,
  connectionEdge,
  createBoundaryForPort,
  createEmptyWorkflow,
  createOperationCanvasNode,
  createWorkflowInputCanvasNode,
  layoutFromCanvas,
  uniqueNodeId,
  validateCanvas,
  validateConnection,
  workflowToCanvas,
} from "./graph";
import {
  BoundaryCanvasNode,
  OperationCanvasNode,
} from "./nodes";
import { latestWorkflowVersions } from "./workflowVersions";
import type {
  ArtifactPort,
  CapabilitySummary,
  ComposerEdge,
  ComposerNode,
  DraftValidation,
  OperationDefinition,
  ParameterDefinition,
  ParameterValue,
  PublishedWorkflow,
  Workflow,
  WorkflowDraft,
  WorkflowPreflight,
} from "./types";


type LibraryView = "operations" | "templates" | "drafts";
type ComposerMode = "basic" | "guided" | "advanced";
type BasicPathId = "simulate" | "transform" | "hardware";
type BasicBlockKind = "input" | "transform" | "execution" | "analysis" | "output";
type BasicIntentId =
  | "circuit-input"
  | "simulate"
  | "transform"
  | "compile-target"
  | "analyze-results"
  | "run-hardware"
  | "results";
type SaveState = "idle" | "dirty" | "saving" | "saved" | "error";

interface GraphSnapshot {
  nodes: ComposerNode[];
  edges: ComposerEdge[];
}

interface LatestDocument {
  nodes: ComposerNode[];
  edges: ComposerEdge[];
  metadata: Workflow["metadata"];
  viewport: { x: number; y: number; zoom: number };
  changeVersion: number;
}

type BlueprintStageStatus =
  | "Evidence passed"
  | "Contract defined"
  | "Partial evidence"
  | "Optional future"
  | "Source verified"
  | "Developer reported"
  | "Result pending";

interface IncubationBlueprint {
  name: string;
  description: string;
  metrics: { label: string; value: string }[];
  pipelineTitle: string;
  stages: {
    name: string;
    tool: string;
    status: BlueprintStageStatus;
    handoff: string;
    detail: string;
  }[];
  factsTitle: string;
  facts: { label: string; value: string }[];
  evidenceTable?: {
    ariaLabel: string;
    columns: string[];
    rows: string[][];
    note: string;
    noteTone: "passed" | "pending";
  };
  artifactsTitle: string;
  artifacts: {
    name: string;
    reference: string;
    status: string;
  }[];
  gatesTitle: string;
  remainingGates: string[];
  callout: {
    title: string;
    detail: string;
    tone: "information" | "warning";
  };
  footerStatus: string;
  evidenceAction: {
    label: string;
    href: string;
  };
  runDisabledTitle: string;
}

interface ScientificPathDefinition {
  workflowId: string;
  code: string;
  shortName: string;
  section: "start" | "journey" | "tour" | "gated";
  featuredRecipe?: {
    detail: string;
  };
  toolChain: string[];
  kind:
    | "Cross-tool study"
    | "Flagship showcase"
    | "Focused example"
    | "Hardware execution"
    | "Incubation blueprint";
  blueprint?: IncubationBlueprint;
  inputLabel?: string;
  inputFileLabel?: string;
  inputAccept?: string;
  inputPlaceholder?: string;
  exampleName?: string;
  exampleLabel?: string;
  exampleContent?: string;
  examples?: Array<{
    name: string;
    label: string;
    content: string;
  }>;
  hardwareNotice?: {
    title: string;
    detail: string;
  };
}

interface ScientificPath {
  definition: ScientificPathDefinition;
  workflow?: PublishedWorkflow;
}

interface BasicPathDefinition {
  id: BasicPathId;
  workflowId: string;
  title: string;
  detail: string;
  actionLabel: string;
  inputLabel: string;
  inputAccept: string;
  inputPlaceholder: string;
  exampleName: string;
  exampleLabel: string;
  exampleContent: string;
  blocks: BasicPathBlock[];
  hardwareNotice?: string;
}

interface BasicIntentBlock {
  id: BasicIntentId;
  title: string;
  detail: string;
  kind: BasicBlockKind;
}

interface BasicPathBlock extends BasicIntentBlock {
  nodeIds?: string[];
}

interface BasicPath extends BasicPathDefinition {
  workflow?: PublishedWorkflow;
}

interface ComposerInputDefinition {
  id: string;
  name: string;
  title: string;
  detail: string;
  artifactType: string;
}


const NODE_TYPES = {
  operation: OperationCanvasNode,
  boundary: BoundaryCanvasNode,
};

const COMPOSER_INPUTS: ComposerInputDefinition[] = [
  {
    id: "openqasm-circuit",
    name: "circuit",
    title: "Input OpenQASM Circuit",
    detail: "qhpc.quantum-circuit@1",
    artifactType: "qhpc.quantum-circuit@1",
  },
  {
    id: "pauli-hamiltonian",
    name: "hamiltonian",
    title: "Input Pauli Hamiltonian",
    detail: "qhpc.pauli-hamiltonian@1",
    artifactType: "qhpc.pauli-hamiltonian@1",
  },
  {
    id: "stim-circuit",
    name: "stim_circuit",
    title: "Input Stim Circuit",
    detail: "qhpc.stim-circuit@1",
    artifactType: "qhpc.stim-circuit@1",
  },
  {
    id: "tsim-circuit",
    name: "tsim_circuit",
    title: "Input TSim Circuit",
    detail: "qhpc.tsim-circuit@1",
    artifactType: "qhpc.tsim-circuit@1",
  },
  {
    id: "glcb-circuit-specification",
    name: "glcb_circuit",
    title: "Input GLCB Circuit Specification",
    detail: "qhpc.glcb-circuit-spec@1",
    artifactType: "qhpc.glcb-circuit-spec@1",
  },
];

const OPERATION_GRID = {
  columns: 2,
  origin: { x: 56, y: 64 },
  gap: { x: 322, y: 248 },
};

function nextOperationPosition(nodes: ComposerNode[]): { x: number; y: number } {
  const index = nodes.filter((node) => node.data.kind === "operation").length;
  const column = index % OPERATION_GRID.columns;
  const row = Math.floor(index / OPERATION_GRID.columns);
  return {
    x: OPERATION_GRID.origin.x + column * OPERATION_GRID.gap.x,
    y: OPERATION_GRID.origin.y + row * OPERATION_GRID.gap.y,
  };
}

const QASMTRANS_BELL_EXAMPLE = `OPENQASM 2.0;
include "qelib1.inc";

qreg q[2];
creg c[2];

h q[0];
cx q[0],q[1];
measure q[0] -> c[0];
measure q[1] -> c[1];
`;

const NWQEC_BELL_EXAMPLE = `OPENQASM 2.0;
include "qelib1.inc";
qreg q[2];
h q[0];
cx q[0],q[1];
`;

const OPENQEVO_HAMILTONIAN_EXAMPLE = `{
  "qubits": 2,
  "terms": [
    {
      "pauli": "ZI",
      "coefficient": 1.0
    },
    {
      "pauli": "IZ",
      "coefficient": 0.5
    },
    {
      "pauli": "XX",
      "coefficient": 0.25
    }
  ]
}
`;

const FTQC_BELL_EXAMPLE = `OPENQASM 3.0;
include "stdgates.inc";

qubit[2] q;
bit[2] result;

h q[0];
cx q[0], q[1];
result[0] = measure q[0];
result[1] = measure q[1];
`;

const FTQC_LOGICAL_ZERO_EXAMPLE = `OPENQASM 3.0;
include "stdgates.inc";

qubit[1] q;
bit[1] result;
result[0] = measure q[0];
`;

const FTQC_LOGICAL_H_EXAMPLE = `OPENQASM 3.0;
include "stdgates.inc";

qubit[1] q;
bit[1] result;
h q[0];
h q[0];
h q[0];
h q[0];
result[0] = measure q[0];
`;

const BASIC_INTENT_BLOCKS: readonly BasicIntentBlock[] = [
  {
    id: "circuit-input",
    title: "Circuit input",
    detail: "OpenQASM circuit",
    kind: "input",
  },
  {
    id: "simulate",
    title: "Simulate",
    detail: "Local CPU execution",
    kind: "execution",
  },
  {
    id: "transform",
    title: "Transform circuit",
    detail: "QASM conversion",
    kind: "transform",
  },
  {
    id: "compile-target",
    title: "Compile for target",
    detail: "FTQC preparation",
    kind: "transform",
  },
  {
    id: "analyze-results",
    title: "Analyze results",
    detail: "Measurement counts or circuit resources",
    kind: "analysis",
  },
  {
    id: "run-hardware",
    title: "Run on hardware",
    detail: "Configured IQM worker",
    kind: "execution",
  },
  {
    id: "results",
    title: "Results",
    detail: "Run artifacts and receipt",
    kind: "output",
  },
];

const BASIC_INTENT_BY_ID = new Map(
  BASIC_INTENT_BLOCKS.map((block) => [block.id, block]),
);

function basicPathBlock(
  id: BasicIntentId,
  nodeIds?: string[],
): BasicPathBlock {
  const block = BASIC_INTENT_BY_ID.get(id);
  if (!block) throw new Error(`Unknown basic intent block: ${id}`);
  return { ...block, nodeIds };
}

export const BASIC_PATHS: BasicPathDefinition[] = [
  {
    id: "simulate",
    workflowId: "nwqsim-bell-simulation",
    title: "Simulate a circuit",
    detail: "Run a bounded local Bell-circuit simulation and inspect its measurements.",
    actionLabel: "Run simulation",
    inputLabel: "OpenQASM 2 circuit",
    inputAccept: ".qasm,.txt,text/plain",
    inputPlaceholder: "OPENQASM 2.0;",
    exampleName: "bell.qasm",
    exampleLabel: "Load Bell circuit",
    exampleContent: QASMTRANS_BELL_EXAMPLE,
    blocks: [
      basicPathBlock("circuit-input"),
      basicPathBlock("simulate", ["simulate"]),
      basicPathBlock("analyze-results", ["simulate"]),
      basicPathBlock("results"),
    ],
  },
  {
    id: "transform",
    workflowId: "ct-hw-qasm-analysis",
    title: "Transform a circuit",
    detail: "Convert an OpenQASM circuit into an inspectable form and review its resource metrics.",
    actionLabel: "Transform circuit",
    inputLabel: "OpenQASM 2 circuit",
    inputAccept: ".qasm,.txt,text/plain",
    inputPlaceholder: "OPENQASM 2.0;",
    exampleName: "bell.qasm",
    exampleLabel: "Load Bell circuit",
    exampleContent: QASMTRANS_BELL_EXAMPLE,
    blocks: [
      basicPathBlock("circuit-input"),
      basicPathBlock("transform", ["transpile"]),
      {
        ...basicPathBlock("analyze-results", ["analyze"]),
        title: "Analyze metrics",
        detail: "Circuit resources",
      },
      {
        ...basicPathBlock("results"),
        detail: "Circuit and metrics",
      },
    ],
  },
  {
    id: "hardware",
    workflowId: "ftqc-iqm-bell-execution",
    title: "Run on quantum hardware",
    detail: "Prepare a Bell circuit for the configured IQM target, then submit it when the target is ready.",
    actionLabel: "Submit hardware run",
    inputLabel: "OpenQASM 3 circuit",
    inputAccept: ".qasm,.txt,text/plain",
    inputPlaceholder: "OPENQASM 3.0;",
    exampleName: "bell-hardware.qasm",
    exampleLabel: "Load Bell circuit",
    exampleContent: FTQC_BELL_EXAMPLE,
    blocks: [
      basicPathBlock("circuit-input"),
      basicPathBlock("compile-target", ["prepare"]),
      basicPathBlock("run-hardware", ["execute"]),
      {
        ...basicPathBlock("results"),
        detail: "Counts and receipt",
      },
    ],
    hardwareNotice:
      "Submitting this path creates a QPU job. EQO checks the admitted target first but does not reserve provider capacity.",
  },
];

function requestedBasicPathId(): BasicPathId {
  const requested = new URLSearchParams(window.location.search).get("basic");
  return BASIC_PATHS.some((path) => path.id === requested)
    ? requested as BasicPathId
    : "simulate";
}

export const SCIENTIFIC_PATHS: ScientificPathDefinition[] = [
  {
    workflowId: "showcase-evolution-readiness",
    code: "01",
    shortName: "Evolution to hardware readiness",
    section: "journey",
    kind: "Cross-tool study",
    toolChain: ["OpenQEvo", "QASMTrans", "STABSim", "NWQEC"],
    inputLabel: "Pauli Hamiltonian",
    inputFileLabel: "Choose .json",
    inputAccept: ".json,application/json,text/plain",
    inputPlaceholder: '{"qubits": 2, "terms": [...]}',
    exampleName: "two-qubit-hamiltonian.json",
    exampleLabel: "Load example",
    exampleContent: OPENQEVO_HAMILTONIAN_EXAMPLE,
  },
  {
    workflowId: "showcase-qec-distance-study",
    code: "02",
    shortName: "Compare QEC memory protection",
    section: "journey",
    kind: "Cross-tool study",
    toolChain: ["FTPrimitiveBench", "LightStim"],
  },
  {
    workflowId: "blueprint-h6-qflow-cycle",
    code: "H6",
    shortName: "H6 QFlow chemistry cycle",
    section: "gated",
    kind: "Incubation blueprint",
    toolChain: ["ExaChem", "QIRIS", "NWQSim", "FTQC"],
    blueprint: {
      name: "H6 QFlow heterogeneous chemistry cycle",
      description:
        "A validated H6/STO-3G chemistry handoff from ExaChem through QIRIS to NWQSim and back to QFlow. FTQC circuit lowering is shown as an optional extension, not a requirement for the VQE cycle.",
      metrics: [
        { label: "STATUS", value: "Incubation" },
        { label: "EVIDENCE", value: "3 / 3 tasks" },
        { label: "RUN", value: "Disabled" },
      ],
      pipelineTitle: "Proposed heterogeneous pipeline",
      stages: [
        {
          name: "Form the H6 active-space task set",
          tool: "ExaChem / QFlow",
          status: "Evidence passed",
          handoff: "qhpc.qflow-taskset@1",
          detail:
            "One chemistry cycle exports three identity-preserving VQE tasks from a shared pre-cycle snapshot.",
        },
        {
          name: "Schedule tasks and preserve identity",
          tool: "QIRIS over IRIS / QIR-EE",
          status: "Contract defined",
          handoff: "Task-set orchestration",
          detail:
            "The orchestration boundary is specified; live QIRIS submission and QIR expectation conversion remain pending.",
        },
        {
          name: "Solve each active-space VQE task",
          tool: "NWQSim QFlow plugin",
          status: "Evidence passed",
          handoff: "qhpc.qflow-taskset-result@1",
          detail:
            "All three task energies agree with the native reference within the 1e-8 hartree acceptance tolerance.",
        },
        {
          name: "Accept results and update amplitudes",
          tool: "ExaChem / QFlow",
          status: "Partial evidence",
          handoff: "qhpc.qflow-cycle-checkpoint@1",
          detail:
            "Aggregate acceptance passes in the cycle harness; live amplitude application, checkpointing, and restart equivalence remain.",
        },
        {
          name: "Lower an emitted circuit kernel",
          tool: "FTQC compiler",
          status: "Optional future",
          handoff: "qhpc.quantum-circuit@1 → qhpc.ftqc-mlir@1",
          detail:
            "Attach only when a QIRIS or solver path emits OpenQASM. The current H6 application-level VQE path does not compile quantum circuits.",
        },
      ],
      factsTitle: "Validated H6 cycle",
      facts: [
        { label: "Molecule", value: "Linear H6 · 2 bohr spacing" },
        { label: "Basis", value: "STO-3G" },
        { label: "Cycle", value: "1 chemistry cycle" },
        { label: "Tasks", value: "3 active-space VQE tasks" },
        { label: "Task size", value: "4 particles · 10 qubits each" },
        {
          label: "Snapshot",
          value: "h6_qflow_cycle1.sto-3g:cycle-1:dt1dt2-before-cycle",
        },
      ],
      evidenceTable: {
        ariaLabel: "H6 VQE energy comparison",
        columns: [
          "Task",
          "Native energy (Ha)",
          "NWQSim energy (Ha)",
          "Absolute delta",
        ],
        rows: [
          ["01", "-3.173416876000", "-3.173416876226", "2.262e-10"],
          ["02", "-3.200023047000", "-3.200023046772", "2.282e-10"],
          ["03", "-3.217620883000", "-3.217620882509", "4.911e-10"],
        ],
        note: "Acceptance tolerance: 1e-8 hartree · all three tasks pass",
        noteTone: "passed",
      },
      artifactsTitle: "Handoff artifacts",
      artifacts: [
        {
          name: "Chemistry task set",
          reference: "qhpc.qflow-taskset@1",
          status: "Evidence passed",
        },
        {
          name: "Aggregated solver results",
          reference: "qhpc.qflow-taskset-result@1",
          status: "Evidence passed",
        },
        {
          name: "Cycle checkpoint",
          reference: "qhpc.qflow-cycle-checkpoint@1",
          status: "Live write pending",
        },
        {
          name: "Optional FTQC lowering",
          reference: "qhpc.quantum-circuit@1 → qhpc.ftqc-mlir@1",
          status: "Circuit source and runtime pending",
        },
      ],
      gatesTitle: "Gates before Run can be enabled",
      remainingGates: [
        "Run the QIRIS service over an admitted IRIS/QIR-EE runtime and verify scheduler submission.",
        "Generate QIR, convert expectation results, and compare native amplitude artifacts.",
        "Apply amplitudes in live QFlow, write the cycle checkpoint, and prove restart equivalence.",
        "For the optional FTQC branch only: emit OpenQASM and admit an immutable LLVM/MLIR runtime.",
      ],
      callout: {
        title: "FTQC is optional.",
        detail:
          "The validated H6 VQE cycle does not require circuit compilation. Its FTQC branch becomes relevant only after a solver emits a circuit artifact.",
        tone: "information",
      },
      footerStatus: "Evidence blueprint · runtime gates pending",
      evidenceAction: {
        label: "Explore H6 evidence",
        href: "?view=knowledge&knowledge_node=packages/nwqsim-qflow",
      },
      runDisabledTitle:
        "Run becomes available after the live QIRIS and QFlow runtime gates pass.",
    },
  },
  {
    workflowId: "ftqc-iqm-bell-preparation",
    code: "F1",
    shortName: "Prepare a two-qubit Bell circuit",
    section: "tour",
    kind: "Flagship showcase",
    toolChain: ["FTQC", "IQM JSON"],
    inputLabel: "Measured two-device-qubit OpenQASM 3 circuit",
    inputFileLabel: "Choose .qasm",
    examples: [
      {
        name: "ftqc-bell.qasm",
        label: "Load Bell input",
        content: FTQC_BELL_EXAMPLE,
      },
    ],
  },
  {
    workflowId: "ftqc-iqm-steane-preparation",
    code: "F2",
    shortName: "Prepare one Steane logical qubit",
    section: "journey",
    kind: "Flagship showcase",
    toolChain: ["FTQC", "Steane [[7,1,3]]", "IQM JSON"],
    inputLabel: "One-logical-qubit OpenQASM 3 circuit",
    inputFileLabel: "Choose .qasm",
    examples: [
      {
        name: "logical0.qasm",
        label: "Load logical |0⟩",
        content: FTQC_LOGICAL_ZERO_EXAMPLE,
      },
      {
        name: "logical0-H.qasm",
        label: "Load four-H variant",
        content: FTQC_LOGICAL_H_EXAMPLE,
      },
    ],
  },
  {
    workflowId: "ftqc-iqm-steane-execution",
    code: "F3",
    shortName: "Route and execute one Steane logical qubit",
    section: "gated",
    kind: "Flagship showcase",
    toolChain: ["FTQC", "IQM route", "secured worker"],
    inputLabel: "One-logical-qubit OpenQASM 3 circuit",
    inputFileLabel: "Choose .qasm",
    examples: [
      {
        name: "logical0.qasm",
        label: "Load logical |0⟩",
        content: FTQC_LOGICAL_ZERO_EXAMPLE,
      },
      {
        name: "logical0-H.qasm",
        label: "Load four-H variant",
        content: FTQC_LOGICAL_H_EXAMPLE,
      },
    ],
  },
  {
    workflowId: "ftqc-iqm-bell-execution",
    code: "F4",
    shortName: "Route and execute a two-qubit Bell circuit",
    section: "gated",
    featuredRecipe: {
      detail: "Compile a known Bell circuit, check the admitted target, then submit an IQM QPU job.",
    },
    kind: "Hardware execution",
    toolChain: ["FTQC", "IQM route", "secured worker"],
    inputLabel: "Measured two-device-qubit OpenQASM 3 circuit",
    inputFileLabel: "Choose .qasm",
    inputPlaceholder: "OPENQASM 3.0;",
    examples: [
      {
        name: "ftqc-bell.qasm",
        label: "Load Bell input",
        content: FTQC_BELL_EXAMPLE,
      },
    ],
    hardwareNotice: {
      title: "Hardware execution",
      detail:
        "This published workflow sends the loaded Bell circuit to the configured IQM device for 512 shots. Select Run workflow only when you intend to submit a QPU job.",
    },
  },
  {
    workflowId: "ct-hw-qasm-analysis",
    code: "03",
    shortName: "Circuit transformation and metrics",
    section: "tour",
    featuredRecipe: {
      detail: "Start with OpenQASM and receive a transformed circuit plus inspectable resource metrics.",
    },
    kind: "Focused example",
    toolChain: ["QASMTrans", "STABSim"],
    inputLabel: "OpenQASM 2 circuit",
    exampleName: "bell.qasm",
    exampleContent: QASMTRANS_BELL_EXAMPLE,
  },
  {
    workflowId: "qec-memory-estimation",
    code: "04",
    shortName: "Fault-tolerant memory estimate",
    section: "journey",
    featuredRecipe: {
      detail: "Build a memory experiment and estimate its logical error rate under published assumptions.",
    },
    kind: "Focused example",
    toolChain: ["FTPrimitiveBench", "LightStim"],
  },
  {
    workflowId: "nwqec-counts",
    code: "05",
    shortName: "Clifford and T resource count",
    section: "tour",
    kind: "Focused example",
    toolChain: ["NWQEC"],
    inputLabel: "OpenQASM 2 circuit",
    exampleName: "bell-clifford.qasm",
    exampleContent: NWQEC_BELL_EXAMPLE,
  },
  {
    workflowId: "openqevo-trotter-synthesis",
    code: "GO",
    shortName: "Turn a Hamiltonian into a Trotter circuit",
    section: "start",
    featuredRecipe: {
      detail: "Start from a Pauli Hamiltonian and produce a Trotter circuit with its synthesis report.",
    },
    kind: "Focused example",
    toolChain: ["OpenQEvo", "Qiskit"],
    inputLabel: "Pauli Hamiltonian",
    inputFileLabel: "Choose .json",
    inputAccept: ".json,application/json,text/plain",
    inputPlaceholder: '{"qubits": 2, "terms": [...]}',
    exampleName: "two-qubit-hamiltonian.json",
    exampleLabel: "Load example",
    exampleContent: OPENQEVO_HAMILTONIAN_EXAMPLE,
  },
  {
    workflowId: "openqevo-dense-reference",
    code: "07",
    shortName: "Compare dense evolution methods",
    section: "tour",
    kind: "Focused example",
    toolChain: ["OpenQEvo"],
    inputLabel: "Pauli Hamiltonian",
    inputFileLabel: "Choose .json",
    inputAccept: ".json,application/json,text/plain",
    inputPlaceholder: '{"qubits": 2, "terms": [...]}',
    exampleName: "two-qubit-hamiltonian.json",
    exampleLabel: "Load example",
    exampleContent: OPENQEVO_HAMILTONIAN_EXAMPLE,
  },
  {
    workflowId: "openqevo-nwqsim-tour",
    code: "08",
    shortName: "OpenQEvo to NWQ-Sim CPU",
    section: "journey",
    kind: "Cross-tool study",
    toolChain: ["OpenQEvo", "NWQ-Sim CPU"],
    inputLabel: "Pauli Hamiltonian",
    inputFileLabel: "Choose .json",
    inputAccept: ".json,application/json,text/plain",
    inputPlaceholder: '{"qubits": 2, "terms": [...]}',
    exampleName: "two-qubit-hamiltonian.json",
    exampleLabel: "Load example",
    exampleContent: OPENQEVO_HAMILTONIAN_EXAMPLE,
  },
  {
    workflowId: "nwqsim-bell-simulation",
    code: "09",
    shortName: "NWQ-Sim CPU Bell simulation",
    section: "tour",
    kind: "Focused example",
    toolChain: ["NWQ-Sim CPU"],
    inputLabel: "OpenQASM 2 circuit",
    exampleName: "bell.qasm",
    exampleContent: QASMTRANS_BELL_EXAMPLE,
  },
  {
    workflowId: "chatqec-qec-toolchain",
    code: "10",
    shortName: "QEC circuit toolchain",
    section: "journey",
    kind: "Cross-tool study",
    toolChain: ["ChatQEC", "Stim", "PyMatching"],
  },
  {
    workflowId: "chatqec-tsim-simulation",
    code: "11",
    shortName: "Tsim non-Clifford simulation",
    section: "tour",
    kind: "Focused example",
    toolChain: ["Tsim"],
    inputLabel: "Tsim circuit",
  },
];

const GUIDED_SECTIONS = [
  { id: "start", title: "Getting started", detail: "Runnable workflows with a clear result" },
  { id: "journey", title: "Multi-tool studies", detail: "Connected workflows for program review" },
  { id: "tour", title: "Focused examples", detail: "Bounded demonstrations of individual capabilities" },
  { id: "gated", title: "Hardware and blueprints", detail: "Paths with readiness or evidence gates" },
] as const;

const GUIDED_RECIPE_ORDER = [
  "openqevo-trotter-synthesis",
  "ct-hw-qasm-analysis",
  "qec-memory-estimation",
  "ftqc-iqm-bell-execution",
] as const;

const ARTIFACT_LABELS: Record<string, string> = {
  "qhpc.quantum-circuit@1": "OpenQASM circuit",
  "qhpc.transpiled-circuit@1": "Transpiled circuit",
  "qhpc.circuit-metrics@1": "Circuit metrics",
  "qhpc.pauli-hamiltonian@1": "Pauli Hamiltonian",
  "qhpc.evolution-method-context@1": "Evolution method context",
  "qhpc.evolution-result@1": "Evolution method result",
  "qhpc.evolution-synthesis-report@1": "Evolution synthesis report",
  "qhpc.dense-unitary@1": "Dense reference unitary",
  "qhpc.stim-circuit@1": "Stim circuit",
  "qhpc.logical-error-estimate@1": "Logical error estimate",
  "qhpc.clifford-t-counts@1": "Clifford and T counts",
  "qhpc.ftqc-mlir@1": "FTQC MLIR program",
  "qhpc.iqm-circuit@1": "IQM-native circuit",
  "qhpc.ftqc-iqm-preparation-report@1": "FTQC preparation report",
  "qhpc.iqm-routed-layout@1": "IQM routed layout",
  "qhpc.iqm-job-receipt@1": "IQM job receipt",
  "qhpc.iqm-raw-counts@1": "IQM raw counts",
  "qhpc.ftqc-logical-result@1": "FTQC logical result",
};


function blueprintCountLabel(count: number): string {
  return `${count} blueprint${count === 1 ? "" : "s"}`;
}


function cloneGraph(nodes: ComposerNode[], edges: ComposerEdge[]): GraphSnapshot {
  return {
    nodes: structuredClone(nodes),
    edges: structuredClone(edges),
  };
}

function artifactLabel(artifactType: string): string {
  return ARTIFACT_LABELS[artifactType] ?? artifactType;
}


function artifactExtension(artifactType: string): string {
  if (artifactType === "qhpc.iqm-circuit@1") return "json";
  if (artifactType === "qhpc.ftqc-mlir@1") return "mlir";
  if (artifactType.includes("circuit")) return "qasm";
  if (
    artifactType.includes("hamiltonian") ||
    artifactType.includes("context") ||
    artifactType.includes("report") ||
    artifactType.includes("estimate") ||
    artifactType.includes("counts") ||
    artifactType.includes("metrics")
  ) {
    return "json";
  }
  return "txt";
}


function parameterLabel(value: string): string {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}


function displayPublishedParameter(name: string, value: ParameterValue): string {
  if (/(credential|secret|token|password|api[_-]?key)/i.test(name)) {
    return "Managed by the worker";
  }
  return typeof value === "string" ? value : JSON.stringify(value);
}


function workflowTarget(
  workflow: Workflow,
  capabilities: CapabilitySummary[],
): string {
  try {
    const defaultTarget = executionTarget(workflow, capabilities);
    const targets = new Set(
      workflow.spec.nodes.map(
        (node) => node.execution_target ?? defaultTarget,
      ),
    );
    return targets.size === 1 ? [...targets][0] : "Mixed targets";
  } catch {
    return "No compatible target";
  }
}


function toMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}


function timestamp(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}


function workflowForkMetadata(
  workflow: Workflow,
  workflows: PublishedWorkflow[],
): Workflow["metadata"] {
  const used = new Set(workflows.map((item) => item.id));
  const base = `${workflow.metadata.id}-copy`;
  let id = base;
  let suffix = 2;
  while (used.has(id)) {
    id = `${base}-${suffix}`;
    suffix += 1;
  }
  return {
    ...structuredClone(workflow.metadata),
    id,
    name: `${workflow.metadata.name} copy`,
    owner: "workbench-user",
    visibility: "internal",
  };
}


function operationSearchText(
  capability: CapabilitySummary,
  operation: OperationDefinition,
): string {
  return [
    capability.name,
    capability.id,
    operation.title,
    operation.id,
    operation.description ?? "",
    ...Object.values(operation.inputs).map((item) => item.artifact_type),
    ...Object.values(operation.outputs).map((item) => item.artifact_type),
  ]
    .join(" ")
    .toLowerCase();
}


function parameterValue(
  definition: ParameterDefinition,
  raw: string | boolean,
): ParameterValue {
  if (definition.type === "boolean") return Boolean(raw);
  if (definition.type === "integer") return Number.parseInt(String(raw), 10);
  if (definition.type === "number") return Number.parseFloat(String(raw));
  return String(raw);
}


function operationForNode(
  node: Extract<ComposerNode, { type: "operation" }>,
  capabilities: CapabilitySummary[],
): OperationDefinition | undefined {
  return capabilityOperationIndex(capabilities).get(
    `${node.data.operation.capability}@${node.data.operation.version}/${node.data.operation.operation}`,
  )?.operation;
}


function executionTarget(
  workflow: Workflow,
  capabilities: CapabilitySummary[],
): string {
  const index = capabilityOperationIndex(capabilities);
  const explicitTargets = workflow.spec.nodes.flatMap((node) =>
    node.execution_target ? [node.execution_target] : [],
  );
  const inheritedTargetSets = workflow.spec.nodes.flatMap((node) => {
    if (node.execution_target) return [];
    return [(
      index.get(
        `${node.operation.capability}@${node.operation.version}/${node.operation.operation}`,
      )?.operation.execution_targets ?? []
    )];
  });
  if (!inheritedTargetSets.length) {
    if (!explicitTargets.length) {
      throw new Error("Workflow operations do not declare an execution target.");
    }
    return preferredLocalTarget(explicitTargets) ?? explicitTargets[0];
  }
  if (inheritedTargetSets.some((targets) => !targets.length)) {
    throw new Error("Workflow operations do not declare a common execution target.");
  }
  const common = inheritedTargetSets
    .slice(1)
    .reduce(
      (values, targets) => values.filter((value) => targets.includes(value)),
      [...inheritedTargetSets[0]],
    );
  if (!common.length) {
    throw new Error("Workflow operations do not share an execution target.");
  }
  return preferredLocalTarget(common) ?? common[0];
}

function preferredLocalTarget(targets: string[]): string | undefined {
  return ["local-container", "local-development"].find((target) =>
    targets.includes(target),
  );
}

function useWorkflowPreflight(
  workflow: PublishedWorkflow | null | undefined,
  capabilities: CapabilitySummary[],
): PreflightDisplay {
  const [readiness, setReadiness] = useState<PreflightDisplay>({
    status: "idle",
    message: "Select a published workflow to inspect its execution requirements.",
    canQueue: false,
  });

  useEffect(() => {
    if (!workflow) {
      setReadiness({
        status: "idle",
        message: "Publish a workflow to inspect its execution requirements.",
        canQueue: false,
      });
      return;
    }
    let cancelled = false;
    setReadiness({
      status: "checking",
      message: "Checking published requirements against available workers.",
      canQueue: false,
    });
    const inspect = async () => {
      try {
        const target = executionTarget(workflow.definition, capabilities);
        const report = await composerApi.workflowPreflight(
          workflow.id,
          workflow.version,
          target,
        );
        if (!cancelled) setReadiness(workflowPreflightDisplay(report));
      } catch (error) {
        if (!cancelled) {
          setReadiness({
            status: "error",
            message: `Execution check failed: ${toMessage(error)}`,
            canQueue: false,
          });
        }
      }
    };
    void inspect();
    return () => {
      cancelled = true;
    };
  }, [capabilities, workflow]);

  return readiness;
}


function StatusMark({
  state,
  message,
}: {
  state: SaveState;
  message: string;
}): React.JSX.Element {
  const Icon =
    state === "saving"
      ? LoaderCircle
      : state === "error"
        ? CircleAlert
        : state === "saved"
          ? Check
          : Braces;
  return (
    <span className={`composer-save-state is-${state}`} title={message}>
      <Icon
        size={14}
        className={state === "saving" ? "composer-spin" : undefined}
        aria-hidden="true"
      />
      <span>{message}</span>
    </span>
  );
}


function IconButton({
  label,
  disabled,
  onClick,
  children,
}: {
  label: string;
  disabled?: boolean;
  onClick: () => void;
  children: React.ReactNode;
}): React.JSX.Element {
  return (
    <button
      type="button"
      className="composer-icon-button"
      aria-label={label}
      title={label}
      disabled={disabled}
      onClick={onClick}
    >
      {children}
    </button>
  );
}


function preflightStateLabel(
  state: PreflightDisplay["status"] | WorkflowPreflight["checks"][number]["state"],
): string {
  switch (state) {
    case "passed":
    case "ready":
      return "Passed";
    case "degraded":
      return "Advisory";
    case "warning":
      return "Warning";
    case "blocked":
    case "unavailable":
      return "Blocked";
    case "checking":
      return "Checking";
    case "unknown":
      return "Unknown";
    case "error":
      return "Unavailable";
    default:
      return "Not checked";
  }
}


function PreflightMark({
  state,
}: {
  state: PreflightDisplay["status"] | WorkflowPreflight["checks"][number]["state"];
}): React.JSX.Element {
  if (state === "ready" || state === "passed") {
    return <Check size={15} aria-hidden="true" />;
  }
  if (state === "checking") {
    return <LoaderCircle size={15} className="composer-spin" aria-hidden="true" />;
  }
  if (state === "idle") {
    return <Unplug size={15} aria-hidden="true" />;
  }
  return <CircleAlert size={15} aria-hidden="true" />;
}


function ExecutionPreflight({
  readiness,
  compact = false,
}: {
  readiness: PreflightDisplay;
  compact?: boolean;
}): React.JSX.Element {
  const report = readiness.report;
  return (
    <section
      className={`composer-preflight is-${readiness.status}${compact ? " is-compact" : ""}`}
      aria-label="Execution preflight"
    >
      <header className="composer-preflight-header">
        <span className="composer-preflight-mark">
          <PreflightMark state={readiness.status} />
        </span>
        <span>
          <strong>Execution preflight</strong>
          <small>{readiness.message}</small>
        </span>
        <b>{preflightStateLabel(readiness.status)}</b>
      </header>
      {report && (
        <>
          <dl className="composer-preflight-details">
            <div>
              <dt>Target</dt>
              <dd>{report.target}</dd>
            </div>
            <div>
              <dt>Requirements</dt>
              <dd>{report.requirements.length}</dd>
            </div>
            <div>
              <dt>Checked</dt>
              <dd>{timestamp(report.checked_at)}</dd>
            </div>
          </dl>
          <ul className="composer-preflight-checks">
            {report.checks.map((check) => (
              <li className={`is-${check.state}`} key={check.id}>
                <PreflightMark state={check.state} />
                <span>
                  <strong>{check.title}</strong>
                  <small>{check.detail}</small>
                  {check.remediation && (
                    <span className="composer-preflight-remediation">
                      <em>{check.remediation.label}</em>
                      <code>{check.remediation.command}</code>
                    </span>
                  )}
                </span>
                <b>{preflightStateLabel(check.state)}</b>
              </li>
            ))}
          </ul>
          <p className="composer-preflight-boundary">
            Credentials and endpoint values remain isolated with the worker.
          </p>
        </>
      )}
    </section>
  );
}


function ComposerSurface(): React.JSX.Element {
  const flow = useReactFlow<ComposerNode, ComposerEdge>();
  const [composerMode, setComposerMode] = useState<ComposerMode>(() => {
    const requested = new URLSearchParams(window.location.search).get("workflow");
    return requested && SCIENTIFIC_PATHS.some(
      (path) => path.workflowId === requested,
    )
      ? "guided"
      : "basic";
  });
  const [capabilities, setCapabilities] = useState<CapabilitySummary[]>([]);
  const [workflows, setWorkflows] = useState<PublishedWorkflow[]>([]);
  const [drafts, setDrafts] = useState<WorkflowDraft[]>([]);
  const [nodes, setNodes] = useState<ComposerNode[]>([]);
  const [edges, setEdges] = useState<ComposerEdge[]>([]);
  const [metadata, setMetadata] = useState<Workflow["metadata"]>(
    createEmptyWorkflow().metadata,
  );
  const [viewport, setViewport] = useState({ x: 0, y: 0, zoom: 1 });
  const [draft, setDraft] = useState<WorkflowDraft | null>(null);
  const [published, setPublished] = useState<PublishedWorkflow | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);
  const [libraryView, setLibraryView] = useState<LibraryView>("operations");
  const [libraryQuery, setLibraryQuery] = useState("");
  const [leftOpen, setLeftOpen] = useState(true);
  const [rightOpen, setRightOpen] = useState(true);
  const [loading, setLoading] = useState(true);
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [statusMessage, setStatusMessage] = useState("Unsaved draft");
  const [changeVersion, setChangeVersion] = useState(0);
  const [serverValidation, setServerValidation] =
    useState<DraftValidation | null>(null);
  const [runInputs, setRunInputs] = useState<Record<string, string>>({});
  const [runInputNames, setRunInputNames] = useState<Record<string, string>>({});
  const [publishing, setPublishing] = useState(false);
  const [queueing, setQueueing] = useState(false);
  const [lastRunId, setLastRunId] = useState<string | null>(null);
  const [guidedWorkflowId, setGuidedWorkflowId] = useState(() => {
    const requested = new URLSearchParams(window.location.search).get("workflow");
    return requested && SCIENTIFIC_PATHS.some(
      (path) => path.workflowId === requested,
    )
      ? requested
      : null;
  });
  const [guidedInputs, setGuidedInputs] = useState<
    Record<string, Record<string, string>>
  >({});
  const [guidedInputNames, setGuidedInputNames] = useState<
    Record<string, Record<string, string>>
  >({});
  const [guidedQueueing, setGuidedQueueing] = useState(false);
  const [guidedMessage, setGuidedMessage] = useState(
    "Select a path and provide its inputs",
  );
  const [guidedError, setGuidedError] = useState(false);
  const [guidedRunId, setGuidedRunId] = useState<string | null>(null);
  const [basicPathId, setBasicPathId] = useState<BasicPathId>(requestedBasicPathId);
  const [basicQueueing, setBasicQueueing] = useState(false);
  const [basicMessage, setBasicMessage] = useState(
    "Choose a circuit, then run the local simulation",
  );
  const [basicError, setBasicError] = useState(false);
  const [basicRunId, setBasicRunId] = useState<string | null>(null);

  const history = useRef<GraphSnapshot[]>([]);
  const future = useRef<GraphSnapshot[]>([]);
  const dragStart = useRef<GraphSnapshot | null>(null);
  const savePromise = useRef<Promise<WorkflowDraft> | null>(null);
  const latest = useRef<LatestDocument>({
    nodes: [],
    edges: [],
    metadata: createEmptyWorkflow().metadata,
    viewport: { x: 0, y: 0, zoom: 1 },
    changeVersion: 0,
  });
  const draftRef = useRef<WorkflowDraft | null>(null);

  useEffect(() => {
    latest.current = { nodes, edges, metadata, viewport, changeVersion };
  }, [nodes, edges, metadata, viewport, changeVersion]);

  useEffect(() => {
    draftRef.current = draft;
  }, [draft]);

  const guidedPaths = useMemo(
    () =>
      SCIENTIFIC_PATHS.map((definition) => ({
        definition,
        workflow: workflows.find(
          (workflow) => workflow.id === definition.workflowId,
        ),
      })),
    [workflows],
  );
  const basicPaths = useMemo<BasicPath[]>(
    () =>
      BASIC_PATHS.map((definition) => ({
        ...definition,
        workflow: workflows.find(
          (workflow) => workflow.id === definition.workflowId,
        ),
      })),
    [workflows],
  );
  const selectedBasicPath =
    basicPaths.find((path) => path.id === basicPathId) ?? basicPaths[0];
  const selectedBasicWorkflow = selectedBasicPath?.workflow;
  const selectedGuidedPath =
    (guidedWorkflowId
      ? guidedPaths.find(
          (item) => item.definition.workflowId === guidedWorkflowId,
        )
      : undefined) ??
    guidedPaths.find(
      (item) => item.definition.section === "start" && item.workflow,
    ) ??
    guidedPaths.find((item) => item.workflow) ??
    guidedPaths[0];
  const selectedGuidedWorkflow = selectedGuidedPath?.workflow;
  const guidedReadiness = useWorkflowPreflight(
    selectedGuidedWorkflow,
    capabilities,
  );
  const basicReadiness = useWorkflowPreflight(
    selectedBasicWorkflow,
    capabilities,
  );
  const advancedReadiness = useWorkflowPreflight(published, capabilities);

  const markChanged = useCallback(() => {
    setPublished(null);
    setServerValidation(null);
    setLastRunId(null);
    setSaveState("dirty");
    setStatusMessage("Unsaved changes");
    setChangeVersion((value) => value + 1);
  }, []);

  const replaceGraph = useCallback(
    (
      nextNodes: ComposerNode[],
      nextEdges: ComposerEdge[],
      recordHistory = true,
    ) => {
      if (recordHistory) {
        history.current.push(cloneGraph(nodes, edges));
        if (history.current.length > 80) history.current.shift();
        future.current = [];
      }
      setNodes(nextNodes);
      setEdges(nextEdges);
      setSelectedNodeId(null);
      setSelectedEdgeId(null);
      markChanged();
    },
    [edges, markChanged, nodes],
  );

  const resetDocument = useCallback(
    (
      workflow: Workflow,
      layout: WorkflowDraft["spec"]["layout"] | undefined,
      nextDraft: WorkflowDraft | null,
      nextPublished: PublishedWorkflow | null,
    ) => {
      const canvas = workflowToCanvas(workflow, layout, capabilities);
      setNodes(canvas.nodes);
      setEdges(canvas.edges);
      setMetadata(structuredClone(workflow.metadata));
      setViewport(canvas.viewport);
      setDraft(nextDraft);
      setPublished(nextPublished);
      setSelectedNodeId(null);
      setSelectedEdgeId(null);
      setServerValidation(null);
      setRunInputs({});
      setRunInputNames({});
      setLastRunId(null);
      history.current = [];
      future.current = [];
      setChangeVersion((value) => value + 1);
      setSaveState(nextDraft ? "saved" : "idle");
      setStatusMessage(
        nextDraft
          ? `Draft r${nextDraft.metadata.revision}`
          : nextPublished
            ? "Published workflow"
            : "Unsaved draft",
      );
      requestAnimationFrame(() => flow.fitView({ padding: 0.18, duration: 220 }));
    },
    [capabilities, flow],
  );

  useEffect(() => {
    let active = true;
    Promise.all([
      composerApi.capabilities(),
      composerApi.workflows(),
      composerApi.drafts(),
    ])
      .then(([nextCapabilities, nextWorkflows, nextDrafts]) => {
        if (!active) return;
        setCapabilities(nextCapabilities);
        setWorkflows(latestWorkflowVersions(nextWorkflows));
        setDrafts(nextDrafts);
        const blank = createEmptyWorkflow();
        setMetadata(blank.metadata);
        setStatusMessage("Unsaved draft");
      })
      .catch((error) => {
        if (!active) return;
        setSaveState("error");
        setStatusMessage(toMessage(error));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const saveNow = useCallback(async (): Promise<WorkflowDraft> => {
    if (savePromise.current) return savePromise.current;
    const snapshot = latest.current;
    const workflow = canvasToWorkflow(
      snapshot.metadata,
      snapshot.nodes,
      snapshot.edges,
    );
    const layout = layoutFromCanvas(snapshot.nodes, snapshot.viewport);
    const existing = draftRef.current;
    setSaveState("saving");
    setStatusMessage("Saving draft");
    const operation = existing
      ? composerApi.updateDraft(
          existing.metadata.id,
          existing.metadata.revision,
          workflow,
          layout,
        )
      : composerApi.createDraft(workflow, layout);
    savePromise.current = operation;
    try {
      const saved = await operation;
      draftRef.current = saved;
      setDraft(saved);
      setDrafts((items) => [
        saved,
        ...items.filter(
          (item) => item.metadata.id !== saved.metadata.id,
        ),
      ]);
      if (latest.current.changeVersion === snapshot.changeVersion) {
        setSaveState("saved");
        setStatusMessage(`Draft r${saved.metadata.revision}`);
      }
      return saved;
    } catch (error) {
      setSaveState("error");
      setStatusMessage(toMessage(error));
      throw error;
    } finally {
      savePromise.current = null;
    }
  }, []);

  useEffect(() => {
    if (!draft || saveState !== "dirty") return;
    const timer = window.setTimeout(() => {
      void saveNow().catch(() => undefined);
    }, 1400);
    return () => window.clearTimeout(timer);
  }, [changeVersion, draft, saveNow, saveState]);

  const newWorkflow = useCallback(() => {
    resetDocument(createEmptyWorkflow(), undefined, null, null);
    if (window.matchMedia("(max-width: 980px)").matches) setLeftOpen(false);
  }, [resetDocument]);

  const addInputArtifact = useCallback((
    input: ComposerInputDefinition,
    position?: { x: number; y: number },
  ) => {
    const inputNode = createWorkflowInputCanvasNode(
      input.name,
      input.artifactType,
      nodes,
      position,
    );
    replaceGraph([...nodes, inputNode], edges);
    setSelectedNodeId(inputNode.id);
    setLibraryView("operations");
    setLibraryQuery(input.artifactType);
    setLeftOpen(true);
    if (window.matchMedia("(max-width: 980px)").matches) setLeftOpen(false);
    setStatusMessage(
      `${input.title} added. Choose a compatible operation, then connect its input port.`,
    );
  }, [edges, nodes, replaceGraph]);

  const startWithCircuit = useCallback(() => {
    addInputArtifact(COMPOSER_INPUTS[0]);
  }, [addInputArtifact]);

  const openTemplate = useCallback(
    (item: PublishedWorkflow) => {
      const workflow = structuredClone(item.definition);
      workflow.metadata = workflowForkMetadata(workflow, workflows);
      resetDocument(workflow, undefined, null, null);
      if (window.matchMedia("(max-width: 980px)").matches) setLeftOpen(false);
    },
    [resetDocument, workflows],
  );

  const openDraft = useCallback(
    (item: WorkflowDraft) => {
      resetDocument(item.spec.workflow, item.spec.layout, item, null);
      if (window.matchMedia("(max-width: 980px)").matches) setLeftOpen(false);
    },
    [resetDocument],
  );

  const addOperation = useCallback(
    (
      capability: CapabilitySummary,
      operation: OperationDefinition,
      position?: { x: number; y: number },
    ) => {
      const id = uniqueNodeId(operation.id, nodes);
      const nextNode = createOperationCanvasNode(
        capability,
        operation,
        id,
        position ?? nextOperationPosition(nodes),
        nodes.filter((node) => node.data.kind === "operation").length,
      );
      replaceGraph([...nodes, nextNode], edges);
      setSelectedNodeId(nextNode.id);
      if (window.matchMedia("(max-width: 980px)").matches) setLeftOpen(false);
    },
    [edges, nodes, replaceGraph],
  );

  const onConnect = useCallback(
    (connection: Connection) => {
      const result = validateConnection(connection, nodes, edges);
      if (!result.valid) {
        setSaveState("error");
        setStatusMessage(result.message ?? "Invalid connection");
        return;
      }
      const edge = connectionEdge(connection, nodes, edges.length);
      replaceGraph(nodes, [...edges, edge]);
    },
    [edges, nodes, replaceGraph],
  );

  const onNodesChange = useCallback(
    (changes: NodeChange<ComposerNode>[]) => {
      setNodes((items) => applyNodeChanges(changes, items));
    },
    [],
  );

  const onEdgesChange = useCallback(
    (changes: EdgeChange<ComposerEdge>[]) => {
      setEdges((items) => applyEdgeChanges(changes, items));
    },
    [],
  );

  const onSelectionChange = useCallback(
    ({ nodes: selectedNodes, edges: selectedEdges }: OnSelectionChangeParams) => {
      setSelectedNodeId(selectedNodes[0]?.id ?? null);
      setSelectedEdgeId(selectedEdges[0]?.id ?? null);
    },
    [],
  );

  const undo = useCallback(() => {
    const prior = history.current.pop();
    if (!prior) return;
    future.current.push(cloneGraph(nodes, edges));
    setNodes(prior.nodes);
    setEdges(prior.edges);
    markChanged();
  }, [edges, markChanged, nodes]);

  const redo = useCallback(() => {
    const next = future.current.pop();
    if (!next) return;
    history.current.push(cloneGraph(nodes, edges));
    setNodes(next.nodes);
    setEdges(next.edges);
    markChanged();
  }, [edges, markChanged, nodes]);

  const deleteSelection = useCallback(() => {
    if (selectedNodeId) {
      replaceGraph(
        nodes.filter((node) => node.id !== selectedNodeId),
        edges.filter(
          (edge) =>
            edge.source !== selectedNodeId && edge.target !== selectedNodeId,
        ),
      );
      return;
    }
    if (selectedEdgeId) {
      replaceGraph(
        nodes,
        edges.filter((edge) => edge.id !== selectedEdgeId),
      );
    }
  }, [
    edges,
    nodes,
    replaceGraph,
    selectedEdgeId,
    selectedNodeId,
  ]);

  const selectedNode = nodes.find((node) => node.id === selectedNodeId);
  const clientIssues = useMemo(
    () => validateCanvas(nodes, edges),
    [edges, nodes],
  );

  const revealRunPanel = useCallback(() => {
    setRightOpen(true);
    setSelectedNodeId(null);
    setSelectedEdgeId(null);
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        document.getElementById("advanced-run-panel")?.scrollIntoView({
          behavior: "smooth",
          block: "start",
        });
      });
    });
  }, []);

  const validateDraft = useCallback(async () => {
    if (clientIssues.length) {
      setSaveState("error");
      setStatusMessage(
        `${clientIssues.length} composition issue${clientIssues.length === 1 ? "" : "s"}`,
      );
      return;
    }
    try {
      const saved = await saveNow();
      const result = await composerApi.validateDraft(
        saved.metadata.id,
        saved.metadata.revision,
      );
      setServerValidation(result);
      setSaveState(result.valid ? "saved" : "error");
      setStatusMessage(
        result.valid
          ? `Valid · ${result.digest?.slice(0, 15)}`
          : `${result.issues.length} contract issue${result.issues.length === 1 ? "" : "s"}`,
      );
    } catch (error) {
      setSaveState("error");
      setStatusMessage(toMessage(error));
    }
  }, [clientIssues.length, saveNow]);

  const publishDraft = useCallback(async () => {
    if (clientIssues.length) {
      setSaveState("error");
      setStatusMessage(
        `${clientIssues.length} composition issue${clientIssues.length === 1 ? "" : "s"}`,
      );
      return;
    }
    setPublishing(true);
    try {
      const saved = await saveNow();
      const validation = await composerApi.validateDraft(
        saved.metadata.id,
        saved.metadata.revision,
      );
      setServerValidation(validation);
      if (!validation.valid) {
        setSaveState("error");
        setStatusMessage(`${validation.issues.length} contract issues`);
        return;
      }
      const result = await composerApi.publishDraft(
        saved.metadata.id,
        saved.metadata.revision,
      );
      setPublished(result.workflow);
      setWorkflows((items) => latestWorkflowVersions([result.workflow, ...items]));
      setRunInputs((existing) =>
        Object.fromEntries(
          Object.keys(result.workflow.definition.spec.inputs).map((name) => [
            name,
            existing[name] ?? "",
          ]),
        ),
      );
      setRunInputNames((existing) =>
        Object.fromEntries(
          Object.keys(result.workflow.definition.spec.inputs)
            .filter((name) => Boolean(existing[name]))
            .map((name) => [name, existing[name]]),
        ),
      );
      setSaveState("saved");
      setStatusMessage(`Published · ${result.workflow.digest.slice(0, 15)}`);
      revealRunPanel();
    } catch (error) {
      setSaveState("error");
      setStatusMessage(toMessage(error));
    } finally {
      setPublishing(false);
    }
  }, [clientIssues.length, revealRunPanel, saveNow]);

  const submitPublishedWorkflow = useCallback(
    async (
      workflow: PublishedWorkflow,
      inputs: Record<string, string>,
      inputNames: Record<string, string> = {},
    ) => {
      const inputArtifacts: Record<string, string> = {};
      for (const [name, definition] of Object.entries(
        workflow.definition.spec.inputs,
      )) {
        const content = inputs[name]?.trim() ?? "";
        if ((definition.required ?? true) && !content) {
          throw new Error(`Input artifact ${name} is required.`);
        }
        if (!content) continue;
        const extension = artifactExtension(definition.artifact_type);
        const artifact = await composerApi.createArtifact(
          definition.artifact_type,
          inputNames[name] || `${name}.${extension}`,
          content,
        );
        inputArtifacts[name] = artifact.id;
      }
      return composerApi.submitRun(
        workflow.id,
        workflow.version,
        inputArtifacts,
        executionTarget(workflow.definition, capabilities),
      );
    },
    [capabilities],
  );

  const queueRun = useCallback(async () => {
    if (!published) return;
    setQueueing(true);
    try {
      const run = await submitPublishedWorkflow(
        published,
        runInputs,
        runInputNames,
      );
      setLastRunId(run.id);
      setStatusMessage(`Queued · ${run.id}`);
    } catch (error) {
      setSaveState("error");
      setStatusMessage(toMessage(error));
    } finally {
      setQueueing(false);
    }
  }, [published, runInputNames, runInputs, submitPublishedWorkflow]);

  const queueGuidedRun = useCallback(async () => {
    const workflow = selectedGuidedPath?.workflow;
    if (!workflow) {
      setGuidedError(true);
      setGuidedMessage("This published workflow is unavailable");
      return;
    }
    if (!guidedReadiness.canQueue) {
      setGuidedError(true);
      setGuidedMessage(guidedReadiness.message);
      return;
    }
    setGuidedQueueing(true);
    setGuidedError(false);
    setGuidedRunId(null);
    setGuidedMessage("Submitting workflow");
    try {
      const run = await submitPublishedWorkflow(
        workflow,
        guidedInputs[workflow.id] ?? {},
        guidedInputNames[workflow.id] ?? {},
      );
      setGuidedRunId(run.id);
      setGuidedMessage(`Queued · ${run.id}`);
    } catch (error) {
      setGuidedError(true);
      setGuidedMessage(toMessage(error));
    } finally {
      setGuidedQueueing(false);
    }
  }, [
    guidedInputNames,
    guidedInputs,
    guidedReadiness,
    selectedGuidedPath,
    submitPublishedWorkflow,
  ]);

  const queueBasicRun = useCallback(async () => {
    const workflow = selectedBasicPath?.workflow;
    if (!workflow) {
      setBasicError(true);
      setBasicMessage("This published workflow is unavailable");
      return;
    }
    if (!basicReadiness.canQueue) {
      setBasicError(true);
      setBasicMessage(basicReadiness.message);
      return;
    }
    setBasicQueueing(true);
    setBasicError(false);
    setBasicRunId(null);
    setBasicMessage(
      selectedBasicPath.id === "hardware"
        ? "Submitting hardware workflow"
        : "Submitting simulation",
    );
    try {
      const run = await submitPublishedWorkflow(
        workflow,
        guidedInputs[workflow.id] ?? {},
        guidedInputNames[workflow.id] ?? {},
      );
      setBasicRunId(run.id);
      setBasicMessage(`Queued · ${run.id}`);
    } catch (error) {
      setBasicError(true);
      setBasicMessage(toMessage(error));
    } finally {
      setBasicQueueing(false);
    }
  }, [
    basicReadiness,
    guidedInputNames,
    guidedInputs,
    selectedBasicPath,
    submitPublishedWorkflow,
  ]);

  const selectBasicPath = useCallback((pathId: BasicPathId) => {
    setBasicPathId(pathId);
    setBasicError(false);
    setBasicRunId(null);
    setBasicMessage(
      pathId === "hardware"
        ? "Add a circuit, then review target readiness before submitting"
        : "Choose a circuit, then run the local simulation",
    );
  }, []);

  const selectGuidedPath = useCallback((workflowId: string) => {
    setGuidedWorkflowId(workflowId);
    setGuidedError(false);
    setGuidedRunId(null);
    setGuidedMessage("Ready to configure");
  }, []);

  const updateGuidedInput = useCallback(
    (
      workflowId: string,
      name: string,
      content: string,
      sourceName?: string,
    ) => {
      setGuidedInputs((items) => ({
        ...items,
        [workflowId]: {
          ...(items[workflowId] ?? {}),
          [name]: content,
        },
      }));
      if (sourceName !== undefined) {
        setGuidedInputNames((items) => ({
          ...items,
          [workflowId]: {
            ...(items[workflowId] ?? {}),
            [name]: sourceName,
          },
        }));
      }
      setGuidedError(false);
      setGuidedRunId(null);
      setGuidedMessage(content.trim() ? "Input ready" : "Input required");
    },
    [],
  );

  const updateBasicInput = useCallback(
    (
      workflowId: string,
      name: string,
      content: string,
      sourceName?: string,
    ) => {
      updateGuidedInput(workflowId, name, content, sourceName);
      setBasicError(false);
      setBasicRunId(null);
      setBasicMessage(content.trim() ? "Circuit input ready" : "Circuit input required");
    },
    [updateGuidedInput],
  );

  const openWorkflowInAdvanced = useCallback(
    (
      workflow: PublishedWorkflow,
      inputs: Record<string, string> = {},
      inputNames: Record<string, string> = {},
    ) => {
      openTemplate(workflow);
      setRunInputs(inputs);
      setRunInputNames(inputNames);
      setLibraryView("templates");
      setComposerMode("advanced");
    },
    [openTemplate],
  );

  const openGuidedInAdvanced = useCallback(() => {
    if (!selectedGuidedPath?.workflow) return;
    openWorkflowInAdvanced(selectedGuidedPath.workflow);
  }, [openWorkflowInAdvanced, selectedGuidedPath]);

  const openBasicInGuided = useCallback(() => {
    if (!selectedBasicPath) return;
    setGuidedWorkflowId(selectedBasicPath.workflowId);
    setComposerMode("guided");
  }, [selectedBasicPath]);

  const deleteDraft = useCallback(async () => {
    if (!draft) return;
    try {
      await composerApi.deleteDraft(
        draft.metadata.id,
        draft.metadata.revision,
      );
      setDrafts((items) =>
        items.filter((item) => item.metadata.id !== draft.metadata.id),
      );
      newWorkflow();
    } catch (error) {
      setSaveState("error");
      setStatusMessage(toMessage(error));
    }
  }, [draft, newWorkflow]);

  const updateMetadata = useCallback(
    <K extends keyof Workflow["metadata"]>(
      key: K,
      value: Workflow["metadata"][K],
    ) => {
      setMetadata((item) => ({ ...item, [key]: value }));
      markChanged();
    },
    [markChanged],
  );

  const updateOperationNode = useCallback(
    (
      nodeId: string,
      update: (
        node: Extract<ComposerNode, { type: "operation" }>,
      ) => Extract<ComposerNode, { type: "operation" }>,
    ) => {
      history.current.push(cloneGraph(nodes, edges));
      future.current = [];
      setNodes((items) =>
        items.map((node) =>
          node.id === nodeId && node.type === "operation"
            ? update(node)
            : node,
        ),
      );
      markChanged();
    },
    [edges, markChanged, nodes],
  );

  const renameNode = useCallback(
    (oldId: string, proposed: string) => {
      const nextId = proposed.trim();
      if (
        nextId === oldId ||
        !/^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$/.test(nextId) ||
        nodes.some((node) => node.id === nextId)
      ) {
        return;
      }
      history.current.push(cloneGraph(nodes, edges));
      future.current = [];
      setNodes((items) =>
        items.map((node) => {
          if (node.id !== oldId || node.type !== "operation") return node;
          return {
            ...node,
            id: nextId,
            data: {
              ...node.data,
              originalNode: { ...node.data.originalNode, id: nextId },
            },
          };
        }),
      );
      setEdges((items) =>
        items.map((edge) => ({
          ...edge,
          source: edge.source === oldId ? nextId : edge.source,
          target: edge.target === oldId ? nextId : edge.target,
        })),
      );
      setSelectedNodeId(nextId);
      markChanged();
    },
    [edges, markChanged, nodes],
  );

  const exposePort = useCallback(
    (
      operationNode: Extract<ComposerNode, { type: "operation" }>,
      port: string,
      kind: "workflow-input" | "workflow-output",
    ) => {
      const created = createBoundaryForPort(
        operationNode,
        port,
        kind,
        nodes,
        edges.length,
      );
      replaceGraph(
        [...nodes, created.node],
        [...edges, created.edge],
      );
    },
    [edges, nodes, replaceGraph],
  );

  const filteredOperations = useMemo(() => {
    const query = libraryQuery.trim().toLowerCase();
    return capabilities.flatMap((capability) =>
      capability.operations
        .filter(
          (operation) =>
            !query || operationSearchText(capability, operation).includes(query),
        )
        .map((operation) => ({ capability, operation })),
    );
  }, [capabilities, libraryQuery]);

  const filteredInputs = useMemo(() => {
    const query = libraryQuery.trim().toLowerCase();
    return COMPOSER_INPUTS.filter((input) =>
      !query || [input.title, input.detail, input.name]
        .join(" ")
        .toLowerCase()
        .includes(query),
    );
  }, [libraryQuery]);

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      const inputId = event.dataTransfer.getData("application/qhpc-input");
      if (inputId) {
        const input = COMPOSER_INPUTS.find((item) => item.id === inputId);
        if (!input) return;
        addInputArtifact(
          input,
          flow.screenToFlowPosition({ x: event.clientX, y: event.clientY }),
        );
        return;
      }
      const key = event.dataTransfer.getData("application/qhpc-operation");
      if (!key) return;
      const [capabilityId, version, operationId] = key.split("\u0000");
      const capability = capabilities.find(
        (item) => item.id === capabilityId && item.version === version,
      );
      const operation = capability?.operations.find(
        (item) => item.id === operationId,
      );
      if (!capability || !operation) return;
      addOperation(
        capability,
        operation,
        flow.screenToFlowPosition({ x: event.clientX, y: event.clientY }),
      );
    },
    [addInputArtifact, addOperation, capabilities, flow],
  );

  const showInspector = rightOpen && selectedNode?.type === "operation";

  if (loading) {
    return (
      <div className="composer-loading">
        <LoaderCircle size={18} className="composer-spin" aria-hidden="true" />
        <span>Loading registry</span>
      </div>
    );
  }

  return (
    <section
      className={`qhpc-composer is-${composerMode}`}
      aria-label="Workflow composer"
    >
      <header className="composer-modebar">
        <div
          className="composer-mode-switch"
          role="tablist"
          aria-label="Composer mode"
        >
          <button
            type="button"
            role="tab"
            aria-selected={composerMode === "basic"}
            className={composerMode === "basic" ? "is-active" : ""}
            onClick={() => setComposerMode("basic")}
          >
            Basic
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={composerMode === "guided"}
            className={composerMode === "guided" ? "is-active" : ""}
            onClick={() => setComposerMode("guided")}
          >
            Guided
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={composerMode === "advanced"}
            className={composerMode === "advanced" ? "is-active" : ""}
            onClick={() => setComposerMode("advanced")}
          >
            Advanced
          </button>
        </div>
        <span className="composer-mode-context">
          <strong>
            {composerMode === "basic"
              ? "Build with basic blocks"
              : composerMode === "guided"
                ? "Start with a goal"
                : "Workflow graph"}
          </strong>
          <small>
            {composerMode === "basic"
              ? "3 starter paths · inspectable workflow details"
              : composerMode === "guided"
                ? `${guidedPaths.filter((item) => item.workflow).length} runnable workflows · ${blueprintCountLabel(guidedPaths.filter((item) => item.definition.blueprint).length)}`
                : `${nodes.filter((node) => node.type === "operation").length} operations`}
          </small>
        </span>
      </header>

      {composerMode === "basic" ? (
        <BasicComposer
          paths={basicPaths}
          selectedPath={selectedBasicPath}
          capabilities={capabilities}
          inputs={
            selectedBasicWorkflow
              ? guidedInputs[selectedBasicWorkflow.id] ?? {}
              : {}
          }
          inputNames={
            selectedBasicWorkflow
              ? guidedInputNames[selectedBasicWorkflow.id] ?? {}
              : {}
          }
          queueing={basicQueueing}
          statusMessage={basicMessage}
          hasError={basicError}
          lastRunId={basicRunId}
          readiness={basicReadiness}
          onSelect={selectBasicPath}
          onInput={updateBasicInput}
          onQueue={() => void queueBasicRun()}
          onOpenGuided={openBasicInGuided}
          onOpenAdvanced={() => {
            if (selectedBasicWorkflow) {
              openWorkflowInAdvanced(
                selectedBasicWorkflow,
                guidedInputs[selectedBasicWorkflow.id] ?? {},
                guidedInputNames[selectedBasicWorkflow.id] ?? {},
              );
            }
          }}
        />
      ) : composerMode === "guided" ? (
        <GuidedComposer
          paths={guidedPaths}
          selectedPath={selectedGuidedPath}
          capabilities={capabilities}
          inputs={
            selectedGuidedPath?.workflow
              ? guidedInputs[selectedGuidedPath.workflow.id] ?? {}
              : {}
          }
          inputNames={
            selectedGuidedPath?.workflow
              ? guidedInputNames[selectedGuidedPath.workflow.id] ?? {}
              : {}
          }
          queueing={guidedQueueing}
          statusMessage={guidedMessage}
          hasError={guidedError}
          lastRunId={guidedRunId}
          readiness={guidedReadiness}
          onSelect={selectGuidedPath}
          onInput={updateGuidedInput}
          onQueue={() => void queueGuidedRun()}
          onOpenAdvanced={openGuidedInAdvanced}
        />
      ) : (
        <>
          <header className="composer-commandbar">
        <div className="composer-document">
          <IconButton
            label={leftOpen ? "Hide library" : "Show library"}
            onClick={() => setLeftOpen((value) => !value)}
          >
            <PanelLeft size={16} />
          </IconButton>
          <span>
            <strong>{metadata.name}</strong>
            <small>
              {metadata.id}@{metadata.version}
            </small>
          </span>
        </div>
        <div className="composer-command-group">
          <IconButton label="New workflow" onClick={newWorkflow}>
            <FilePlus2 size={16} />
          </IconButton>
          <IconButton
            label="Undo"
            disabled={!history.current.length}
            onClick={undo}
          >
            <Undo2 size={16} />
          </IconButton>
          <IconButton
            label="Redo"
            disabled={!future.current.length}
            onClick={redo}
          >
            <Redo2 size={16} />
          </IconButton>
          <IconButton
            label="Delete selection"
            disabled={!selectedNodeId && !selectedEdgeId}
            onClick={deleteSelection}
          >
            <Trash2 size={16} />
          </IconButton>
          <IconButton
            label="Fit workflow"
            onClick={() => flow.fitView({ padding: 0.18, duration: 220 })}
          >
            <Maximize2 size={16} />
          </IconButton>
        </div>
        <div className="composer-primary-actions">
          <StatusMark state={saveState} message={statusMessage} />
          <button
            type="button"
            className="composer-button is-secondary"
            onClick={() => void saveNow()}
            disabled={saveState === "saving"}
          >
            <Save size={14} aria-hidden="true" />
            Save
          </button>
          <button
            type="button"
            className="composer-button is-secondary"
            onClick={() => void validateDraft()}
            disabled={saveState === "saving"}
          >
            <FlaskConical size={14} aria-hidden="true" />
            Validate
          </button>
          {published ? (
            <button
              type="button"
              className="composer-button is-primary"
              onClick={revealRunPanel}
            >
              <Play size={14} aria-hidden="true" />
              Run workflow
            </button>
          ) : (
            <button
              type="button"
              className="composer-button is-primary"
              onClick={() => void publishDraft()}
              disabled={publishing || saveState === "saving" || !nodes.length}
            >
              {publishing ? (
                <LoaderCircle
                  size={14}
                  className="composer-spin"
                  aria-hidden="true"
                />
              ) : (
                <CloudUpload size={14} aria-hidden="true" />
              )}
              {publishing ? "Publishing" : "Publish to run"}
            </button>
          )}
          <IconButton
            label={rightOpen ? "Hide inspector" : "Show inspector"}
            onClick={() => setRightOpen((value) => !value)}
          >
            <PanelRight size={16} />
          </IconButton>
        </div>
          </header>

          <div
            className={`composer-grid${leftOpen ? "" : " without-library"}${rightOpen ? "" : " without-inspector"}`}
          >
        {leftOpen && (
          <aside className="composer-library" aria-label="Workflow library">
            <div className="composer-tabs" role="tablist">
              {(
                [
                  ["operations", "Operations"],
                  ["templates", "Templates"],
                  ["drafts", "Drafts"],
                ] as const
              ).map(([id, label]) => (
                <button
                  type="button"
                  role="tab"
                  aria-selected={libraryView === id}
                  className={libraryView === id ? "is-active" : ""}
                  onClick={() => setLibraryView(id)}
                  key={id}
                >
                  {label}
                </button>
              ))}
            </div>
            {libraryView === "operations" && (
              <label className="composer-search">
                <Search size={14} aria-hidden="true" />
                <input
                  type="search"
                  value={libraryQuery}
                  onChange={(event) => setLibraryQuery(event.target.value)}
                  placeholder="Filter operations"
                  aria-label="Filter operations"
                />
              </label>
            )}
            <div className="composer-library-list">
              {libraryView === "operations" && Boolean(filteredInputs.length) && (
                <section
                  className="composer-library-section"
                  aria-label="Input artifacts"
                >
                  <div className="composer-library-section-heading">
                    <strong>Input artifacts</strong>
                    <small>Add a workflow entry block</small>
                  </div>
                  {filteredInputs.map((input) => (
                    <button
                      type="button"
                      className="composer-library-item is-input-artifact"
                      key={input.id}
                      draggable
                      onDragStart={(event) => {
                        event.dataTransfer.effectAllowed = "copy";
                        event.dataTransfer.setData(
                          "application/qhpc-input",
                          input.id,
                        );
                      }}
                      onClick={() => addInputArtifact(input)}
                    >
                      <span
                        className="composer-item-glyph is-input"
                        aria-hidden="true"
                      >
                        <FileUp size={14} />
                      </span>
                      <span>
                        <strong>{input.title}</strong>
                        <small>{input.detail}</small>
                      </span>
                      <ChevronRight size={14} aria-hidden="true" />
                    </button>
                  ))}
                </section>
              )}
              {libraryView === "operations" &&
                filteredOperations.map(({ capability, operation }) => (
                  <button
                    type="button"
                    className="composer-library-item"
                    key={`${capability.id}/${operation.id}`}
                    draggable
                    onDragStart={(event) => {
                      event.dataTransfer.effectAllowed = "copy";
                      event.dataTransfer.setData(
                        "application/qhpc-operation",
                        [
                          capability.id,
                          capability.version,
                          operation.id,
                        ].join("\u0000"),
                      );
                    }}
                    onClick={() => addOperation(capability, operation)}
                  >
                    <span className="composer-item-glyph" aria-hidden="true">
                      {capability.id.slice(0, 2).toUpperCase()}
                    </span>
                    <span>
                      <strong>{operation.title}</strong>
                      <small>
                        {capability.id} · {Object.keys(operation.inputs).length} in
                        {" / "}
                        {Object.keys(operation.outputs).length} out
                      </small>
                    </span>
                    <ChevronRight size={14} aria-hidden="true" />
                  </button>
                ))}
              {libraryView === "templates" &&
                workflows.map((item) => (
                  <button
                    type="button"
                    className="composer-library-item"
                    key={`${item.id}@${item.version}`}
                    onClick={() => openTemplate(item)}
                  >
                    <span className="composer-item-glyph is-template" aria-hidden="true">
                      <GitFork size={14} />
                    </span>
                    <span>
                      <strong>{item.definition.metadata.name}</strong>
                      <small>
                        {item.definition.spec.nodes.length} nodes · {item.version}
                      </small>
                    </span>
                    <ChevronRight size={14} aria-hidden="true" />
                  </button>
                ))}
              {libraryView === "drafts" &&
                drafts.map((item) => (
                  <button
                    type="button"
                    className={`composer-library-item${draft?.metadata.id === item.metadata.id ? " is-current" : ""}`}
                    key={item.metadata.id}
                    onClick={() => openDraft(item)}
                  >
                    <span className="composer-item-glyph is-draft" aria-hidden="true">
                      <FolderOpen size={14} />
                    </span>
                    <span>
                      <strong>{item.metadata.name}</strong>
                      <small>
                        r{item.metadata.revision} · {timestamp(item.metadata.updated_at)}
                      </small>
                    </span>
                    <ChevronRight size={14} aria-hidden="true" />
                  </button>
                ))}
              {libraryView === "operations" && !filteredInputs.length && !filteredOperations.length && (
                <p className="composer-empty-list">No matching operations</p>
              )}
              {libraryView === "templates" && !workflows.length && (
                <p className="composer-empty-list">No published workflows</p>
              )}
              {libraryView === "drafts" && !drafts.length && (
                <p className="composer-empty-list">No saved drafts</p>
              )}
            </div>
          </aside>
        )}

        <div
          className="composer-canvas"
          onDrop={onDrop}
          onDragOver={(event) => {
            event.preventDefault();
            event.dataTransfer.dropEffect = "copy";
          }}
        >
          <ReactFlow<ComposerNode, ComposerEdge>
            nodes={nodes}
            edges={edges}
            nodeTypes={NODE_TYPES}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            isValidConnection={(candidate) =>
              validateConnection(
                {
                  source: candidate.source,
                  sourceHandle: candidate.sourceHandle ?? null,
                  target: candidate.target,
                  targetHandle: candidate.targetHandle ?? null,
                },
                nodes,
                edges,
              ).valid
            }
            onSelectionChange={onSelectionChange}
            onNodeDragStart={() => {
              dragStart.current = cloneGraph(nodes, edges);
            }}
            onNodeDragStop={() => {
              if (dragStart.current) {
                history.current.push(dragStart.current);
                future.current = [];
                dragStart.current = null;
                markChanged();
              }
            }}
            onMoveEnd={(_, nextViewport) => {
              if (
                nextViewport.x !== viewport.x ||
                nextViewport.y !== viewport.y ||
                nextViewport.zoom !== viewport.zoom
              ) {
                setViewport(nextViewport);
                markChanged();
              }
            }}
            defaultViewport={viewport}
            minZoom={0.25}
            maxZoom={2}
            fitViewOptions={{ padding: 0.12, maxZoom: 1 }}
            deleteKeyCode={null}
            multiSelectionKeyCode="Shift"
            fitView
            proOptions={{ hideAttribution: true }}
          >
            <Background
              variant={BackgroundVariant.Dots}
              gap={18}
              size={1}
              color="var(--line-strong)"
            />
          </ReactFlow>
          {!nodes.length && (
            <div className="composer-canvas-empty">
              <Braces size={20} aria-hidden="true" />
              <strong>Start with an input or a tool</strong>
              <p>
                Add an input block—such as a circuit or Hamiltonian—then connect
                it to a compatible operation from the library.
              </p>
              <div className="composer-canvas-empty-actions">
                <button
                  type="button"
                  className="composer-button is-primary"
                  onClick={startWithCircuit}
                >
                  <FileCode2 size={14} aria-hidden="true" />
                  Add Input Circuit
                </button>
                <button
                  type="button"
                  className="composer-button is-secondary"
                  onClick={() => setComposerMode("guided")}
                >
                  <GitFork size={14} aria-hidden="true" />
                  Use a guided example
                </button>
              </div>
            </div>
          )}
          <div className="composer-validation-strip">
            <span className={clientIssues.length ? "has-issues" : "is-valid"}>
              {clientIssues.length ? (
                <CircleAlert size={13} aria-hidden="true" />
              ) : (
                <Check size={13} aria-hidden="true" />
              )}
              {clientIssues.length
                ? `${clientIssues.length} local issue${clientIssues.length === 1 ? "" : "s"}`
                : `${nodes.filter((node) => node.type === "operation").length} operations · ${edges.length} connections`}
            </span>
            {draft && <span>revision {draft.metadata.revision}</span>}
          </div>
        </div>

        {rightOpen && (
          <aside className="composer-inspector-panel" aria-label="Workflow inspector">
            <div className="composer-inspector-header">
              <span>
                <small>{showInspector ? "OPERATION" : "WORKFLOW"}</small>
                <strong>
                  {showInspector && selectedNode
                    ? selectedNode.id
                    : metadata.name}
                </strong>
              </span>
              {selectedNodeId && (
                <IconButton
                  label="Clear selection"
                  onClick={() => {
                    setSelectedNodeId(null);
                    setSelectedEdgeId(null);
                    flow.setNodes((items) =>
                      items.map((node) => ({ ...node, selected: false })),
                    );
                  }}
                >
                  <X size={15} />
                </IconButton>
              )}
            </div>
            {showInspector && selectedNode?.type === "operation" ? (
              <OperationInspector
                node={selectedNode}
                operation={operationForNode(selectedNode, capabilities)}
                edges={edges}
                onRename={(nextId) => renameNode(selectedNode.id, nextId)}
                onParameter={(name, value) =>
                  updateOperationNode(selectedNode.id, (node) => ({
                    ...node,
                    data: {
                      ...node.data,
                      parameters: { ...node.data.parameters, [name]: value },
                    },
                  }))
                }
                onExpose={(port, kind) =>
                  exposePort(selectedNode, port, kind)
                }
              />
            ) : (
              <WorkflowInspector
                metadata={metadata}
                draft={draft}
                published={published}
                validation={serverValidation}
                clientIssues={clientIssues}
                runInputs={runInputs}
                preflight={advancedReadiness}
                publishing={publishing}
                queueing={queueing}
                lastRunId={lastRunId}
                onMetadata={updateMetadata}
                onRunInput={(name, value) =>
                  setRunInputs((items) => ({ ...items, [name]: value }))
                }
                onPublish={() => void publishDraft()}
                onQueue={() => void queueRun()}
                onDeleteDraft={() => void deleteDraft()}
              />
            )}
          </aside>
        )}
          </div>
        </>
      )}
    </section>
  );
}


function IncubationBlueprintView({
  definition,
}: {
  definition: ScientificPathDefinition & { blueprint: IncubationBlueprint };
}): React.JSX.Element {
  const { blueprint } = definition;

  return (
    <>
      <header className="composer-guided-header is-blueprint">
        <span className="composer-guided-glyph" aria-hidden="true">
          {definition.code}
        </span>
        <span>
          <small>{definition.shortName}</small>
          <h2>{blueprint.name}</h2>
          <p>{blueprint.description}</p>
        </span>
        <dl>
          {blueprint.metrics.map((metric) => (
            <Fragment key={metric.label}>
              <dt>{metric.label}</dt>
              <dd>{metric.value}</dd>
            </Fragment>
          ))}
        </dl>
      </header>

      <div className="composer-guided-body">
        <section className="composer-guided-section">
          <h3>{blueprint.pipelineTitle}</h3>
          <ol className="composer-guided-pipeline composer-blueprint-pipeline">
            {blueprint.stages.map((stage, index) => (
              <li key={stage.name}>
                <span className="composer-pipeline-sequence">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <span>
                  <strong>{stage.name}</strong>
                  <small>{stage.tool}</small>
                  <small>{stage.detail}</small>
                </span>
                <span className="composer-blueprint-handoff">
                  <span
                    className={`composer-blueprint-status is-${stage.status.toLowerCase().replaceAll(" ", "-")}`}
                  >
                    {stage.status}
                  </span>
                  <small>{stage.handoff}</small>
                </span>
              </li>
            ))}
          </ol>
        </section>

        <section className="composer-guided-section">
          <h3>{blueprint.factsTitle}</h3>
          <dl className="composer-blueprint-facts">
            {blueprint.facts.map((fact) => (
              <div key={fact.label}>
                <dt>{fact.label}</dt>
                <dd>{fact.value}</dd>
              </div>
            ))}
          </dl>
          {blueprint.evidenceTable && (
            <>
              <div
                className="composer-blueprint-table-wrap"
                role="region"
                aria-label={blueprint.evidenceTable.ariaLabel}
                tabIndex={0}
              >
                <table
                  className={`composer-blueprint-table is-${blueprint.evidenceTable.noteTone}`}
                >
                  <thead>
                    <tr>
                      {blueprint.evidenceTable.columns.map((column) => (
                        <th key={column}>{column}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {blueprint.evidenceTable.rows.map((row, rowIndex) => (
                      <tr key={`${row[0]}-${rowIndex}`}>
                        {row.map((value, columnIndex) => (
                          <td
                            data-label={
                              blueprint.evidenceTable?.columns[columnIndex]
                            }
                            key={`${columnIndex}-${value}`}
                          >
                            {value}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p
                className={`composer-blueprint-acceptance is-${blueprint.evidenceTable.noteTone}`}
              >
                {blueprint.evidenceTable.note}
              </p>
            </>
          )}
        </section>

        <section className="composer-guided-section">
          <h3>{blueprint.artifactsTitle}</h3>
          <div className="composer-guided-outputs composer-blueprint-artifacts">
            {blueprint.artifacts.map((artifact, index) => (
              <div key={`${artifact.reference}-${index}`}>
                <FileCode2 size={15} aria-hidden="true" />
                <span>
                  <strong>{artifact.name}</strong>
                  <small>{artifact.reference}</small>
                  <small>{artifact.status}</small>
                </span>
              </div>
            ))}
          </div>
        </section>

        <section className="composer-guided-section">
          <h3>{blueprint.gatesTitle}</h3>
          <ul className="composer-blueprint-gates">
            {blueprint.remainingGates.map((gate) => (
              <li key={gate}>{gate}</li>
            ))}
          </ul>
          <p
            className={`composer-blueprint-callout is-${blueprint.callout.tone}`}
          >
            {blueprint.callout.tone === "warning" ? (
              <CircleAlert size={15} aria-hidden="true" />
            ) : (
              <FlaskConical size={15} aria-hidden="true" />
            )}
            <span>
              <strong>{blueprint.callout.title}</strong>{" "}
              {blueprint.callout.detail}
            </span>
          </p>
        </section>
      </div>

      <footer className="composer-guided-actions">
        <span className="composer-guided-status is-blueprint">
          <FlaskConical size={14} aria-hidden="true" />
          <span>{blueprint.footerStatus}</span>
        </span>
        <div>
          <a
            className="composer-button is-secondary"
            href={blueprint.evidenceAction.href}
          >
            {blueprint.evidenceAction.label}
          </a>
          <button
            type="button"
            className="composer-button is-primary"
            disabled
            title={blueprint.runDisabledTitle}
          >
            <Play size={14} aria-hidden="true" />
            Run unavailable
          </button>
        </div>
      </footer>
    </>
  );
}


function BasicComposer({
  paths,
  selectedPath,
  capabilities,
  inputs,
  inputNames,
  queueing,
  statusMessage,
  hasError,
  lastRunId,
  readiness,
  onSelect,
  onInput,
  onQueue,
  onOpenGuided,
  onOpenAdvanced,
}: {
  paths: BasicPath[];
  selectedPath: BasicPath | undefined;
  capabilities: CapabilitySummary[];
  inputs: Record<string, string>;
  inputNames: Record<string, string>;
  queueing: boolean;
  statusMessage: string;
  hasError: boolean;
  lastRunId: string | null;
  readiness: PreflightDisplay;
  onSelect: (pathId: BasicPathId) => void;
  onInput: (
    workflowId: string,
    name: string,
    content: string,
    sourceName?: string,
  ) => void;
  onQueue: () => void;
  onOpenGuided: () => void;
  onOpenAdvanced: () => void;
}): React.JSX.Element {
  const [fileError, setFileError] = useState<string | null>(null);
  const [blockQuery, setBlockQuery] = useState("");
  const [selectedBlockIndex, setSelectedBlockIndex] = useState(0);
  const [canvasDropActive, setCanvasDropActive] = useState(false);
  const [intentPlan, setIntentPlan] = useState<BasicIntentId[]>(
    () => selectedPath?.blocks.map((block) => block.id) ?? [],
  );
  const normalizedBlockQuery = blockQuery.trim().toLocaleLowerCase();
  const visiblePaths = paths.filter((path) => {
    if (!normalizedBlockQuery) return true;
    return [
      path.title,
      path.detail,
      path.actionLabel,
      ...path.blocks.flatMap((block) => [block.title, block.detail]),
    ].some((value) => value.toLocaleLowerCase().includes(normalizedBlockQuery));
  });
  const visibleIntentBlocks = BASIC_INTENT_BLOCKS.filter((block) =>
    !normalizedBlockQuery || [block.title, block.detail].some(
      (value) => value.toLocaleLowerCase().includes(normalizedBlockQuery),
    ),
  );
  const matchingPaths = paths.filter((path) =>
    intentPlan.every((id, index) => path.blocks[index]?.id === id),
  );
  const completePath = matchingPaths.find(
    (path) => path.blocks.length === intentPlan.length,
  );
  const planPath = completePath ?? (
    matchingPaths.length === 1 ? matchingPaths[0] : undefined
  );
  const workflow = planPath?.workflow;
  const isPlanExecutable = Boolean(completePath && workflow);
  const nextIntentIds = new Set(
    matchingPaths
      .map((path) => path.blocks[intentPlan.length]?.id)
      .filter((id): id is BasicIntentId => Boolean(id)),
  );
  const activeBlocks = intentPlan
    .map(
      (id) => planPath?.blocks.find((block) => block.id === id)
        ?? BASIC_INTENT_BY_ID.get(id),
    )
    .filter((block): block is BasicIntentBlock => Boolean(block));
  const workflowInputs = workflow
    ? Object.entries(workflow.definition.spec.inputs)
    : [];
  const [inputName, inputDefinition] = workflowInputs[0] ?? [];
  const inputReady =
    isPlanExecutable &&
    !!workflow &&
    workflowInputs.every(
      ([name, input]) =>
        !(input.required ?? true) || Boolean(inputs[name]?.trim()),
    );
  const selectedBlock = activeBlocks[selectedBlockIndex] ?? activeBlocks[0];
  const selectedPathBlock = planPath?.blocks.find(
    (block) => block.id === selectedBlock?.id,
  );
  const selectedNodes = workflow && selectedPathBlock?.nodeIds
    ? workflow.definition.spec.nodes.filter((node) =>
        selectedPathBlock.nodeIds?.includes(node.id),
      )
    : [];
  const blockInputArtifacts = new Set<string>();
  const blockOutputArtifacts = new Set<string>();
  if (workflow && selectedBlock) {
    if (selectedBlock.kind === "input") {
      workflowInputs.forEach(([, input]) =>
        blockInputArtifacts.add(input.artifact_type),
      );
    } else if (selectedBlock.kind === "output") {
      Object.values(workflow.definition.spec.outputs).forEach((output) =>
        blockOutputArtifacts.add(output.artifact_type),
      );
    } else {
      selectedNodes.forEach((node) => {
        Object.values(workflow.definition.spec.inputs)
          .filter((input) => input.to.node === node.id)
          .forEach((input) => blockInputArtifacts.add(input.artifact_type));
        workflow.definition.spec.edges
          .filter((edge) => edge.to.node === node.id)
          .forEach((edge) => blockInputArtifacts.add(edge.to.artifact_type));
        workflow.definition.spec.edges
          .filter((edge) => edge.from.node === node.id)
          .forEach((edge) => blockOutputArtifacts.add(edge.from.artifact_type));
        Object.values(workflow.definition.spec.outputs)
          .filter((output) => output.from.node === node.id)
          .forEach((output) => blockOutputArtifacts.add(output.artifact_type));
      });
    }
  }
  const selectedBlockTarget = selectedNodes
    .map((node) => node.execution_target)
    .find(Boolean) ?? readiness.report?.target ?? "Published target";
  const selectedBlockParameters = selectedNodes.flatMap((node) =>
    Object.entries(node.parameters).map(([name, value]) => ({
      nodeId: node.id,
      name,
      value,
    })),
  );
  const transformationEvidence = planPath?.id === "transform" && workflow
    ? workflow.definition.spec.nodes.flatMap((node) => {
      const capability = capabilities.find(
        (item) =>
          item.id === node.operation.capability &&
          item.version === node.operation.version,
      );
      const operation = capability?.operations.find(
        (item) => item.id === node.operation.operation,
      );
      if (node.operation.capability !== "qasmtrans-transpiler" || !operation) {
        return [];
      }
      const outputs = Object.entries(workflow.definition.spec.outputs).filter(
        ([, output]) => output.from.node === node.id,
      );
      return [{
        node,
        capability,
        operation,
        target: node.execution_target ?? operation.execution_targets.join(", "),
        outputs,
        limitations: capability?.guidance?.limitations ?? [],
      }];
    })
    : [];

  useEffect(() => {
    setSelectedBlockIndex((index) => Math.min(index, Math.max(0, activeBlocks.length - 1)));
  }, [activeBlocks.length]);

  const choosePath = (pathId: BasicPathId) => {
    setFileError(null);
    const path = paths.find((item) => item.id === pathId);
    if (path) setIntentPlan(path.blocks.map((block) => block.id));
    onSelect(pathId);
  };

  const addIntentBlock = (id: BasicIntentId) => {
    if (!nextIntentIds.has(id)) return;
    const nextPlan = [...intentPlan, id];
    const nextMatches = paths.filter((path) =>
      nextPlan.every((intent, index) => path.blocks[index]?.id === intent),
    );
    const nextPath = nextMatches.find(
      (path) => path.blocks.length === nextPlan.length,
    ) ?? (nextMatches.length === 1 ? nextMatches[0] : undefined);
    setFileError(null);
    setIntentPlan(nextPlan);
    if (nextPath) onSelect(nextPath.id);
  };

  const resetIntentPlan = () => {
    setFileError(null);
    setSelectedBlockIndex(0);
    setIntentPlan([]);
  };

  const canDropBasicItem = (types: readonly string[]) =>
    types.includes("application/x-eqo-basic-path") ||
    types.includes("application/x-eqo-basic-intent");

  const flowCanvas = (
    <section
      className={`composer-basic-flow-section${canvasDropActive ? " is-drop-target" : ""}`}
      aria-labelledby="basic-canvas-title"
      aria-describedby="basic-canvas-hint"
      onDragEnter={(event) => {
        if (canDropBasicItem(event.dataTransfer.types)) {
          event.preventDefault();
          setCanvasDropActive(true);
        }
      }}
      onDragOver={(event) => {
        if (canDropBasicItem(event.dataTransfer.types)) {
          event.preventDefault();
          event.dataTransfer.dropEffect = "copy";
        }
      }}
      onDragLeave={(event) => {
        if (event.currentTarget === event.target) setCanvasDropActive(false);
      }}
      onDrop={(event) => {
        event.preventDefault();
        setCanvasDropActive(false);
        const pathId = event.dataTransfer.getData("application/x-eqo-basic-path");
        if (paths.some((path) => path.id === pathId)) {
          choosePath(pathId as BasicPathId);
          return;
        }
        const intentId = event.dataTransfer.getData("application/x-eqo-basic-intent") as BasicIntentId;
        if (BASIC_INTENT_BY_ID.has(intentId)) addIntentBlock(intentId);
      }}
    >
      <div className="composer-basic-section-heading">
        <h3 id="basic-canvas-title">Your workflow</h3>
        <p>Drag an intent block here. EQO connects only compatible published handoffs.</p>
      </div>
      <p id="basic-canvas-hint" className="composer-basic-canvas-hint" role="status">
        {isPlanExecutable
          ? `Compatible published workflow selected: ${completePath?.title}.`
          : nextIntentIds.size
            ? `Next compatible block: ${[...nextIntentIds].map((id) => BASIC_INTENT_BY_ID.get(id)?.title).join(" or ")}.`
            : "Start a new plan with Circuit input."}
        {" Drag a starter path here to switch the canvas, or build one compatible intent at a time."}
      </p>
      {activeBlocks.length ? (
        <ol
          className="composer-basic-flow"
          aria-label={`${planPath?.title ?? selectedPath?.title ?? "Basic"} workflow blocks`}
        >
          {activeBlocks.map((block, index) => (
            <Fragment key={`${block.id}-${index}`}>
              <li>
                <button
                  type="button"
                  className={`composer-basic-block is-${block.kind}${selectedBlock?.id === block.id && selectedBlockIndex === index ? " is-selected" : ""}`}
                  aria-pressed={selectedBlock?.id === block.id && selectedBlockIndex === index}
                  onClick={() => setSelectedBlockIndex(index)}
                >
                  <span className="composer-basic-block-index" aria-hidden="true">
                    {index + 1}
                  </span>
                  <span>
                    <strong>{block.title}</strong>
                    <small>{block.detail}</small>
                  </span>
                </button>
              </li>
              {index < activeBlocks.length - 1 && (
                <li className="composer-basic-connector" aria-hidden="true">
                  <ChevronRight size={18} />
                </li>
              )}
            </Fragment>
          ))}
        </ol>
      ) : (
        <div className="composer-basic-empty-canvas">
          <FileCode2 size={18} aria-hidden="true" />
          <strong>Start with Circuit input</strong>
          <p>EQO will reveal only the next compatible intent block.</p>
        </div>
      )}
    </section>
  );

  return (
    <div className="composer-basic-workspace">
      <aside className="composer-basic-library" aria-label="Basic building blocks">
        <header>
          <h2>Basic building blocks</h2>
          <p>Start with a circuit, then choose what should happen next.</p>
        </header>
        <div className="composer-basic-picker">
          <label htmlFor="basic-block-search">Find a basic block</label>
          <input
            id="basic-block-search"
            type="search"
            value={blockQuery}
            placeholder="Search simulation, transform, hardware"
            onChange={(event) => setBlockQuery(event.target.value)}
          />
          <p>
            Each choice maps to a published workflow with compatible circuit input.
          </p>
        </div>
        <div className="composer-basic-paths">
          {visiblePaths.map((path) => {
            const selected = path.id === completePath?.id;
            return (
              <button
                type="button"
                aria-pressed={selected}
                className={`composer-basic-path${selected ? " is-selected" : ""}`}
                key={path.id}
                draggable
                onDragStart={(event) => {
                  event.dataTransfer.effectAllowed = "copy";
                  event.dataTransfer.setData("application/x-eqo-basic-path", path.id);
                  event.dataTransfer.setData("text/plain", path.title);
                }}
                onDragEnd={() => setCanvasDropActive(false)}
                onClick={() => {
                  choosePath(path.id);
                }}
              >
                <span>
                  <strong>{path.title}</strong>
                  <small>{path.detail}</small>
                </span>
                <ChevronRight size={16} aria-hidden="true" />
              </button>
            );
          })}
          {!visiblePaths.length && (
            <p className="composer-basic-empty" role="status">
              No basic block matches “{blockQuery.trim()}”. Try simulation, transform, or hardware.
            </p>
          )}
        </div>
        <div className="composer-basic-intent-library" aria-label="Intent blocks">
          <div>
            <strong>Build a path</strong>
            <button type="button" onClick={resetIntentPlan}>
              Start new
            </button>
          </div>
          <p>Drop the next compatible intent onto the canvas. EQO adds the typed connection.</p>
          {visibleIntentBlocks.map((block) => {
            const compatible = nextIntentIds.has(block.id);
            return (
              <button
                type="button"
                className="composer-basic-intent"
                key={block.id}
                disabled={!compatible}
                draggable={compatible}
                onDragStart={(event) => {
                  event.dataTransfer.effectAllowed = "copy";
                  event.dataTransfer.setData("application/x-eqo-basic-intent", block.id);
                  event.dataTransfer.setData("text/plain", block.title);
                }}
                onDragEnd={() => setCanvasDropActive(false)}
                onClick={() => addIntentBlock(block.id)}
                title={
                  compatible
                    ? `Add ${block.title} to the compatible workflow path`
                    : "Complete or restart the current path before this block can connect"
                }
              >
                <span>
                  <strong>{block.title}</strong>
                  <small>{block.detail}</small>
                </span>
                <ChevronRight size={15} aria-hidden="true" />
              </button>
            );
          })}
        </div>
        <p className="composer-basic-library-note">
          Hardware stays explicit and is never selected automatically. A blank or incomplete plan cannot be submitted.
        </p>
      </aside>

      <main className="composer-basic-detail">
        {!workflow ? (
          <div className="composer-basic-body">
            {flowCanvas}
            <section className="composer-basic-plan-boundary" aria-label="Basic plan validation">
              <CircleAlert size={18} aria-hidden="true" />
              <div>
                <strong>Complete a compatible path before configuring a run</strong>
                <p>EQO will reveal circuit input, target constraints, and preflight only after this intent plan maps to a published workflow.</p>
              </div>
            </section>
          </div>
        ) : (
          <>
            <header className="composer-basic-header">
              <span>
                <h2>{planPath.title}</h2>
                <p>{planPath.detail}</p>
              </span>
              <dl>
                <dt>WORKFLOW</dt>
                <dd>{workflow.id}@{workflow.version}</dd>
                <dt>OUTPUTS</dt>
                <dd>{Object.keys(workflow.definition.spec.outputs).length} artifacts</dd>
              </dl>
            </header>

            <div className="composer-basic-body">
              {flowCanvas}

              {selectedBlock && (
                <section
                  className="composer-basic-block-inspector"
                  aria-labelledby="basic-block-inspector-title"
                >
                  <div className="composer-basic-section-heading">
                    <h3 id="basic-block-inspector-title">
                      Inspect {selectedBlock.title}
                    </h3>
                    <p>{selectedBlock.detail}. This is the published information EQO will preserve with the run.</p>
                  </div>
                  <dl className="composer-basic-block-facts">
                    <div>
                      <dt>INPUT HANDOFF</dt>
                      <dd>
                        {[...blockInputArtifacts].map(artifactLabel).join(", ") || "None"}
                      </dd>
                    </div>
                    <div>
                      <dt>OUTPUT HANDOFF</dt>
                      <dd>
                        {[...blockOutputArtifacts].map(artifactLabel).join(", ") || "None"}
                      </dd>
                    </div>
                    <div>
                      <dt>EXECUTION TARGET</dt>
                      <dd>{selectedBlockTarget}</dd>
                    </div>
                    <div>
                      <dt>ADMISSION</dt>
                      <dd>{readiness.canQueue ? "Ready after input" : readiness.message}</dd>
                    </div>
                  </dl>
                  {selectedBlock.kind === "input" && inputName && inputDefinition && (
                    <p className="composer-basic-block-source">
                      Source: <strong>{inputNames[inputName] || "Pasted circuit"}</strong> · {inputDefinition.artifact_type} · {(inputs[inputName] ?? "").length.toLocaleString()} characters
                    </p>
                  )}
                  {!!selectedNodes.length && (
                    <div className="composer-basic-implementations">
                      {selectedNodes.map((node) => {
                        const operation = capabilities
                          .find((capability) =>
                            capability.id === node.operation.capability &&
                            capability.version === node.operation.version,
                          )
                          ?.operations.find(
                            (item) => item.id === node.operation.operation,
                          );
                        return (
                          <div key={node.id}>
                            <strong>{operation?.title ?? node.operation.operation}</strong>
                            <small>
                              {node.operation.capability}@{node.operation.version} / {node.operation.operation}
                            </small>
                          </div>
                        );
                      })}
                    </div>
                  )}
                  {!!selectedBlockParameters.length && (
                    <dl className="composer-basic-block-parameters">
                      {selectedBlockParameters.map(({ nodeId, name, value }) => (
                        <div key={`${nodeId}-${name}`}>
                          <dt>{parameterLabel(name)}</dt>
                          <dd>{displayPublishedParameter(name, value)}</dd>
                          <small>{nodeId} · {name}</small>
                        </div>
                      ))}
                    </dl>
                  )}
                </section>
              )}

              {planPath.hardwareNotice && (
                <aside className="composer-basic-hardware-notice" role="note">
                  <CircleAlert size={16} aria-hidden="true" />
                  <span>{planPath.hardwareNotice}</span>
                </aside>
              )}

              {planPath.id === "hardware" && (
                <section
                  className="composer-basic-target"
                  aria-labelledby="basic-hardware-target-title"
                >
                  <div>
                    <h3 id="basic-hardware-target-title">Hardware target</h3>
                    <p>
                      This starter workflow is pinned to its admitted execution target.
                      The IQM device is configured by the isolated worker, not in this form.
                    </p>
                  </div>
                  <dl>
                    <dt>EXECUTION TARGET</dt>
                    <dd>{readiness.report?.target ?? "Checking admission"}</dd>
                    <dt>DEVICE</dt>
                    <dd>Worker-configured IQM device</dd>
                  </dl>
                  <p className="composer-basic-target-note">
                    To use a different target or device contract, open Advanced and publish a compatible workflow.
                  </p>
                </section>
              )}

              {transformationEvidence.map((evidence) => (
                <section
                  className="composer-basic-transformation-evidence"
                  aria-labelledby={`transformation-evidence-${evidence.node.id}`}
                  key={evidence.node.id}
                >
                  <div className="composer-basic-section-heading">
                    <h3 id={`transformation-evidence-${evidence.node.id}`}>
                      Transformation route
                    </h3>
                    <p>
                      EQO will run this pinned compiler implementation and preserve
                      its generated circuit evidence with the run.
                    </p>
                  </div>
                  <dl className="composer-basic-transformation-facts">
                    <div>
                      <dt>IMPLEMENTATION</dt>
                      <dd>{evidence.operation.title}</dd>
                      <small>
                        {evidence.capability?.id}@{evidence.capability?.version} / {evidence.operation.id}
                      </small>
                    </div>
                    <div>
                      <dt>TARGET CONSTRAINT</dt>
                      <dd>{evidence.target}</dd>
                      <small>
                        {Object.entries(evidence.node.parameters)
                          .map(([name, value]) => `${parameterLabel(name)}: ${displayPublishedParameter(name, value)}`)
                          .join(" · ") || "Published defaults"}
                      </small>
                    </div>
                  </dl>
                  <div className="composer-basic-transformation-outputs">
                    <strong>Generated artifacts</strong>
                    <ul>
                      {evidence.outputs.map(([name, output]) => (
                        <li key={name}>
                          <span>{artifactLabel(output.artifact_type)}</span>
                          <small>{name} · {output.artifact_type}</small>
                        </li>
                      ))}
                    </ul>
                  </div>
                  {!!evidence.limitations.length && (
                    <div className="composer-basic-transformation-limitations">
                      <strong>Current limits</strong>
                      <ul>
                        {evidence.limitations.map((limitation) => (
                          <li key={limitation}>{limitation}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </section>
              ))}

              {inputName && inputDefinition && (
                <section className="composer-basic-input" aria-labelledby="basic-input-title">
                  <div className="composer-basic-section-heading">
                    <h3 id="basic-input-title">Circuit input</h3>
                    <p>Paste OpenQASM, upload a circuit file, or begin with the Bell example.</p>
                  </div>
                  <div className="composer-basic-input-actions">
                    <label className="composer-button is-secondary">
                      <FileUp size={14} aria-hidden="true" />
                      Upload circuit
                      <input
                        type="file"
                        accept={planPath.inputAccept}
                        aria-label={`Upload ${planPath.inputLabel} file`}
                        onChange={(event) => {
                          const file = event.currentTarget.files?.[0];
                          if (!file) return;
                          setFileError(null);
                          void file
                            .text()
                            .then((text) =>
                              onInput(
                                workflow.id,
                                inputName,
                                text,
                                file.name,
                              ),
                            )
                            .catch((error) => setFileError(toMessage(error)));
                          event.currentTarget.value = "";
                        }}
                      />
                    </label>
                    <button
                      type="button"
                      className="composer-button is-secondary"
                      onClick={() => {
                        setFileError(null);
                        onInput(
                          workflow.id,
                          inputName,
                          planPath.exampleContent,
                          planPath.exampleName,
                        );
                      }}
                    >
                      <FileCode2 size={14} aria-hidden="true" />
                      {planPath.exampleLabel}
                    </button>
                  </div>
                  <textarea
                    rows={8}
                    aria-label={planPath.inputLabel}
                    spellCheck={false}
                    value={inputs[inputName] ?? ""}
                    placeholder={planPath.inputPlaceholder}
                    onChange={(event) =>
                      onInput(workflow.id, inputName, event.target.value)
                    }
                  />
                  <div className="composer-basic-input-meta">
                    <span>{inputNames[inputName] || "Pasted text"}</span>
                    <span>{(inputs[inputName] ?? "").length.toLocaleString()} characters</span>
                    <span>{inputDefinition.artifact_type}</span>
                  </div>
                  {fileError && <p className="composer-guided-input-error">{fileError}</p>}
                </section>
              )}

              <section className="composer-basic-readiness" aria-label="Execution readiness">
                <ExecutionPreflight readiness={readiness} compact />
              </section>

              <section className="composer-basic-output-summary" aria-labelledby="basic-output-title">
                <div className="composer-basic-section-heading">
                  <h3 id="basic-output-title">What you will receive</h3>
                  <p>Every result stays attached to the run with its exact workflow and target details.</p>
                </div>
                <ul>
                  {Object.entries(workflow.definition.spec.outputs).map(([name, output]) => (
                    <li key={name}>
                      <FileCode2 size={15} aria-hidden="true" />
                      <span>
                        <strong>{artifactLabel(output.artifact_type)}</strong>
                        <small>{name}</small>
                      </span>
                    </li>
                  ))}
                </ul>
              </section>
            </div>

            <footer className="composer-basic-actions">
              <span
                className={`composer-guided-status${hasError ? " is-error" : ""}${lastRunId ? " is-queued" : ""}`}
                title={statusMessage}
              >
                {queueing ? (
                  <LoaderCircle size={14} className="composer-spin" aria-hidden="true" />
                ) : hasError ? (
                  <CircleAlert size={14} aria-hidden="true" />
                ) : (
                  <Check size={14} aria-hidden="true" />
                )}
                <span>{statusMessage}</span>
              </span>
              <div>
                {lastRunId && (
                  <a className="composer-button is-secondary" href="?view=runs">
                    View run
                  </a>
                )}
                <button type="button" className="composer-button is-secondary" onClick={onOpenGuided}>
                  <GitFork size={14} aria-hidden="true" />
                  See full workflow
                </button>
                <button type="button" className="composer-button is-secondary" onClick={onOpenAdvanced}>
                  <Braces size={14} aria-hidden="true" />
                  Customize in Advanced
                </button>
                <button
                  type="button"
                  className="composer-button is-primary"
                  disabled={!isPlanExecutable || !inputReady || queueing || !readiness.canQueue}
                  title={
                    !isPlanExecutable
                      ? "Complete a compatible Basic Composer path before submitting."
                      : readiness.canQueue
                        ? planPath.actionLabel
                        : readiness.message
                  }
                  onClick={onQueue}
                >
                  {queueing ? (
                    <LoaderCircle size={14} className="composer-spin" aria-hidden="true" />
                  ) : (
                    <Play size={14} aria-hidden="true" />
                  )}
                  {queueing ? "Submitting" : planPath.actionLabel}
                </button>
              </div>
            </footer>
          </>
        )}
      </main>
    </div>
  );
}

function GuidedComposer({
  paths,
  selectedPath,
  capabilities,
  inputs,
  inputNames,
  queueing,
  statusMessage,
  hasError,
  lastRunId,
  readiness,
  onSelect,
  onInput,
  onQueue,
  onOpenAdvanced,
}: {
  paths: ScientificPath[];
  selectedPath: ScientificPath | undefined;
  capabilities: CapabilitySummary[];
  inputs: Record<string, string>;
  inputNames: Record<string, string>;
  queueing: boolean;
  statusMessage: string;
  hasError: boolean;
  lastRunId: string | null;
  readiness: PreflightDisplay;
  onSelect: (workflowId: string) => void;
  onInput: (
    workflowId: string,
    name: string,
    content: string,
    sourceName?: string,
  ) => void;
  onQueue: () => void;
  onOpenAdvanced: () => void;
}): React.JSX.Element {
  const [fileError, setFileError] = useState<string | null>(null);
  const operationIndex = useMemo(
    () => capabilityOperationIndex(capabilities),
    [capabilities],
  );
  const workflow = selectedPath?.workflow;
  const definition = selectedPath?.definition;
  const examples = definition?.examples ??
    (definition?.exampleContent && definition.exampleName
      ? [
          {
            name: definition.exampleName,
            label: definition.exampleLabel ?? "Load example",
            content: definition.exampleContent,
          },
        ]
      : []);
  const workflowInputs = workflow
    ? Object.entries(workflow.definition.spec.inputs)
    : [];
  const workflowParameters = workflow
    ? workflow.definition.spec.nodes.flatMap((node) => {
        const resolved = operationIndex.get(
          `${node.operation.capability}@${node.operation.version}/${node.operation.operation}`,
        );
        return Object.entries(node.parameters).map(([name, value]) => ({
          nodeId: node.id,
          name,
          label:
            resolved?.operation.parameters?.[name]?.title ??
            parameterLabel(name),
          value,
        }));
      })
    : [];
  const inputReady =
    !!workflow &&
    workflowInputs.every(
      ([name, input]) =>
        !(input.required ?? true) || Boolean(inputs[name]?.trim()),
    );
  const target = workflow
    ? workflowTarget(workflow.definition, capabilities)
    : "Unavailable";
  const recipePaths = GUIDED_RECIPE_ORDER.flatMap((workflowId) => {
    const path = paths.find((item) => item.definition.workflowId === workflowId);
    return path?.definition.featuredRecipe ? [path] : [];
  });
  const recipeWorkflowIds = new Set(
    recipePaths.map((path) => path.definition.workflowId),
  );
  const catalogPaths = paths.filter(
    (path) => !recipeWorkflowIds.has(path.definition.workflowId),
  );
  const selectedPathIsInCatalog = Boolean(
    definition && !recipeWorkflowIds.has(definition.workflowId),
  );
  const [catalogOpen, setCatalogOpen] = useState(selectedPathIsInCatalog);

  useEffect(() => {
    if (selectedPathIsInCatalog) setCatalogOpen(true);
  }, [selectedPathIsInCatalog]);

  return (
    <div className="composer-guided-workspace">
      <aside className="composer-path-index" aria-label="Scientific goals">
        <div className="composer-path-index-header">
          <h2>Guided scientific recipes</h2>
          <p>Start from a scientific goal. EQO reveals the published workflow, inputs, evidence, and result it requires.</p>
        </div>
        <div className="composer-path-list">
          <section className="composer-recipe-section" aria-labelledby="recommended-recipes-title">
            <h3 id="recommended-recipes-title">Recommended recipes</h3>
            <div className="composer-recipe-list">
              {recipePaths.map((path) => {
                const selected = definition?.workflowId === path.definition.workflowId;
                return (
                  <button
                    type="button"
                    className={`composer-path-item composer-recipe-item${selected ? " is-selected" : ""}`}
                    aria-pressed={selected}
                    onClick={() => {
                      setFileError(null);
                      onSelect(path.definition.workflowId);
                    }}
                    key={path.definition.workflowId}
                  >
                    <span className="composer-path-code">{path.definition.code}</span>
                    <span>
                      <strong>{path.definition.shortName}</strong>
                      <small>{path.definition.featuredRecipe?.detail}</small>
                    </span>
                    {path.workflow ? (
                      <ChevronRight size={14} aria-hidden="true" />
                    ) : (
                      <CircleAlert size={14} aria-label="Unavailable" />
                    )}
                  </button>
                );
              })}
            </div>
          </section>
          <details
            className="composer-path-catalog"
            open={catalogOpen}
            onToggle={(event) => setCatalogOpen(event.currentTarget.open)}
          >
            <summary>
              Browse {catalogPaths.length} more published workflows
            </summary>
            <div className="composer-path-catalog-content">
              {GUIDED_SECTIONS.map((section) => {
                const sectionPaths = catalogPaths.filter(
                  (path) => path.definition.section === section.id,
                );
                if (!sectionPaths.length) return null;
                return (
                  <section className="composer-path-section" key={section.id}>
                    <header>
                      <strong>{section.title}</strong>
                      <small>{section.detail}</small>
                    </header>
                    {sectionPaths.map((path) => {
                      const selected =
                        definition?.workflowId === path.definition.workflowId;
                      return (
                        <button
                          type="button"
                          className={`composer-path-item${selected ? " is-selected" : ""}${path.definition.blueprint ? " is-blueprint" : ""}`}
                          aria-pressed={selected}
                          onClick={() => {
                            setFileError(null);
                            onSelect(path.definition.workflowId);
                          }}
                          key={path.definition.workflowId}
                        >
                          <span className="composer-path-code">
                            {path.definition.code}
                          </span>
                          <span>
                            <strong>{path.definition.shortName}</strong>
                            <small>
                              {path.definition.kind} · {path.definition.toolChain.join(" + ")}
                            </small>
                          </span>
                          {path.definition.blueprint ? (
                            <FlaskConical
                              size={14}
                              aria-label="Incubation blueprint"
                            />
                          ) : path.workflow ? (
                            <ChevronRight size={14} aria-hidden="true" />
                          ) : (
                            <CircleAlert size={14} aria-label="Unavailable" />
                          )}
                        </button>
                      );
                    })}
                  </section>
                );
              })}
            </div>
          </details>
        </div>
      </aside>

      <main className="composer-guided-detail">
        {definition?.blueprint ? (
          <IncubationBlueprintView
            definition={
              definition as ScientificPathDefinition & {
                blueprint: IncubationBlueprint;
              }
            }
          />
        ) : !workflow || !definition ? (
          <div className="composer-guided-unavailable">
            <CircleAlert size={20} aria-hidden="true" />
            <strong>Published workflow unavailable</strong>
          </div>
        ) : (
          <>
            <header className="composer-guided-header">
              <span className="composer-guided-glyph" aria-hidden="true">
                {definition.code}
              </span>
              <span>
                <small>{definition.shortName}</small>
                <h2>{workflow.definition.metadata.name}</h2>
                <p>{workflow.definition.metadata.description}</p>
              </span>
              <dl>
                <dt>VERSION</dt>
                <dd>{workflow.version}</dd>
                <dt>TARGET</dt>
                <dd>{target}</dd>
                <dt>DIGEST</dt>
                <dd>{workflow.digest.slice(0, 15)}</dd>
              </dl>
            </header>

            <div className="composer-guided-body">
              {definition.workflowId === "openqevo-trotter-synthesis" && (
                <section className="composer-guided-purpose" aria-labelledby="openqevo-path-title">
                  <div>
                    <span>YOUR PATH</span>
                    <h3 id="openqevo-path-title">Hamiltonian to inspectable circuit</h3>
                    <p>Start from a Pauli Hamiltonian. EQO creates a Trotter circuit and preserves the synthesis report with the run.</p>
                  </div>
                  <ol>
                    <li><strong>1</strong><span><b>Add Hamiltonian</b><small>Paste, upload, or load the example.</small></span></li>
                    <li><strong>2</strong><span><b>Create circuit</b><small>OpenQEvo and Qiskit apply the published Trotter settings.</small></span></li>
                    <li><strong>3</strong><span><b>Inspect result</b><small>Open the run to view the circuit and synthesis report.</small></span></li>
                  </ol>
                </section>
              )}
              {definition.hardwareNotice && (
                <aside className="composer-guided-hardware-notice" role="note">
                  <CircleAlert size={16} aria-hidden="true" />
                  <span>
                    <strong>{definition.hardwareNotice.title}</strong>
                    <small>{definition.hardwareNotice.detail}</small>
                  </span>
                </aside>
              )}
              <section className="composer-guided-section">
                <h3>Connected pipeline</h3>
                <ol className="composer-guided-pipeline">
                  {workflow.definition.spec.nodes.map((node, index) => {
                    const resolved = operationIndex.get(
                      `${node.operation.capability}@${node.operation.version}/${node.operation.operation}`,
                    );
                    const inbound = workflow.definition.spec.edges.find(
                      (edge) => edge.to.node === node.id,
                    );
                    return (
                      <li key={node.id}>
                        <span className="composer-pipeline-sequence">
                          {String(index + 1).padStart(2, "0")}
                        </span>
                        <span>
                          <strong>
                            {resolved?.operation.title ??
                              node.operation.operation}
                          </strong>
                          <small>
                            {resolved?.capability.name ??
                              node.operation.capability}
                          </small>
                        </span>
                        <span className="composer-pipeline-contract">
                          {inbound
                            ? artifactLabel(inbound.to.artifact_type)
                            : index === 0 && workflowInputs.length
                              ? artifactLabel(
                                  workflowInputs[0][1].artifact_type,
                                )
                              : "Generated in workflow"}
                        </span>
                      </li>
                    );
                  })}
                </ol>
                <ExecutionPreflight readiness={readiness} />
              </section>

              <section className="composer-guided-section">
                <h3>
                  {workflowInputs.length
                    ? "Scientific input"
                    : "Published configuration"}
                </h3>
                {workflowInputs.map(([name, input]) => {
                  const content = inputs[name] ?? "";
                  const inputLabel =
                    definition.inputLabel ??
                    artifactLabel(input.artifact_type);
                  return (
                    <div className="composer-guided-input" key={name}>
                      <div className="composer-guided-input-title">
                        <span>
                          <strong>{inputLabel}</strong>
                          <small>{input.artifact_type}</small>
                        </span>
                        <div>
                          <label className="composer-button is-secondary">
                            <FileUp size={14} aria-hidden="true" />
                            {definition.inputFileLabel ?? "Choose .qasm"}
                            <input
                              type="file"
                              accept={
                                definition.inputAccept ??
                                ".qasm,.txt,text/plain"
                              }
                              aria-label={`Upload ${inputLabel} file`}
                              onChange={(event) => {
                                const file = event.currentTarget.files?.[0];
                                if (!file) return;
                                setFileError(null);
                                void file
                                  .text()
                                  .then((text) =>
                                    onInput(
                                      workflow.id,
                                      name,
                                      text,
                                      file.name,
                                    ),
                                  )
                                  .catch((error) =>
                                    setFileError(toMessage(error)),
                                  );
                                event.currentTarget.value = "";
                              }}
                            />
                          </label>
                          {examples.map((example) => (
                              <button
                                type="button"
                                className="composer-button is-secondary"
                                key={example.name}
                                onClick={() => {
                                  setFileError(null);
                                  onInput(
                                    workflow.id,
                                    name,
                                    example.content,
                                    example.name,
                                  );
                                }}
                              >
                                <FileCode2 size={14} aria-hidden="true" />
                                {example.label}
                              </button>
                          ))}
                        </div>
                      </div>
                      <textarea
                        rows={10}
                        aria-label={inputLabel}
                        spellCheck={false}
                        value={content}
                        placeholder={
                          definition.inputPlaceholder ?? "OPENQASM 2.0;"
                        }
                        onChange={(event) =>
                          onInput(workflow.id, name, event.target.value)
                        }
                      />
                      <div className="composer-guided-input-meta">
                        <span>{inputNames[name] || "Pasted text"}</span>
                        <span>{content.length.toLocaleString()} characters</span>
                      </div>
                      {fileError && (
                        <p className="composer-guided-input-error">
                          {fileError}
                        </p>
                      )}
                    </div>
                  );
                })}
              </section>

              {!!workflowParameters.length && (
                <section className="composer-guided-section">
                  <h3>Published configuration</h3>
                  <dl className="composer-guided-parameters">
                    {workflowParameters.map(
                      ({ nodeId, name, label, value }) => (
                      <div key={`${nodeId}-${name}`}>
                        <dt>{label}</dt>
                        <dd>{String(value)}</dd>
                        <small>
                          {nodeId} · {name}
                        </small>
                      </div>
                      ),
                    )}
                  </dl>
                </section>
              )}

              <section className="composer-guided-section">
                <h3>Produced artifacts</h3>
                <div className="composer-guided-outputs">
                  {Object.entries(workflow.definition.spec.outputs).map(
                    ([name, output]) => (
                      <div key={name}>
                        <FileCode2 size={15} aria-hidden="true" />
                        <span>
                          <strong>{artifactLabel(output.artifact_type)}</strong>
                          <small>
                            {name} · {output.artifact_type}
                          </small>
                        </span>
                      </div>
                    ),
                  )}
                </div>
              </section>
            </div>

            <footer className="composer-guided-actions">
              <span
                className={`composer-guided-status${hasError ? " is-error" : ""}${lastRunId ? " is-queued" : ""}`}
                title={statusMessage}
              >
                {queueing ? (
                  <LoaderCircle
                    size={14}
                    className="composer-spin"
                    aria-hidden="true"
                  />
                ) : hasError ? (
                  <CircleAlert size={14} aria-hidden="true" />
                ) : (
                  <Check size={14} aria-hidden="true" />
                )}
                <span>{statusMessage}</span>
              </span>
              <div>
                {lastRunId && (
                  <a
                    className="composer-button is-secondary"
                    href="?view=runs"
                  >
                    View run
                  </a>
                )}
                <button
                  type="button"
                  className="composer-button is-secondary"
                  onClick={onOpenAdvanced}
                >
                  <GitFork size={14} aria-hidden="true" />
                  Customize in Advanced
                </button>
                <button
                  type="button"
                  className="composer-button is-primary"
                  disabled={
                    !inputReady ||
                    queueing ||
                    target === "No compatible target" ||
                    !readiness.canQueue
                  }
                  title={
                    readiness.canQueue
                      ? "Run this published workflow"
                      : readiness.message
                  }
                  onClick={onQueue}
                >
                  {queueing ? (
                    <LoaderCircle
                      size={14}
                      className="composer-spin"
                      aria-hidden="true"
                    />
                  ) : (
                    <Play size={14} aria-hidden="true" />
                  )}
                  Run workflow
                </button>
              </div>
            </footer>
          </>
        )}
      </main>
    </div>
  );
}


function PortInspector({
  title,
  ports,
  kind,
  node,
  edges,
  onExpose,
}: {
  title: string;
  ports: Record<string, ArtifactPort>;
  kind: "workflow-input" | "workflow-output";
  node: Extract<ComposerNode, { type: "operation" }>;
  edges: ComposerEdge[];
  onExpose: (
    port: string,
    kind: "workflow-input" | "workflow-output",
  ) => void;
}): React.JSX.Element {
  return (
    <section className="composer-inspector-section">
      <h3>{title}</h3>
      <div className="composer-port-inspector">
        {Object.entries(ports).map(([name, definition]) => {
          const connected = edges.some((edge) =>
            kind === "workflow-input"
              ? edge.target === node.id && edge.targetHandle === `in:${name}`
              : edge.source === node.id &&
                edge.sourceHandle === `out:${name}` &&
                edge.data?.kind === "workflow-output",
          );
          return (
            <div key={name}>
              <span>
                <strong>{name}</strong>
                <small>{definition.artifact_type}</small>
              </span>
              <IconButton
                label={
                  connected
                    ? `${name} is connected`
                    : `Expose ${name} as workflow ${kind === "workflow-input" ? "input" : "output"}`
                }
                disabled={connected}
                onClick={() => onExpose(name, kind)}
              >
                {connected ? <Check size={14} /> : <Unplug size={14} />}
              </IconButton>
            </div>
          );
        })}
      </div>
    </section>
  );
}


function ParameterControl({
  name,
  definition,
  value,
  onChange,
}: {
  name: string;
  definition: ParameterDefinition;
  value: ParameterValue | undefined;
  onChange: (value: ParameterValue) => void;
}): React.JSX.Element {
  const label = definition.title ?? name;
  if (definition.type === "boolean") {
    return (
      <label className="composer-toggle-control">
        <span>
          <strong>{label}</strong>
          <small>{definition.description ?? name}</small>
        </span>
        <input
          type="checkbox"
          checked={Boolean(value)}
          onChange={(event) => onChange(event.target.checked)}
        />
      </label>
    );
  }
  if (definition.enum) {
    return (
      <label className="composer-field">
        <span>{label}</span>
        <select
          value={String(value ?? "")}
          onChange={(event) =>
            onChange(parameterValue(definition, event.target.value))
          }
        >
          {definition.enum.map((item) => (
            <option value={String(item)} key={String(item)}>
              {String(item)}
            </option>
          ))}
        </select>
        {definition.description && (
          <small className="composer-field-help">{definition.description}</small>
        )}
      </label>
    );
  }
  return (
    <label className="composer-field">
      <span>{label}</span>
      <input
        type={definition.type === "string" ? "text" : "number"}
        value={value === undefined || value === null ? "" : String(value)}
        min={definition.minimum}
        max={definition.maximum}
        step={definition.type === "integer" ? 1 : "any"}
        onChange={(event) =>
          onChange(parameterValue(definition, event.target.value))
        }
      />
      {definition.description && (
        <small className="composer-field-help">{definition.description}</small>
      )}
    </label>
  );
}


function OperationInspector({
  node,
  operation,
  edges,
  onRename,
  onParameter,
  onExpose,
}: {
  node: Extract<ComposerNode, { type: "operation" }>;
  operation: OperationDefinition | undefined;
  edges: ComposerEdge[];
  onRename: (id: string) => void;
  onParameter: (name: string, value: ParameterValue) => void;
  onExpose: (
    port: string,
    kind: "workflow-input" | "workflow-output",
  ) => void;
}): React.JSX.Element {
  return (
    <div className="composer-inspector-body">
      <section className="composer-inspector-section">
        <label className="composer-field">
          <span>Node id</span>
          <input
            key={node.id}
            defaultValue={node.id}
            onBlur={(event) => onRename(event.target.value)}
          />
        </label>
        <dl className="composer-definition">
          <dt>Tool</dt>
          <dd>{node.data.operation.capability}</dd>
          <dt>Operation</dt>
          <dd>{node.data.operation.operation}</dd>
          <dt>Runtime</dt>
          <dd>{operation?.runtime.type ?? "unavailable"}</dd>
        </dl>
      </section>
      {!!Object.keys(node.data.parameterDefinitions).length && (
        <section className="composer-inspector-section">
          <h3>Parameters</h3>
          {Object.entries(node.data.parameterDefinitions).map(
            ([name, definition]) => (
              <ParameterControl
                key={name}
                name={name}
                definition={definition}
                value={node.data.parameters[name]}
                onChange={(value) => onParameter(name, value)}
              />
            ),
          )}
        </section>
      )}
      <PortInspector
        title="Inputs"
        ports={node.data.inputs}
        kind="workflow-input"
        node={node}
        edges={edges}
        onExpose={onExpose}
      />
      <PortInspector
        title="Outputs"
        ports={node.data.outputs}
        kind="workflow-output"
        node={node}
        edges={edges}
        onExpose={onExpose}
      />
    </div>
  );
}


function WorkflowInspector({
  metadata,
  draft,
  published,
  validation,
  clientIssues,
  runInputs,
  preflight,
  publishing,
  queueing,
  lastRunId,
  onMetadata,
  onRunInput,
  onPublish,
  onQueue,
  onDeleteDraft,
}: {
  metadata: Workflow["metadata"];
  draft: WorkflowDraft | null;
  published: PublishedWorkflow | null;
  validation: DraftValidation | null;
  clientIssues: ReturnType<typeof validateCanvas>;
  runInputs: Record<string, string>;
  preflight: PreflightDisplay;
  publishing: boolean;
  queueing: boolean;
  lastRunId: string | null;
  onMetadata: <K extends keyof Workflow["metadata"]>(
    key: K,
    value: Workflow["metadata"][K],
  ) => void;
  onRunInput: (name: string, value: string) => void;
  onPublish: () => void;
  onQueue: () => void;
  onDeleteDraft: () => void;
}): React.JSX.Element {
  const issues = validation?.valid === false
    ? validation.issues.map((item) => item.message)
    : clientIssues.map((item) => item.message);
  const requiredInputsReady = published
    ? Object.entries(published.definition.spec.inputs).every(
        ([name, definition]) =>
          !(definition.required ?? true) || Boolean(runInputs[name]?.trim()),
      )
    : false;
  return (
    <div className="composer-inspector-body">
      {published ? (
        <section
          className="composer-inspector-section composer-execution-section"
          id="advanced-run-panel"
        >
          <div className="composer-section-heading">
            <h3>Run published workflow</h3>
            <span>Published</span>
          </div>
          <p className="composer-section-copy">
            Provide any required artifacts, then queue this immutable workflow
            version on its compatible execution target.
          </p>
          <dl className="composer-definition">
            <dt>Digest</dt>
            <dd>{published.digest.slice(0, 20)}</dd>
          </dl>
          <ExecutionPreflight readiness={preflight} compact />
          {Object.entries(published.definition.spec.inputs).map(
            ([name, definition]) => (
              <label className="composer-field" key={name}>
                <span>
                  {name} · {definition.artifact_type}
                </span>
                <textarea
                  rows={6}
                  value={runInputs[name] ?? ""}
                  onChange={(event) => onRunInput(name, event.target.value)}
                />
              </label>
            ),
          )}
          <button
            type="button"
            className="composer-button is-primary is-full"
            onClick={onQueue}
            disabled={queueing || !requiredInputsReady || !preflight.canQueue}
            title={
              !preflight.canQueue
                ? preflight.message
                : !requiredInputsReady
                  ? "Provide all required input artifacts before queueing."
                  : "Queue this published workflow"
            }
          >
            {queueing ? (
              <LoaderCircle
                size={14}
                className="composer-spin"
                aria-hidden="true"
              />
            ) : (
              <Play size={14} aria-hidden="true" />
            )}
            {queueing ? "Queueing" : "Queue run"}
          </button>
          {lastRunId && <p className="composer-run-id">{lastRunId}</p>}
        </section>
      ) : (
        <section
          className="composer-inspector-section composer-execution-section"
          id="advanced-run-panel"
        >
          <div className="composer-section-heading">
            <h3>Run workflow</h3>
            <span>Draft</span>
          </div>
          <p className="composer-section-copy">
            Compose the artifact handoffs first. Publishing saves and validates
            this draft, then unlocks its run inputs—for example, the OpenQASM
            circuit connected to your first operation.
          </p>
          <ol className="composer-execution-steps" aria-label="Execution steps">
            <li>Compose</li>
            <li>Publish</li>
            <li>Queue</li>
          </ol>
          <button
            type="button"
            className="composer-button is-primary is-full"
            onClick={onPublish}
            disabled={publishing}
          >
            {publishing ? (
              <LoaderCircle
                size={14}
                className="composer-spin"
                aria-hidden="true"
              />
            ) : (
              <CloudUpload size={14} aria-hidden="true" />
            )}
            {publishing ? "Publishing" : "Publish to run"}
          </button>
        </section>
      )}

      <section className="composer-inspector-section">
        <label className="composer-field">
          <span>Name</span>
          <input
            value={metadata.name}
            onChange={(event) => onMetadata("name", event.target.value)}
          />
        </label>
        <label className="composer-field">
          <span>Workflow id</span>
          <input
            value={metadata.id}
            onChange={(event) => onMetadata("id", event.target.value)}
          />
        </label>
        <div className="composer-field-row">
          <label className="composer-field">
            <span>Version</span>
            <input
              value={metadata.version}
              onChange={(event) => onMetadata("version", event.target.value)}
            />
          </label>
          <label className="composer-field">
            <span>Visibility</span>
            <select
              value={metadata.visibility}
              onChange={(event) =>
                onMetadata(
                  "visibility",
                  event.target.value as Workflow["metadata"]["visibility"],
                )
              }
            >
              <option value="private">Private</option>
              <option value="project">Project</option>
              <option value="internal">Internal</option>
              <option value="public">Public</option>
            </select>
          </label>
        </div>
        <label className="composer-field">
          <span>Description</span>
          <textarea
            rows={3}
            value={metadata.description ?? ""}
            onChange={(event) =>
              onMetadata("description", event.target.value)
            }
          />
        </label>
      </section>

      {!!issues.length && (
        <section className="composer-inspector-section">
          <h3>Validation</h3>
          <ul className="composer-issue-list">
            {issues.slice(0, 8).map((issue, index) => (
              <li key={`${issue}-${index}`}>{issue}</li>
            ))}
          </ul>
        </section>
      )}

      {draft && (
        <section className="composer-inspector-section composer-danger-zone">
          <button
            type="button"
            className="composer-button is-danger"
            onClick={onDeleteDraft}
          >
            <Trash2 size={14} aria-hidden="true" />
            Delete draft
          </button>
        </section>
      )}
    </div>
  );
}


export function ComposerApp(): React.JSX.Element {
  return (
    <ReactFlowProvider>
      <ComposerSurface />
    </ReactFlowProvider>
  );
}
