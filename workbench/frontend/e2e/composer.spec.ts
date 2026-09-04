import { expect, test } from "@playwright/test";


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
    "OpenQEvo method discovery, attributed scientific context",
  );
  await openqevo.click();

  const inspector = page.getByRole("dialog", { name: "Details" });
  await expect(
    inspector.getByRole("heading", {
      name: "OpenQEvo Library and Method Context",
    }),
  ).toBeVisible();
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
    "developer-reported one-logical-qubit execution",
  );

  const inspector = page.getByRole("dialog", { name: "Details" });
  await expect(
    inspector.getByRole("heading", {
      name: "FTQC Fault-Tolerant Compiler",
    }),
  ).toBeVisible();
  await expect(inspector).toContainText(
    "one-logical-qubit execution on an ORNL IQM system",
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
  await expect(page.locator(".showcase-trace li")).toHaveCount(5);
  await expect(page.getByText("1 logical → 7 data qubits")).toBeVisible();
  await expect(page.getByText("58 instructions")).toBeVisible();
  await expect(page.getByText("114 instructions")).toBeVisible();
  await expect(page.getByText("Not yet claimed")).toBeVisible();

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
      .getByText("6 runnable · 1 blueprint"),
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
    .getByRole("button", { name: /Clifford and T resource count/ })
    .click();
  await page.getByRole("button", { name: "Bell example" }).click();
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
