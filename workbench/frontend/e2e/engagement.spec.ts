import { expect, test } from "@playwright/test";


test("presents Engagement Thrust material as read-only external resources", async ({ page }) => {
  await page.goto("/?view=engagement");

  await expect(
    page.getByRole("heading", { name: "Engagement resources" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", {
      name: "Learning paths that stay connected to the ecosystem",
    }),
  ).toBeVisible();
  await expect(
    page.getByText("Read-only resource directory", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("No service or execution admission", { exact: true }),
  ).toBeVisible();

  const resources = page.locator('section[aria-label="Engagement learning resources"]');
  await expect(
    resources.getByRole("heading", { name: "HPC / AI / QC Crash Course" }),
  ).toBeVisible();
  await expect(
    resources.getByRole("link", { name: /Open HPC \/ AI \/ QC Crash Course/ }),
  ).toHaveAttribute("href", "https://github.com/olcf/hands-on-with-odo");
  await expect(
    resources.getByRole("link", { name: /Open Quantum Computing User Training/ }),
  ).toHaveAttribute("href", "https://github.com/olcf/quantum-training-series");
  await expect(
    resources.getByRole("link", { name: /Open Quantum Computing Hackathon/ }),
  ).toHaveAttribute(
    "href",
    "https://www.olcf.ornl.gov/calendar/fall-2026-qcup-hackathon/",
  );
  await expect(resources.getByRole("button")).toHaveCount(0);
});
