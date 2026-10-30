import { expect, test } from "@playwright/test";


test("teaches bounded ideal circuit samples before the Basic Composer handoff", async ({ page }) => {
  await page.goto("/?view=training");

  await expect(page.locator("#view-title")).toHaveText("Quantum computing training");
  await expect(
    page.getByText("All lesson samples run as ideal, local browser models.", { exact: false }),
  ).toBeVisible();

  await page.getByRole("button", { name: /Superposition and interference/ }).click();
  await expect(
    page.getByRole("heading", { name: "Superposition and interference" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Sample ideal measurements" }).click();
  await expect(page.getByText("Ideal local sample · 100 shots")).toBeVisible();
  await expect(
    page.locator(".training-results tbody th").filter({ hasText: /^0$/ }),
  ).toHaveCount(1);
  await expect(
    page.locator(".training-results tbody th").filter({ hasText: /^1$/ }),
  ).toHaveCount(1);
  await expect(page.getByText("Lesson glossary")).toBeVisible();

  await page.getByRole("button", { name: "Try it in Basic Composer" }).click();
  await expect(page.getByRole("tab", { name: "Basic", exact: true })).toHaveAttribute(
    "aria-selected",
    "true",
  );
});


test("prefills a contextual question instead of automatically calling ChatQEC", async ({ page }) => {
  await page.goto("/?view=training");
  await page.getByRole("button", { name: /Entanglement/ }).click();
  await page.getByRole("button", { name: "Ask ChatQEC" }).click();

  await expect(page.locator("#view-title")).toHaveText("ChatQEC");
  await expect(page.locator("#assistant-question")).toHaveValue(
    "Why are ideal Bell-pair outcomes correlated as 00 or 11?",
  );
});
