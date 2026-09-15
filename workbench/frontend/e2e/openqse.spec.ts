import { expect, test } from "@playwright/test";


test("presents OpenQSE as a read-only community resource panel", async ({ page }) => {
  await page.goto("/?view=openqse");

  await expect(
    page.getByRole("heading", { name: "OpenQSE resource panel" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", {
      name: "A community and repository catalog, not an EQO runtime",
    }),
  ).toBeVisible();
  await expect(page.getByText("Read-only discovery", { exact: true })).toBeVisible();
  await expect(
    page.getByText("No service or execution admission", { exact: true }),
  ).toBeVisible();

  const documentation = page.locator(
    'section[aria-label="OpenQSE documentation and source records"]',
  );
  await expect(
    documentation.getByRole("heading", { name: "OpenQSE specification" }),
  ).toBeVisible();
  await expect(
    documentation.getByRole("heading", { name: "QFw–SLURM Cluster" }),
  ).toBeVisible();
  await expect(
    documentation.getByRole("link", { name: /Source and README/ }),
  ).toHaveAttribute(
    "href",
    /openQSE\/QFw-SLURM-Cluster\/tree\/eeb42e601383f3d33020f823d4a387ef30b9dd7d/,
  );
  await expect(documentation.getByRole("button")).toHaveCount(0);
});
