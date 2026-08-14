import { expect, test } from "@playwright/test";


test("checks and prepares an allowlisted repository update", async ({ page }) => {
  const currentRevision = "a".repeat(40);
  const candidateRevision = "b".repeat(40);
  let status: "not-checked" | "update-available" | "prepared" = "not-checked";
  let checkBody: Record<string, unknown> | undefined;
  let stageBody: Record<string, unknown> | undefined;

  const response = () => ({
    enabled: true,
    generated_at: "2026-07-29T12:00:00Z",
    items: [
      {
        component_id: "stabsim",
        name: "STABSim",
        role: "operation-provider",
        catalog_repository: "STABSim",
        repository_url: "https://github.com/QSCSoftwareThrust/STABSim",
        current_repository_url: "https://github.com/QSCSoftwareThrust/STABSim",
        tracked_ref: "HEAD",
        current_revision: currentRevision,
        latest_revision: status === "not-checked" ? null : candidateRevision,
        checked_at:
          status === "not-checked" ? null : "2026-07-29T12:00:00Z",
        status,
        error: null,
        capability_ids: ["stabsim-simulator"],
        activation: "rebuild-required",
        next_action: "Rebuild and validate runtime before activation",
        staged_revision: status === "prepared" ? candidateRevision : null,
        staged_at:
          status === "prepared" ? "2026-07-29T12:01:00Z" : null,
        checkout:
          status === "prepared"
            ? `.qhpc/updates/checkouts/stabsim/${candidateRevision}`
            : null,
      },
    ],
  });

  await page.route("**/api/v1/repository-updates", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(response()),
    });
  });
  await page.route("**/api/v1/repository-updates/check", async (route) => {
    checkBody = route.request().postDataJSON() as Record<string, unknown>;
    status = "update-available";
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(response()),
    });
  });
  await page.route("**/api/v1/repository-updates/stage", async (route) => {
    stageBody = route.request().postDataJSON() as Record<string, unknown>;
    status = "prepared";
    await route.fulfill({
      status: 201,
      contentType: "application/json",
      body: JSON.stringify(response().items[0]),
    });
  });

  await page.goto("/?view=updates");

  await expect(page.locator("#view-title")).toHaveText("Repository updates");
  await expect(
    page.getByRole("heading", { name: "Repository update control" }),
  ).toBeVisible();
  await expect(page.getByText("not checked", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Check updates" }).click();
  await expect(page.getByText("available", { exact: true })).toBeVisible();
  await expect(
    page.getByText(candidateRevision.slice(0, 12), { exact: true }),
  ).toBeVisible();
  expect(checkBody).toEqual({});

  await page.getByRole("button", { name: "Prepare", exact: true }).click();
  await expect(page.getByText("prepared", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Discard", exact: true }),
  ).toBeVisible();
  expect(stageBody).toEqual({
    component_id: "stabsim",
    candidate_revision: candidateRevision,
  });
  expect(stageBody).not.toHaveProperty("repository_url");
  expect(stageBody).not.toHaveProperty("tracked_ref");
  expect(stageBody).not.toHaveProperty("credential");
});


test("shows QSC ownership without rewriting older release provenance", async ({
  page,
}) => {
  await page.route("**/api/v1/capabilities", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify([
        {
          id: "lightstim-simulation",
          name: "LightStim Logical Error Estimation",
          version: "0.1.0",
          project: "hybrid-workflows",
          maturity: "alpha",
          visibility: "public",
          repository: {
            url: "https://github.com/QuTone/LightStim",
            canonical_url: "https://github.com/QSCSoftwareThrust/LightStim",
            revision: "b08d4c2f9cd69531a51b658e6f88089be69f16c0",
          },
          integration: {
            authority: "ecosystem",
            maintainers: ["qhpc-ecosystem"],
            project_reviewed: false,
            runtime_status: "verified",
          },
          catalog_repository: "LightStim",
          validation: { status: "integration-tested" },
          operations: [],
          resources: [],
          documentation: {},
          description: "Logical error estimation.",
        },
      ]),
    });
  });

  await page.goto("/?view=tools");

  const row = page.locator('tr[data-capability="lightstim-simulation"]');
  await expect(row).toContainText("QSCSoftwareThrust/LightStim");
  await expect(row).not.toContainText("QuTone/LightStim");
  await row.click();
  await expect(page.locator("#inspector")).toContainText(
    "https://github.com/QSCSoftwareThrust/LightStim",
  );
  await expect(page.locator("#inspector")).toContainText(
    "Release sourcehttps://github.com/QuTone/LightStim",
  );
});
