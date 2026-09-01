const SOURCE_AREAS = {
  "software-engineering": "Software Engineering",
  "data-schema": "Data Schema",
  "agentic-software": "Agentic Software",
  "compilation-tools": "Compilation Tools",
  "hybrid-workflows": "Hybrid Workflows",
  "cross-project": "Cross-project",
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

const VIEW_META = {
  overview: ["QSC / QHPC ECOSYSTEM", "EQO-QSC"],
  tools: ["ECOSYSTEM / TOOLS", "Integrated software"],
  data: ["DATA / SERVICES", "Data services"],
  knowledge: ["KNOWLEDGE / QAPPSWIKI", "Knowledge Explorer"],
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
  },
  assistantDockOpen: false,
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
  const response = await fetch(`/api/v1${path}`, { ...options, headers });
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
              const contentPath = `/api/v1/data/objects/content?key=${encodeURIComponent(object.key)}`;
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
  if (!window.QHPCKnowledge) return;
  window.QHPCKnowledge.mount(root, { initialNodeId: state.knowledgeNode });
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
    if (message.role !== "assistant") return;
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
  const confidence = Number(message.confidence);
  const totalLatency = Number(message.latency_ms?.total);
  const footer = [
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
  ].filter(Boolean).map(item => `<span>${item}</span>`).join("");
  return `<article class="assistant-message assistant">
    <span class="assistant-role">CHATQEC</span>
    <div>
      ${assistantAnswerHtml(message.content)}
      <footer>${footer}</footer>
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
  return {
    service,
    available,
    checking,
    state: checking ? "pending" : available ? "online" : "offline",
    label: checking ? "checking" : available ? "ready" : "unavailable",
    detail: checking
      ? "Verifying the canonical corpus"
      : available
        ? `${service.pages} canonical pages · source ${String(service.source_revision).slice(0, 12)}`
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
  const pending = assistant.submitting
    ? `<article class="assistant-message assistant assistant-pending" aria-live="polite">
        <span class="assistant-role">CHATQEC</span>
        <div><p>Searching the canonical corpus...</p></div>
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

  workspace.innerHTML = sectionHeader(
    "QEC research assistant",
    "Cited answers from the exact-revision ChatQEC canonical corpus",
    `<div class="assistant-service-state">${badge(serviceState, serviceLabel)}<span>${escapeHtml(serviceDetail)}</span></div>`,
  ) + `<div class="assistant-layout">
    <section class="assistant-dialog" aria-label="ChatQEC conversation">
      <div class="assistant-transcript" id="assistant-transcript">${transcript}${pending}</div>
      <form class="assistant-composer" id="assistant-form">
        <label for="assistant-question">QUESTION</label>
        <div>
          <textarea id="assistant-question" maxlength="8000" rows="3" aria-label="Question for ChatQEC" placeholder="Ask about codes, decoders, noise, or fault tolerance" ${available && !assistant.submitting ? "" : "disabled"}></textarea>
          <button class="button" type="submit" ${available && !assistant.submitting ? "" : "disabled"}>Send</button>
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
  const pending = assistant.submitting
    ? `<article class="assistant-message assistant assistant-pending" aria-live="polite">
        <span class="assistant-role">CHATQEC</span>
        <div><p>Searching the canonical corpus...</p></div>
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
      <textarea id="dock-assistant-question" maxlength="8000" rows="3" aria-label="Question for contextual ChatQEC" placeholder="Ask a QEC question" ${available && !assistant.submitting ? "" : "disabled"}></textarea>
      <div>
        <button class="dock-clear" type="button" id="dock-assistant-clear" ${assistant.submitting ? "disabled" : ""}>Clear</button>
        <button class="button" type="submit" ${available && !assistant.submitting ? "" : "disabled"}>Send</button>
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

async function submitAssistantQuestion(event) {
  event.preventDefault();
  const input = event.currentTarget.querySelector("textarea");
  const question = input.value.trim();
  if (!question || state.assistant.submitting || !state.assistant.status?.available) return;

  const history = state.assistant.messages
    .filter(message => ["user", "assistant"].includes(message.role))
    .map(message => ({
      role: message.role,
      content: String(message.content).slice(0, 8000),
    }))
    .slice(-20);
  const requestSerial = ++state.assistant.requestSerial;
  state.assistant.messages.push({ role: "user", content: question });
  state.assistant.submitting = true;
  renderAssistantSurfaces();

  try {
    const response = await api("/assistant/chatqec/answers", {
      method: "POST",
      body: JSON.stringify({
        question,
        conversation_id: state.assistant.conversationId,
        history,
      }),
    });
    if (requestSerial !== state.assistant.requestSerial) return;
    state.assistant.messages.push({
      role: "assistant",
      content: response.answer,
      citations: Array.isArray(response.citations) ? response.citations : [],
      confidence: response.confidence,
      provider: response.provider,
      model: response.model,
      corpus_revision: response.corpus_revision,
      latency_ms: response.latency_ms,
      usage: response.usage,
    });
  } catch (error) {
    if (requestSerial !== state.assistant.requestSerial) return;
    state.assistant.messages.push({ role: "error", content: error.message });
  } finally {
    if (requestSerial === state.assistant.requestSerial) {
      state.assistant.submitting = false;
      renderAssistantSurfaces();
    }
  }
}

function clearAssistantConversation() {
  state.assistant.requestSerial += 1;
  state.assistant.conversationId = createConversationId();
  state.assistant.messages = [];
  state.assistant.submitting = false;
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
  return operation.execution_targets.includes("local-development") ? "local-development" : operation.execution_targets[0];
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
  return common.includes("local-development") ? "local-development" : common[0];
}

function defaultExecutionClass(target) {
  return target === "local-development" ? "interactive-local" : "batch-hpc";
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
    const contentPath = `/api/v1/artifacts/${encodeURIComponent(item.id)}/content`;
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
  ({ overview: renderOverview, tools: renderTools, data: renderData, knowledge: renderKnowledge, assistant: renderAssistant, compose: renderCompose, runs: renderRuns, artifacts: renderArtifacts, environments: renderEnvironments, updates: renderRepositoryUpdates })[state.view]();
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
    const error = task.error
      ? `<div class="task-error"><strong>${escapeHtml(task.error.code || "error")}</strong>${escapeHtml(task.error.message || "")}</div>`
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
  const outputs = Object.entries(run.outputs || {}).map(([name, artifactId]) => {
    const contentPath = `/api/v1/artifacts/${encodeURIComponent(artifactId)}/content`;
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
    const [capabilities, workflows, runs, artifacts, workers] = await Promise.all([api("/capabilities"), api("/workflows"), api("/runs"), api("/artifacts"), api("/workers")]);
    state.capabilities = capabilities; state.workflows = workflows; state.runs = runs; state.artifacts = artifacts; state.workers = workers;
    if (!state.selectedWorkflow && !state.selectedOperation) {
      const preferred = workflows.find(item => item.id === "ct-hw-qasm-analysis") || workflows[0];
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
    ["workspace", "Workspace", ["overview", "tools", "data", "knowledge", "assistant", "compose"]],
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
