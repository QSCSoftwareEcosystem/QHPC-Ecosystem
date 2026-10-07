import { expect, test } from "@playwright/test";


test("explores QAppsWiki through a question-first knowledge workflow", async ({
  page,
}) => {
  await page.goto("/?view=knowledge");

  await expect(
    page.getByRole("heading", {
      name: "Start with a question. Follow the evidence.",
    }),
  ).toBeVisible();
  await expect(page.getByText("Authored pages")).toBeVisible();
  await expect(
    page.getByRole("button", { name: /Find a tool or topic/ }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(
    page.getByRole("button", { name: /Review evidence/ }),
  ).toBeVisible();
  await expect(
    page.getByRole("img", { name: /QAppsWiki atlas with/ }),
  ).toBeVisible();

  await page.getByRole("searchbox", { name: "Search QAppsWiki" }).fill(
    "OpenQEvo",
  );
  const result = page.locator(".knowledge-results > button").filter({
    hasText: "OpenQEvo",
  }).first();
  await expect(result).toBeVisible();
  await result.click();

  const record = page.getByRole("complementary", {
    name: "Knowledge record",
  });
  await expect(
    record.getByRole("heading", { name: "OpenQEvo", exact: true }),
  ).toBeVisible();
  await expect(
    record.getByRole("heading", { name: "Why trust this?" }),
  ).toBeVisible();
  await expect(record).toContainText("Page-level source");

  await record.getByRole("button", { name: "Explore neighbors" }).click();
  await expect(
    page.getByRole("heading", { name: "Neighborhood · OpenQEvo" }),
  ).toBeVisible();
  await expect(
    page.getByRole("img", { name: /Focused QAppsWiki graph/ }),
  ).toBeVisible();
});


test("explains how to recover when the Knowledge Explorer bundle is unavailable", async ({
  page,
}) => {
  await page.route("**/composer.js?*", (route) => route.abort());
  await page.goto("/?view=knowledge");

  await expect(
    page.getByRole("heading", { name: "Knowledge Explorer is unavailable" }),
  ).toBeVisible({ timeout: 3_000 });
  await expect(
    page.getByRole("button", { name: "Retry Knowledge Explorer" }),
  ).toBeVisible();
});


test("opens a tool directly in its QAppsWiki knowledge context", async ({
  page,
}) => {
  await page.goto("/?view=tools");
  await page.locator('tr[data-capability="openqevo-library"]').click();

  const inspector = page.getByRole("dialog", { name: "Details" });
  await inspector.getByRole("button", {
    name: "Explore in Knowledge",
  }).click();

  await expect(page).toHaveURL(/view=knowledge/);
  await expect(page).toHaveURL(/knowledge_node=packages%2Fopenqevo/);
  await expect(
    page.getByRole("heading", { name: "Neighborhood · OpenQEvo" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "OpenQEvo", exact: true }),
  ).toBeVisible();
});


test("shows QFlow incubation maturity and relationships without a run action", async ({
  page,
}) => {
  await page.goto("/?view=tools");
  await page.locator(
    'tr[data-capability="exachem-qflow-tasksets"]',
  ).click();

  const inspector = page.getByRole("dialog", { name: "Details" });
  await expect(inspector).toContainText("prototype");
  await expect(inspector).toContainText(
    "This registry record publishes resources or documentation",
  );
  await expect(
    inspector.getByRole("heading", { name: "Quick start" }),
  ).toBeVisible();
  await expect(
    inspector.getByRole("button", { name: "Explore in Knowledge" }),
  ).toBeVisible();
  await expect(
    inspector.getByRole("button", { name: "Open Compose" }),
  ).toHaveCount(0);

  await inspector.getByRole("button", {
    name: "Explore in Knowledge",
  }).click();

  const record = page.getByRole("complementary", {
    name: "Knowledge record",
  });
  await expect(
    record.getByRole("heading", { name: "ExaChem QFlow", exact: true }),
  ).toBeVisible();
  await expect(record).toContainText("Maturity");
  await expect(record).toContainText("Prototype");
  await expect(record).toContainText("delegates-taskset-to");
  await expect(record).toContainText("QIRIS Runtime");
});
