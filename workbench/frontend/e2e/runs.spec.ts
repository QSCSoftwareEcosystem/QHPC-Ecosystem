import { expect, test } from "@playwright/test";


test("presents a run as an inspectable, exportable receipt", async ({ page }) => {
  const digest = "sha256:receipt-browser-test-digest";
  await page.route("**/api/v1/runs", async (route) => {
    if (route.request().method() !== "GET") {
      await route.continue();
      return;
    }
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify([
        {
          id: "run-receipt-browser-test",
          workflow_id: "nwqsim-bell-simulation",
          workflow_version: "0.1.0",
          workflow_digest: digest,
          execution_target: "local-development",
          state: "succeeded",
          created_at: "2026-10-30T12:00:00Z",
          created_by: "browser-test",
          started_at: "2026-10-30T12:00:01Z",
          finished_at: "2026-10-30T12:00:03Z",
          inputs: { circuit: "artifact-bell-input" },
          outputs: { counts: "artifact-bell-counts" },
          tasks: [
            {
              node_id: "simulate",
              state: "succeeded",
              operation: {
                capability: "nwqsim",
                operation: "simulate-circuit",
              },
              attempt: 1,
              started_at: "2026-10-30T12:00:01Z",
              finished_at: "2026-10-30T12:00:03Z",
              error: null,
              outputs: {},
              attempts: [],
            },
          ],
        },
      ]),
    });
  });

  await page.goto("/?view=runs");
  await page.getByText("nwqsim-bell-simulation", { exact: true }).first().click();

  const inspector = page.locator("#inspector");
  await expect(inspector).toContainText("RUN RECEIPT");
  await expect(inspector.getByRole("heading", { name: "nwqsim-bell-simulation" })).toBeVisible();
  await expect(inspector).toContainText("Workflow digest");
  await expect(inspector).toContainText(digest);
  await expect(inspector).toContainText("Execution timeline");
  await expect(inspector).toContainText("Input artifacts");
  await expect(inspector).toContainText("artifact-bell-input");
  await expect(inspector).toContainText("Output artifacts");
  await expect(inspector).toContainText("artifact-bell-counts");
  await expect(
    inspector.getByRole("button", { name: "Export receipt" }),
  ).toBeVisible();
});
