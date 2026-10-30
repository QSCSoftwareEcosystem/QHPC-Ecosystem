import { expect, test } from "@playwright/test";


test("inspects a public repository into a pinned, non-executable component draft", async ({ page }) => {
  const revision = "a".repeat(40);
  let requestBody: Record<string, unknown> | undefined;
  let editBody: Record<string, unknown> | undefined;
  let buildBody: Record<string, unknown> | undefined;
  let refreshBody: Record<string, unknown> | undefined;
  let activateBody: Record<string, unknown> | undefined;
  let hasDraft = false;
  const response = () => ({
    enabled: true,
    items: hasDraft ? [draft] : [],
  });
  const draft = {
    id: "onboarding-qasm-transpiler",
    status: "inspected",
    source: {
      repository_url: "https://github.com/example/qasm-transpiler",
      requested_ref: "refs/tags/v0.1.0",
      resolved_revision: revision,
      subdirectory: "adapter",
    },
    inspection: {
      recognized_file_count: 3,
      recognized_files: ["pyproject.toml", "adapter/transpiler.py", "Dockerfile"],
    },
    draft: {
      template: "compiler-transpiler",
      capability_interface: {
        id: "qasm-transpiler",
        operation_id: "run",
        input_artifact: "qhpc.quantum-circuit@1",
        output_artifact: "qhpc.measurement-counts@1",
      },
      build_recipe: { state: "not-run" },
    },
    activation: {
      reason: "Isolated build, smoke test, immutable image digest, and admission are required before activation.",
    },
  };

  await page.route("**/api/v1/component-onboarding", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(response()),
    });
  });
  await page.route("**/api/v1/component-onboarding/inspect", async (route) => {
    requestBody = route.request().postDataJSON() as Record<string, unknown>;
    hasDraft = true;
    await route.fulfill({
      status: 201,
      contentType: "application/json",
      body: JSON.stringify(draft),
    });
  });
  await page.route("**/api/v1/component-onboarding/drafts/**", async (route) => {
    if (route.request().url().endsWith("/build")) {
      buildBody = route.request().postDataJSON() as Record<string, unknown>;
      draft.status = "built";
      (draft as Record<string, unknown>).build = {
        state: "succeeded",
        image_digest: `sha256:${"b".repeat(64)}`,
        logs: "isolated build completed",
        detected_entrypoints: ["Dockerfile"],
        produced_artifacts: [{ kind: "oci-image", digest: `sha256:${"b".repeat(64)}` }],
        smoke_test: { state: "passed" },
      };
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify(draft),
      });
      return;
    }
    if (route.request().url().endsWith("/refresh")) {
      refreshBody = route.request().postDataJSON() as Record<string, unknown>;
      (draft as Record<string, unknown>).refresh = { state: "up-to-date" };
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify(draft),
      });
      return;
    }
    if (route.request().url().endsWith("/activate")) {
      activateBody = route.request().postDataJSON() as Record<string, unknown>;
      draft.status = "active";
      draft.activation = {
        state: "active-local",
        reason: "Pinned source and immutable image were explicitly admitted for local component use.",
      };
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify(draft),
      });
      return;
    }
    editBody = route.request().postDataJSON() as Record<string, unknown>;
    draft.draft.template = String(editBody.template);
    draft.draft.capability_interface.id = String(editBody.capability_id);
    draft.draft.capability_interface.operation_id = String(editBody.operation_id);
    draft.draft.capability_interface.input_artifact = String(editBody.input_artifact);
    draft.draft.capability_interface.output_artifact = String(editBody.output_artifact);
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(draft),
    });
  });

  await page.goto("/?view=components");

  await expect(page.locator("#view-title")).toHaveText("Add a component");
  await expect(
    page.getByRole("heading", { name: "Inspect a public source" }),
  ).toBeVisible();
  await expect(page.getByText("It does not execute source code", { exact: false })).toBeVisible();

  await page.getByLabel("Public Git repository URL").fill(
    "https://github.com/example/qasm-transpiler",
  );
  await page.getByLabel("Branch, tag, or commit").fill("refs/tags/v0.1.0");
  await page.getByLabel("Monorepo subdirectory").fill("adapter");
  await page.getByLabel("Integration template").selectOption("compiler-transpiler");
  await page.getByRole("button", { name: "Inspect repository" }).click();

  expect(requestBody).toEqual({
    repository_url: "https://github.com/example/qasm-transpiler",
    ref: "refs/tags/v0.1.0",
    subdirectory: "adapter",
    template: "compiler-transpiler",
  });
  await expect(page.getByRole("heading", { name: "qasm-transpiler" })).toBeVisible();
  await expect(page.getByText(revision.slice(0, 16), { exact: true })).toBeVisible();
  await expect(page.getByText("not-run", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Check source update" }).click();
  expect(refreshBody).toEqual({});
  await expect(page.getByText("Tracked source is current", { exact: false })).toBeVisible();
  await page.getByText("Edit integration draft").click();
  const editor = page.locator(".component-draft-editor");
  await editor.getByLabel("Template").selectOption("simulator");
  await editor.getByLabel("Capability ID").fill("qasm-simulator");
  await editor.getByLabel("Operation ID").fill("simulate");
  await editor.getByRole("button", { name: "Save draft" }).click();
  expect(editBody).toEqual({
    template: "simulator",
    capability_id: "qasm-simulator",
    operation_id: "simulate",
    input_artifact: "qhpc.quantum-circuit@1",
    output_artifact: "qhpc.measurement-counts@1",
  });
  await expect(page.getByText("Simulator · inspected, not built")).toBeVisible();
  await page.getByRole("button", { name: "Build in isolation" }).click();
  expect(buildBody).toEqual({});
  await expect(page.getByText("isolated build passed", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "Activate locally" }).click();
  expect(activateBody).toEqual({});
  await expect(page.getByText("Active locally", { exact: true })).toBeVisible();
  await page.getByText("Build evidence").click();
  await expect(page.getByText("isolated build completed", { exact: true })).toBeVisible();
  await page.getByText("Recognized files · 3").click();
  await expect(page.getByText("adapter/transpiler.py", { exact: true })).toBeVisible();
  await expect(page.getByText("Simulator · isolated build passed")).toBeVisible();
});


test("uses the reviewed QASMTrans source example without treating a draft as a runtime", async ({ page }) => {
  const revision = "1843c98fa4bac9cf6b88412145b69457e9176124";
  let requestBody: Record<string, unknown> | undefined;
  let hasDraft = false;
  const draft = {
    id: "onboarding-qasmtrans-reviewed",
    status: "inspected",
    source: {
      repository_url: "https://github.com/pnnl/qasmtrans",
      requested_ref: revision,
      resolved_revision: revision,
    },
    inspection: { recognized_file_count: 0, recognized_files: [] },
    draft: {
      template: "compiler-transpiler",
      capability_interface: { id: "qasmtrans", operation_id: "run" },
      build_recipe: { state: "not-run" },
    },
    activation: { reason: "A separate build and admission are required for this draft." },
  };

  await page.route("**/api/v1/component-onboarding", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ enabled: true, items: hasDraft ? [draft] : [] }),
    });
  });
  await page.route("**/api/v1/component-onboarding/inspect", async (route) => {
    requestBody = route.request().postDataJSON() as Record<string, unknown>;
    hasDraft = true;
    await route.fulfill({
      status: 201,
      contentType: "application/json",
      body: JSON.stringify(draft),
    });
  });

  await page.goto("/?view=components");
  await page.getByRole("button", { name: "Use QASMTrans example" }).click();
  await expect(page.getByLabel("Public Git repository URL")).toHaveValue(
    "https://github.com/pnnl/qasmtrans",
  );
  await expect(page.getByLabel("Branch, tag, or commit")).toHaveValue(revision);
  await expect(page.getByLabel("Integration template")).toHaveValue("compiler-transpiler");
  await page.getByRole("button", { name: "Inspect repository" }).click();

  expect(requestBody).toEqual({
    repository_url: "https://github.com/pnnl/qasmtrans",
    ref: revision,
    subdirectory: "",
    template: "compiler-transpiler",
  });
  await expect(page.getByText("Published operation available", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Open Transform path" })).toBeVisible();
  await page.getByRole("button", { name: "Open Transform path" }).click();
  await expect(page).toHaveURL(/\?view=compose&basic=transform/);
});
