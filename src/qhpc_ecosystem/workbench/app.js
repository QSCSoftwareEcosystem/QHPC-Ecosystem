const PROJECTS = {
  "software-engineering": { code: "SE", name: "Software Engineering", color: "#167c58", description: "Packaging, releases, CI, containers, and reproducible deployment." },
  "data-schema": { code: "DS", name: "Data Schema", color: "#087a8c", description: "Artifact contracts, metadata, validation, and interoperability." },
  "agentic-software": { code: "AS", name: "Agentic Software", color: "#a86108", description: "Assistance, recommendations, rankings, and knowledge operations." },
  "compilation-tools": { code: "CT", name: "Compilation Tools", color: "#784b9b", description: "Circuit transformation, lowering, mapping, and resource analysis." },
  "hybrid-workflows": { code: "HW", name: "Hybrid Workflows", color: "#b3443b", description: "Simulation, QEC, execution backends, and hybrid orchestration." },
  "cross-project": { code: "XP", name: "Cross-project", color: "#326d9b", description: "Shared libraries, structured context, and integration resources." },
};

const VIEW_META = {
  projects: ["ECOSYSTEM / PROJECTS", "Software Thrust projects"],
  explore: ["REGISTRY / EXPLORE", "Capability registry"],
  compose: ["WORKFLOWS / COMPOSE", "Workflow composer"],
  runs: ["EXECUTION / RUNS", "Run operations"],
  artifacts: ["PROVENANCE / ARTIFACTS", "Produced artifacts"],
  environments: ["RUNTIMES / ENVIRONMENTS", "Execution environments"],
};

const requestedView = new URLSearchParams(window.location.search).get("view");
const initialView = Object.hasOwn(VIEW_META, requestedView) ? requestedView : "projects";
const state = { capabilities: [], workflows: [], runs: [], artifacts: [], view: initialView, query: "", projectFilter: "all", statusFilter: "all", selectedOperation: null, selectedWorkflow: null, parameters: {}, inputContents: {} };
const workspace = document.querySelector("#workspace");

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[char]);
}

async function api(path, options = {}) {
  const response = await fetch(`/api/v1${path}`, { headers: { "Content-Type": "application/json" }, ...options });
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || `Request failed: ${response.status}`);
  return body;
}

function badgeClass(status) {
  if (["production-approved", "integration-tested", "succeeded", "verified"].includes(status)) return "green";
  if (["discovered", "pending", "queued", "declared"].includes(status)) return "amber";
  if (["failed", "canceled"].includes(status)) return "red";
  return "";
}

function showToast(message) {
  const toast = document.createElement("div");
  toast.className = "toast";
  toast.textContent = message;
  document.querySelector("#toast-region").append(toast);
  setTimeout(() => toast.remove(), 3500);
}

function renderSummary() {
  const operations = state.capabilities.reduce((count, item) => count + item.operations.length, 0);
  const tested = state.capabilities.filter(item => ["smoke-tested", "integration-tested", "production-approved"].includes(item.validation.status)).length;
  const activeRuns = state.runs.filter(run => ["queued", "running"].includes(run.state)).length;
  document.querySelector("#summary-strip").innerHTML = [
    [state.capabilities.length, "Registered capabilities"],
    [operations, "Executable operations"],
    [tested, "Evidence tested"],
    [activeRuns, "Active runs"],
  ].map(([value, label]) => `<div class="metric"><strong>${value}</strong><span>${label}</span></div>`).join("");
}

function filteredCapabilities() {
  const query = state.query.trim().toLowerCase();
  return state.capabilities.filter(item => {
    const matchesQuery = !query || [item.name, item.id, item.project, item.catalog_repository, item.description].join(" ").toLowerCase().includes(query);
    return matchesQuery && (state.projectFilter === "all" || item.project === state.projectFilter) && (state.statusFilter === "all" || item.validation.status === state.statusFilter);
  });
}

function sectionHeader(title, detail, controls = "") {
  return `<div class="section-header"><div><h2>${escapeHtml(title)}</h2><p>${escapeHtml(detail)}</p></div>${controls}</div>`;
}

function renderProjects() {
  const panels = Object.entries(PROJECTS).map(([id, project]) => {
    const capabilities = state.capabilities.filter(item => item.project === id);
    const operations = capabilities.reduce((count, item) => count + item.operations.length, 0);
    const evidence = capabilities.filter(item => item.validation.evidence.length).length;
    return `<article class="project-panel" style="--project-color:${project.color}" data-project="${id}">
      <header><span class="project-code">${project.code}</span><span class="badge ${capabilities.length ? "green" : "amber"}">${capabilities.length ? "cataloged" : "pending"}</span></header>
      <h3>${project.name}</h3><p>${project.description}</p>
      <div class="project-counts"><span><strong>${capabilities.length}</strong>capabilities</span><span><strong>${operations}</strong>operations</span><span><strong>${evidence}</strong>evidence</span></div>
    </article>`;
  }).join("");
  workspace.innerHTML = sectionHeader("Project readiness", "Attribution and curator validation remain separate throughout the registry.") + `<div class="project-grid">${panels}</div>`;
  workspace.querySelectorAll("[data-project]").forEach(panel => panel.addEventListener("click", () => {
    state.projectFilter = panel.dataset.project;
    switchView("explore");
  }));
}

function renderExplore() {
  const projects = Object.entries(PROJECTS).map(([id, value]) => `<option value="${id}" ${state.projectFilter === id ? "selected" : ""}>${value.code} · ${value.name}</option>`).join("");
  const statuses = [...new Set(state.capabilities.map(item => item.validation.status))].sort().map(status => `<option value="${status}" ${state.statusFilter === status ? "selected" : ""}>${status}</option>`).join("");
  const rows = filteredCapabilities().map(item => `<tr data-capability="${item.id}">
    <td><span class="cell-title"><strong>${escapeHtml(item.name)}</strong><small>${escapeHtml(item.id)}@${escapeHtml(item.version)}</small></span></td>
    <td>${PROJECTS[item.project]?.code || item.project}</td>
    <td>${escapeHtml(item.catalog_repository)}</td>
    <td><span class="badge ${badgeClass(item.validation.status)}">${escapeHtml(item.validation.status)}</span></td>
    <td>${item.operations.length}</td><td>${item.resources.length}</td>
    <td><span class="badge ${badgeClass(item.integration.runtime_status)}">${escapeHtml(item.integration.runtime_status)}</span></td>
  </tr>`).join("");
  workspace.innerHTML = sectionHeader("Registry records", `${filteredCapabilities().length} of ${state.capabilities.length} capabilities`) + `
    <div class="toolbar"><select id="project-filter"><option value="all">All projects</option>${projects}</select><select id="status-filter"><option value="all">All validation states</option>${statuses}</select></div>
    <table class="data-table"><thead><tr><th>CAPABILITY</th><th>PROJECT</th><th>REPOSITORY</th><th>VALIDATION</th><th>OPS</th><th>RESOURCES</th><th>RUNTIME</th></tr></thead><tbody>${rows || `<tr><td colspan="7">No registry records match the current filters.</td></tr>`}</tbody></table>`;
  document.querySelector("#project-filter").addEventListener("change", event => { state.projectFilter = event.target.value; renderExplore(); });
  document.querySelector("#status-filter").addEventListener("change", event => { state.statusFilter = event.target.value; renderExplore(); });
  workspace.querySelectorAll("[data-capability]").forEach(row => row.addEventListener("click", () => openCapability(row.dataset.capability)));
}

function renderCompose() {
  const operations = state.capabilities.flatMap(capability => capability.operations.map(operation => ({ capability, operation })));
  const palette = operations.map(({ capability, operation }) => `<button class="operation-item" data-operation="${capability.id}/${operation.id}"><strong>${escapeHtml(operation.title)}</strong><small>${PROJECTS[capability.project]?.code} · ${escapeHtml(capability.id)}</small></button>`).join("");
  const workflowPalette = state.workflows.map(workflow => `<button class="operation-item workflow-template" data-workflow="${workflow.id}/${workflow.version}"><strong>${escapeHtml(workflow.definition.metadata.name)}</strong><small>${workflow.definition.spec.nodes.length} nodes · ${escapeHtml(workflow.version)}</small></button>`).join("");
  const selectedWorkflow = state.workflows.find(workflow => `${workflow.id}/${workflow.version}` === state.selectedWorkflow);
  const selected = operations.find(({ capability, operation }) => `${capability.id}/${operation.id}` === state.selectedOperation) || (operations.length === 1 ? operations[0] : null);
  if (selected && !state.selectedOperation && !selectedWorkflow) selectOperation(selected.capability, selected.operation);
  const runnable = Boolean(selectedWorkflow || selected);
  const canvas = selectedWorkflow ? workflowGraph(selectedWorkflow.definition) : selected ? operationNode(selected.capability, selected.operation) : operations.length ? `<div class="empty-canvas"><div><strong>Select an operation</strong><p>Add registry operations to the draft. Typed ports and parameters are validated again by the API on publication.</p></div></div>` : `<div class="empty-canvas"><div><strong>No executable runtime is published</strong><p>Audited resources are visible in Explore. Composition unlocks when a capability publishes an immutable operation runtime.</p></div></div>`;
  const selection = selectedWorkflow ? workflowDetail(selectedWorkflow.definition) : selected ? operationDetail(selected.capability, selected.operation) : `<dl><dt>Registry</dt><dd>${state.capabilities.length} capabilities loaded</dd><dt>Connection policy</dt><dd>Exact artifact type and major version</dd><dt>Execution</dt><dd>Controlled runner only</dd></dl>`;
  const actionLabel = selectedWorkflow ? "Run workflow" : "Publish & run";
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

function operationNode(capability, operation) {
  return `<article class="workflow-node"><header><strong>${escapeHtml(operation.title)}</strong><small>${escapeHtml(capability.id)} / ${escapeHtml(operation.id)}</small></header><div class="ports"><span>IN · ${Object.keys(operation.inputs).length}</span><span>OUT · ${Object.keys(operation.outputs).length}</span></div></article>`;
}

function workflowGraph(workflow) {
  const nodes = workflow.spec.nodes.map((node, index) => {
    const project = state.capabilities.find(item => item.id === node.operation.capability)?.project;
    return `<article class="workflow-node" style="--node-index:${index}"><header><strong>${escapeHtml(node.id)}</strong><small>${escapeHtml(node.operation.capability)} / ${escapeHtml(node.operation.operation)}</small></header><div class="ports"><span>${escapeHtml(PROJECTS[project]?.code || project)}</span><span>${escapeHtml(node.operation.version)}</span></div></article>`;
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
  return `<dl><dt>Project</dt><dd>${escapeHtml(PROJECTS[capability.project]?.name)}</dd><dt>Runtime</dt><dd>${escapeHtml(operation.runtime.type)}</dd><dt>Targets</dt><dd>${escapeHtml(operation.execution_targets.join(", "))}</dd><dt>Validation</dt><dd>${escapeHtml(capability.validation.status)}</dd></dl>${inputs ? `<p class="panel-label parameter-heading">INPUT ARTIFACTS</p>${inputs}` : ""}${parameters ? `<p class="panel-label parameter-heading">PARAMETERS</p>${parameters}` : ""}`;
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
  button.disabled = true; button.textContent = "Submitting";
  try {
    const runInputs = {};
    for (const [name, port] of Object.entries(operation.inputs)) {
      if ((port.required ?? true) && !state.inputContents[name]?.trim()) throw new Error(`Input artifact ${name} is required`);
      if (state.inputContents[name]?.trim()) {
        const artifact = await api("/artifacts", { method: "POST", body: JSON.stringify({ artifact_type: port.artifact_type, name: `${name}.txt`, content: state.inputContents[name], created_by: "workbench-user" }) });
        runInputs[name] = artifact.id;
      }
    }
    await api("/workflows", { method: "POST", body: JSON.stringify({ workflow, created_by: "workbench-user" }) });
    const run = await api("/runs", { method: "POST", body: JSON.stringify({ workflow_id: workflowId, version: "0.1.0", inputs: runInputs, execution_target: "local-development", created_by: "workbench-user" }) });
    await api(`/runs/${run.id}/execute`, { method: "POST", body: "{}" });
    showToast("Workflow completed through the controlled runner");
    await loadData(); switchView("runs");
  } catch (error) {
    showToast(error.message); button.disabled = false; button.textContent = "Publish & run";
  }
}

async function runPublishedWorkflow() {
  const workflow = state.workflows.find(item => `${item.id}/${item.version}` === state.selectedWorkflow);
  const button = document.querySelector("#publish-run");
  button.disabled = true; button.textContent = "Submitting";
  try {
    const runInputs = {};
    for (const [name, definition] of Object.entries(workflow.definition.spec.inputs)) {
      if ((definition.required ?? true) && !state.inputContents[name]?.trim()) throw new Error(`Input artifact ${name} is required`);
      if (state.inputContents[name]?.trim()) {
        const extension = definition.artifact_type.includes("circuit") ? "qasm" : "txt";
        const artifact = await api("/artifacts", { method: "POST", body: JSON.stringify({ artifact_type: definition.artifact_type, name: `${name}.${extension}`, content: state.inputContents[name], created_by: "workbench-user" }) });
        runInputs[name] = artifact.id;
      }
    }
    const run = await api("/runs", { method: "POST", body: JSON.stringify({ workflow_id: workflow.id, version: workflow.version, inputs: runInputs, execution_target: "local-development", created_by: "workbench-user" }) });
    await api(`/runs/${run.id}/execute`, { method: "POST", body: "{}" });
    showToast("Published workflow completed through the controlled runner");
    await loadData(); switchView("runs");
  } catch (error) {
    showToast(error.message); button.disabled = false; button.textContent = "Run workflow";
  }
}

function renderRuns() {
  if (!state.runs.length) {
    workspace.innerHTML = `<div class="empty-state"><div><span class="empty-code">RUN</span><h2>No execution records</h2><p>Runs will appear here after a validated workflow version is submitted to a configured controlled runner.</p></div></div>`;
    return;
  }
  const rows = state.runs.map(run => `<tr data-run="${run.id}"><td><span class="cell-title"><strong>${escapeHtml(run.workflow_id)}</strong><small>${escapeHtml(run.id)}</small></span></td><td>${escapeHtml(run.workflow_version)}</td><td><span class="badge ${badgeClass(run.state)}">${escapeHtml(run.state)}</span></td><td>${run.tasks.length}</td><td>${escapeHtml(run.execution_target)}</td><td>${escapeHtml(run.created_at)}</td></tr>`).join("");
  workspace.innerHTML = sectionHeader("Run history", `${state.runs.length} persisted execution records`) + `<table class="data-table run-table"><thead><tr><th>WORKFLOW / RUN</th><th>VERSION</th><th>STATE</th><th>TASKS</th><th>TARGET</th><th>CREATED</th></tr></thead><tbody>${rows}</tbody></table>`;
  workspace.querySelectorAll("[data-run]").forEach(row => row.addEventListener("click", () => openRun(row.dataset.run)));
}

function renderArtifacts() {
  const artifacts = state.artifacts;
  if (!artifacts.length) {
    workspace.innerHTML = `<div class="empty-state"><div><span class="empty-code">ART</span><h2>No artifacts recorded</h2><p>Checksummed outputs and their producing run and task will be indexed here.</p></div></div>`;
    return;
  }
  const rows = artifacts.map(item => `<tr><td><span class="cell-title"><strong>${escapeHtml(item.id)}</strong><small>${escapeHtml(item.artifact_type)}</small></span></td><td>${escapeHtml(item.provenance)}</td><td>${escapeHtml(item.size_bytes)} B</td><td><span class="cell-title"><strong>${escapeHtml(item.checksum.slice(0, 24))}…</strong><small>${escapeHtml(item.uri)}</small></span></td></tr>`).join("");
  workspace.innerHTML = sectionHeader("Artifact index", `${artifacts.length} checksummed artifacts`) + `<table class="data-table"><thead><tr><th>ARTIFACT</th><th>PROVENANCE</th><th>SIZE</th><th>CHECKSUM / URI</th></tr></thead><tbody>${rows}</tbody></table>`;
}

function renderEnvironments() {
  const runtimes = state.capabilities.flatMap(capability => capability.operations.map(operation => ({ capability, operation })));
  if (!runtimes.length) {
    workspace.innerHTML = `<div class="empty-state"><div><span class="empty-code">ENV</span><h2>No component runtime published</h2><p>Shared development environments exist, but production operations require immutable component-specific images or approved runtime mappings.</p></div></div>`;
    return;
  }
  const rows = runtimes.map(({ capability, operation }) => `<tr><td>${escapeHtml(capability.name)}</td><td>${escapeHtml(operation.id)}</td><td>${escapeHtml(operation.runtime.type)}</td><td><span class="cell-title"><strong>${escapeHtml(operation.runtime.digest.slice(0, 20))}…</strong><small>${escapeHtml(operation.runtime.reference)}</small></span></td><td>${escapeHtml(operation.execution_targets.join(", "))}</td></tr>`).join("");
  workspace.innerHTML = sectionHeader("Runtime inventory", `${runtimes.length} operation runtimes`) + `<table class="data-table"><thead><tr><th>CAPABILITY</th><th>OPERATION</th><th>TYPE</th><th>IDENTITY</th><th>TARGETS</th></tr></thead><tbody>${rows}</tbody></table>`;
}

function render() {
  renderSummary();
  ({ projects: renderProjects, explore: renderExplore, compose: renderCompose, runs: renderRuns, artifacts: renderArtifacts, environments: renderEnvironments })[state.view]();
}

function switchView(view) {
  state.view = view;
  const url = new URL(window.location.href);
  if (view === "projects") url.searchParams.delete("view"); else url.searchParams.set("view", view);
  window.history.replaceState({}, "", url);
  document.querySelectorAll(".nav-item").forEach(item => item.classList.toggle("active", item.dataset.view === view));
  document.querySelector("#view-eyebrow").textContent = VIEW_META[view][0];
  document.querySelector("#view-title").textContent = VIEW_META[view][1];
  render();
}

function openInspector(html) {
  document.querySelector("#inspector-content").innerHTML = html;
  document.querySelector("#inspector").classList.add("open");
  document.querySelector("#inspector").setAttribute("aria-hidden", "false");
  document.querySelector("#scrim").classList.add("open");
}

function closeInspector() {
  document.querySelector("#inspector").classList.remove("open");
  document.querySelector("#inspector").setAttribute("aria-hidden", "true");
  document.querySelector("#scrim").classList.remove("open");
}

function openCapability(id) {
  const item = state.capabilities.find(capability => capability.id === id);
  openInspector(`<h2>${escapeHtml(item.name)}</h2><p class="description">${escapeHtml(item.description)}</p><p><span class="badge ${badgeClass(item.validation.status)}">${escapeHtml(item.validation.status)}</span></p><dl class="detail-list"><dt>Capability</dt><dd>${escapeHtml(item.id)}@${escapeHtml(item.version)}</dd><dt>Origin project</dt><dd>${escapeHtml(PROJECTS[item.project]?.name || item.project)}</dd><dt>Repository</dt><dd>${escapeHtml(item.repository.url)}</dd><dt>Revision</dt><dd>${escapeHtml(item.repository.revision)}</dd><dt>Authority</dt><dd>${escapeHtml(item.integration.authority)}</dd><dt>Curated by</dt><dd>${escapeHtml(item.integration.maintainers.join(", "))}</dd><dt>Project reviewed</dt><dd>${item.integration.project_reviewed ? "yes" : "no"}</dd><dt>Runtime</dt><dd>${escapeHtml(item.integration.runtime_status)}</dd><dt>Operations</dt><dd>${item.operations.length}</dd><dt>Resources</dt><dd>${item.resources.length}</dd></dl>`);
}

function openRun(id) {
  const run = state.runs.find(item => item.id === id);
  const timeline = run.tasks.map(task => `<div class="timeline-row"><span class="badge ${badgeClass(task.state)}">${escapeHtml(task.state)}</span><span class="timeline-rail"><i class="timeline-dot"></i></span><div><strong>${escapeHtml(task.node_id)}</strong><p class="description">${escapeHtml(task.operation.capability)} / ${escapeHtml(task.operation.operation)} · attempt ${task.attempt}</p></div></div>`).join("");
  const retry = run.tasks.find(task => task.state === "failed");
  openInspector(`<h2>${escapeHtml(run.workflow_id)}</h2><p class="description">${escapeHtml(run.id)}</p><p><span class="badge ${badgeClass(run.state)}">${escapeHtml(run.state)}</span></p><div class="run-actions"><button class="button secondary" id="export-run">Export</button>${["queued", "running"].includes(run.state) ? `<button class="button danger" id="cancel-run">Cancel</button>` : ""}${retry ? `<button class="button" id="retry-run" data-node="${escapeHtml(retry.node_id)}">Retry task</button>` : ""}</div><div class="timeline">${timeline}</div>`);
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
  try { await api(`/runs/${runId}/tasks/${nodeId}/retry`, { method: "POST", body: "{}" }); await api(`/runs/${runId}/execute`, { method: "POST", body: "{}" }); closeInspector(); await loadData(); } catch (error) { showToast(error.message); }
}

async function loadData() {
  workspace.innerHTML = `<div class="loading">LOADING REGISTRY AND RUN STATE</div>`;
  try {
    const [capabilities, workflows, runs, artifacts] = await Promise.all([api("/capabilities"), api("/workflows"), api("/runs"), api("/artifacts")]);
    state.capabilities = capabilities; state.workflows = workflows; state.runs = runs; state.artifacts = artifacts;
    if (!state.selectedWorkflow && !state.selectedOperation) {
      const preferred = workflows.find(item => item.id === "ct-hw-qasm-analysis") || workflows[0];
      if (preferred) selectWorkflow(`${preferred.id}/${preferred.version}`);
    }
    document.querySelector("#service-dot").classList.add("online");
    document.querySelector("#service-state").textContent = "Online";
    switchView(state.view);
  } catch (error) {
    document.querySelector("#service-state").textContent = "Unavailable";
    workspace.innerHTML = `<div class="empty-state"><div><span class="empty-code">ERR</span><h2>Workbench service unavailable</h2><p>${escapeHtml(error.message)}</p></div></div>`;
  }
}

document.querySelectorAll(".nav-item").forEach(item => item.addEventListener("click", () => switchView(item.dataset.view)));
document.querySelector("#refresh-button").addEventListener("click", () => { loadData(); showToast("Registry and run state refreshed"); });
document.querySelector("#global-search").addEventListener("input", event => { state.query = event.target.value; if (state.view !== "explore") switchView("explore"); else renderExplore(); });
document.querySelector("#close-inspector").addEventListener("click", closeInspector);
document.querySelector("#scrim").addEventListener("click", closeInspector);
document.addEventListener("keydown", event => { if (event.key === "Escape") closeInspector(); });
loadData();
