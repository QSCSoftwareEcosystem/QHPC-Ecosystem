import { expect, test } from "@playwright/test";


test("presents the materials service in the Data workspace", async ({ page }) => {
  await page.goto("/?view=data");

  await expect(
    page.getByRole("heading", {
      name: "Governed datasets and schemas",
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "QSC Materials Repository" }),
  ).toBeVisible();
  await expect(
    page.getByText("kcuf3-hamiltonian-yaml", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Open", exact: true }).first(),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Download", exact: true }),
  ).toHaveCount(0);
  await expect(page.getByText("Optional S3 mirror")).toHaveCount(0);
});
