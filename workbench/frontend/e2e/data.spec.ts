import { expect, test } from "@playwright/test";


test("presents the materials service in the Data workspace", async ({ page }) => {
  await page.goto("/?view=data");

  await expect(
    page.getByRole("heading", {
      name: "Governed datasets and SDL-backed services",
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "QSC Materials Repository" }),
  ).toBeVisible();
  await expect(
    page.getByText("materials-schema-v0.1", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Live Object Storage (databucket)" }),
  ).toBeVisible();
  await expect(
    page.getByText("databucket/Garage is not configured for this Workbench"),
  ).toBeVisible();
});
