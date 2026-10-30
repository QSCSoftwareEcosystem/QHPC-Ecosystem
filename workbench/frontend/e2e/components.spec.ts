import { expect, test } from "@playwright/test";


test("inspects a public repository into a pinned, non-executable component draft", async ({ page }) => {
  const revision = "a".repeat(40);
  let requestBody: Record<string, unknown> | undefined;
  let editBody: Record<string, unknown> | undefined;
  const response = () => ({
    enabled: true,
    items: [],
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
    await route.fulfill({
      status: 201,
      contentType: "application/json",
      body: JSON.stringify(draft),
    });
  });
  await page.route("**/api/v1/component-onboarding/drafts/**", async (route) => {
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
  await page.getByText("Recognized files · 3").click();
  await expect(page.getByText("adapter/transpiler.py", { exact: true })).toBeVisible();
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
});
