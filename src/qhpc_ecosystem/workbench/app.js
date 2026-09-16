const SOURCE_AREAS = {
  "software-engineering": "Software Engineering",
  "data-schema": "Data Schema",
  "agentic-software": "Agentic Software",
  "compilation-tools": "Compilation Tools",
  "hybrid-workflows": "Hybrid Workflows",
  "cross-project": "Cross-project",
};

// Names are transcribed only from the reviewed, pinned-source attribution
// record.  They identify developers or publication authors, not current
// maintainers; the latter requires an explicit project statement.
const TOOL_PEOPLE = {
  "quantum-sdk-ranking": { basis: "Named repository contributor", people: ["Sharmin Afrose"] },
  "chatqec-assistant-service": { basis: "Package and publication authors", people: ["Sharmin Afrose", "Vicente Leyton-Ortega", "Travis Humble", "Tirthankar Ghosal"] },
  "chatqec-qec-tools": { basis: "Package and publication authors", people: ["Sharmin Afrose", "Vicente Leyton-Ortega", "Travis Humble", "Tirthankar Ghosal"] },
  "qsc-hardware-survey": { basis: "Named repository contributors", people: ["Swen Boehm", "Thomas Naughton", "Vicente Leyton-Ortega"] },
  "exachem-qflow-tasksets": { basis: "Publication authors named by the project", people: ["Ajay Panyala", "Nicholas Bauman", "Daniel Mejia Rodriguez", "Himadri Pathak", "Bo Peng", "Marcus Liebenthal", "David Murphy", "Giridhar Nandipati", "Erdal Mutlu", "Sriram Krishnamoorthy", "Edo Aprà", "Sotiris Xantheas", "Niranjan Govind", "Karol Kowalski"] },
  "ftprimitivebench-primitives": { basis: "Publication authors named by the project", people: ["Shuwen Kan", "Adrian Harkness", "Zefan Du", "Rod Rofougaran", "Sean Garner", "Chenxu Liu", "Ying Mao", "Samuel Stein"] },
  "ftqc-compiler": { basis: "Named repository contributors", people: ["Narasinga Rao Miniskar", "Seyong Lee"] },
  "iris-qiris-runtime": { basis: "Package and publication authors", people: ["Narasinga Rao Miniskar", "Jungwon Kim", "Seyong Lee", "Beau Johnston", "Jeffrey S. Vetter"] },
  "lightstim-simulation": { basis: "Software and package authors", people: ["Xiang Fang", "Ming Wang", "Yue Wu", "Sharanya Prabhu", "Dean Tullsen", "Narasinga Rao Miniskar", "Frank Mueller", "Travis Humble", "Yufei Ding"] },
  "tn-sim-mps-simulation": { basis: "Publication authors named by the project", people: ["Ang Li", "Omer Subasi", "Xiu Yang", "Sriram Krishnamoorthy"] },
  "nwqsim-qflow-vqe-plugin": { basis: "Publication authors named by the project", people: ["Ang Li", "Omer Subasi", "Xiu Yang", "Sriram Krishnamoorthy"] },
  "openqevo-library": { basis: "Named repository contributors", people: ["Thomas Naughton", "Vicente Leyton-Ortega"] },
  "qappswiki-tooling": { basis: "Named repository contributor", people: ["Vicente Leyton-Ortega"] },
  "stabsim-simulator": { basis: "Publication authors named by the project", people: ["Sean Garner", "Chenxu Liu", "Meng Wang", "Samuel Stein", "Ang Li"] },
  "nwqec-qec-transpilation": { basis: "Publication authors named by the project", people: ["Meng Wang", "Chenxu Liu", "Samuel Stein", "Yufei Ding", "Poulami Das", "Prashant J. Nair", "Ang Li", "Sean Garner"] },
  "openqse-specification": { basis: "Named repository contributors", people: ["Amir Shehata", "Josh Moles", "Patrick Deuley", "Thomas Naughton"] },
  "qasmtrans-transpiler": { basis: "Developers named by the project", people: ["Fei Hua", "Meng Wang", "Muqing Zheng", "Ang Li"] },
  "qsc-materials-db-schema": { basis: "No individual developers are named in the reviewed source", people: [] },
  "qsc-spack-repository": { basis: "Named repository contributors", people: ["Brad Chase", "Charles Ferenbaugh", "Seth R. Johnson"] },
};

/* Every state carries a class, a glyph, and its own word, so state is never
   communicated by color alone. Red and green stay semantic; the glyph is the
   channel that survives deuteranopia and forced-colors mode. */
const STATE_META = {
  succeeded: { cls: "green", glyph: "✓", color: "var(--ok)" },
  verified: { cls: "green", glyph: "✓", color: "var(--ok)" },
  "production-approved": { cls: "green", glyph: "✓", color: "var(--ok)" },
  "integration-tested": { cls: "green", glyph: "✓", color: "var(--ok)" },
  "up-to-date": { cls: "green", glyph: "✓", color: "var(--ok)" },
  "smoke-tested": { cls: "blue", glyph: "◐", color: "var(--run)" },
  prepared: { cls: "blue", glyph: "◐", color: "var(--run)" },
  online: { cls: "green", glyph: "✓", color: "var(--ok)" },
  running: { cls: "blue", glyph: "▶", color: "var(--run)" },
  draining: { cls: "amber", glyph: "◷", color: "var(--warn)" },
  queued: { cls: "amber", glyph: "◷", color: "var(--warn)" },
  pending: { cls: "amber", glyph: "◷", color: "var(--warn)" },
  "not-checked": { cls: "amber", glyph: "◷", color: "var(--warn)" },
  "update-available": { cls: "amber", glyph: "!", color: "var(--warn)" },
  discovered: { cls: "amber", glyph: "◷", color: "var(--warn)" },
  declared: { cls: "amber", glyph: "◷", color: "var(--warn)" },
  stale: { cls: "red", glyph: "!", color: "var(--bad)" },
  offline: { cls: "red", glyph: "✕", color: "var(--bad)" },
  failed: { cls: "red", glyph: "✕", color: "var(--bad)" },
  error: { cls: "red", glyph: "✕", color: "var(--bad)" },
  canceled: { cls: "red", glyph: "⊘", color: "var(--bad)" },
};

function stateMeta(status) {
  return STATE_META[status] || { cls: "", glyph: "·", color: "var(--idle)" };
}

const FTQC_EXECUTION_WORKFLOWS = new Set([
  "ftqc-iqm-bell-execution",
  "ftqc-iqm-steane-execution",
]);

function isIqmExecutionTask(task) {
  return task?.operation?.capability === "ftqc-compiler"
    && task?.operation?.operation === "route-submit-collect";
}

function iqmExecutionLifecycle(run) {
  const task = run?.tasks?.find(isIqmExecutionTask);
  if (!run || !task) {
    return {
      present: Boolean(run),
      status: run ? "Preparing" : "Awaiting execution",
      detail: run
        ? "The local preparation boundary is running before any backend submission."
        : "No hardware or safe-simulation execution has been started.",
      tone: "waiting",
    };
  }
  const attempt = task.attempts?.at(-1);
  if (task.state === "cancel_requested" || attempt?.state === "cancel_requested") {
    return { present: true, status: "Cancellation requested", detail: "EQO has asked the isolated backend worker to cancel the admitted job.", tone: "waiting" };
  }
  if (task.state === "succeeded" || run.state === "succeeded") {
    return { present: true, status: "Completed", detail: "Typed layout, receipt, counts, and logical-result artifacts are available in the run record.", tone: "ready" };
  }
  if (task.state === "failed" || run.state === "failed") {
    return { present: true, status: "Failed", detail: "The isolated backend execution did not complete. Review the non-secret admission gates and retry only when they are resolved.", tone: "failed" };
  }
  if (task.state === "canceled" || run.state === "canceled") {
    return { present: true, status: "Canceled", detail: "The backend execution was canceled before results were collected.", tone: "failed" };
  }
  if (attempt?.state === "collecting" || attempt?.target_state === "succeeded") {
    return { present: true, status: "Collecting results", detail: "The backend has reached a terminal result; EQO is preserving typed artifacts and provenance.", tone: "active" };
  }
  if (attempt?.state === "submitting") {
    return { present: true, status: "Routing and submitting", detail: "The isolated worker is routing the prepared circuit and submitting its admitted job.", tone: "active" };
  }
  if (attempt?.target_state === "queued" || attempt?.state === "submitted") {
    return { present: true, status: "Provider queued", detail: "The backend has accepted the job and EQO is waiting for its next non-secret status transition.", tone: "waiting" };
  }
  if (attempt?.target_state === "running" || task.state === "running") {
    return { present: true, status: "Provider running", detail: "The isolated worker is polling the admitted backend job. Credentials remain inside that worker.", tone: "active" };
  }
  return { present: true, status: "Queued for backend admission", detail: "The preparation stage is complete; EQO is waiting for a compatible backend worker.", tone: "waiting" };
}

function latestIqmExecutionRun() {
  return state.runs.find(run => FTQC_EXECUTION_WORKFLOWS.has(run.workflow_id));
}

function compareWorkflowVersions(left, right) {
  const parse = value => /^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$/.exec(value);
  const leftVersion = parse(left);
  const rightVersion = parse(right);
  if (!leftVersion || !rightVersion) return String(left).localeCompare(String(right));
  for (let index = 1; index <= 3; index += 1) {
    const difference = Number(leftVersion[index]) - Number(rightVersion[index]);
    if (difference) return difference;
  }
  const leftPrerelease = leftVersion[4]?.split(".") || null;
  const rightPrerelease = rightVersion[4]?.split(".") || null;
  if (!leftPrerelease && !rightPrerelease) return 0;
  if (!leftPrerelease) return 1;
  if (!rightPrerelease) return -1;
  const length = Math.max(leftPrerelease.length, rightPrerelease.length);
  for (let index = 0; index < length; index += 1) {
    const leftPart = leftPrerelease[index];
    const rightPart = rightPrerelease[index];
    if (leftPart === undefined) return -1;
    if (rightPart === undefined) return 1;
    const leftNumeric = /^\d+$/.test(leftPart);
    const rightNumeric = /^\d+$/.test(rightPart);
    if (leftNumeric && rightNumeric) {
      const difference = Number(leftPart) - Number(rightPart);
      if (difference) return difference;
      continue;
    }
    if (leftNumeric) return -1;
    if (rightNumeric) return 1;
    const difference = leftPart.localeCompare(rightPart);
    if (difference) return difference;
  }
  return 0;
}

function latestWorkflowVersions(workflows) {
  const latest = new Map();
  workflows.forEach(workflow => {
    const current = latest.get(workflow.id);
    if (!current || compareWorkflowVersions(workflow.version, current.version) > 0) latest.set(workflow.id, workflow);
  });
  return [...latest.values()].sort((left, right) => left.id.localeCompare(right.id));
}

function sanitizedIqmFailure(task) {
  if (!isIqmExecutionTask(task) || !task.error) return "";
  return "The isolated backend execution failed. Provider details are deliberately not displayed; verify the non-secret worker admission gates before retrying.";
}

const VIEW_META = {
  overview: ["QSC / QHPC ECOSYSTEM", "EQO-QSC"],
  showcases: ["SCIENCE / SHOWCASES", "Scientific showcases"],
  tools: ["ECOSYSTEM / TOOLS", "Integrated software"],
  data: ["DATA / SERVICES", "Data services"],
  knowledge: ["KNOWLEDGE / QAPPSWIKI", "Knowledge Explorer"],
  openqse: ["COMMUNITY / OPENQSE", "OpenQSE resources"],
  engagement: ["COMMUNITY / ENGAGEMENT", "Learning and events"],
  assistant: ["ASSISTANCE / CHATQEC", "ChatQEC"],
  compose: ["WORKFLOWS / COMPOSE", "Workflow composer"],
  runs: ["EXECUTION / RUNS", "Run operations"],
  artifacts: ["PROVENANCE / ARTIFACTS", "Produced artifacts"],
  environments: ["RUNTIMES / ENVIRONMENTS", "Execution environments"],
  updates: ["SOURCES / UPDATES", "Repository updates"],
};

const VIEW_ALIASES = { projects: "overview", explore: "tools", "data-services": "data" };
const initialSearchParams = new URLSearchParams(window.location.search);
const rawRequestedView = initialSearchParams.get("view");
const requestedView = VIEW_ALIASES[rawRequestedView] || rawRequestedView;
const initialView = Object.hasOwn(VIEW_META, requestedView) ? requestedView : "overview";
const ASSISTANT_HISTORY_MESSAGE_LIMIT = 20;
const ASSISTANT_HISTORY_CHARACTER_BUDGET = 24_000;
const state = {
  capabilities: [],
  workflows: [],
  runs: [],
  artifacts: [],
  workers: [],
  view: initialView,
  knowledgeNode: initialSearchParams.get("knowledge_node"),
  requestedCapability: initialSearchParams.get("capability"),
  selectedDataService: initialSearchParams.get("data_service"),
  query: "",
  statusFilter: "all",
  selectedOperation: null,
  selectedWorkflow: null,
  parameters: {},
  inputContents: {},
  assistant: {
    conversationId: createConversationId(),
    messages: [],
    status: null,
    statusLoading: false,
    submitting: false,
    requestSerial: 0,
    streamAbortController: null,
    contextNotice: "",
  },
  assistantDockOpen: false,
  engagement: {
    resources: [],
  },
  repositoryUpdates: {
    data: null,
    loading: false,
    checking: false,
    staging: null,
    error: null,
  },
  dataObjectsByPrefix: {},
};
const workspace = document.querySelector("#workspace");
let quantumAsciiCleanup = () => {};

function quantumAsciiFrame(index) {
  const steps = [
    {
      flow: "*|psi> => [QEC [[7,1,3]]] -> [QHPC ORCH]",
      route: "              ^                    |",
      recovery: "        frame |                    v",
      feedback: "      [HPC DECODER] <- s/counts <- [QPU]",
      provenance: "              +------> [PROVENANCE]",
      state: "01/04 ENCODE   logical state -> QEC block",
    },
    {
      flow: " |psi> -> [QEC [[7,1,3]]] => [QHPC ORCH]*",
      route: "              ^                    v*",
      recovery: "        frame |                    v",
      feedback: "      [HPC DECODER] <- s/counts <- [QPU]",
      provenance: "              +------> [PROVENANCE]",
      state: "02/04 DISPATCH encoded circuit -> QPU",
    },
    {
      flow: " |psi> -> [QEC [[7,1,3]]] -> [QHPC ORCH]",
      route: "              ^                    |",
      recovery: "        frame |                    v",
      feedback: "      [HPC DECODER] <= s/counts <= [QPU]*",
      provenance: "              +------> [PROVENANCE]",
      state: "03/04 DECODE   syndrome -> HPC decoder",
    },
    {
      flow: " |psi> -> [QEC [[7,1,3]]] -> [QHPC ORCH]",
      route: "              ^                    |",
      recovery: "       *frame ^                    v",
      feedback: "      [HPC DECODER] <- s/counts <- [QPU]",
      provenance: "              +======> [PROVENANCE]*",
      state: "04/04 RECOVER  frame + provenance -> cycle",
    },
    {
      flow: " |psi> -> [QEC [[7,1,3]]] -> [QHPC ORCH]",
      route: "              ^                    |",
      recovery: "        frame |                    v",
      feedback: "      [HPC DECODER] <- s/counts <- [QPU]",
      provenance: "              +------> [PROVENANCE]",
      state: "STATIC  QEC protection <-> QHPC orchestration",
    },
  ];
  const step = steps[index] ?? steps[index % 4];
  const panelLine = content => `| ${content.padEnd(43, " ")} |`;
  return [
    ".---------- QEC + QHPC CONTROL LOOP ----------.",
    panelLine(step.flow),
    panelLine(step.route),
    panelLine(step.recovery),
    panelLine(step.feedback),
    panelLine(step.provenance),
    "'---------------------------------------------'",
    step.state,
  ].join("\n");
}

function mountQuantumAsciiAnimation() {
  quantumAsciiCleanup();
  const output = document.querySelector("#qsc-quantum-ascii");
  if (!output) return;
  const status = document.querySelector("#qsc-quantum-state");

  const motionPreference = window.matchMedia("(prefers-reduced-motion: reduce)");
  let frame = motionPreference.matches ? 4 : 0;
  let visible = !("IntersectionObserver" in window);
  let timer = null;

  const draw = () => {
    output.textContent = quantumAsciiFrame(frame);
    if (status) {
      status.textContent = motionPreference.matches
        ? "Static schematic · reduced motion"
        : "Explanatory sequence · not live telemetry";
    }
  };
  const stop = () => {
    if (timer === null) return;
    window.clearInterval(timer);
    timer = null;
  };
  const sync = () => {
    if (motionPreference.matches) {
      frame = 4;
      draw();
    }
    const shouldRun = visible && !document.hidden && !motionPreference.matches;
    if (!shouldRun) {
      stop();
      return;
    }
    if (timer !== null) return;
    timer = window.setInterval(() => {
      frame = (frame + 1) % 4;
      draw();
    }, 1250);
  };

  draw();
  const observer = "IntersectionObserver" in window
    ? new IntersectionObserver(entries => {
        visible = entries.some(entry => entry.isIntersecting);
        sync();
      }, { threshold: .15 })
    : null;
  observer?.observe(output);
  document.addEventListener("visibilitychange", sync);
  motionPreference.addEventListener?.("change", sync);
  sync();

  quantumAsciiCleanup = () => {
    stop();
    observer?.disconnect();
    document.removeEventListener("visibilitychange", sync);
    motionPreference.removeEventListener?.("change", sync);
    quantumAsciiCleanup = () => {};
  };
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[char]);
}

function createConversationId() {
  const suffix = window.crypto?.randomUUID
    ? window.crypto.randomUUID()
    : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 14)}`;
  return `conversation-${suffix}`;
}

function safeHttpUrl(value) {
  try {
    const parsed = new URL(String(value));
    return ["http:", "https:"].includes(parsed.protocol) ? parsed.href : null;
  } catch {
    return null;
  }
}

async function api(path, options = {}) {
  const csrfToken = document.cookie
    .split("; ")
    .find(value => value.startsWith("csrftoken="))
    ?.split("=")
    .slice(1)
    .join("=");
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (csrfToken && !["GET", "HEAD", "OPTIONS", "TRACE"].includes(options.method || "GET")) {
    headers["X-CSRFToken"] = decodeURIComponent(csrfToken);
  }
  const response = await fetch(`api/v1${path}`, { ...options, headers });
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || `Request failed: ${response.status}`);
  return body;
}

function badgeClass(status) {
  return stateMeta(status).cls;
}

function badge(status, label = status) {
  const meta = stateMeta(status);
  return `<span class="badge ${meta.cls}" data-glyph="${meta.glyph}">${escapeHtml(label)}</span>`;
}

/* Duration is derived from the started_at / finished_at wall-clock timestamps
   the engine already persists. ADR 0007 specifies a per-stage event stream
   measured on a monotonic clock; until that exists this reports coarse
   task-level elapsed time and says so rather than implying more precision. */
function elapsedMs(from, to) {
  if (!from || !to) return null;
  const start = Date.parse(from);
  const end = Date.parse(to);
  return Number.isFinite(start) && Number.isFinite(end) && end >= start ? end - start : null;
}

function formatDuration(ms) {
  if (ms === null || ms === undefined) return null;
  if (ms < 1000) return `${ms} ms`;
  const seconds = ms / 1000;
  if (seconds < 60) return `${seconds.toFixed(seconds < 10 ? 1 : 0)} s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ${String(Math.round(seconds % 60)).padStart(2, "0")}s`;
  return `${Math.floor(minutes / 60)}h ${String(minutes % 60).padStart(2, "0")}m`;
}

function formatClock(value) {
  if (!value) return "—";
  const parsed = Date.parse(value);
  if (!Number.isFinite(parsed)) return value;
  return new Date(parsed).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "medium" });
}

function showToast(message) {
  const toast = document.createElement("div");
  toast.className = "toast";
  toast.textContent = message;
  document.querySelector("#toast-region").append(toast);
  setTimeout(() => toast.remove(), 3500);
}

/* A bare count hides whether 3 is most of the registry or a sliver of it.
   Each metric that is genuinely a part of a whole shows its denominator and a
   proportion meter; the two that are plain totals show neither. */
function metricTile({ value, total, label, color }) {
  const share = total ? Math.min(100, Math.round((value / total) * 100)) : null;
  const of = total ? `<span class="metric-of">/ ${total}</span>` : "";
  const meter = share === null ? "" :
    `<div class="meter" role="img" aria-label="${value} of ${total}, ${share} percent"><i style="width:${share}%;--meter-color:${color}"></i></div>`;
  return `<div class="metric">
    <div class="metric-value"><strong>${value}</strong>${of}</div>
    <span class="metric-label">${escapeHtml(label)}</span>${meter}
  </div>`;
}

function renderSummary() {
  const operations = state.capabilities.reduce((count, item) => count + item.operations.length, 0);
  const activeRuns = state.runs.filter(run => ["queued", "running"].includes(run.state)).length;
  const dataResources = dataCapabilities().reduce((count, item) => count + item.resources.length, 0);
  document.querySelector("#summary-strip").innerHTML = [
    { value: state.capabilities.length, label: "Integrated capabilities" },
    { value: dataResources, label: "Data resources" },
    { value: operations, label: "Executable operations" },
    { value: activeRuns, total: state.runs.length, label: "Active runs", color: "var(--run)" },
  ].map(metricTile).join("");
}

function textSearchBlob(values) {
  return values.flatMap(value => Array.isArray(value) ? value : [value])
    .filter(value => value !== null && value !== undefined)
    .join(" ")
    .toLowerCase();
}

function filteredTools() {
  const query = state.query.trim().toLowerCase();
  return state.capabilities.filter(item => {
    const operationText = item.operations.flatMap(operation => [operation.id, operation.title, operation.description || ""]);
    const resourceText = item.resources.flatMap(resource => [resource.id, resource.kind, resource.description || "", resource.uri]);
    const guidanceText = [
      item.guidance?.use_when || [],
      item.guidance?.quick_start || [],
      item.guidance?.limitations || [],
    ];
    const matchesQuery = !query || textSearchBlob([
      item.name,
      item.capability_name || item.name,
      item.id,
      item.catalog_repository,
      item.description,
      item.repository?.canonical_url,
      item.repository?.url,
      ...operationText,
      ...resourceText,
      ...guidanceText,
    ]).includes(query);
    return matchesQuery && (state.statusFilter === "all" || item.validation.status === state.statusFilter);
  });
}

function sectionHeader(title, detail, controls = "") {
  return `<div class="section-header"><div><h2>${escapeHtml(title)}</h2><p>${escapeHtml(detail)}</p></div>${controls}</div>`;
}

function workerDetail(worker) {
  const metadata = worker.metadata || {};
  return {
    targets: metadata.execution_targets || [],
    classes: metadata.execution_classes || [],
    runtimes: metadata.runtime_digests || [],
  };
}

function renderOverview() {
  quantumAsciiCleanup();
  const availableWorkers = state.workers.filter(worker => worker.available);
  const targets = new Set(state.workers.flatMap(worker => workerDetail(worker).targets));
  const workerSignals = state.workers.map(worker => {
    const detail = workerDetail(worker);
    const heartbeat = Number.isFinite(worker.heartbeat_age_seconds) ? `${worker.heartbeat_age_seconds.toFixed(1)} s ago` : "—";
    return `<article class="service-signal">
      <div class="service-signal-head">
        <span class="cell-title"><strong>${escapeHtml(worker.kind || "Execution worker")}</strong><small>${escapeHtml(worker.id)}</small></span>
        ${badge(worker.effective_state || worker.state)}
      </div>
      <dl>
        <div><dt>Targets</dt><dd>${escapeHtml(detail.targets.join(", ") || "—")}</dd></div>
        <div><dt>Classes</dt><dd>${escapeHtml(detail.classes.join(", ") || "—")}</dd></div>
        <div><dt>Runtimes</dt><dd>${detail.runtimes.length}</dd></div>
        <div><dt>Heartbeat</dt><dd>${escapeHtml(heartbeat)}</dd></div>
      </dl>
    </article>`;
  }).join("");
  const workflowLaunchers = state.workflows.slice(0, 4).map((workflow, index) => {
    const definition = workflow.definition;
    return `<button class="workflow-launch" type="button" data-overview-workflow="${escapeHtml(workflow.id)}/${escapeHtml(workflow.version)}">
      <span class="workflow-index" aria-hidden="true">${String(index + 1).padStart(2, "0")}</span>
      <span class="workflow-launch-name"><strong>${escapeHtml(definition.metadata.name)}</strong><small>${escapeHtml(workflow.id)} · v${escapeHtml(workflow.version)}</small></span>
      <span class="workflow-facts"><span>${definition.spec.nodes.length} nodes</span><span>${Object.keys(definition.spec.outputs).length} outputs</span></span>
      <span class="workflow-arrow" aria-hidden="true">↗</span>
    </button>`;
  }).join("");
  const runEvents = state.runs.slice(0, 5).map(run => `<button class="run-event" type="button" data-overview-run="${escapeHtml(run.id)}">
    <span class="run-event-line" aria-hidden="true"></span>
    <span class="run-event-copy"><strong>${escapeHtml(run.workflow_id)}</strong><small>${escapeHtml(run.id)}</small></span>
    <span class="run-event-meta">${badge(run.state)}<small>${escapeHtml(run.execution_target)} · ${escapeHtml(formatClock(run.created_at))}</small></span>
  </button>`).join("");
  const workerSummary = state.workers.length
    ? `${availableWorkers.length} of ${state.workers.length} workers available across ${targets.size} execution target${targets.size === 1 ? "" : "s"}`
    : "No execution workers have registered";
  workspace.innerHTML = `
    <section class="command-deck" aria-labelledby="eqo-qsc-heading">
      <div class="command-core">
        <span class="command-kicker"><i class="hex" aria-hidden="true"></i>EQO-QSC / LIVE ORCHESTRATION</span>
        <h2 id="eqo-qsc-heading">Integrate heterogeneous quantum–classical workflows across QHPC systems</h2>
        <p class="command-lede">Compose typed pipelines that coordinate quantum and classical stages across HPC resources and quantum runtimes, with exact provenance throughout the QSC software ecosystem.</p>
        <div class="command-actions">
          <button class="button command-primary" id="overview-compose" type="button">Compose a workflow <span aria-hidden="true">→</span></button>
          <button class="command-link" id="overview-showcases" type="button">Explore showcases</button>
          <button class="command-link" id="overview-runs" type="button">Inspect all runs</button>
        </div>
        <div class="workflow-launcher">
          <header>
            <div><span class="panel-label">QUICK COMPOSE</span><h3>Published starting points</h3></div>
            <span>${state.workflows.length} available</span>
          </header>
          <div class="workflow-launch-list">
            ${workflowLaunchers || `<p class="command-empty">No workflow templates are published.</p>`}
          </div>
        </div>
      </div>
      <figure
        class="qsc-ascii-stage command-instrument"
        role="img"
        aria-label="Animated schematic of a QEC and QHPC control loop. A logical state is encoded with a seven-qubit code, routed by a QHPC orchestrator to a QPU, returned as syndrome data to an HPC decoder, and recorded with its recovery frame as provenance."
      >
        <figcaption><span>QEC × QHPC instrument</span><strong>Logical-qubit control loop</strong></figcaption>
        <pre id="qsc-quantum-ascii" aria-hidden="true"></pre>
        <span class="instrument-state"><i aria-hidden="true"></i><span id="qsc-quantum-state">Explanatory sequence · not live telemetry</span></span>
      </figure>
      <section class="run-stream" aria-labelledby="recent-runs-heading">
        <header>
          <div><span class="panel-label">EVENT STREAM</span><h3 id="recent-runs-heading">Recent runs</h3></div>
          <button type="button" id="overview-runs-inline">View all</button>
        </header>
        <div class="run-event-list">
          ${runEvents || `<div class="run-stream-empty">
            <span aria-hidden="true">00</span>
            <strong>Run stream quiet</strong>
            <p>No workflow runs have been submitted. A queued workflow will appear here with its target and state.</p>
          </div>`}
        </div>
      </section>
    </section>
    <section class="execution-band" aria-labelledby="execution-services-heading">
      <header>
        <div>
          <span class="panel-label">RUNTIME FABRIC</span>
          <h2 id="execution-services-heading">Execution services</h2>
        </div>
        <p>${escapeHtml(workerSummary)}</p>
      </header>
      <div class="service-signal-list">
        ${workerSignals || `<div class="service-empty"><span class="hex" aria-hidden="true"></span><div><strong>Awaiting a worker</strong><p>Start an execution worker to make workflow submission available.</p></div></div>`}
      </div>
    </section>`;
  document.querySelector("#overview-compose").addEventListener("click", () => switchView("compose"));
  document.querySelector("#overview-showcases").addEventListener("click", () => switchView("showcases"));
  document.querySelector("#overview-runs").addEventListener("click", () => switchView("runs"));
  document.querySelector("#overview-runs-inline").addEventListener("click", () => switchView("runs"));
  workspace.querySelectorAll("[data-overview-workflow]").forEach(button => button.addEventListener("click", () => {
    selectWorkflow(button.dataset.overviewWorkflow);
    switchView("compose");
  }));
  workspace.querySelectorAll("[data-overview-run]").forEach(row => {
    row.addEventListener("click", () => openRun(row.dataset.overviewRun));
    row.addEventListener("keydown", event => {
      if (event.key === "Enter" || event.key === " ") { event.preventDefault(); openRun(row.dataset.overviewRun); }
    });
  });
  mountQuantumAsciiAnimation();
}

function openShowcaseWorkflow(workflowId) {
  const url = new URL(window.location.href);
  url.searchParams.set("workflow", workflowId);
  window.history.replaceState({}, "", url);
  switchView("compose");
}

function renderShowcases() {
  quantumAsciiCleanup();
  const ftqc = state.capabilities.find(item => item.id === "ftqc-compiler");
  const operation = ftqc?.operations?.find(item => item.id === "prepare-iqm");
  const hardwareOperation = ftqc?.operations?.find(item => item.id === "route-submit-collect");
  const runtimeDigest = operation?.runtime?.digest;
  const hardwareRuntimeDigest = hardwareOperation?.runtime?.digest;
  const readyWorker = Boolean(runtimeDigest && state.workers.some(worker => {
    const detail = workerDetail(worker);
    return worker.available
      && detail.targets.includes("local-development")
      && detail.classes.includes("interactive-local")
      && detail.runtimes.includes(runtimeDigest);
  }));
  const bellWorkflow = state.workflows.find(item => item.id === "ftqc-iqm-bell-preparation");
  const steaneWorkflow = state.workflows.find(item => item.id === "ftqc-iqm-steane-preparation");
  const steaneHardwareWorkflow = state.workflows.find(item => item.id === "ftqc-iqm-steane-execution");
  const hardwareWorker = hardwareRuntimeDigest && state.workers.find(worker => {
    const detail = workerDetail(worker);
    return worker.available
      && detail.targets.includes("local-development")
      && detail.classes.includes("quantum-backend")
      && detail.runtimes.includes(hardwareRuntimeDigest)
      && worker.metadata?.iqm?.mode !== "simulation";
  });
  const simulationWorker = hardwareRuntimeDigest && state.workers.find(worker => {
    const detail = workerDetail(worker);
    return worker.available
      && detail.targets.includes("local-development")
      && detail.classes.includes("quantum-backend")
      && detail.runtimes.includes(hardwareRuntimeDigest)
      && worker.metadata?.iqm?.mode === "simulation";
  });
  const iqmWorker = hardwareWorker?.metadata?.iqm || {};
  const hardwareGates = [
    {
      label: "Execution workflow",
      ready: Boolean(steaneHardwareWorkflow),
      detail: steaneHardwareWorkflow
        ? "Prepared circuit and report are both connected to the backend stage."
        : "The complete workflow has not been published to this control plane.",
    },
    {
      label: "Quantum-backend worker",
      ready: Boolean(hardwareWorker),
      detail: hardwareWorker
        ? `Worker ${hardwareWorker.id} admits the pinned IQM runtime.`
        : "Start the separately admitted IQM worker; local and Slurm workers cannot claim this task.",
    },
    {
      label: "Internal endpoint and device",
      ready: Boolean(iqmWorker.endpoint_configured && iqmWorker.device_alias),
      detail: iqmWorker.endpoint_configured && iqmWorker.device_alias
        ? `Device ${iqmWorker.device_alias} is configured for internal alpha use.`
        : "Configure the internal IQM endpoint and one device alias in the IQM worker.",
    },
    {
      label: "Worker-local credential",
      ready: Boolean(iqmWorker.credential_available),
      detail: iqmWorker.credential_available
        ? "A credential reference resolves only inside the quantum worker."
        : "The worker does not currently report an available credential reference.",
    },
  ];
  const hardwareReady = hardwareGates.every(gate => gate.ready);
  const simulationReady = Boolean(steaneHardwareWorkflow && simulationWorker);
  const hardwareActionLabel = hardwareReady
    ? "Open hardware execution workflow"
    : "Hardware execution unavailable";
  const localStatus = readyWorker ? "Runnable now" : "Runtime not ready";
  const localStatusClass = readyWorker ? "is-ready" : "is-waiting";
  const sourceRevision = ftqc?.repository?.revision?.slice(0, 12) || "779216de8805";
  const executionRun = latestIqmExecutionRun();
  const lifecycle = iqmExecutionLifecycle(executionRun);

  workspace.innerHTML = `
    <section class="showcase-hero" aria-labelledby="ftqc-showcase-title">
      <div class="showcase-hero-copy">
        <span class="showcase-kicker"><i class="hex" aria-hidden="true"></i>FLAGSHIP SHOWCASE · FTQC × IQM</span>
        <p class="showcase-sequence" aria-hidden="true">01 / LOGICAL&nbsp;&nbsp;→&nbsp;&nbsp;07 / PHYSICAL&nbsp;&nbsp;→&nbsp;&nbsp;IQM / NATIVE</p>
        <h2 id="ftqc-showcase-title">Prepare a fault-tolerant logical qubit for an IQM quantum computer</h2>
        <p class="showcase-lede">EQO turns an authored OpenQASM circuit into typed FTQC MLIR, expands one logical qubit through the Steane <strong>[[7,1,3]]</strong> code, and emits an IQM-native circuit—while preserving the exact compiler revision and every artifact handoff.</p>
        <div class="showcase-actions">
          <button class="button command-primary" type="button" data-showcase-workflow="ftqc-iqm-steane-preparation" ${steaneWorkflow ? "" : "disabled"}>Run logical-qubit preparation <span aria-hidden="true">→</span></button>
          <button class="command-link" type="button" data-showcase-workflow="ftqc-iqm-bell-preparation" ${bellWorkflow ? "" : "disabled"}>Run Bell preparation</button>
        </div>
      </div>
      <aside class="showcase-readout" aria-label="FTQC IQM showcase status">
        <span class="showcase-readout-label">DEMONSTRATION STATUS</span>
        <strong class="showcase-local-status ${localStatusClass}"><i aria-hidden="true"></i>${escapeHtml(localStatus)}</strong>
        <dl>
          <div><dt>Local preparation</dt><dd>Verified</dd></div>
          <div><dt>Source revision</dt><dd>${escapeHtml(sourceRevision)}</dd></div>
          <div><dt>Logical encoding</dt><dd>Steane [[7,1,3]]</dd></div>
          <div><dt>Hardware stage</dt><dd>Pending evidence</dd></div>
        </dl>
        <p>The FTQC runtime is locally installed and is not distributed by EQO until its license permits publication.</p>
      </aside>
    </section>

    <section class="showcase-trace" aria-labelledby="showcase-trace-title">
      <header>
        <div><span class="panel-label">EXECUTION TRACE</span><h2 id="showcase-trace-title">One workflow, explicit scientific boundaries</h2></div>
        <p>Solid stages run locally. The open stage requires current IQM calibration and backend credentials.</p>
      </header>
      <ol>
        <li class="is-complete"><span>01</span><div><strong>Author circuit</strong><small>OpenQASM 3 · one logical qubit</small></div></li>
        <li class="is-complete"><span>02</span><div><strong>Compile with FTQC</strong><small>Pinned C API · typed MLIR</small></div></li>
        <li class="is-complete"><span>03</span><div><strong>Expand the code block</strong><small>1 logical → 7 data qubits</small></div></li>
        <li class="is-complete"><span>04</span><div><strong>Emit IQM instructions</strong><small>PRX · CZ · measurement</small></div></li>
        <li class="is-boundary"><span>05</span><div><strong>Route and submit</strong><small>Live calibration · secured worker</small></div></li>
        <li class="is-boundary"><span>06</span><div><strong>Collect and decode</strong><small>Receipt · raw counts · logical result</small></div></li>
      </ol>
    </section>

    <section class="showcase-evidence-grid">
      <article class="showcase-proof" aria-labelledby="showcase-proof-title">
        <span class="panel-label">WHAT THE SHOWCASE PROVES</span>
        <h2 id="showcase-proof-title">Interoperability you can inspect</h2>
        <ul>
          <li><strong>Real compiler path</strong><span>EQO invokes FTQC through its constrained, pinned C API rather than replacing it with a mock.</span></li>
          <li><strong>Typed handoffs</strong><span>OpenQASM, FTQC MLIR, IQM JSON, and the preparation report are preserved as normal EQO artifacts.</span></li>
          <li><strong>Reproducible provenance</strong><span>The run records input and output digests, compiler revision, circuit width, instruction counts, and gate counts.</span></li>
          <li><strong>Secure hardware boundary</strong><span>IQM credentials never enter the browser or workflow document; submission belongs to an admitted backend worker.</span></li>
        </ul>
      </article>
      <aside class="showcase-result" aria-labelledby="showcase-result-title">
        <span class="panel-label">ACCEPTED LOCAL EVIDENCE</span>
        <h2 id="showcase-result-title">The output is concrete</h2>
        <div class="showcase-result-primary"><strong>7</strong><span>IQM loci from<br>one logical qubit</span></div>
        <dl>
          <div><dt>Logical |0⟩</dt><dd>58 instructions</dd></div>
          <div><dt>Four-H variant</dt><dd>114 instructions</dd></div>
          <div><dt>Bell circuit</dt><dd>2 loci · 9 instructions</dd></div>
        </dl>
        <div class="showcase-claim-boundary"><strong>Not yet claimed</strong><span>Hardware execution, decoded results, error suppression, or fault-tolerant advantage.</span></div>
      </aside>
    </section>

    <section class="showcase-gates" aria-labelledby="showcase-gates-title">
      <header>
        <div><span class="panel-label">HARDWARE ADMISSION</span><h2 id="showcase-gates-title">The next action is gated, not hidden</h2></div>
        <p>For the internal alpha, EQO enables the execution workflow only when its isolated worker can account for the runtime, configured device, and credential boundary.</p>
      </header>
      <ol>
        ${hardwareGates.map((gate, index) => `<li class="${gate.ready ? "is-ready" : "is-pending"}"><span>${String(index + 1).padStart(2, "0")}</span><div><strong>${escapeHtml(gate.label)}</strong><small>${escapeHtml(gate.detail)}</small></div><b>${gate.ready ? "Ready" : "Required"}</b></li>`).join("")}
      </ol>
      <footer>
        <p>${hardwareReady ? "The worker is configured. Opening the workflow still does not constitute a verified hardware claim." : "Preparation remains available without credentials while these gates are incomplete."}</p>
        <button class="button ${hardwareReady ? "command-primary" : "secondary"}" type="button" data-showcase-workflow="${escapeHtml(steaneHardwareWorkflow?.id || "")}" ${hardwareReady ? "" : "disabled"} title="${escapeHtml(hardwareReady ? "Open the separately admitted execution workflow" : "Complete the listed worker gates before opening hardware execution")}">${hardwareActionLabel}<span aria-hidden="true">→</span></button>
      </footer>
    </section>

    <section class="showcase-execution-status" aria-labelledby="showcase-execution-status-title" aria-live="polite">
      <div>
        <span class="panel-label">EXECUTION LIFECYCLE</span>
        <h2 id="showcase-execution-status-title">${escapeHtml(lifecycle.status)}</h2>
        <p>${escapeHtml(lifecycle.detail)}</p>
      </div>
      <div class="showcase-execution-actions">
        <span class="showcase-execution-state is-${escapeHtml(lifecycle.tone)}">${escapeHtml(lifecycle.status)}</span>
        ${executionRun ? `<button class="button secondary" type="button" data-showcase-run="${escapeHtml(executionRun.id)}">Open run record</button>` : ""}
      </div>
    </section>

    <section class="showcase-simulation" aria-labelledby="showcase-simulation-title">
      <div>
        <span class="panel-label">SAFE DEMONSTRATION MODE</span>
        <h2 id="showcase-simulation-title">Practice the typed route-and-collect boundary without IQM access</h2>
        <p>${simulationReady
          ? "The local simulation worker is available. It uses no network connection or credential, and labels every output as simulated-iqm rather than hardware evidence."
          : "Start EQO Local with --iqm-simulation to make the credential-free simulated worker available. It cannot contact IQM or create a hardware claim."}</p>
      </div>
      <button class="button ${simulationReady ? "command-primary" : "secondary"}" type="button" data-showcase-workflow="${escapeHtml(steaneHardwareWorkflow?.id || "")}" ${simulationReady ? "" : "disabled"} title="${escapeHtml(simulationReady ? "Open the simulated execution workflow" : "Start the safe IQM simulation worker first")}">${simulationReady ? "Open simulated execution workflow" : "Simulation worker unavailable"}<span aria-hidden="true">→</span></button>
    </section>`;

  workspace.querySelectorAll("[data-showcase-workflow]").forEach(button => {
    button.addEventListener("click", () => openShowcaseWorkflow(button.dataset.showcaseWorkflow));
  });
  workspace.querySelectorAll("[data-showcase-run]").forEach(button => {
    button.addEventListener("click", () => openRun(button.dataset.showcaseRun));
  });
}

function repositoryDisplay(item) {
  const source = item.repository?.canonical_url || item.repository?.url || item.catalog_repository || "—";
  const revision = item.repository?.revision || "unversioned";
  try {
    const parsed = new URL(source);
    return {
      label: parsed.pathname.replace(/^\/|\.git$/g, "") || parsed.hostname,
      detail: revision,
    };
  } catch {
    return { label: source, detail: revision };
  }
}

function renderTools() {
  const statuses = [...new Set(state.capabilities.map(item => item.validation.status))].sort().map(status => `<option value="${status}" ${state.statusFilter === status ? "selected" : ""}>${status}</option>`).join("");
  const rows = filteredTools().map(item => {
    const repository = repositoryDisplay(item);
    return `<tr data-capability="${item.id}" tabindex="0">
    <td><span class="cell-title tool-catalog-title"><strong>${escapeHtml(item.name)}</strong><span class="tool-catalog-purpose">${escapeHtml(item.description)}</span><small>${escapeHtml(item.capability_name || item.name)} · ${escapeHtml(item.id)}@${escapeHtml(item.version)}</small></span></td>
    <td><span class="cell-title"><strong>${escapeHtml(repository.label)}</strong><small>${escapeHtml(repository.detail)}</small></span></td>
    <td>${badge(item.validation.status)} ${badge(item.maturity)}</td>
    <td class="numeric">${item.operations.length}</td><td class="numeric">${item.resources.length}</td>
    <td>${badge(item.integration.runtime_status)}</td>
  </tr>`;
  }).join("");
  workspace.innerHTML = sectionHeader("Tool catalog", `${filteredTools().length} of ${state.capabilities.length} integrated tools · Select a row to open its usage guide`) + `
    <div class="toolbar"><select id="status-filter"><option value="all">All validation states</option>${statuses}</select></div>
    <table class="data-table tool-catalog"><thead><tr><th>TOOL / PURPOSE</th><th>SOURCE / REVISION</th><th>VALIDATION</th><th>OPERATIONS</th><th>RESOURCES</th><th>RUNTIME</th></tr></thead><tbody>${rows || `<tr><td colspan="6">No tools match the current filters.</td></tr>`}</tbody></table>`;
  document.querySelector("#status-filter").addEventListener("change", event => { state.statusFilter = event.target.value; renderTools(); });
  workspace.querySelectorAll("[data-capability]").forEach(row => {
    row.addEventListener("click", () => openCapability(row.dataset.capability));
    row.addEventListener("keydown", event => {
      if (event.key === "Enter" || event.key === " ") { event.preventDefault(); openCapability(row.dataset.capability); }
    });
  });
}

function titleLabel(value) {
  return String(value || "")
    .replaceAll("-", " ")
    .replaceAll("_", " ")
    .replace(/\b\w/g, character => character.toUpperCase());
}

function dataResourceRole(resource) {
  const text = textSearchBlob([resource.id, resource.kind, resource.description || "", resource.uri]);
  if (resource.kind === "schema") return "Schema";
  if (resource.kind === "data-service") return "Data Service";
  if (resource.kind === "provenance") return "Provenance";
  if (resource.kind === "artifact-type") return "Schema";
  if (resource.kind === "dataset") return "Dataset";
  if (resource.kind === "adapter") return "Adapter";
  if (resource.kind === "documentation") return "Documentation";
  if (text.includes("provenance") || text.includes("lineage") || hasSdlToken(text)) return "Provenance";
  return titleLabel(resource.kind || "resource");
}

function hasSdlToken(text) {
  return /(^|[^a-z0-9])sdl([^a-z0-9]|$)/.test(text);
}

function dataCapabilityText(item) {
  return textSearchBlob([
    item.id,
    item.name,
    item.capability_name,
    item.catalog_repository,
    item.project,
    item.description,
    item.repository?.url,
    item.repository?.canonical_url,
    item.resources.flatMap(resource => [resource.id, resource.kind, resource.description || "", resource.uri]),
    item.guidance?.use_when || [],
    item.guidance?.quick_start || [],
    item.guidance?.limitations || [],
  ]);
}

function isDataCapability(item) {
  const text = dataCapabilityText(item);
  return item.project === "data-schema"
    || item.catalog_repository === "DataSchema"
    || text.includes("materials-db")
    || text.includes("materials db")
    || text.includes("scientific data layer")
    || hasSdlToken(text);
}

function dataCapabilities() {
  return state.capabilities
    .filter(isDataCapability)
    .sort((left, right) => {
      const leftMaterials = dataCapabilityText(left).includes("materials");
      const rightMaterials = dataCapabilityText(right).includes("materials");
      if (leftMaterials !== rightMaterials) return leftMaterials ? -1 : 1;
      return left.name.localeCompare(right.name);
    });
}

function filteredDataCapabilities() {
  const query = state.query.trim().toLowerCase();
  return dataCapabilities().filter(item => !query || dataCapabilityText(item).includes(query));
}

function dataServiceKind(item) {
  const text = dataCapabilityText(item);
  if (text.includes("materials-db") || text.includes("materials db")) return "SDL service";
  if (item.resources.some(resource => dataResourceRole(resource) === "Dataset")) return "Dataset";
  if (item.resources.some(resource => dataResourceRole(resource) === "Schema")) return "Schema";
  return "Data resource";
}

function dataObjectsPrefix(item) {
  // The registry doesn't publish a storage prefix per capability yet, so
  // this reuses the same materials-db text heuristic as isDataCapability
  // rather than inventing a second, more general mechanism for the one
  // live-backed data service that exists so far.
  const text = dataCapabilityText(item);
  if (text.includes("materials-db") || text.includes("materials db")) return "materials-db/";
  return null;
}

function ensureDataObjectsLoaded(prefix) {
  if (!prefix) return;
  const cached = state.dataObjectsByPrefix[prefix];
  if (cached && (cached.loading || cached.loadedAt)) return;
  state.dataObjectsByPrefix[prefix] = {
    loading: true,
    available: null,
    bucket: null,
    objects: [],
    error: null,
    loadedAt: null,
  };
  api(`/data/objects?prefix=${encodeURIComponent(prefix)}`)
    .then(body => {
      state.dataObjectsByPrefix[prefix] = {
        loading: false,
        available: Boolean(body.available),
        bucket: body.bucket || null,
        objects: body.objects || [],
        error: null,
        loadedAt: Date.now(),
      };
    })
    .catch(error => {
      state.dataObjectsByPrefix[prefix] = {
        loading: false,
        available: false,
        bucket: null,
        objects: [],
        error: error.message,
        loadedAt: Date.now(),
      };
    })
    .finally(() => {
      if (state.view === "data") renderData();
    });
}

function evidenceList(item) {
  return [...new Set([
    ...(item.integration?.evidence || []),
    ...(item.validation?.evidence || []),
  ])];
}

function resourceSourceLink(resource) {
  const href = safeHttpUrl(resource.uri);
  return href
    ? `<a href="${escapeHtml(href)}" target="_blank" rel="noreferrer">Open source <span aria-hidden="true">↗</span></a>`
    : `<code>${escapeHtml(resource.uri)}</code>`;
}

function dataDetail(item) {
  if (!item) {
    return `<section class="data-detail data-detail-empty">
      <span class="empty-code">DAT</span>
      <h2>No data service selected</h2>
      <p>Admitted SDL-backed services and governed datasets will appear here when their registry resources are available.</p>
    </section>`;
  }
  const repository = repositoryDisplay(item);
  const canonicalRepository = item.repository?.canonical_url || item.repository?.url || "";
  const documentationUrl = safeHttpUrl(item.documentation?.url);
  const knowledgeNodeId = qappswikiNodeId(item.documentation?.qappswiki);
  const resources = item.resources.map(resource => `
    <article class="data-resource-card">
      <header>
        <span>${escapeHtml(dataResourceRole(resource))}</span>
        <strong>${escapeHtml(resource.id)}</strong>
      </header>
      <dl>
        <div><dt>Version</dt><dd>${escapeHtml(resource.version)}</dd></div>
        <div><dt>Kind</dt><dd>${escapeHtml(resource.kind)}</dd></div>
        ${resource.digest ? `<div><dt>Digest</dt><dd>${escapeHtml(resource.digest)}</dd></div>` : ""}
      </dl>
      ${resource.description ? `<p>${escapeHtml(resource.description)}</p>` : ""}
      <footer>${resourceSourceLink(resource)}</footer>
    </article>`).join("");
  const evidence = evidenceList(item);
  const evidenceRows = evidence.length
    ? evidence.map(reference => `<li><code>${escapeHtml(reference)}</code></li>`).join("")
    : `<li><span>No separate evidence reference is published.</span></li>`;
  const sourceReviewed = item.integration?.project_reviewed ? "yes" : "no";
  const objectsPrefix = dataObjectsPrefix(item);
  const objectsState = objectsPrefix ? state.dataObjectsByPrefix[objectsPrefix] : null;
  const liveObjectsBody = !objectsPrefix
    ? ""
    : !objectsState || objectsState.loading
      ? `<p class="tool-record-empty">Loading live objects from databucket…</p>`
      : !objectsState.available
        ? `<p class="tool-record-empty">databucket/Garage is not configured for this Workbench — start it with <code>eqo dev up</code> (without <code>--no-databucket</code>).</p>`
        : objectsState.objects.length
          ? `<table class="data-table"><thead><tr><th>KEY</th><th>SIZE</th><th>LAST MODIFIED</th><th>ACTIONS</th></tr></thead><tbody>${objectsState.objects.map(object => {
              const contentPath = `api/v1/data/objects/content?key=${encodeURIComponent(object.key)}`;
              return `<tr><td><code>${escapeHtml(object.key)}</code></td><td>${escapeHtml(object.size)} B</td><td>${escapeHtml(object.last_modified)}</td><td><span class="artifact-actions"><a class="button secondary" href="${contentPath}" target="_blank" rel="noopener">Preview</a><a class="button secondary" href="${contentPath}&download=1">Download</a></span></td></tr>`;
            }).join("")}</tbody></table>`
          : `<p class="tool-record-empty">Bucket '${escapeHtml(objectsState.bucket || "")}' has no objects under this prefix yet.</p>`;
  const liveObjectsSection = !objectsPrefix ? "" : `
    <section class="data-detail-section">
      <div class="data-section-title"><h3>Live Object Storage (databucket)</h3><span>${objectsState?.objects?.length ?? 0}</span></div>
      ${liveObjectsBody}
    </section>`;
  return `<section class="data-detail">
    <header class="data-detail-head">
      <div>
        <span class="panel-label">${escapeHtml(dataServiceKind(item))}</span>
        <h2>${escapeHtml(item.name)}</h2>
        <p>${escapeHtml(item.description)}</p>
      </div>
      <div class="data-detail-status">
        ${badge(item.validation.status)}
        ${badge(item.integration.runtime_status)}
      </div>
    </header>
    <dl class="data-facts">
      <div><dt>Capability</dt><dd>${escapeHtml(item.id)}@${escapeHtml(item.version)}</dd></div>
      <div><dt>Source</dt><dd>${escapeHtml(repository.label)}</dd></div>
      <div><dt>Revision</dt><dd title="${escapeHtml(item.repository?.revision || "")}">${escapeHtml(repository.detail)}</dd></div>
      <div><dt>Resources</dt><dd>${item.resources.length}</dd></div>
    </dl>
    <section class="data-detail-section">
      <div class="data-section-title"><h3>Published Data Resources</h3><span>${item.resources.length}</span></div>
      <div class="data-resource-grid">${resources || `<p class="tool-record-empty">No data resources are published for this service.</p>`}</div>
    </section>
    ${liveObjectsSection}
    <section class="data-detail-section">
      <div class="data-section-title"><h3>Provenance Ledger</h3><span>${evidence.length}</span></div>
      <dl class="data-provenance-ledger">
        <div><dt>Repository</dt><dd>${escapeHtml(canonicalRepository || "unresolved")}</dd></div>
        <div><dt>Catalog component</dt><dd>${escapeHtml(item.catalog_repository)}</dd></div>
        <div><dt>Source ownership</dt><dd>${escapeHtml(SOURCE_AREAS[item.project] || item.project)}</dd></div>
        <div><dt>Integration authority</dt><dd>${escapeHtml(item.integration.authority)}</dd></div>
        <div><dt>Curated by</dt><dd>${escapeHtml((item.integration.maintainers || []).join(", ") || "unassigned")}</dd></div>
        <div><dt>Source reviewed</dt><dd>${sourceReviewed}</dd></div>
      </dl>
      <ul class="data-evidence-list">${evidenceRows}</ul>
    </section>
    <div class="data-actions">
      <button class="button secondary" id="data-open-record" type="button">Open Registry Record</button>
      ${knowledgeNodeId ? `<button class="button secondary" id="data-open-knowledge" type="button">Explore Knowledge Link</button>` : ""}
      ${documentationUrl ? `<a class="button secondary" href="${escapeHtml(documentationUrl)}" target="_blank" rel="noreferrer">Open Documentation</a>` : ""}
    </div>
  </section>`;
}

function renderData() {
  const allData = dataCapabilities();
  const filtered = filteredDataCapabilities();
  const hasQuery = Boolean(state.query.trim());
  const selected = filtered.find(item => item.id === state.selectedDataService)
    || (!hasQuery ? allData.find(item => item.id === state.selectedDataService) : null)
    || filtered[0]
    || (!hasQuery ? allData[0] : null)
    || null;
  if (selected) state.selectedDataService = selected.id;
  const totalResources = allData.reduce((count, item) => count + item.resources.length, 0);
  const hasMaterialsDb = allData.some(item => {
    const text = dataCapabilityText(item);
    return text.includes("materials-db") || text.includes("materials db");
  });
  new Set(allData.map(dataObjectsPrefix).filter(Boolean)).forEach(ensureDataObjectsLoaded);
  const serviceRows = filtered.map(item => {
    const repository = repositoryDisplay(item);
    const objectsState = state.dataObjectsByPrefix[dataObjectsPrefix(item)];
    const liveBadge = objectsState?.available && objectsState.objects.length
      ? `<span class="badge blue" data-glyph="●">Live · ${objectsState.objects.length} object${objectsState.objects.length === 1 ? "" : "s"}</span>`
      : "";
    return `<button class="data-service-card ${selected?.id === item.id ? "active" : ""}" type="button" data-data-service="${escapeHtml(item.id)}">
      <span>${escapeHtml(dataServiceKind(item))}</span>
      <strong>${escapeHtml(item.name)}</strong>
      <small>${escapeHtml(item.id)}@${escapeHtml(item.version)}</small>
      <span class="data-service-meta">${badge(item.validation.status)}${liveBadge}<em>${item.resources.length} resources</em></span>
      <small>${escapeHtml(repository.label)}</small>
    </button>`;
  }).join("");
  const materialsSlot = hasMaterialsDb
    ? ""
    : `<aside class="data-sdl-slot" aria-label="SDL materials-db integration slot">
        <span class="panel-label">SDL SERVICE SLOT</span>
        <strong>materials-db</strong>
        <p>Awaiting an admitted data-service contract or registry resource from the Scientific Data Layer.</p>
      </aside>`;
  workspace.innerHTML = sectionHeader(
    "Data services",
    `${allData.length} admitted data component${allData.length === 1 ? "" : "s"} · ${totalResources} published resource${totalResources === 1 ? "" : "s"}`,
  ) + `
    <section class="data-command" aria-labelledby="data-command-heading">
      <div>
        <span class="panel-label">DATA / SCIENTIFIC DATA LAYER</span>
        <h2 id="data-command-heading">Governed datasets and SDL-backed services</h2>
        <p>Data stays discoverable without becoming an execution tool. Admitted records can show live object-storage contents from databucket when it's running; selected records can become QHPC artifacts only after an explicit materialization path exists.</p>
      </div>
      <dl>
        <div><dt>Components</dt><dd>${allData.length}</dd></div>
        <div><dt>Resources</dt><dd>${totalResources}</dd></div>
        <div><dt>Operations</dt><dd>${allData.reduce((count, item) => count + item.operations.length, 0)}</dd></div>
      </dl>
    </section>
    <div class="data-layout">
      <aside class="data-services-panel" aria-label="Data service registry">
        <label class="data-search">
          <span aria-hidden="true">⌕</span>
          <input id="data-search" type="search" value="${escapeHtml(state.query)}" placeholder="Search data resources" aria-label="Search data resources">
        </label>
        <div class="data-service-list">
          ${serviceRows || `<div class="data-empty"><strong>No matching data resources</strong><p>Clear search to show admitted data components.</p></div>`}
        </div>
        ${materialsSlot}
      </aside>
      ${dataDetail(selected)}
    </div>`;
  document.querySelector("#data-search").addEventListener("input", event => {
    state.query = event.target.value;
    document.querySelector("#global-search").value = state.query;
    renderData();
  });
  workspace.querySelectorAll("[data-data-service]").forEach(button => {
    button.addEventListener("click", () => {
      state.selectedDataService = button.dataset.dataService;
      const url = new URL(window.location.href);
      url.searchParams.set("view", "data");
      url.searchParams.set("data_service", state.selectedDataService);
      window.history.replaceState({}, "", url);
      renderData();
    });
  });
  document.querySelector("#data-open-record")?.addEventListener("click", () => openCapability(selected.id));
  document.querySelector("#data-open-knowledge")?.addEventListener("click", () => {
    state.knowledgeNode = qappswikiNodeId(selected.documentation?.qappswiki);
    switchView("knowledge");
  });
}

function renderKnowledge() {
  workspace.innerHTML = `<div id="knowledge-root"><div class="loading">LOADING QAPPSWIKI KNOWLEDGE GRAPH</div></div>`;
  const root = document.querySelector("#knowledge-root");
  if (!window.QHPCKnowledge) {
    const mountWhenReady = () => {
      if (state.view === "knowledge" && window.QHPCKnowledge) renderKnowledge();
    };
    window.addEventListener("qhpc-knowledge-ready", mountWhenReady, { once: true });
    window.setTimeout(() => {
      if (state.view !== "knowledge" || window.QHPCKnowledge) return;
      root.innerHTML = `<div class="empty-state"><div><span class="empty-code">KN</span><h2>Knowledge Explorer is unavailable</h2><p>The Knowledge Explorer bundle did not finish loading. Retry the view, or refresh the Workbench if the problem persists.</p><button class="button secondary" id="knowledge-retry" type="button">Retry Knowledge Explorer</button></div></div>`;
      document.querySelector("#knowledge-retry")?.addEventListener("click", renderKnowledge);
    }, 1500);
    return;
  }
  window.QHPCKnowledge.mount(root, { initialNodeId: state.knowledgeNode });
}

function capabilityResourceUrl(capabilityId, resourceId, fallbackUrl) {
  const capability = state.capabilities.find(item => item.id === capabilityId);
  const resource = capability?.resources?.find(item => item.id === resourceId);
  return safeHttpUrl(resource?.uri) || fallbackUrl;
}

function externalResourceLink(url, label) {
  const href = safeHttpUrl(url);
  if (!href) return `<span class="openqse-link-disabled">${escapeHtml(label)}</span>`;
  return `<a href="${escapeHtml(href)}" target="_blank" rel="noopener noreferrer">${escapeHtml(label)} <span aria-hidden="true">↗</span></a>`;
}

function renderOpenQSE() {
  quantumAsciiCleanup();
  const specRevision = "c172c716e6566bd0a7502b34896dce7467f5a474";
  const qfwRevision = "eeb42e601383f3d33020f823d4a387ef30b9dd7d";
  const glossaryUrl = capabilityResourceUrl(
    "openqse-specification",
    "openqse-glossary",
    `https://github.com/openQSE/openqse-spec/tree/${specRevision}/specification/term`,
  );
  const architectureUrl = capabilityResourceUrl(
    "openqse-specification",
    "openqse-architecture",
    `https://github.com/openQSE/openqse-spec/tree/${specRevision}/architecture`,
  );
  const specificationUrl = `https://github.com/openQSE/openqse-spec/tree/${specRevision}`;

  workspace.innerHTML = sectionHeader(
    "OpenQSE resource panel",
    "Organization documentation and repository discovery — no EQO tool, service, or execution target is created here.",
  ) + `
    <section class="openqse-hero" aria-labelledby="openqse-hero-title">
      <div class="openqse-hero-copy">
        <span class="panel-label">OPEN QUANTUM SYSTEMS ENGINEERING</span>
        <h2 id="openqse-hero-title">A community and repository catalog, not an EQO runtime</h2>
        <p>OpenQSE is an organization with multiple independent projects. This panel makes its public documentation and repository catalog easy to reach while keeping admission explicit: a repository is not automatically an integrated tool, service, container, or workflow target.</p>
        <div class="openqse-hero-actions">
          ${externalResourceLink("https://github.com/openQSE", "Browse OpenQSE on GitHub")}
          ${externalResourceLink(specificationUrl, "Open the specification repository")}
        </div>
      </div>
      <aside class="openqse-boundary" aria-label="OpenQSE integration boundary">
        <span class="panel-label">EQO BOUNDARY</span>
        <strong>Read-only discovery</strong>
        <p>Documentation links and source intake are exposed here. Run, build, credential, and hardware controls remain outside this panel.</p>
        ${badge("pending", "No service or execution admission")}
      </aside>
    </section>

    <section class="openqse-resource-grid" aria-label="OpenQSE documentation and source records">
      <article class="openqse-resource-card">
        <header><span>PINNED DOCUMENTATION</span><h3>OpenQSE specification</h3></header>
        <p>The reviewed glossary and architecture resources used by EQO for shared systems-engineering terminology and definitions.</p>
        <dl>
          <div><dt>PINNED REVISION</dt><dd><code>${specRevision.slice(0, 12)}</code></dd></div>
          <div><dt>ADMISSION</dt><dd>Non-executable resource</dd></div>
        </dl>
        <footer>
          ${externalResourceLink(glossaryUrl, "Glossary")}
          ${externalResourceLink(architectureUrl, "Architecture")}
        </footer>
      </article>

      <article class="openqse-resource-card">
        <header><span>ORGANIZATION CATALOG</span><h3>OpenQSE repositories</h3></header>
        <p>Explore the organization’s public projects directly. Each project retains its own source authority, licensing, interface, runtime, and security review; browsing the catalog does not admit any of them to EQO.</p>
        <dl>
          <div><dt>SURFACE</dt><dd>Public GitHub organization</dd></div>
          <div><dt>EQO TREATMENT</dt><dd>Community resource</dd></div>
        </dl>
        <footer>${externalResourceLink("https://github.com/openQSE?tab=repositories", "Browse repositories")}</footer>
      </article>

      <article class="openqse-resource-card openqse-qfw-card">
        <header><span>VALIDATED DEVELOPMENT FIXTURE</span><h3>QFw–SLURM Cluster</h3></header>
        <p>OpenQSE’s Docker Compose environment for QFw development, integration testing, and profiling. It is a distinct development-cluster reference, not the EQO scheduler-conformance cluster.</p>
        <dl>
          <div><dt>PINNED SOURCE</dt><dd><code>${qfwRevision.slice(0, 12)}</code></dd></div>
          <div><dt>STATUS</dt><dd>Validated office development simulation</dd></div>
        </dl>
        <footer>
          ${externalResourceLink(`https://github.com/openQSE/QFw-SLURM-Cluster/tree/${qfwRevision}`, "Source and README")}
          ${externalResourceLink(`https://github.com/openQSE/QFw-SLURM-Cluster/tree/${qfwRevision}/docs`, "Project documentation")}
        </footer>
      </article>
    </section>

    <section class="openqse-admission-note" aria-labelledby="openqse-admission-title">
      <div>
        <span class="panel-label">QFW–SLURM ADMISSION</span>
        <h2 id="openqse-admission-title">Validated without becoming a workflow target</h2>
      </div>
      <p>The public immutable Linux/AMD64 compatibility image is admitted with pinned material inputs, secure transport, SBOM, signature, provenance, and office scheduler evidence. EQO may start this development fixture, but it is not a workflow, CLI, or Workbench execution target: a separately reviewed QFw operation or target-adapter contract is still required.</p>
    </section>`;
}

function renderEngagement() {
  quantumAsciiCleanup();
  const resources = state.engagement.resources;
  workspace.innerHTML = sectionHeader(
    "Engagement resources",
    "Learning materials and community events shared by the Engagement Thrust — links only; no EQO tool, service, runtime, or workflow target is created here.",
  ) + `
    <section class="engagement-intro" aria-labelledby="engagement-title">
      <div class="engagement-intro-copy">
        <span class="panel-label">ENGAGEMENT THRUST</span>
        <h2 id="engagement-title">Learning paths that stay connected to the ecosystem</h2>
        <p>Find course material, training tutorials, and a community event without blurring the boundary between learning resources and operational EQO capabilities. Each destination remains owned and maintained at its source.</p>
      </div>
      <aside class="engagement-boundary" aria-label="Engagement resource boundary">
        <span class="panel-label">EQO BOUNDARY</span>
        <strong>Read-only resource directory</strong>
        <p>These links help people learn and connect. They do not provision infrastructure, expose credentials, or submit workloads.</p>
        ${badge("pending", "No service or execution admission")}
      </aside>
    </section>

    <section class="engagement-resource-ledger" aria-label="Engagement learning resources">
      ${resources.length ? resources.map((resource, index) => {
        const kind = String(resource.kind || "resource").replaceAll("-", " ").toUpperCase();
        const provider = String(resource.provider || "external source").toUpperCase();
        const classes = ["engagement-resource"];
        if (index === 0) classes.push("engagement-resource-featured");
        if (resource.kind === "community-event") classes.push("engagement-resource-event");
        return `<article class="${classes.join(" ")}">
          <div class="engagement-resource-kind">${escapeHtml(kind)} · ${escapeHtml(provider)}</div>
          <div class="engagement-resource-body">
            <h3>${escapeHtml(resource.title || "Engagement resource")}</h3>
            <p>${escapeHtml(resource.description || "Public Engagement Thrust resource.")}</p>
          </div>
          <footer>${externalResourceLink(resource.url, `Open ${resource.title || "resource"}`)}</footer>
        </article>`;
      }).join("") : `<p class="engagement-empty">No Engagement resources are currently published by this EQO endpoint.</p>`}
    </section>

    <section class="engagement-note" aria-labelledby="engagement-note-title">
      <div>
        <span class="panel-label">RESOURCE TREATMENT</span>
        <h2 id="engagement-note-title">Visible in EQO, operational elsewhere</h2>
      </div>
      <p>Use these sources to discover learning opportunities and community participation. Integration, containerization, hardware admission, and workflow registration each remain separate reviewed paths.</p>
    </section>`;
}

function assistantAnswerHtml(value) {
  return String(value ?? "")
    .split(/\n\s*\n/)
    .filter(Boolean)
    .map(block => {
      const safe = escapeHtml(block)
        .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
        .replace(/\n/g, "<br>");
      return `<p>${safe}</p>`;
    })
    .join("");
}

function assistantCitations() {
  const citations = [];
  const seen = new Set();
  state.assistant.messages.forEach(message => {
    if (message.role !== "assistant" || message.streaming || message.interrupted) return;
    (message.citations || []).forEach(citation => {
      const key = citation.id
        || `${citation.source_uri || citation.url || ""}\0${citation.locator || ""}`;
      if (!seen.has(key)) {
        seen.add(key);
        citations.push(citation);
      }
    });
  });
  return citations;
}

function boundedAssistantHistory(messages) {
  const eligible = messages
    .filter(message => ["user", "assistant"].includes(message.role) && !message.streaming && !message.interrupted)
    .map(message => ({ role: message.role, content: String(message.content || "").slice(0, 8000) }));
  const kept = [];
  let characters = 0;
  for (const message of eligible.slice(-ASSISTANT_HISTORY_MESSAGE_LIMIT).reverse()) {
    if (characters + message.content.length > ASSISTANT_HISTORY_CHARACTER_BUDGET) break;
    kept.push(message);
    characters += message.content.length;
  }
  const history = kept.reverse();
  const omitted = eligible.length - history.length;
  return {
    history,
    notice: omitted > 0
      ? `For this answer, ChatQEC received the most recent ${history.length} conversation message${history.length === 1 ? "" : "s"}; ${omitted} older message${omitted === 1 ? " was" : "s were"} omitted to stay within the ${ASSISTANT_HISTORY_CHARACTER_BUDGET.toLocaleString()}-character context budget.`
      : "",
  };
}

function assistantMessageHtml(message) {
  if (message.role === "user") {
    return `<article class="assistant-message user">
      <span class="assistant-role">YOU</span>
      <div>${assistantAnswerHtml(message.content)}</div>
    </article>`;
  }
  if (message.role === "error") {
    return `<article class="assistant-message assistant-error" role="alert">
      <span class="assistant-role">ERROR</span>
      <div><p>${escapeHtml(message.content)}</p></div>
    </article>`;
  }
  const streaming = message.streaming === true;
  const interrupted = message.interrupted === true;
  const confidence = Number(message.confidence);
  const totalLatency = Number(message.latency_ms?.total);
  const footer = streaming
    ? ["Receiving a verified response stream…"]
    : interrupted
      ? ["Cancelled before ChatQEC returned its verified final response."]
      : [
    message.provider && message.model
      ? `${escapeHtml(message.provider)} / ${escapeHtml(message.model)}`
      : "",
    Number.isFinite(confidence)
      ? `${Math.round(confidence * 100)}% confidence`
      : "",
    Number.isFinite(totalLatency)
      ? `${totalLatency.toFixed(totalLatency < 10 ? 1 : 0)} ms`
      : "",
    message.citations?.length
      ? `${message.citations.length} cited source${message.citations.length === 1 ? "" : "s"}`
      : "No cited source",
    message.tool_calls?.length
      ? `Executed: ${message.tool_calls.map(call => call.name).join(", ")}`
      : "",
  ];
  const content = message.content || (streaming
    ? "Preparing a cited response…"
    : interrupted
      ? "This response was cancelled. Ask again when you are ready to receive a complete, cited answer."
      : "ChatQEC returned an empty answer.");
  return `<article class="assistant-message assistant">
    <span class="assistant-role">CHATQEC</span>
    <div>
      ${assistantAnswerHtml(content)}
      <footer>${footer.filter(Boolean).map(item => `<span>${item}</span>`).join("")}</footer>
    </div>
  </article>`;
}

function assistantCitationHtml(citation, index) {
  const sourceUri = citation.source_uri || citation.url;
  const href = safeHttpUrl(sourceUri);
  const title = escapeHtml(citation.title || citation.id || `Source ${index + 1}`);
  const source = href
    ? `<a href="${escapeHtml(href)}" target="_blank" rel="noopener noreferrer">${title}</a>`
    : `<strong>${title}</strong>`;
  const locator = citation.locator
    ? `<small>${escapeHtml(citation.locator)}</small>`
    : "";
  const revision = citation.source_revision
    ? `<code>${escapeHtml(citation.source_revision)}</code>`
    : "";
  return `<li>
    <span class="assistant-citation-index">[${index + 1}]</span>
    <div>${source}${locator}${revision}</div>
  </li>`;
}

function assistantServiceView() {
  const service = state.assistant.status;
  const available = service?.available === true;
  const checking = service === null;
  const fallback = service?.mode === "canonical-corpus-extractive-fallback"
    || service?.mode === "canonical-extractive-development";
  const directTools = service?.mode === "mcp-direct-tools";
  const missing = Object.entries(service?.readiness || {})
    .filter(([, value]) => !["ready", "disabled"].includes(value))
    .map(([name]) => name);
  return {
    service,
    available,
    checking,
    state: checking ? "pending" : available ? "online" : "offline",
    label: checking ? "checking" : available && fallback ? "fallback" : available ? "ready" : "unavailable",
    detail: checking
      ? "Verifying the canonical corpus"
      : available
        ? fallback
          ? `${service.pages} canonical pages · deterministic extractive fallback`
          : directTools
            ? "MCP circuit tools are ready in the ChatQEC container · model-backed RAG needs provider and corpus configuration"
          : `${service.pages} governed corpus pages · source ${String(service.source_revision).slice(0, 12)}`
        : missing.length
          ? `Full upstream RAG is awaiting: ${missing.join(", ")}`
        : service?.error || (service?.status === "unconfigured"
          ? "ChatQEC is not configured for this API"
          : "ChatQEC did not pass its service health check"),
  };
}

function renderAssistant() {
  const assistant = state.assistant;
  const { service, available, checking, state: serviceState, label: serviceLabel, detail: serviceDetail } = assistantServiceView();
  const citations = assistantCitations();
  const transcript = assistant.messages.length
    ? assistant.messages.map(assistantMessageHtml).join("")
    : `<div class="assistant-start">
        <span class="empty-code" aria-hidden="true">QEC</span>
        <h2>Ask a QEC question</h2>
        <div class="assistant-prompts">
          ${[
            "How is the surface code decoded?",
            "Compare minimum-weight perfect matching and union-find decoders.",
            "What is required for a fault-tolerant logical gate?",
          ].map(prompt => `<button type="button" class="assistant-prompt" data-assistant-prompt="${escapeHtml(prompt)}">${escapeHtml(prompt)}</button>`).join("")}
        </div>
      </div>`;
  const pending = assistant.submitting && !assistant.messages.some(message => message.streaming)
    ? `<article class="assistant-message assistant assistant-pending" aria-live="polite">
        <span class="assistant-role">CHATQEC</span>
        <div><p>Searching the governed ChatQEC sources...</p></div>
      </article>`
    : "";
  const citationList = citations.length
    ? `<ol>${citations.map(assistantCitationHtml).join("")}</ol>`
    : `<p class="assistant-ledger-empty">Cited sources will appear with each answer.</p>`;
  const mode = available ? service.mode : "unavailable";
  const toolExecution = available
    ? service.tool_execution === false ? "disabled" : "not reported"
    : "unavailable";
  const corpus = available ? service.corpus_revision : "unavailable";
  const contextNotice = assistant.contextNotice
    ? `<p class="assistant-context-notice" role="status">${escapeHtml(assistant.contextNotice)}</p>`
    : "";

  workspace.innerHTML = sectionHeader(
    "QEC research assistant",
    available && service?.mode === "canonical-corpus-extractive-fallback"
      ? "Offline deterministic answers from the ChatQEC canonical-corpus extractive fallback"
      : "Cited answers through the governed ChatQEC service boundary",
    `<div class="assistant-service-state">${badge(serviceState, serviceLabel)}<span>${escapeHtml(serviceDetail)}</span></div>`,
  ) + `<div class="assistant-layout">
    <section class="assistant-dialog" aria-label="ChatQEC conversation">
      <div class="assistant-transcript" id="assistant-transcript">${transcript}${pending}</div>
      <form class="assistant-composer" id="assistant-form">
        <label for="assistant-question">QUESTION</label>
        ${contextNotice}
        <div>
          <textarea id="assistant-question" maxlength="8000" rows="3" aria-label="Question for ChatQEC" placeholder="Ask about codes, decoders, noise, or fault tolerance" ${available && !assistant.submitting ? "" : "disabled"}></textarea>
          ${assistant.submitting
            ? '<button class="button secondary" id="assistant-cancel" type="button">Cancel</button>'
            : `<button class="button" type="submit" ${available ? "" : "disabled"}>Send</button>`}
        </div>
      </form>
    </section>
    <aside class="assistant-ledger" aria-label="ChatQEC sources and service details">
      <header>
        <div><p class="panel-label">SOURCE LEDGER</p><strong>${citations.length} cited source${citations.length === 1 ? "" : "s"}</strong></div>
        <button class="button secondary" type="button" id="assistant-clear" ${assistant.submitting ? "disabled" : ""}>Clear</button>
      </header>
      ${citationList}
      <dl>
        <dt>Mode</dt><dd>${escapeHtml(mode)}</dd>
        <dt>Tools</dt><dd>${escapeHtml(toolExecution)}</dd>
        <dt>Corpus</dt><dd>${escapeHtml(corpus)}</dd>
      </dl>
    </aside>
  </div>`;

  document.querySelector("#assistant-form").addEventListener("submit", submitAssistantQuestion);
  document.querySelector("#assistant-question").addEventListener("keydown", event => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      event.currentTarget.form.requestSubmit();
    }
  });
  workspace.querySelectorAll("[data-assistant-prompt]").forEach(button => {
    button.addEventListener("click", () => {
      const input = document.querySelector("#assistant-question");
      input.value = button.dataset.assistantPrompt;
      input.focus();
    });
  });
  document.querySelector("#assistant-clear").addEventListener("click", clearAssistantConversation);
  document.querySelector("#assistant-cancel")?.addEventListener("click", cancelAssistantQuestion);
  const transcriptElement = document.querySelector("#assistant-transcript");
  if (transcriptElement.scrollHeight > transcriptElement.clientHeight) {
    transcriptElement.scrollTop = transcriptElement.scrollHeight;
  } else if (
    assistant.messages.length
    && window.matchMedia("(max-width: 760px)").matches
  ) {
    transcriptElement.querySelector(".assistant-message:last-of-type")
      ?.scrollIntoView({ block: "start" });
  }

  if (checking && !assistant.statusLoading) {
    assistant.statusLoading = true;
    loadAssistantStatus();
  }
}

function renderAssistantDock() {
  const body = document.querySelector("#chatqec-dock-body");
  if (!body) return;
  const assistant = state.assistant;
  const { available, checking, state: serviceState, label: serviceLabel, detail: serviceDetail } = assistantServiceView();
  const transcript = assistant.messages.length
    ? assistant.messages.map(assistantMessageHtml).join("")
    : `<div class="dock-assistant-start">
        <span class="empty-code hex" aria-hidden="true">QEC</span>
        <h2>Keep the workflow in view.</h2>
        <p>Ask ChatQEC about codes, decoders, noise, or fault tolerance without leaving this workspace.</p>
        <div class="dock-prompts">
          ${[
            "How is the surface code decoded?",
            "What is required for a fault-tolerant logical gate?",
          ].map(prompt => `<button type="button" data-dock-assistant-prompt="${escapeHtml(prompt)}">${escapeHtml(prompt)}</button>`).join("")}
        </div>
      </div>`;
  const pending = assistant.submitting && !assistant.messages.some(message => message.streaming)
    ? `<article class="assistant-message assistant assistant-pending" aria-live="polite">
        <span class="assistant-role">CHATQEC</span>
        <div><p>Searching the governed ChatQEC sources...</p></div>
      </article>`
    : "";
  body.innerHTML = `
    <div class="dock-service-state">
      ${badge(serviceState, serviceLabel)}
      <span>${escapeHtml(serviceDetail)}</span>
    </div>
    <div class="dock-transcript" id="dock-assistant-transcript">${transcript}${pending}</div>
    <form class="dock-composer" id="dock-assistant-form">
      <label for="dock-assistant-question">ASK CHATQEC</label>
      ${assistant.contextNotice ? `<p class="assistant-context-notice" role="status">${escapeHtml(assistant.contextNotice)}</p>` : ""}
      <textarea id="dock-assistant-question" maxlength="8000" rows="3" aria-label="Question for contextual ChatQEC" placeholder="Ask a QEC question" ${available && !assistant.submitting ? "" : "disabled"}></textarea>
      <div>
        <button class="dock-clear" type="button" id="dock-assistant-clear">Clear</button>
        ${assistant.submitting
          ? '<button class="button secondary" id="dock-assistant-cancel" type="button">Cancel</button>'
          : `<button class="button" type="submit" ${available ? "" : "disabled"}>Send</button>`}
      </div>
    </form>
    <button class="dock-open-full" id="dock-assistant-open-full" type="button">Open the full research workspace <span aria-hidden="true">↗</span></button>`;

  body.querySelector("#dock-assistant-form").addEventListener("submit", submitAssistantQuestion);
  body.querySelector("#dock-assistant-question").addEventListener("keydown", event => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      event.currentTarget.form.requestSubmit();
    }
  });
  body.querySelectorAll("[data-dock-assistant-prompt]").forEach(button => {
    button.addEventListener("click", () => {
      const input = body.querySelector("#dock-assistant-question");
      input.value = button.dataset.dockAssistantPrompt;
      input.focus();
    });
  });
  body.querySelector("#dock-assistant-clear").addEventListener("click", clearAssistantConversation);
  body.querySelector("#dock-assistant-cancel")?.addEventListener("click", cancelAssistantQuestion);
  body.querySelector("#dock-assistant-open-full").addEventListener("click", () => {
    closeAssistantDock(false);
    switchView("assistant");
  });
  const transcriptElement = body.querySelector("#dock-assistant-transcript");
  transcriptElement.scrollTop = transcriptElement.scrollHeight;

  if (checking && !assistant.statusLoading) {
    assistant.statusLoading = true;
    loadAssistantStatus();
  }
}

let assistantDockLastFocus = null;

function openAssistantDock() {
  if (state.view === "assistant" || state.assistantDockOpen) return;
  assistantDockLastFocus = document.activeElement;
  state.assistantDockOpen = true;
  const dock = document.querySelector("#chatqec-dock");
  dock.classList.add("open");
  dock.setAttribute("aria-hidden", "false");
  document.querySelector("#chatqec-dock-scrim").classList.add("open");
  document.querySelector("#chatqec-dock-toggle").setAttribute("aria-expanded", "true");
  document.body.classList.add("chatqec-open");
  renderAssistantDock();
  window.requestAnimationFrame(() => {
    document.querySelector("#dock-assistant-question:not([disabled])")?.focus()
      || document.querySelector("#chatqec-dock-close")?.focus();
  });
}

function closeAssistantDock(restoreFocus = true) {
  if (!state.assistantDockOpen) return;
  state.assistantDockOpen = false;
  const dock = document.querySelector("#chatqec-dock");
  dock.classList.remove("open");
  dock.setAttribute("aria-hidden", "true");
  document.querySelector("#chatqec-dock-scrim").classList.remove("open");
  document.querySelector("#chatqec-dock-toggle").setAttribute("aria-expanded", "false");
  document.body.classList.remove("chatqec-open");
  if (restoreFocus && assistantDockLastFocus && document.contains(assistantDockLastFocus)) {
    assistantDockLastFocus.focus();
  }
  assistantDockLastFocus = null;
}

function trapAssistantDockFocus(event) {
  const dock = document.querySelector("#chatqec-dock");
  if (event.key !== "Tab" || !state.assistantDockOpen) return;
  const focusable = [...dock.querySelectorAll(
    'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
  )].filter(element => element.getClientRects().length);
  if (!focusable.length) return;
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}

function renderAssistantSurfaces() {
  if (state.view === "assistant") renderAssistant();
  if (state.assistantDockOpen) renderAssistantDock();
}

async function loadAssistantStatus() {
  try {
    state.assistant.status = await api("/assistant/chatqec/status");
  } catch (error) {
    state.assistant.status = {
      status: "unavailable",
      available: false,
      error: error.message,
    };
  } finally {
    state.assistant.statusLoading = false;
    renderAssistantSurfaces();
  }
}

function assistantRequestHeaders() {
  const csrfToken = document.cookie
    .split("; ")
    .find(value => value.startsWith("csrftoken="))
    ?.split("=")
    .slice(1)
    .join("=");
  return csrfToken ? { "Content-Type": "application/json", "X-CSRFToken": decodeURIComponent(csrfToken) } : { "Content-Type": "application/json" };
}

function assignAssistantResponse(message, response) {
  message.content = response.answer;
  message.citations = Array.isArray(response.citations) ? response.citations : [];
  message.confidence = response.confidence;
  message.provider = response.provider;
  message.model = response.model;
  message.corpus_revision = response.corpus_revision;
  message.latency_ms = response.latency_ms;
  message.usage = response.usage;
  message.tool_calls = Array.isArray(response.tool_calls) ? response.tool_calls : [];
  message.streaming = false;
  message.interrupted = false;
}

async function streamAssistantAnswer(payload, signal, onEvent) {
  const response = await fetch("api/v1/assistant/chatqec/answers/stream", {
    method: "POST",
    headers: assistantRequestHeaders(),
    body: JSON.stringify(payload),
    signal,
  });
  const contentType = response.headers.get("content-type") || "";
  if (!response.ok) {
    let body = {};
    try { body = await response.json(); } catch { /* Preserve the status below. */ }
    throw new Error(body.error || `Request failed: ${response.status}`);
  }
  if (!contentType.toLowerCase().startsWith("text/event-stream") || !response.body) {
    const error = new Error("ChatQEC streaming is unavailable");
    error.code = "stream-unavailable";
    throw error;
  }
  const decoder = new TextDecoder();
  const reader = response.body.getReader();
  let buffer = "";
  let finalResponse = null;
  let receivedEvent = false;
  const processFrame = frame => {
    const lines = frame.split(/\r?\n/).filter(Boolean);
    const event = lines.find(line => line.startsWith("event:"))?.slice(6).trim();
    const data = lines.filter(line => line.startsWith("data:")).map(line => line.slice(5).trim()).join("\n");
    if (!event || !data) throw new Error("ChatQEC returned an invalid stream event");
    const parsed = JSON.parse(data);
    if (!parsed || parsed.event !== event || !parsed.data) {
      throw new Error("ChatQEC returned an invalid stream payload");
    }
    receivedEvent = true;
    onEvent(parsed);
    if (event === "final") finalResponse = parsed.data.response;
  };
  try {
    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
      let separator;
      while ((separator = buffer.indexOf("\n\n")) !== -1) {
        const frame = buffer.slice(0, separator);
        buffer = buffer.slice(separator + 2);
        if (frame.trim()) processFrame(frame);
      }
      if (done) break;
    }
    buffer += decoder.decode();
    if (buffer.trim()) processFrame(buffer);
  } finally {
    reader.releaseLock();
  }
  if (!finalResponse) {
    const error = new Error("ChatQEC ended before a verified final response");
    error.code = receivedEvent ? "stream-interrupted" : "stream-unavailable";
    throw error;
  }
  return finalResponse;
}

async function submitAssistantQuestion(event) {
  event.preventDefault();
  const input = event.currentTarget.querySelector("textarea");
  const question = input.value.trim();
  if (!question || state.assistant.submitting || !state.assistant.status?.available) return;

  const historyResult = boundedAssistantHistory(state.assistant.messages);
  const history = historyResult.history;
  state.assistant.contextNotice = historyResult.notice;
  const requestSerial = ++state.assistant.requestSerial;
  state.assistant.messages.push({ role: "user", content: question });
  const responseMessage = {
    role: "assistant",
    content: "",
    citations: [],
    streaming: true,
  };
  state.assistant.messages.push(responseMessage);
  state.assistant.submitting = true;
  const abortController = new AbortController();
  state.assistant.streamAbortController = abortController;
  renderAssistantSurfaces();

  try {
    const payload = {
      question,
      conversation_id: state.assistant.conversationId,
      history,
    };
    let response;
    try {
      response = await streamAssistantAnswer(payload, abortController.signal, event => {
        if (requestSerial !== state.assistant.requestSerial) return;
        if (event.event === "token") {
          responseMessage.content += String(event.data.text || "");
        } else if (event.event === "citation" && event.data.citation) {
          responseMessage.citations.push(event.data.citation);
        }
        renderAssistantSurfaces();
      });
    } catch (error) {
      if (error?.code !== "stream-unavailable") throw error;
      response = await api("/assistant/chatqec/answers", {
        method: "POST",
        body: JSON.stringify(payload),
      });
    }
    if (requestSerial !== state.assistant.requestSerial) return;
    assignAssistantResponse(responseMessage, response);
  } catch (error) {
    if (requestSerial !== state.assistant.requestSerial) return;
    const message = error?.name === "AbortError"
      ? "The ChatQEC response was cancelled before a verified final response."
      : error.message;
    responseMessage.streaming = false;
    responseMessage.interrupted = true;
    responseMessage.content = "";
    responseMessage.citations = [];
    state.assistant.messages.push({ role: "error", content: message });
  } finally {
    if (requestSerial === state.assistant.requestSerial) {
      state.assistant.submitting = false;
      state.assistant.streamAbortController = null;
      renderAssistantSurfaces();
    }
  }
}

function cancelAssistantQuestion() {
  if (!state.assistant.submitting) return;
  state.assistant.requestSerial += 1;
  state.assistant.streamAbortController?.abort();
  state.assistant.streamAbortController = null;
  const partial = [...state.assistant.messages].reverse().find(message => message.streaming);
  if (partial) {
    partial.streaming = false;
    partial.interrupted = true;
    partial.citations = [];
  }
  state.assistant.submitting = false;
  renderAssistantSurfaces();
}

function clearAssistantConversation() {
  state.assistant.streamAbortController?.abort();
  state.assistant.streamAbortController = null;
  state.assistant.requestSerial += 1;
  state.assistant.conversationId = createConversationId();
  state.assistant.messages = [];
  state.assistant.submitting = false;
  state.assistant.contextNotice = "";
  renderAssistantSurfaces();
  const input = state.assistantDockOpen
    ? document.querySelector("#dock-assistant-question")
    : document.querySelector("#assistant-question");
  input?.focus();
}

function renderComposeLegacy() {
  const operations = state.capabilities.flatMap(capability => capability.operations.map(operation => ({ capability, operation })));
  const palette = operations.map(({ capability, operation }) => `<button class="operation-item" data-operation="${capability.id}/${operation.id}"><strong>${escapeHtml(operation.title)}</strong><small>${escapeHtml(capability.name)} · ${escapeHtml(capability.id)}</small></button>`).join("");
  const workflowPalette = state.workflows.map(workflow => `<button class="operation-item workflow-template" data-workflow="${workflow.id}/${workflow.version}"><strong>${escapeHtml(workflow.definition.metadata.name)}</strong><small>${workflow.definition.spec.nodes.length} nodes · ${escapeHtml(workflow.version)}</small></button>`).join("");
  const selectedWorkflow = state.workflows.find(workflow => `${workflow.id}/${workflow.version}` === state.selectedWorkflow);
  const selected = operations.find(({ capability, operation }) => `${capability.id}/${operation.id}` === state.selectedOperation) || (operations.length === 1 ? operations[0] : null);
  if (selected && !state.selectedOperation && !selectedWorkflow) selectOperation(selected.capability, selected.operation);
  const runnable = Boolean(selectedWorkflow || selected);
  const canvas = selectedWorkflow ? workflowGraph(selectedWorkflow.definition) : selected ? operationNode(selected.capability, selected.operation) : operations.length ? `<div class="empty-canvas"><div><strong>Select an operation</strong><p>Add tool operations to the draft. Typed ports and parameters are validated again by the API on publication.</p></div></div>` : `<div class="empty-canvas"><div><strong>No executable runtime is published</strong><p>Audited resources are visible in Tools. Composition unlocks when a tool publishes an immutable operation runtime.</p></div></div>`;
  const selection = selectedWorkflow ? workflowDetail(selectedWorkflow.definition) : selected ? operationDetail(selected.capability, selected.operation) : `<dl><dt>Tools</dt><dd>${state.capabilities.length} integrated tools loaded</dd><dt>Connection policy</dt><dd>Exact artifact type and major version</dd><dt>Execution</dt><dd>Controlled runner only</dd></dl>`;
  const actionLabel = selectedWorkflow ? "Queue run" : "Publish & queue";
  workspace.innerHTML = sectionHeader("Draft workflow", "Typed composition against the active capability registry", `<button class="button" id="publish-run" ${runnable ? "" : "disabled"}>${actionLabel}</button>`) + `<div class="compose-layout"><aside class="palette"><p class="panel-label">WORKFLOW TEMPLATES · ${state.workflows.length}</p><div class="operation-list">${workflowPalette || `<p class="description">No published workflows.</p>`}</div><p class="panel-label palette-section">OPERATION PALETTE · ${operations.length}</p><div class="operation-list">${palette || `<p class="description">No operations available.</p>`}</div></aside><div class="canvas" id="compose-canvas">${canvas}</div><aside class="compose-inspector"><p class="panel-label">SELECTION</p><div id="selection-detail">${selection}</div></aside></div>`;
  workspace.querySelectorAll("[data-operation]").forEach(button => button.addEventListener("click", () => {
    const [capabilityId, operationId] = button.dataset.operation.split("/");
    const capability = state.capabilities.find(item => item.id === capabilityId);
    const operation = capability.operations.find(item => item.id === operationId);
    selectOperation(capability, operation);
    renderCompose();
  }));
  workspace.querySelectorAll("[data-workflow]").forEach(button => button.addEventListener("click", () => {
    selectWorkflow(button.dataset.workflow);
    renderCompose();
  }));
  document.querySelector("#publish-run").addEventListener("click", selectedWorkflow ? runPublishedWorkflow : runDraft);
  workspace.querySelectorAll("[data-parameter]").forEach(input => input.addEventListener("change", event => {
    const definition = selected.operation.parameters[event.target.dataset.parameter];
    state.parameters[event.target.dataset.parameter] = definition.type === "boolean" ? event.target.checked : definition.type === "integer" ? Number.parseInt(event.target.value, 10) : definition.type === "number" ? Number.parseFloat(event.target.value) : event.target.value;
  }));
  workspace.querySelectorAll("[data-input-port]").forEach(input => input.addEventListener("input", event => {
    state.inputContents[event.target.dataset.inputPort] = event.target.value;
  }));
  workspace.querySelectorAll("[data-workflow-input]").forEach(input => input.addEventListener("input", event => {
    state.inputContents[event.target.dataset.workflowInput] = event.target.value;
  }));
}

function renderCompose() {
  if (!window.QHPCComposer) {
    renderComposeLegacy();
    return;
  }
  workspace.innerHTML = `<div id="composer-root"></div>`;
  window.QHPCComposer.mount(document.querySelector("#composer-root"));
}

function selectOperation(capability, operation) {
  state.selectedWorkflow = null;
  state.selectedOperation = `${capability.id}/${operation.id}`;
  state.parameters = Object.fromEntries(Object.entries(operation.parameters || {}).filter(([, definition]) => Object.hasOwn(definition, "default")).map(([name, definition]) => [name, definition.default]));
  state.inputContents = Object.fromEntries(Object.keys(operation.inputs || {}).map(name => [name, ""]));
}

function selectWorkflow(key) {
  state.selectedWorkflow = key;
  state.selectedOperation = null;
  const workflow = state.workflows.find(item => `${item.id}/${item.version}` === key);
  state.inputContents = Object.fromEntries(Object.keys(workflow.definition.spec.inputs).map(name => [name, ""]));
}

function operationExecutionTarget(operation) {
  if (!operation.execution_targets?.length) throw new Error("Operation has no execution target");
  return preferredLocalTarget(operation.execution_targets) || operation.execution_targets[0];
}

function workflowExecutionTarget(workflow) {
  const supported = workflow.spec.nodes.map(node => {
    if (node.execution_target) return [node.execution_target];
    const capability = state.capabilities.find(item => item.id === node.operation.capability && item.version === node.operation.version);
    const operation = capability?.operations.find(item => item.id === node.operation.operation);
    if (!operation) throw new Error(`Operation is unavailable: ${node.operation.capability}/${node.operation.operation}`);
    return operation.execution_targets;
  });
  const common = supported.slice(1).reduce((values, targets) => values.filter(value => targets.includes(value)), [...supported[0]]);
  if (!common.length) throw new Error("Workflow nodes do not share an execution target");
  return preferredLocalTarget(common) || common[0];
}

function preferredLocalTarget(targets) {
  return ["local-container", "local-development"].find(target => targets.includes(target));
}

function isLocalExecutionTarget(target) {
  return target === "local-development" || target === "local-container";
}

function defaultExecutionClass(target) {
  return isLocalExecutionTarget(target) ? "interactive-local" : "batch-hpc";
}

async function requireWorkerReadiness(requirements) {
  const groups = new Map();
  requirements.forEach(requirement => {
    const key = `${requirement.executionTarget}\u0000${requirement.executionClass}`;
    if (!groups.has(key)) groups.set(key, { ...requirement, runtimeDigests: [] });
    groups.get(key).runtimeDigests.push(requirement.runtimeDigest);
  });
  for (const group of groups.values()) {
    const query = new URLSearchParams({
      execution_target: group.executionTarget,
      execution_class: group.executionClass,
    });
    [...new Set(group.runtimeDigests)].forEach(digest => query.append("runtime_digest", digest));
    const readiness = await api(`/readiness?${query}`);
    if (!readiness.ready) throw new Error(readiness.reason);
  }
}

function operationReadiness(capability, operation) {
  const target = operationExecutionTarget(operation);
  return [{
    executionTarget: target,
    executionClass: defaultExecutionClass(target),
    runtimeDigest: operation.runtime.digest,
  }];
}

function workflowReadiness(workflow) {
  const target = workflowExecutionTarget(workflow);
  return workflow.spec.nodes.map(node => {
    const capability = state.capabilities.find(item => item.id === node.operation.capability && item.version === node.operation.version);
    const operation = capability?.operations.find(item => item.id === node.operation.operation);
    if (!operation) throw new Error(`Operation is unavailable: ${node.operation.capability}/${node.operation.operation}`);
    const nodeTarget = node.execution_target || target;
    return {
      executionTarget: nodeTarget,
      executionClass: node.execution_class || defaultExecutionClass(target),
      runtimeDigest: operation.runtime.digest,
    };
  });
}

function operationNode(capability, operation) {
  return `<article class="workflow-node"><header><strong>${escapeHtml(operation.title)}</strong><small>${escapeHtml(capability.id)} / ${escapeHtml(operation.id)}</small></header><div class="ports"><span>IN · ${Object.keys(operation.inputs).length}</span><span>OUT · ${Object.keys(operation.outputs).length}</span></div></article>`;
}

function workflowGraph(workflow) {
  const nodes = workflow.spec.nodes.map((node, index) => {
    const capability = state.capabilities.find(item => item.id === node.operation.capability);
    const operation = capability?.operations.find(item => item.id === node.operation.operation);
    return `<article class="workflow-node" style="--node-index:${index}"><header><strong>${escapeHtml(node.id)}</strong><small>${escapeHtml(node.operation.capability)} / ${escapeHtml(node.operation.operation)} @ ${escapeHtml(node.operation.version)}</small></header><div class="ports"><span>${Object.keys(operation?.inputs || {}).length} in</span><span>${Object.keys(operation?.outputs || {}).length} out</span></div></article>`;
  }).join(`<span class="workflow-arrow" aria-hidden="true">→</span>`);
  return `<div class="workflow-chain">${nodes}</div>`;
}

function workflowDetail(workflow) {
  const inputs = Object.entries(workflow.spec.inputs).map(([name, definition]) => `<label class="artifact-input"><span>${escapeHtml(name)} · ${escapeHtml(definition.artifact_type)}</span><textarea data-workflow-input="${name}" rows="8" placeholder="Paste input artifact content">${escapeHtml(state.inputContents[name] || "")}</textarea></label>`).join("");
  return `<dl><dt>Workflow</dt><dd>${escapeHtml(workflow.metadata.id)}@${escapeHtml(workflow.metadata.version)}</dd><dt>Nodes</dt><dd>${workflow.spec.nodes.length}</dd><dt>Edges</dt><dd>${workflow.spec.edges.length}</dd><dt>Outputs</dt><dd>${escapeHtml(Object.keys(workflow.spec.outputs).join(", "))}</dd></dl>${inputs ? `<p class="panel-label parameter-heading">INPUT ARTIFACTS</p>${inputs}` : ""}`;
}

function operationDetail(capability, operation) {
  const parameters = Object.entries(operation.parameters || {}).map(([name, definition]) => definition.type === "boolean" ? `<label class="parameter-control"><input type="checkbox" data-parameter="${name}" ${state.parameters[name] ? "checked" : ""}><span>${escapeHtml(definition.title || name)}</span></label>` : `<label class="parameter-control"><span>${escapeHtml(definition.title || name)}</span><input data-parameter="${name}" type="${["integer", "number"].includes(definition.type) ? "number" : "text"}" value="${escapeHtml(state.parameters[name] ?? "")}"></label>`).join("");
  const inputs = Object.entries(operation.inputs || {}).map(([name, definition]) => `<label class="artifact-input"><span>${escapeHtml(name)} · ${escapeHtml(definition.artifact_type)}</span><textarea data-input-port="${name}" rows="7" placeholder="Paste input artifact content">${escapeHtml(state.inputContents[name] || "")}</textarea></label>`).join("");
  return `<dl><dt>Tool</dt><dd>${escapeHtml(capability.name)}</dd><dt>Runtime</dt><dd>${escapeHtml(operation.runtime.type)}</dd><dt>Targets</dt><dd>${escapeHtml(operation.execution_targets.join(", "))}</dd><dt>Validation</dt><dd>${escapeHtml(capability.validation.status)}</dd></dl>${inputs ? `<p class="panel-label parameter-heading">INPUT ARTIFACTS</p>${inputs}` : ""}${parameters ? `<p class="panel-label parameter-heading">PARAMETERS</p>${parameters}` : ""}`;
}

async function runDraft() {
  const [capabilityId, operationId] = state.selectedOperation.split("/");
  const capability = state.capabilities.find(item => item.id === capabilityId);
  const operation = capability.operations.find(item => item.id === operationId);
  const workflowId = `workbench-${capabilityId}-${operationId}`;
  const outputs = Object.fromEntries(Object.entries(operation.outputs).map(([name, port]) => [name, { artifact_type: port.artifact_type, from: { node: operationId, port: name } }]));
  const workflowInputs = Object.fromEntries(Object.entries(operation.inputs).map(([name, port]) => [name, { artifact_type: port.artifact_type, required: port.required ?? true, to: { node: operationId, port: name } }]));
  const workflow = { api_version: "qhpc/v1", kind: "Workflow", metadata: { id: workflowId, name: operation.title, version: "0.1.0", owner: "workbench-user", visibility: "internal" }, spec: { nodes: [{ id: operationId, operation: { capability: capabilityId, version: capability.version, operation: operationId }, parameters: state.parameters }], edges: [], inputs: workflowInputs, outputs } };
  const button = document.querySelector("#publish-run");
  button.disabled = true; button.textContent = "Queueing";
  try {
    await requireWorkerReadiness(operationReadiness(capability, operation));
    const runInputs = {};
    for (const [name, port] of Object.entries(operation.inputs)) {
      if ((port.required ?? true) && !state.inputContents[name]?.trim()) throw new Error(`Input artifact ${name} is required`);
      if (state.inputContents[name]?.trim()) {
        const artifact = await api("/artifacts", { method: "POST", body: JSON.stringify({ artifact_type: port.artifact_type, name: `${name}.txt`, content: state.inputContents[name], created_by: "workbench-user" }) });
        runInputs[name] = artifact.id;
      }
    }
    await api("/workflows", { method: "POST", body: JSON.stringify({ workflow, created_by: "workbench-user" }) });
    await api("/runs", { method: "POST", body: JSON.stringify({ workflow_id: workflowId, version: "0.1.0", inputs: runInputs, execution_target: operationExecutionTarget(operation), created_by: "workbench-user" }) });
    showToast("Workflow queued for a worker");
    await loadData(); switchView("runs");
  } catch (error) {
    showToast(error.message); button.disabled = false; button.textContent = "Publish & queue";
  }
}

async function runPublishedWorkflow() {
  const workflow = state.workflows.find(item => `${item.id}/${item.version}` === state.selectedWorkflow);
  const button = document.querySelector("#publish-run");
  button.disabled = true; button.textContent = "Queueing";
  try {
    await requireWorkerReadiness(workflowReadiness(workflow.definition));
    const runInputs = {};
    for (const [name, definition] of Object.entries(workflow.definition.spec.inputs)) {
      if ((definition.required ?? true) && !state.inputContents[name]?.trim()) throw new Error(`Input artifact ${name} is required`);
      if (state.inputContents[name]?.trim()) {
        const extension = definition.artifact_type.includes("circuit") ? "qasm" : "txt";
        const artifact = await api("/artifacts", { method: "POST", body: JSON.stringify({ artifact_type: definition.artifact_type, name: `${name}.${extension}`, content: state.inputContents[name], created_by: "workbench-user" }) });
        runInputs[name] = artifact.id;
      }
    }
    await api("/runs", { method: "POST", body: JSON.stringify({ workflow_id: workflow.id, version: workflow.version, inputs: runInputs, execution_target: workflowExecutionTarget(workflow.definition), created_by: "workbench-user" }) });
    showToast("Run queued for a worker");
    await loadData(); switchView("runs");
  } catch (error) {
    showToast(error.message); button.disabled = false; button.textContent = "Queue run";
  }
}

function renderRuns() {
  if (!state.runs.length) {
    workspace.innerHTML = `<div class="empty-state"><div><span class="empty-code">RUN</span><h2>No execution records</h2><p>Runs will appear here after a validated workflow version is submitted to a configured controlled runner.</p></div></div>`;
    return;
  }
  const rows = state.runs.map(run => {
    const total = elapsedMs(run.started_at, run.finished_at);
    const elapsed = total === null
      ? `<span class="stage-pending">${run.state === "running" ? "in progress" : "—"}</span>`
      : `<span class="numeric">${formatDuration(total)}</span>`;
    return `<tr data-run="${run.id}" tabindex="0">
      <td><span class="cell-title"><strong>${escapeHtml(run.workflow_id)}</strong><small>${escapeHtml(run.id)}</small></span></td>
      <td class="numeric">${escapeHtml(run.workflow_version)}</td>
      <td>${badge(run.state)}</td>
      <td>${elapsed}</td>
      <td class="numeric">${run.tasks.length}</td>
      <td>${escapeHtml(run.execution_target)}</td>
      <td class="numeric">${escapeHtml(formatClock(run.created_at))}</td>
    </tr>`;
  }).join("");
  workspace.innerHTML = sectionHeader("Run history", `${state.runs.length} persisted execution records`) + `<table class="data-table run-table"><thead><tr><th>WORKFLOW / RUN</th><th>VERSION</th><th>STATE</th><th>ELAPSED</th><th>TASKS</th><th>TARGET</th><th>CREATED</th></tr></thead><tbody>${rows}</tbody></table>`;
  workspace.querySelectorAll("[data-run]").forEach(row => {
    row.addEventListener("click", () => openRun(row.dataset.run));
    row.addEventListener("keydown", event => {
      if (event.key === "Enter" || event.key === " ") { event.preventDefault(); openRun(row.dataset.run); }
    });
  });
}

function renderArtifacts() {
  const artifacts = state.artifacts;
  if (!artifacts.length) {
    workspace.innerHTML = `<div class="empty-state"><div><span class="empty-code">ART</span><h2>No artifacts recorded</h2><p>Checksummed outputs and their producing run and task will be indexed here.</p></div></div>`;
    return;
  }
  const rows = artifacts.map(item => {
    const contentPath = `api/v1/artifacts/${encodeURIComponent(item.id)}/content`;
    return `<tr><td><span class="cell-title"><strong>${escapeHtml(item.id)}</strong><small>${escapeHtml(item.artifact_type)}</small></span></td><td>${escapeHtml(item.provenance)}</td><td>${escapeHtml(item.size_bytes)} B</td><td><span class="cell-title"><strong>${escapeHtml(item.checksum.slice(0, 24))}…</strong><small>${escapeHtml(item.uri)}</small></span></td><td><span class="artifact-actions"><a class="button secondary" href="${contentPath}" target="_blank" rel="noopener">Preview</a><a class="button secondary" href="${contentPath}?download=1">Download</a></span></td></tr>`;
  }).join("");
  workspace.innerHTML = sectionHeader("Artifact index", `${artifacts.length} checksummed artifacts`) + `<table class="data-table"><thead><tr><th>ARTIFACT</th><th>PROVENANCE</th><th>SIZE</th><th>CHECKSUM / URI</th><th>ACTIONS</th></tr></thead><tbody>${rows}</tbody></table>`;
}

function renderEnvironments() {
  const runtimes = state.capabilities.flatMap(capability => capability.operations.map(operation => ({ capability, operation })));
  if (!runtimes.length) {
    workspace.innerHTML = `<div class="empty-state"><div><span class="empty-code">ENV</span><h2>No component runtime published</h2><p>Shared development environments exist, but production operations require immutable component-specific images or approved runtime mappings.</p></div></div>`;
    return;
  }
  const rows = runtimes.map(({ capability, operation }) => `<tr><td>${escapeHtml(capability.name)}</td><td>${escapeHtml(operation.id)}</td><td>${escapeHtml(operation.runtime.type)}</td><td><span class="cell-title"><strong>${escapeHtml(operation.runtime.digest.slice(0, 20))}…</strong><small>${escapeHtml(operation.runtime.reference)}</small></span></td><td>${escapeHtml(operation.execution_targets.join(", "))}</td></tr>`).join("");
  workspace.innerHTML = sectionHeader("Runtime inventory", `${runtimes.length} operation runtimes`) + `<table class="data-table"><thead><tr><th>TOOL</th><th>OPERATION</th><th>TYPE</th><th>IDENTITY</th><th>TARGETS</th></tr></thead><tbody>${rows}</tbody></table>`;
}

function updateStatusLabel(status) {
  return {
    "not-checked": "not checked",
    "up-to-date": "current",
    "update-available": "available",
    prepared: "prepared",
    error: "check failed",
  }[status] || status;
}

function updateRevisionCell(revision, detail) {
  const value = revision
    ? `<strong title="${escapeHtml(revision)}">${escapeHtml(revision.slice(0, 12))}</strong>`
    : `<strong>—</strong>`;
  return `<span class="cell-title update-revision">${value}<small>${escapeHtml(detail || "not resolved")}</small></span>`;
}

function renderRepositoryUpdates() {
  const updates = state.repositoryUpdates;
  if (!updates.data && !updates.loading) {
    updates.loading = true;
    loadRepositoryUpdates();
  }
  if (updates.loading && !updates.data) {
    workspace.innerHTML = `<div class="loading">LOADING REPOSITORY UPDATE STATE</div>`;
    return;
  }
  if (updates.error && !updates.data) {
    workspace.innerHTML = `<div class="empty-state"><div><span class="empty-code">ERR</span><h2>Repository update service unavailable</h2><p>${escapeHtml(updates.error)}</p></div></div>`;
    return;
  }
  if (!updates.data?.enabled) {
    workspace.innerHTML = `<div class="empty-state"><div><span class="empty-code">UPD</span><h2>Repository updates are disabled</h2><p>The active control API has not admitted source update operations.</p></div></div>`;
    return;
  }

  const items = updates.data.items || [];
  const available = items.filter(item => item.status === "update-available").length;
  const prepared = items.filter(item => item.status === "prepared").length;
  const controls = `<div class="update-header-actions">
    <span class="update-counts">${available} available · ${prepared} prepared</span>
    <button class="button" id="check-repository-updates" ${updates.checking || updates.staging ? "disabled" : ""}>${updates.checking ? "Checking" : "Check updates"}</button>
  </div>`;
  const rows = items.map(item => {
    const checkingThis = updates.staging === item.component_id;
    const canStage = item.status === "update-available"
      && item.latest_revision
      && !updates.checking
      && !updates.staging;
    const action = canStage
      ? `<button class="button secondary" data-stage-update="${escapeHtml(item.component_id)}" data-candidate-revision="${escapeHtml(item.latest_revision)}">Prepare</button>`
      : checkingThis
        ? `<button class="button secondary" disabled>Preparing</button>`
        : item.status === "prepared" && !updates.checking && !updates.staging
          ? `<button class="button secondary" data-discard-update="${escapeHtml(item.component_id)}">Discard</button>`
          : `<span class="update-action-state">—</span>`;
    const statusDetail = item.error || item.next_action;
    const repository = safeHttpUrl(item.repository_url);
    const name = repository
      ? `<a href="${escapeHtml(repository)}" target="_blank" rel="noopener noreferrer">${escapeHtml(item.name)}</a>`
      : escapeHtml(item.name);
    const latestDetail = item.checked_at
      ? `checked ${formatClock(item.checked_at)}`
      : "remote not checked";
    return `<tr>
      <td data-label="Component"><span class="cell-title update-component"><strong>${name}</strong><small>${escapeHtml(item.component_id)} · ${escapeHtml(item.role)}</small></span></td>
      <td data-label="Current">${updateRevisionCell(item.current_revision, item.tracked_ref)}</td>
      <td data-label="Latest">${updateRevisionCell(item.latest_revision, latestDetail)}</td>
      <td data-label="State"><span class="update-status">${badge(item.status, updateStatusLabel(item.status))}<small class="${item.error ? "update-error" : ""}">${escapeHtml(statusDetail)}</small></span></td>
      <td class="update-action" data-label="Action">${action}</td>
    </tr>`;
  }).join("");
  workspace.innerHTML = sectionHeader(
    "Repository update control",
    "Exact source candidates; runtime activation remains gated by rebuild and validation",
    controls,
  ) + `<table class="data-table update-table">
    <thead><tr><th>COMPONENT</th><th>CURRENT / REF</th><th>LATEST / CHECKED</th><th>STATE / NEXT GATE</th><th>ACTION</th></tr></thead>
    <tbody>${rows || `<tr><td colspan="5">No admitted repository targets.</td></tr>`}</tbody>
  </table>`;
  document.querySelector("#check-repository-updates").addEventListener("click", checkRepositoryUpdates);
  workspace.querySelectorAll("[data-stage-update]").forEach(button => {
    button.addEventListener("click", () => stageRepositoryUpdate(
      button.dataset.stageUpdate,
      button.dataset.candidateRevision,
    ));
  });
  workspace.querySelectorAll("[data-discard-update]").forEach(button => {
    button.addEventListener("click", () => discardRepositoryUpdate(
      button.dataset.discardUpdate,
    ));
  });
}

async function loadRepositoryUpdates() {
  try {
    state.repositoryUpdates.data = await api("/repository-updates");
    state.repositoryUpdates.error = null;
  } catch (error) {
    state.repositoryUpdates.error = error.message;
  } finally {
    state.repositoryUpdates.loading = false;
    if (state.view === "updates") renderRepositoryUpdates();
  }
}

async function checkRepositoryUpdates() {
  state.repositoryUpdates.checking = true;
  renderRepositoryUpdates();
  try {
    state.repositoryUpdates.data = await api("/repository-updates/check", {
      method: "POST",
      body: "{}",
    });
    state.repositoryUpdates.error = null;
    const available = state.repositoryUpdates.data.items.filter(
      item => item.status === "update-available",
    ).length;
    showToast(available ? `${available} repository updates available` : "Repository pins are current");
  } catch (error) {
    state.repositoryUpdates.error = error.message;
    showToast(error.message);
  } finally {
    state.repositoryUpdates.checking = false;
    if (state.view === "updates") renderRepositoryUpdates();
  }
}

async function stageRepositoryUpdate(componentId, candidateRevision) {
  state.repositoryUpdates.staging = componentId;
  renderRepositoryUpdates();
  try {
    await api("/repository-updates/stage", {
      method: "POST",
      body: JSON.stringify({
        component_id: componentId,
        candidate_revision: candidateRevision,
      }),
    });
    state.repositoryUpdates.data = await api("/repository-updates");
    state.repositoryUpdates.error = null;
    showToast(`${componentId} candidate prepared`);
  } catch (error) {
    state.repositoryUpdates.error = error.message;
    showToast(error.message);
  } finally {
    state.repositoryUpdates.staging = null;
    if (state.view === "updates") renderRepositoryUpdates();
  }
}

async function discardRepositoryUpdate(componentId) {
  state.repositoryUpdates.staging = componentId;
  renderRepositoryUpdates();
  try {
    await api("/repository-updates/discard", {
      method: "POST",
      body: JSON.stringify({ component_id: componentId }),
    });
    state.repositoryUpdates.data = await api("/repository-updates");
    state.repositoryUpdates.error = null;
    showToast(`${componentId} candidate released`);
  } catch (error) {
    state.repositoryUpdates.error = error.message;
    showToast(error.message);
  } finally {
    state.repositoryUpdates.staging = null;
    if (state.view === "updates") renderRepositoryUpdates();
  }
}

function render() {
  quantumAsciiCleanup();
  renderSummary();
  if (state.view !== "compose") window.QHPCComposer?.unmount();
  if (state.view !== "knowledge") window.QHPCKnowledge?.unmount();
  ({ overview: renderOverview, showcases: renderShowcases, tools: renderTools, data: renderData, knowledge: renderKnowledge, openqse: renderOpenQSE, engagement: renderEngagement, assistant: renderAssistant, compose: renderCompose, runs: renderRuns, artifacts: renderArtifacts, environments: renderEnvironments, updates: renderRepositoryUpdates })[state.view]();
}

function switchView(view) {
  if (view === "assistant") closeAssistantDock(false);
  state.view = view;
  const url = new URL(window.location.href);
  if (view === "overview") url.searchParams.delete("view"); else url.searchParams.set("view", view);
  if (view === "knowledge" && state.knowledgeNode) {
    url.searchParams.set("knowledge_node", state.knowledgeNode);
  } else if (view !== "knowledge") {
    url.searchParams.delete("knowledge_node");
  }
  if (view === "data" && state.selectedDataService) {
    url.searchParams.set("data_service", state.selectedDataService);
  } else if (view !== "data") {
    url.searchParams.delete("data_service");
  }
  if (view !== "compose") url.searchParams.delete("workflow");
  if (view !== "tools") url.searchParams.delete("capability");
  window.history.replaceState({}, "", url);
  document.querySelectorAll(".nav-item").forEach(item => {
    const current = item.dataset.view === view;
    item.classList.toggle("active", current);
    if (current) item.setAttribute("aria-current", "page"); else item.removeAttribute("aria-current");
  });
  document.querySelector("#view-eyebrow").textContent = VIEW_META[view][0];
  document.querySelector("#view-title").textContent = VIEW_META[view][1];
  document.querySelector("#chatqec-dock-toggle").hidden = view === "assistant";
  render();
}

let lastFocused = null;

function openInspector(html, kind = "DETAILS") {
  const inspector = document.querySelector("#inspector");
  lastFocused = document.activeElement;
  document.querySelector("#inspector-kind").textContent = kind;
  document.querySelector("#inspector-content").innerHTML = html;
  inspector.classList.toggle("is-wide", kind === "TOOL RECORD");
  inspector.classList.add("open");
  inspector.setAttribute("aria-hidden", "false");
  document.querySelector("#scrim").classList.add("open");
  inspector.focus();
}

function closeInspector() {
  const inspector = document.querySelector("#inspector");
  if (!inspector.classList.contains("open")) return;
  inspector.classList.remove("open");
  inspector.setAttribute("aria-hidden", "true");
  document.querySelector("#scrim").classList.remove("open");
  // Return focus to whatever opened the panel, so keyboard position is not lost.
  if (lastFocused && document.contains(lastFocused)) lastFocused.focus();
  lastFocused = null;
  if (state.view === "tools" || state.view === "data") {
    const url = new URL(window.location.href);
    url.searchParams.delete("capability");
    window.history.replaceState({}, "", url);
  }
}

/* Keep Tab inside the panel while it is modal. */
function trapFocus(event) {
  const inspector = document.querySelector("#inspector");
  if (event.key !== "Tab" || !inspector.classList.contains("open")) return;
  const focusable = inspector.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
  if (!focusable.length) return;
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
}

const THEME_KEY = "qhpc-workbench-theme";

function applyTheme(theme) {
  const toggle = document.querySelector("#theme-toggle");
  if (theme) document.documentElement.setAttribute("data-theme", theme);
  else document.documentElement.removeAttribute("data-theme");
  const dark = theme === "dark" || (!theme && window.matchMedia("(prefers-color-scheme: dark)").matches);
  toggle.textContent = dark ? "Light theme" : "Dark theme";
}

function toggleTheme() {
  const dark = document.documentElement.getAttribute("data-theme") === "dark"
    || (!document.documentElement.hasAttribute("data-theme") && window.matchMedia("(prefers-color-scheme: dark)").matches);
  const next = dark ? "light" : "dark";
  try { localStorage.setItem(THEME_KEY, next); } catch { /* storage unavailable */ }
  applyTheme(next);
}

function capabilityGuidance(item) {
  if (item.guidance?.use_when?.length && item.guidance?.quick_start?.length) {
    return item.guidance;
  }
  return {
    use_when: [item.description],
    quick_start: item.operations.length
      ? ["Open Compose, add a published operation, provide its declared inputs, and review its parameters before running."]
      : ["Review the published resources and documentation. This capability does not expose an executable workflow operation."],
    example_workflows: [],
    limitations: [],
  };
}

function guidanceList(items, ordered = false) {
  const tag = ordered ? "ol" : "ul";
  return `<${tag}>${items.map(item => `<li>${escapeHtml(item)}</li>`).join("")}</${tag}>`;
}

function portList(ports) {
  const entries = Object.entries(ports || {});
  if (!entries.length) return `<span class="tool-contract-empty">None</span>`;
  return `<ul class="tool-contract-list">${entries.map(([name, definition]) => `
    <li>
      <strong>${escapeHtml(name)}</strong>
      <code>${escapeHtml(definition.artifact_type)}</code>
      ${definition.description ? `<span>${escapeHtml(definition.description)}</span>` : ""}
    </li>`).join("")}</ul>`;
}

function parameterList(parameters) {
  const entries = Object.entries(parameters || {});
  if (!entries.length) return `<span class="tool-contract-empty">No configurable parameters</span>`;
  return `<ul class="tool-contract-list">${entries.map(([name, definition]) => {
    const facts = [definition.type];
    if (Object.hasOwn(definition, "default")) facts.push(`default ${JSON.stringify(definition.default)}`);
    if (definition.enum?.length) facts.push(`choices ${definition.enum.join(", ")}`);
    return `<li>
      <strong>${escapeHtml(definition.title || name)}</strong>
      <code>${escapeHtml(name)}</code>
      <span>${escapeHtml(facts.join(" · "))}</span>
      ${definition.description ? `<span>${escapeHtml(definition.description)}</span>` : ""}
    </li>`;
  }).join("")}</ul>`;
}

function operationGuide(operation) {
  return `<details class="tool-operation">
    <summary>
      <span>
        <strong>${escapeHtml(operation.title)}</strong>
        <small>${escapeHtml(operation.id)}</small>
      </span>
      <span class="tool-operation-target">${escapeHtml(operation.execution_targets.join(", "))}</span>
    </summary>
    <div class="tool-operation-body">
      <p>${escapeHtml(operation.description || "No operation description has been published.")}</p>
      <div class="tool-contract-grid">
        <section><h4>Inputs</h4>${portList(operation.inputs)}</section>
        <section><h4>Outputs</h4>${portList(operation.outputs)}</section>
      </div>
      <section class="tool-parameter-section"><h4>Parameters</h4>${parameterList(operation.parameters)}</section>
      <dl class="tool-operation-runtime">
        <div><dt>Runtime</dt><dd>${escapeHtml(operation.runtime.type)}</dd></div>
        <div><dt>Targets</dt><dd>${escapeHtml(operation.execution_targets.join(", "))}</dd></div>
      </dl>
    </div>
  </details>`;
}

function qappswikiNodeId(reference) {
  const value = String(reference || "").trim();
  if (!value || value.includes("://")) return null;
  return value
    .replace(/^\.?\//, "")
    .replace(/\.md(?:#.*)?$/, "");
}

function openCapability(id) {
  const item = state.capabilities.find(capability => capability.id === id);
  if (!item) return;
  const url = new URL(window.location.href);
  url.searchParams.set("view", state.view === "data" ? "data" : "tools");
  url.searchParams.set("capability", id);
  window.history.replaceState({}, "", url);
  const guidance = capabilityGuidance(item);
  const canonicalRepository = item.repository.canonical_url || item.repository.url;
  const releaseSource = canonicalRepository === item.repository.url
    ? ""
    : `<dt>Release source</dt><dd>${escapeHtml(item.repository.url)}</dd>`;
  const documentationUrl = safeHttpUrl(item.documentation?.url);
  const knowledgeNodeId = qappswikiNodeId(item.documentation?.qappswiki);
  const documentedWorkflowIds = guidance.example_workflows || [];
  const workflows = documentedWorkflowIds.map(workflowId =>
    state.workflows.find(workflow => workflow.id === workflowId)
  ).filter(Boolean);
  const workflowList = documentedWorkflowIds.length
    ? `<ul class="tool-example-list">${documentedWorkflowIds.map(workflowId => {
        const workflow = state.workflows.find(candidate => candidate.id === workflowId);
        return `<li><strong>${escapeHtml(workflow?.definition.metadata.name || workflowId)}</strong><code>${escapeHtml(workflowId)}</code></li>`;
      }).join("")}</ul>`
    : `<p class="tool-record-empty">No example workflow is published for this tool.</p>`;
  const operations = item.operations.length
    ? item.operations.map(operationGuide).join("")
    : `<p class="tool-record-empty">This registry record publishes resources or documentation; it has no executable operation.</p>`;
  const resources = item.resources.length
    ? `<ul class="tool-resource-list">${item.resources.map(resource => `<li><span><strong>${escapeHtml(resource.id)}</strong><small>${escapeHtml(resource.kind)} · ${escapeHtml(resource.version)}</small></span>${resource.description ? `<p>${escapeHtml(resource.description)}</p>` : ""}</li>`).join("")}</ul>`
    : `<p class="tool-record-empty">No additional resources are published.</p>`;
  const limitations = guidance.limitations?.length
    ? `<section class="tool-record-section tool-limitations"><h3>Current limitations</h3>${guidanceList(guidance.limitations)}</section>`
    : "";
  const serviceModes = guidance.service_modes?.length
    ? `<section class="tool-record-section"><h3>Service modes</h3>${guidanceList(guidance.service_modes)}</section>`
    : "";
  const people = TOOL_PEOPLE[item.id] || {
    basis: "No source-reviewed developer attribution is recorded for this tool",
    people: [],
  };
  const peopleList = people.people.length
    ? `<ul class="tool-example-list">${people.people.map(person => `<li>${escapeHtml(person)}</li>`).join("")}</ul>`
    : `<p class="tool-record-empty">No individual developer is named in the reviewed source.</p>`;
  const attribution = `<section class="tool-record-section tool-people">
      <h3>Developers and authors</h3>
      <p>${escapeHtml(people.basis)}. Attribution is limited to people named by the reviewed source; it does not imply current maintenance responsibility.</p>
      ${peopleList}
    </section>`;

  openInspector(`<article class="tool-record">
    <header class="tool-record-intro">
      <h2>${escapeHtml(item.name)}</h2>
      <p>${escapeHtml(item.description)}</p>
      <div class="tool-record-capability">
        <span>EQO INTEGRATION</span>
        <strong>${escapeHtml(item.capability_name || item.name)}</strong>
        <small>${escapeHtml(item.id)}@${escapeHtml(item.version)}</small>
      </div>
      <div class="tool-record-status">${badge(item.maturity)}${badge(item.validation.status)}${badge(item.integration.runtime_status)}</div>
    </header>
    <section class="tool-record-section">
      <h3>When to use this tool</h3>
      ${guidanceList(guidance.use_when)}
    </section>
    <section class="tool-record-section">
      <h3>Quick start</h3>
      ${guidanceList(guidance.quick_start, true)}
    </section>
    <section class="tool-record-section">
      <div class="tool-section-heading"><h3>Example workflows</h3>${workflows.length ? `<button class="button secondary" id="tool-record-compose" type="button">Open Compose</button>` : ""}</div>
      ${workflowList}
    </section>
    <section class="tool-record-section">
      <h3>Available operations <span>${item.operations.length}</span></h3>
      <div class="tool-operation-list">${operations}</div>
    </section>
    <section class="tool-record-section">
      <h3>Published resources <span>${item.resources.length}</span></h3>
      ${resources}
    </section>
    ${attribution}
    ${serviceModes}
    ${limitations}
    <details class="tool-provenance">
      <summary>Release, ownership, and provenance</summary>
      <dl class="detail-list"><dt>Tool release</dt><dd>${escapeHtml(item.id)}@${escapeHtml(item.version)}</dd><dt>Repository</dt><dd>${escapeHtml(canonicalRepository)}</dd>${releaseSource}<dt>Revision</dt><dd>${escapeHtml(item.repository.revision)}</dd><dt>Source ownership</dt><dd>${escapeHtml(SOURCE_AREAS[item.project] || item.project)}</dd><dt>Integration authority</dt><dd>${escapeHtml(item.integration.authority)}</dd><dt>Curated by</dt><dd>${escapeHtml(item.integration.maintainers.join(", "))}</dd><dt>Source reviewed</dt><dd>${item.integration.project_reviewed ? "yes" : "no"}</dd></dl>
    </details>
    <div class="tool-record-links">
      ${knowledgeNodeId ? `<button class="tool-knowledge-link" id="tool-record-knowledge" type="button">Explore in Knowledge <span aria-hidden="true">→</span></button>` : ""}
      ${documentationUrl ? `<a class="tool-documentation-link" href="${escapeHtml(documentationUrl)}" target="_blank" rel="noreferrer">Open source documentation <span aria-hidden="true">↗</span></a>` : ""}
    </div>
  </article>`, "TOOL RECORD");
  document.querySelector("#tool-record-compose")?.addEventListener("click", () => {
    closeInspector();
    switchView("compose");
  });
  document.querySelector("#tool-record-knowledge")?.addEventListener("click", () => {
    state.knowledgeNode = knowledgeNodeId;
    closeInspector();
    switchView("knowledge");
  });
}

function openRun(id) {
  const run = state.runs.find(item => item.id === id);
  const durations = run.tasks.map(task => elapsedMs(task.started_at, task.finished_at));
  const longest = Math.max(1, ...durations.filter(value => value !== null));

  const timeline = run.tasks.map((task, index) => {
    const meta = stateMeta(task.state);
    const ms = durations[index];
    const bar = ms === null
      ? `<p class="stage-pending">${task.started_at ? "running — no end time recorded" : "not started"}</p>`
      : `<div class="stage-bar">
           <div class="stage-track"><i class="stage-fill" style="width:${Math.max(2, Math.round((ms / longest) * 100))}%"></i></div>
           <span class="stage-duration">${formatDuration(ms)}</span>
         </div>`;
    const safeFailure = sanitizedIqmFailure(task);
    const error = task.error
      ? `<div class="task-error"><strong>${escapeHtml(task.error.code || "error")}</strong>${escapeHtml(safeFailure || task.error.message || "")}</div>`
      : "";
    return `<div class="timeline-row" style="--state-color:${meta.color}">
      ${badge(task.state)}
      <span class="timeline-rail" aria-hidden="true"><i class="timeline-node hex"></i></span>
      <div class="timeline-body">
        <strong>${escapeHtml(task.node_id)}</strong>
        <p class="description">${escapeHtml(task.operation.capability)} / ${escapeHtml(task.operation.operation)} · attempt ${task.attempt}</p>
        ${bar}${error}
      </div>
    </div>`;
  }).join("");

  const total = elapsedMs(run.started_at, run.finished_at);
  const accounted = durations.reduce((sum, value) => sum + (value || 0), 0);
  const overhead = total === null ? null : Math.max(0, total - accounted);
  const summary = `<dl class="run-summary">
    <div><dt>ELAPSED</dt><dd>${formatDuration(total) ?? "—"}</dd></div>
    <div><dt>IN TASKS</dt><dd>${formatDuration(accounted) ?? "—"}</dd></div>
    <div><dt>SCHEDULING</dt><dd>${formatDuration(overhead) ?? "—"}</dd></div>
  </dl>`;

  const retry = run.tasks.find(task => task.state === "failed");
  const lifecycle = iqmExecutionLifecycle(run);
  const lifecyclePanel = lifecycle.present && run.tasks.some(isIqmExecutionTask)
    ? `<section class="run-execution-status"><span class="panel-label">IQM EXECUTION LIFECYCLE</span><strong>${escapeHtml(lifecycle.status)}</strong><p>${escapeHtml(lifecycle.detail)}</p></section>`
    : "";
  const outputs = Object.entries(run.outputs || {}).map(([name, artifactId]) => {
    const contentPath = `api/v1/artifacts/${encodeURIComponent(artifactId)}/content`;
    return `<div class="run-output"><span><strong>${escapeHtml(name)}</strong><small>${escapeHtml(artifactId)}</small></span><span class="artifact-actions"><a class="button secondary" href="${contentPath}" target="_blank" rel="noopener">Preview</a><a class="button secondary" href="${contentPath}?download=1">Download</a></span></div>`;
  }).join("");
  openInspector(`<h2>${escapeHtml(run.workflow_id)}</h2>
    <p class="description">${escapeHtml(run.id)}</p>
    <p>${badge(run.state)}</p>
    <div class="run-actions">
      <button class="button secondary" id="export-run">Export</button>
      ${["queued", "running"].includes(run.state) ? `<button class="button danger" id="cancel-run">Cancel run</button>` : ""}
      ${retry ? `<button class="button" id="retry-run" data-node="${escapeHtml(retry.node_id)}">Retry task</button>` : ""}
    </div>
    ${summary}
    ${lifecyclePanel}
    ${outputs ? `<p class="panel-label" style="margin-top:18px">WORKFLOW OUTPUTS</p><div class="run-outputs">${outputs}</div>` : ""}
    <p class="panel-label" style="margin-top:18px">TASK TIMELINE</p>
    <div class="timeline">${timeline}</div>
    <dl class="detail-list">
      <dt>Started</dt><dd>${escapeHtml(formatClock(run.started_at))}</dd>
      <dt>Finished</dt><dd>${escapeHtml(formatClock(run.finished_at))}</dd>
      <dt>Target</dt><dd>${escapeHtml(run.execution_target)}</dd>
      <dt>Submitted by</dt><dd>${escapeHtml(run.created_by)}</dd>
    </dl>`, "RUN RECORD");
  document.querySelector("#export-run").addEventListener("click", () => exportRun(run.id));
  document.querySelector("#cancel-run")?.addEventListener("click", () => runAction(run.id, "cancel"));
  document.querySelector("#retry-run")?.addEventListener("click", event => retryRun(run.id, event.target.dataset.node));
}

async function exportRun(runId) {
  try {
    const bundle = await api(`/runs/${runId}/export`);
    const link = document.createElement("a");
    link.href = URL.createObjectURL(new Blob([JSON.stringify(bundle, null, 2)], { type: "application/json" }));
    link.download = `${runId}.json`; link.click(); URL.revokeObjectURL(link.href);
  } catch (error) { showToast(error.message); }
}

async function runAction(runId, action) {
  try { await api(`/runs/${runId}/${action}`, { method: "POST", body: "{}" }); closeInspector(); await loadData(); } catch (error) { showToast(error.message); }
}

async function retryRun(runId, nodeId) {
  try { await api(`/runs/${runId}/tasks/${nodeId}/retry`, { method: "POST", body: "{}" }); showToast("Task requeued for a worker"); closeInspector(); await loadData(); } catch (error) { showToast(error.message); }
}

let operationalRefreshPending = false;

async function refreshOperationalState() {
  if (operationalRefreshPending) return;
  operationalRefreshPending = true;
  try {
    const [runs, artifacts, workers] = await Promise.all([api("/runs"), api("/artifacts"), api("/workers")]);
    state.runs = runs; state.artifacts = artifacts; state.workers = workers; renderSummary();
    if (state.view === "overview") renderOverview();
    if (state.view === "runs") renderRuns();
    if (state.view === "artifacts") renderArtifacts();
    if (state.view === "showcases") renderShowcases();
  } catch (error) {
    document.querySelector("#service-state").textContent = "Unavailable";
  } finally {
    operationalRefreshPending = false;
  }
}

async function loadData() {
  window.QHPCComposer?.unmount();
  window.QHPCKnowledge?.unmount();
  workspace.innerHTML = `<div class="loading">LOADING TOOL CATALOG AND RUN STATE</div>`;
  try {
    const [capabilities, workflows, runs, artifacts, workers, engagement] = await Promise.all([api("/capabilities"), api("/workflows"), api("/runs"), api("/artifacts"), api("/workers"), api("/engagement-resources")]);
    state.capabilities = capabilities; state.workflows = latestWorkflowVersions(workflows); state.runs = runs; state.artifacts = artifacts; state.workers = workers;
    state.engagement.resources = Array.isArray(engagement.resources) ? engagement.resources : [];
    if (!state.selectedWorkflow && !state.selectedOperation) {
      const preferred = state.workflows.find(item => item.id === "ct-hw-qasm-analysis") || state.workflows[0];
      if (preferred) selectWorkflow(`${preferred.id}/${preferred.version}`);
    }
    document.querySelector("#service-dot").classList.add("online");
    document.querySelector("#service-state").textContent = "Online";
    switchView(state.view);
    if (state.view === "tools" && state.requestedCapability) {
      openCapability(state.requestedCapability);
      state.requestedCapability = null;
    }
    if (state.view === "data" && state.requestedCapability) {
      openCapability(state.requestedCapability);
      state.requestedCapability = null;
    }
  } catch (error) {
    document.querySelector("#service-state").textContent = "Unavailable";
    workspace.innerHTML = `<div class="empty-state"><div><span class="empty-code">ERR</span><h2>Workbench service unavailable</h2><p>${escapeHtml(error.message)}</p></div></div>`;
  }
}

try { applyTheme(localStorage.getItem(THEME_KEY)); } catch { applyTheme(null); }

function enhancePrimaryNavigation() {
  const navigation = document.querySelector("#primary-nav");
  if (!navigation || navigation.querySelector(".nav-group")) return;
  const groups = [
    ["workspace", "Workspace", ["overview", "showcases", "tools", "data", "knowledge", "openqse", "engagement", "assistant", "compose"]],
    ["execution", "Execution", ["runs", "artifacts"]],
    ["system", "System", ["environments", "updates"]],
  ];
  navigation.setAttribute("aria-label", "EQO-QSC workspaces");
  groups.forEach(([id, label, views]) => {
    const group = document.createElement("div");
    const heading = document.createElement("span");
    group.className = "nav-group";
    group.setAttribute("aria-labelledby", `nav-${id}-label`);
    heading.className = "nav-group-label";
    heading.id = `nav-${id}-label`;
    heading.textContent = label;
    group.append(heading);
    views.forEach(view => {
      const item = navigation.querySelector(`[data-view="${view}"]`);
      if (!item) return;
      const text = Array.from(item.childNodes).find(node => node.nodeType === Node.TEXT_NODE);
      if (text?.textContent.trim()) {
        const itemLabel = document.createElement("span");
        itemLabel.className = "nav-item-label";
        itemLabel.textContent = text.textContent.trim();
        text.replaceWith(itemLabel);
      }
      group.append(item);
    });
    navigation.append(group);
  });
}

enhancePrimaryNavigation();
document.querySelectorAll(".nav-item").forEach(item => item.addEventListener("click", () => switchView(item.dataset.view)));
document.querySelector("#refresh-button").addEventListener("click", () => {
  if (state.view === "assistant") state.assistant.status = null;
  if (state.view === "updates") state.repositoryUpdates.data = null;
  loadData();
  showToast("Workbench data refreshed");
});
document.querySelector("#global-search").addEventListener("input", event => {
  state.query = event.target.value;
  if (state.view === "data") renderData();
  else if (state.view !== "tools") switchView("tools");
  else renderTools();
});
document.querySelector("#close-inspector").addEventListener("click", closeInspector);
document.querySelector("#scrim").addEventListener("click", closeInspector);
document.querySelector("#chatqec-dock-toggle").addEventListener("click", () => {
  if (state.assistantDockOpen) closeAssistantDock(); else openAssistantDock();
});
document.querySelector("#chatqec-dock-close").addEventListener("click", () => closeAssistantDock());
document.querySelector("#chatqec-dock-scrim").addEventListener("click", () => closeAssistantDock());
document.querySelector("#theme-toggle").addEventListener("click", toggleTheme);
window.addEventListener("qhpc-composer-ready", () => {
  if (state.view === "compose") renderCompose();
});
window.addEventListener("qhpc-knowledge-ready", () => {
  if (state.view === "knowledge") renderKnowledge();
});
document.addEventListener("keydown", event => {
  if (event.key === "Escape") {
    closeInspector();
    closeAssistantDock();
  }
  trapFocus(event);
  trapAssistantDockFocus(event);
});
loadData();
setInterval(refreshOperationalState, 5000);
