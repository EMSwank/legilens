import { test, expect } from "@playwright/test";
import { expectNoAxeViolations } from "./axe-helper";

// The e2e webServer runs the frontend only (no backend), so api.coverage()
// errors and the page shows its error state. The h1 and axe-cleanliness hold
// in every data state (ready / pending / error), so they are the stable
// invariants to assert — mirrors the tags.spec tolerance pattern.
test("coverage page renders and is axe-clean", async ({ page }) => {
  await page.goto("/coverage");
  await expect(page.getByRole("heading", { level: 1, name: /corpus coverage/i })).toBeVisible();
  await expectNoAxeViolations(page, "/coverage");
});

test("dashboard links to coverage", async ({ page }) => {
  await page.goto("/");
  const link = page.getByRole("link", { name: /corpus coverage/i });
  await expect(link).toBeVisible();
  await link.click();
  await expect(page).toHaveURL(/\/coverage/);
});
