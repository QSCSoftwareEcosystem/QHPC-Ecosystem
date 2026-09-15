import { expect, test } from "@playwright/test";


const IQM_RUNTIME_DIGEST =
  "sha256:718119bf215316c3b09c825203a30c2f9868490302f36f5e6fba303244f45413";

function iqmWorker(mode: "simulation" | "hardware", credentialAvailable = false) {
  return {
    id: `${mode}-iqm-worker`,
    available: true,
    kind: "target",
    metadata: {
      execution_targets: ["local-development"],
      execution_classes: ["quantum-backend"],
      runtime_digests: [IQM_RUNTIME_DIGEST],
      iqm: mode === "simulation"
        ? { mode, provider: "simulated-iqm" }
        : {
            mode,
            provider: "iqm-client-qiskit",
            endpoint_configured: true,
            device_alias: "approved-qpu",
            access_scope: "internal-alpha",
            credential_available: credentialAvailable,
          },
    },
  };
}

function iqmExecutionRun(
  taskState: string,
  attemptState: string,
  targetState: string,
  runState = "running",
) {
  return {
    id: `run-iqm-${taskState}-${attemptState}`,
    workflow_id: "ftqc-iqm-steane-execution",
    workflow_version: "0.1.0",
    state: runState,
    created_at: "2026-09-10T12:00:00Z",
    execution_target: "local-development",
    outputs: {},
    tasks: [{
      node_id: "execute",
      state: taskState,
      operation: {
        capability: "ftqc-compiler",
        operation: "route-submit-collect",
      },
      attempts: [{ state: attemptState, target_state: targetState }],
    }],
  };
}

async function mockIqmShowcase(
  page: import("@playwright/test").Page,
  workers: unknown[],
  getRuns: () => unknown[],
) {
  await page.route("**/api/v1/runs", async route => {
    if (route.request().method() !== "GET") {
      await route.continue();
      return;
    }
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(getRuns()),
    });
  });
  await page.route("**/api/v1/workers", async route => {
    const response = await route.fetch();
    const current = await response.json();
    await route.fulfill({ response, body: JSON.stringify([...current, ...workers]) });
  });
}


test("presents the EQO-QSC product instead of internal project governance", async ({ page }) => {
  await page.goto("/");

  const rail = page.locator(".rail");
  const viewportWidth = page.viewportSize()?.width ?? 1440;
  const productName = rail.getByText("EQO-QSC", { exact: true });
  const productExpansion = rail.getByText(
    "Ecosystem for Quantum Orchestration",
    { exact: true },
  );
  if (viewportWidth > 760) {
    await expect(productName).toBeVisible();
    await expect(productExpansion).toBeVisible();
    await expect(rail.getByText("Workspace", { exact: true })).toBeVisible();
    await expect(rail.getByText("Execution", { exact: true })).toBeVisible();
    await expect(rail.getByText("System", { exact: true })).toBeVisible();
  } else {
    await expect(productName).toBeHidden();
    await expect(productExpansion).toBeHidden();
    await expect(rail.getByText("Workspace", { exact: true })).toBeHidden();
    await expect(rail.getByText("Execution", { exact: true })).toBeHidden();
    await expect(rail.getByText("System", { exact: true })).toBeHidden();
  }
  const expectedLogoWidth =
    viewportWidth > 1080 ? 146 : viewportWidth > 760 ? 112 : 104;
  await expect(rail.getByAltText("Quantum Science Center")).toHaveCSS(
    "width",
    `${expectedLogoWidth}px`,
  );

  await expect(
    page.getByRole("heading", { name: "EQO-QSC" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", {
      name: "Integrate heterogeneous quantum–classical workflows across QHPC systems",
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Execution services" }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Projects" })).toHaveCount(0);

  const overviewNavigation = page.getByRole("button", {
    name: "Overview",
    exact: true,
  });
  const toolsNavigation = page.getByRole("button", {
    name: "Tools",
    exact: true,
  });
  await expect(overviewNavigation).toHaveAttribute("aria-current", "page");
  await toolsNavigation.click();
  await expect(toolsNavigation).toHaveAttribute("aria-current", "page");
  await expect(overviewNavigation).not.toHaveAttribute("aria-current");
  await expect(
    page.getByRole("heading", { name: "Integrated software" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Tool catalog" }),
  ).toBeVisible();
  await expect(
    page.getByRole("columnheader", { name: "PROJECT" }),
  ).toHaveCount(0);
});


test("explains what a tool does and how to use it", async ({ page }) => {
  await page.goto("/?view=tools");

  const openqevo = page.locator(
    'tr[data-capability="openqevo-library"]',
  );
  await expect(openqevo).toContainText(
    "Reusable, documented, and reproducible Python library",
  );
  await openqevo.click();

  const inspector = page.getByRole("dialog", { name: "Details" });
  await expect(
    inspector.getByRole("heading", {
      name: "OpenQEvo",
    }),
  ).toBeVisible();
  await expect(inspector).toContainText("OpenQEvo Library and Method Context");
  await expect(
    inspector.getByRole("heading", { name: "When to use this tool" }),
  ).toBeVisible();
  await expect(
    inspector.getByRole("heading", { name: "Quick start" }),
  ).toBeVisible();
  await expect(inspector).toContainText(
    "Open Compose and choose Hamiltonian to evolution circuit.",
  );
  await expect(inspector.getByRole("button", { name: "Open Compose" })).toBeVisible();

  const synthesis = inspector.locator("details.tool-operation").filter({
    hasText: "Synthesize a Trotter evolution circuit",
  });
  await synthesis.locator("summary").click();
  await expect(synthesis).toContainText("qhpc.pauli-hamiltonian@1");
  await expect(synthesis).toContainText("Evolution time");
  await expect(synthesis).toContainText("local-development");
  await expect(inspector).toContainText(
    "Circuit synthesis is a local-development OpenQEvo and Qiskit bridge",
  );
});


test("shows the FTQC IQM run as a hardware evidence candidate", async ({
  page,
}) => {
  await page.goto("/?view=tools&capability=ftqc-compiler");

  const ftqc = page.locator('tr[data-capability="ftqc-compiler"]');
  await expect(ftqc).toContainText(
    "C++ and LLVM/MLIR compiler project for fault-tolerant quantum operations",
  );

  const inspector = page.getByRole("dialog", { name: "Details" });
  await expect(
    inspector.getByRole("heading", {
      name: "FTQC",
    }),
  ).toBeVisible();
  await expect(inspector).toContainText(
    "FTQC Fault-Tolerant Compiler",
  );
  await expect(inspector).toContainText(
    "one-logical-qubit ORNL IQM demonstration candidate",
  );
  await expect(inspector).toContainText(
    "ftqc-iqm-logical-qubit-candidate",
  );
  await expect(inspector).toContainText(
    "not verified hardware evidence",
  );
  await expect(inspector).toContainText(
    "does not assert that they are the same device",
  );
});


test("animates the QEC and QHPC control loop and offers a reduced-motion state", async ({ page }) => {
  await page.goto("/");

  const loop = page.locator("#qsc-quantum-ascii");
  const status = page.locator("#qsc-quantum-state");
  await loop.scrollIntoViewIfNeeded();
  await expect(loop).toBeVisible();
  await expect(loop).toContainText("QEC + QHPC CONTROL LOOP");
  await expect
    .poll(() => loop.textContent(), { timeout: 7_000 })
    .toContain("02/04 DISPATCH encoded circuit -> QPU");
  await expect
    .poll(() => loop.textContent(), { timeout: 7_000 })
    .toContain("03/04 DECODE   syndrome -> HPC decoder");
  await expect
    .poll(() => loop.textContent(), { timeout: 7_000 })
    .toContain("04/04 RECOVER  frame + provenance -> cycle");
  await expect(status).toHaveText("Explanatory sequence · not live telemetry");

  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.reload();
  await expect(loop).toContainText("STATIC  QEC protection <-> QHPC orchestration");
  await expect(status).toHaveText("Static schematic · reduced motion");
  const staticFrame = await loop.textContent();
  await page.waitForTimeout(1_500);
  await expect(loop).toHaveText(staticFrame ?? "");
});


test("presents FTQC IQM as a runnable flagship showcase", async ({ page }) => {
  await page.goto("/?view=showcases");

  await expect(
    page.getByRole("button", { name: "Showcases", exact: true }),
  ).toHaveAttribute("aria-current", "page");
  await expect(
    page.getByRole("heading", {
      name: "Prepare a fault-tolerant logical qubit for an IQM quantum computer",
    }),
  ).toBeVisible();
  await expect(page.locator(".showcase-trace li")).toHaveCount(6);
  await expect(page.getByText("1 logical → 7 data qubits")).toBeVisible();
  await expect(page.getByText("58 instructions")).toBeVisible();
  await expect(page.getByText("114 instructions")).toBeVisible();
  await expect(page.getByText("Not yet claimed")).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "The next action is gated, not hidden" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Hardware execution unavailable" }),
  ).toBeDisabled();
  await expect(
    page.getByRole("heading", { name: "Awaiting execution" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Simulation worker unavailable" }),
  ).toBeDisabled();

  await page
    .getByRole("button", { name: "Run logical-qubit preparation" })
    .click();
  await expect(page).toHaveURL(/view=compose/);
  await expect(page).toHaveURL(/workflow=ftqc-iqm-steane-preparation/);
  await expect(
    page.getByRole("heading", {
      name: "Prepare one Steane logical qubit for IQM",
    }),
  ).toBeVisible();
});


test("keeps simulated IQM orchestration distinct from hardware admission", async ({
  page,
}) => {
  await page.route("**/api/v1/runs", async route => {
    if (route.request().method() !== "GET") {
      await route.continue();
      return;
    }
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify([{
        id: "run-simulated-iqm",
        workflow_id: "ftqc-iqm-steane-execution",
        workflow_version: "0.1.0",
        state: "running",
        created_at: "2026-09-10T12:00:00Z",
        execution_target: "local-development",
        outputs: {},
        tasks: [{
          node_id: "execute",
          state: "running",
          operation: {
            capability: "ftqc-compiler",
            operation: "route-submit-collect",
          },
          attempts: [{ state: "collecting", target_state: "succeeded" }],
        }],
      }]),
    });
  });
  await page.route("**/api/v1/workers", async route => {
    const response = await route.fetch();
    const workers = await response.json();
    workers.push({
      id: "safe-simulation-worker",
      available: true,
      kind: "target",
      metadata: {
        execution_targets: ["local-development"],
        execution_classes: ["quantum-backend"],
        runtime_digests: [
          "sha256:718119bf215316c3b09c825203a30c2f9868490302f36f5e6fba303244f45413",
        ],
        iqm: { mode: "simulation" },
      },
    });
    await route.fulfill({ response, body: JSON.stringify(workers) });
  });

  await page.goto("/?view=showcases");

  await expect(
    page.getByRole("heading", { name: "Collecting results" }),
  ).toBeVisible();
  await expect(
    page.getByText("simulation worker is available", { exact: false }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Open simulated execution workflow" }),
  ).toBeEnabled();
  await expect(
    page.getByRole("button", { name: "Hardware execution unavailable" }),
  ).toBeDisabled();
});


test("renders every non-secret IQM execution phase", async ({ page }) => {
  let currentRun = iqmExecutionRun("running", "submitting", "unknown");
  await mockIqmShowcase(page, [iqmWorker("simulation")], () => [currentRun]);

  const phases = [
    ["running", "submitting", "unknown", "running", "Routing and submitting"],
    ["running", "submitted", "queued", "running", "Provider queued"],
    ["running", "running", "running", "running", "Provider running"],
    ["cancel_requested", "cancel_requested", "queued", "running", "Cancellation requested"],
    ["running", "collecting", "succeeded", "running", "Collecting results"],
    ["succeeded", "succeeded", "succeeded", "succeeded", "Completed"],
    ["failed", "failed", "failed", "failed", "Failed"],
  ] as const;

  for (const [taskState, attemptState, targetState, runState, label] of phases) {
    currentRun = iqmExecutionRun(taskState, attemptState, targetState, runState);
    await page.goto("/?view=showcases");
    await expect(page.getByRole("heading", { name: label })).toBeVisible();
  }

  currentRun = iqmExecutionRun("failed", "failed", "failed", "failed");
  currentRun.tasks[0].error = {
    code: "IQMAdapterError",
    message: "provider response contained worker-only-token",
  };
  await page.goto("/?view=showcases");
  await page.getByRole("button", { name: "Open run record" }).click();
  const inspector = page.getByRole("dialog", { name: "Details" });
  await expect(inspector).toContainText("Provider details are deliberately not displayed");
  await expect(inspector).not.toContainText("worker-only-token");
});


test("distinguishes credential-unavailable from fully admitted hardware", async ({
  page,
}) => {
  const workers = [iqmWorker("hardware", false)];
  await mockIqmShowcase(page, workers, () => []);
  await page.goto("/?view=showcases");
  await expect(page.getByText("Worker-local credential", { exact: true })).toBeVisible();
  await expect(
    page.getByText("The worker does not currently report an available credential reference."),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Hardware execution unavailable" }),
  ).toBeDisabled();

  workers[0] = iqmWorker("hardware", true);
  await page.goto("/?view=showcases");
  await expect(
    page.getByRole("button", { name: "Open hardware execution workflow" }),
  ).toBeEnabled();
});


test("renders a static high-resolution QSC binary canvas", async ({ page }) => {
  await page.goto("/");

  const nebula = page.locator("#neon-nebula");
  await expect(nebula).toBeVisible();
  const signature = () => nebula.evaluate((canvas: HTMLCanvasElement) => {
    const sample = document.createElement("canvas");
    sample.width = 24;
    sample.height = 14;
    const context = sample.getContext("2d");
    context?.drawImage(canvas, 0, 0, sample.width, sample.height);
    const pixels = context?.getImageData(0, 0, sample.width, sample.height).data ?? [];
    let hash = 2166136261;
    for (const value of pixels) {
      hash ^= value;
      hash = Math.imul(hash, 16777619);
    }
    return {
      width: canvas.width,
      height: canvas.height,
      cssWidth: canvas.getBoundingClientRect().width,
      cssHeight: canvas.getBoundingClientRect().height,
      pixelRatio: Number(canvas.dataset.pixelRatio),
      staticRender: canvas.dataset.static,
      hash: hash >>> 0,
    };
  });

  const first = await signature();
  expect(first.staticRender).toBe("true");
  expect(first.pixelRatio).toBeGreaterThanOrEqual(1.5);
  expect(first.width).toBeGreaterThan(first.cssWidth);
  expect(first.height).toBeGreaterThan(first.cssHeight);
  await page.waitForTimeout(260);
  expect((await signature()).hash).toBe(first.hash);
  expect(Number(await nebula.getAttribute("data-render-ms"))).toBeLessThan(250);
});


test("creates, saves, and validates a typed workflow draft", async ({ page }) => {
  let submittedRun: Record<string, unknown> | undefined;
  await page.route("**/api/v1/runs", async (route) => {
    if (route.request().method() !== "POST") {
      await route.continue();
      return;
    }
    submittedRun = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        id: "run-advanced-browser-smoke",
        workflow_id: submittedRun.workflow_id,
        workflow_version: submittedRun.version,
        state: "queued",
        outputs: {},
      }),
    });
  });

  await page.goto("/?view=compose");
  await expect(page.locator(".qhpc-composer")).toBeVisible();
  await page.getByRole("tab", { name: "Advanced", exact: true }).click();
  await expect(
    page
      .locator(".composer-inspector-panel")
      .getByRole("button", { name: "Publish to run", exact: true }),
  ).toBeVisible();

  await page
    .getByRole("button", { name: /List registered evolution methods/ })
    .click();
  await expect(page.locator(".composer-operation-node")).toHaveCount(1);

  const exposeOutput = page.getByRole("button", {
    name: "Expose methods as workflow output",
  });
  await exposeOutput.click();
  await expect(page.locator(".composer-boundary-node.is-output")).toHaveCount(1);
  await expect(page.locator(".composer-validation-strip")).toContainText(
    "1 operations",
  );

  const uniqueId = `browser-smoke-${Date.now()}`;
  await page.getByLabel("Workflow id").fill(uniqueId);
  await page.getByLabel("Name").fill("Browser smoke workflow");
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.locator(".composer-save-state")).toContainText(
    /Draft r\d+/,
  );

  await page.getByRole("button", { name: "Validate", exact: true }).click();
  await expect(page.locator(".composer-save-state")).toContainText("Valid");

  await page
    .locator(".composer-primary-actions")
    .getByRole("button", { name: "Publish to run", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Run published workflow" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Run workflow", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Queue run", exact: true })
    .click();
  await expect(page.locator(".composer-save-state")).toContainText(
    "run-advanced-browser-smoke",
  );
  expect(submittedRun).toMatchObject({
    workflow_id: uniqueId,
    version: "0.1.0",
    inputs: {},
  });

  const drafts = await page.request.get(
    "/api/v1/workflow-drafts?owner=workbench-user",
  );
  expect(drafts.ok()).toBeTruthy();
  expect(
    (await drafts.json()).some(
      (item: { spec: { workflow: { metadata: { id: string } } } }) =>
        item.spec.workflow.metadata.id === uniqueId,
    ),
  ).toBeTruthy();
});


test("lays out advanced blocks for direct movement and port connections", async ({
  page,
}) => {
  await page.goto("/?view=compose");
  await page.getByRole("tab", { name: "Advanced", exact: true }).click();

  await page
    .getByRole("button", { name: /Synthesize a Trotter evolution circuit/ })
    .click();
  if ((page.viewportSize()?.width ?? 1440) <= 760) {
    await page.getByRole("button", { name: "Show library" }).click();
  }
  await page
    .getByRole("button", { name: /Transpile OpenQASM circuit/ })
    .click();

  const synthesis = page
    .locator(".react-flow__node")
    .filter({ hasText: "Synthesize a Trotter evolution circuit" });
  const transpiler = page
    .locator(".react-flow__node")
    .filter({ hasText: "Transpile OpenQASM circuit" });
  await expect(synthesis).toBeVisible();
  await expect(transpiler).toBeVisible();

  const beforeMove = await synthesis.boundingBox();
  const transpilerBox = await transpiler.boundingBox();
  expect(beforeMove).not.toBeNull();
  expect(transpilerBox).not.toBeNull();
  if (!beforeMove || !transpilerBox) return;

  const horizontalOverlap = Math.max(
    0,
    Math.min(beforeMove.x + beforeMove.width, transpilerBox.x + transpilerBox.width) -
      Math.max(beforeMove.x, transpilerBox.x),
  );
  const verticalOverlap = Math.max(
    0,
    Math.min(beforeMove.y + beforeMove.height, transpilerBox.y + transpilerBox.height) -
      Math.max(beforeMove.y, transpilerBox.y),
  );
  expect(horizontalOverlap * verticalOverlap).toBe(0);

  await page.mouse.move(beforeMove.x + 84, beforeMove.y + 22);
  await page.mouse.down();
  await page.mouse.move(beforeMove.x + 34, beforeMove.y + 22, { steps: 8 });
  await page.mouse.up();
  await expect
    .poll(async () => (await synthesis.boundingBox())?.x, { timeout: 3_000 })
    .not.toBe(beforeMove.x);

  const source = synthesis.locator(
    '.react-flow__handle.source[title="circuit: qhpc.quantum-circuit@1"]',
  );
  const target = transpiler.locator(
    '.react-flow__handle.target[title="circuit: qhpc.quantum-circuit@1"]',
  );
  await source.dragTo(target);
  await expect(page.locator(".react-flow__edge")).toHaveCount(1);
});


test("starts an advanced workflow from an explicit circuit input", async ({
  page,
}) => {
  await page.goto("/?view=compose");
  await page.getByRole("tab", { name: "Advanced", exact: true }).click();

  await page
    .getByRole("button", { name: "Add Input Circuit", exact: true })
    .click();

  await expect(
    page.locator(".composer-boundary-node.is-input"),
  ).toContainText("Input Circuit");
  await expect(page.getByLabel("Filter operations")).toHaveValue("qhpc.quantum-circuit@1");
  await expect(
    page.getByRole("button", { name: /Transpile OpenQASM circuit/ }),
  ).toBeVisible();
});


test("offers Hamiltonian input in the Operations palette", async ({ page }) => {
  await page.goto("/?view=compose");
  await page.getByRole("tab", { name: "Advanced", exact: true }).click();

  const inputs = page.getByLabel("Input artifacts");
  await expect(
    inputs.getByRole("button", { name: "Input OpenQASM Circuit" }),
  ).toBeVisible();
  await expect(
    inputs.getByRole("button", { name: "Input Pauli Hamiltonian" }),
  ).toBeVisible();

  await inputs.getByRole("button", { name: "Input Pauli Hamiltonian" }).click();

  await expect(
    page.locator(".composer-boundary-node.is-input"),
  ).toContainText("Input Hamiltonian");
  await expect(page.getByLabel("Filter operations")).toHaveValue(
    "qhpc.pauli-hamiltonian@1",
  );
  await expect(
    page.getByRole("button", { name: /Synthesize a Trotter evolution circuit/ }),
  ).toBeVisible();
});


test("configures a guided scientific path from an OpenQASM file", async ({ page }) => {
  let submittedRun: Record<string, unknown> | undefined;
  await page.route("**/api/v1/artifacts", async (route) => {
    if (route.request().method() !== "POST") {
      await route.continue();
      return;
    }
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        id: "artifact-guided-browser-smoke",
        artifact_type: "qhpc.quantum-circuit@1",
        name: "browser-bell.qasm",
        checksum: "sha256:browser-smoke",
        size_bytes: 80,
        provenance: "browser-smoke",
        uri: "artifact://artifact-guided-browser-smoke",
      }),
    });
  });
  await page.route("**/api/v1/runs", async (route) => {
    if (route.request().method() !== "POST") {
      await route.continue();
      return;
    }
    submittedRun = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        id: "run-guided-browser-smoke",
        workflow_id: "ct-hw-qasm-analysis",
        workflow_version: "0.1.0",
        state: "queued",
        outputs: {},
      }),
    });
  });

  await page.goto("/?view=compose");

  await expect(
    page.getByRole("tab", { name: "Guided", exact: true }),
  ).toHaveAttribute("aria-selected", "true");
  await expect(
    page.getByRole("heading", {
      name: "Prepare an evolution circuit for QHPC execution",
    }),
  ).toBeVisible();
  await expect(
    page
      .getByLabel("Scientific showcases")
      .getByText("10 runnable · 1 blueprint"),
  ).toBeVisible();
  await expect(
    page.getByText(
      "Cross-tool study · OpenQEvo + QASMTrans + STABSim + NWQEC",
    ),
  ).toBeVisible();
  const targetLabel = page.getByText("Mixed targets", { exact: true });
  if ((page.viewportSize()?.width ?? 1440) > 760) {
    await expect(targetLabel).toBeVisible();
  } else {
    await expect(targetLabel).toBeHidden();
  }
  await page.getByRole("button", { name: "Load example" }).click();
  await expect(
    page.getByLabel("Pauli Hamiltonian", { exact: true }),
  ).toHaveValue(/"pauli": "XX"/);
  const showcaseOutputs = page.locator(".composer-guided-outputs");
  await expect(showcaseOutputs).toContainText("Evolution synthesis report");
  await expect(showcaseOutputs).toContainText("Transpiled circuit");
  await expect(showcaseOutputs).toContainText("Circuit metrics");
  await expect(showcaseOutputs).toContainText("Clifford and T counts");
  await expect(
    page.getByRole("button", { name: "Run workflow" }),
  ).toBeEnabled();

  await page
    .getByRole("button", { name: /H6 QFlow chemistry cycle/ })
    .click();
  await expect(
    page.getByRole("heading", {
      name: "H6 QFlow heterogeneous chemistry cycle",
    }),
  ).toBeVisible();
  await expect(page.locator(".composer-blueprint-pipeline li")).toHaveCount(5);
  await expect(page.getByText("QIRIS over IRIS / QIR-EE")).toBeVisible();
  await expect(page.getByText("4.911e-10")).toBeVisible();
  const blueprintArtifacts = page.locator(".composer-blueprint-artifacts");
  await expect(
    blueprintArtifacts.getByText("qhpc.qflow-taskset@1"),
  ).toBeVisible();
  await expect(
    blueprintArtifacts.getByText("qhpc.ftqc-mlir@1"),
  ).toBeVisible();
  await expect(page.getByText("FTQC is optional.")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Run unavailable" }),
  ).toBeDisabled();
  await expect(
    page.getByRole("button", { name: "Open in Advanced", exact: true }),
  ).toHaveCount(0);

  await page
    .getByRole("button", { name: /Prepare one Steane logical qubit/ })
    .click();
  await expect(page.getByText("Flagship showcase · FTQC + Steane [[7,1,3]] + IQM JSON")).toBeVisible();
  await expect(
    page.getByRole("heading", {
      name: "Prepare one Steane logical qubit for IQM",
    }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Load logical |0⟩" }).click();
  await expect(
    page.getByLabel("One-logical-qubit OpenQASM 3 circuit", { exact: true }),
  ).toHaveValue(/qubit\[1\] q/);
  await expect(page.locator(".composer-guided-outputs")).toContainText(
    "FTQC preparation report",
  );

  await page
    .getByRole("button", { name: /Compare QEC memory protection/ })
    .click();
  await expect(
    page.getByRole("heading", { name: "Compare QEC memory protection" }),
  ).toBeVisible();
  await expect(page.getByText("Physical Error Rate").first()).toBeVisible();
  await expect(page.locator(".composer-guided-pipeline li")).toHaveCount(4);

  await page
    .getByRole("button", { name: /Fault-tolerant memory estimate/ })
    .click();
  await expect(
    page.getByRole("heading", {
      name: "Build and estimate a fault-tolerant memory circuit",
    }),
  ).toBeVisible();
  await expect(page.getByText("Physical Error Rate")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Run workflow" }),
  ).toBeEnabled();

  await page
    .getByRole("button", { name: /Hamiltonian to evolution circuit/ })
    .click();
  await expect(
    page.getByRole("heading", {
      name: "Synthesize an OpenQEvo Trotter circuit",
    }),
  ).toBeVisible();
  await expect(page.getByText("OpenQEvo + Qiskit")).toBeVisible();
  await expect(
    page.getByText("local-development", { exact: true }),
  ).toHaveText("local-development");
  await page.getByRole("button", { name: "Load example" }).click();
  await expect(
    page.getByLabel("Pauli Hamiltonian", { exact: true }),
  ).toHaveValue(/"pauli": "XX"/);
  await expect(page.locator(".composer-guided-outputs")).toContainText(
    "Evolution synthesis report",
  );
  await expect(page.getByText(/^Evolution time$/i)).toBeVisible();
  await expect(page.getByText(/^Trotter steps$/i)).toBeVisible();
  await expect(page.getByText(/^Suzuki order$/i)).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Run workflow" }),
  ).toBeEnabled();

  await page
    .getByRole("button", { name: /Compare dense evolution methods/ })
    .click();
  await expect(
    page.getByRole("heading", {
      name: "Evaluate an OpenQEvo dense evolution reference",
    }),
  ).toBeVisible();
  await expect(page.getByText("OpenQEvo", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Load example" }).click();
  await expect(
    page.getByLabel("Pauli Hamiltonian", { exact: true }),
  ).toHaveValue(/"pauli": "XX"/);
  await expect(page.locator(".composer-guided-outputs")).toContainText(
    "Evolution method result",
  );
  await expect(page.locator(".composer-guided-outputs")).toContainText(
    "Dense reference unitary",
  );
  await expect(page.getByText(/^Dense reference method$/i)).toBeVisible();
  await expect(page.getByText(/^Krylov subspace dimension$/i)).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Run workflow" }),
  ).toBeEnabled();

  await page
    .getByRole("button", { name: /Clifford and T resource count/ })
    .click();
  await page.getByRole("button", { name: "Load example" }).click();
  await expect(
    page.getByLabel("OpenQASM 2 circuit", { exact: true }),
  ).toHaveValue(/cx q\[0\],q\[1\];/);
  await expect(page.locator(".composer-guided-outputs")).toContainText(
    "Clifford and T counts",
  );

  await page
    .getByRole("button", { name: /Circuit transformation and metrics/ })
    .click();
  await page.getByLabel("Upload OpenQASM 2 circuit file").setInputFiles({
    name: "browser-bell.qasm",
    mimeType: "text/plain",
    buffer: Buffer.from(
      [
        "OPENQASM 2.0;",
        'include "qelib1.inc";',
        "qreg q[2];",
        "h q[0];",
        "cx q[0],q[1];",
      ].join("\n"),
    ),
  });

  await expect(
    page.getByLabel("OpenQASM 2 circuit", { exact: true }),
  ).toHaveValue(/OPENQASM 2\.0;/);
  await expect(page.getByText("browser-bell.qasm")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Run workflow" }),
  ).toBeEnabled();
  const outputs = page.locator(".composer-guided-outputs");
  await expect(outputs).toContainText("Transpiled circuit");
  await expect(outputs).toContainText("Circuit metrics");

  await page.getByRole("button", { name: "Run workflow" }).click();
  await expect(page.locator(".composer-guided-status")).toContainText(
    "run-guided-browser-smoke",
  );
  expect(submittedRun).toMatchObject({
    workflow_id: "ct-hw-qasm-analysis",
    version: "0.1.0",
    inputs: { circuit: "artifact-guided-browser-smoke" },
    execution_target: "development-slurm-docker",
  });

  await page
    .getByRole("button", { name: "Open in Advanced", exact: true })
    .click();
  await expect(
    page.getByRole("tab", { name: "Advanced", exact: true }),
  ).toHaveAttribute("aria-selected", "true");
  await expect(page.locator(".composer-operation-node")).toHaveCount(2);
  await expect(page.locator(".composer-boundary-node.is-input")).toHaveCount(1);
  await expect(page.locator(".composer-boundary-node.is-output")).toHaveCount(2);
});
