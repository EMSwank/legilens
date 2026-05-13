import { test, expect } from "@playwright/test";
import { expectNoAxeViolations } from "./axe-helper";

test("about page renders with all sections and no axe violations", async ({ page }) => {
  await page.goto("/about");
  await expect(page.getByRole("heading", { level: 1, name: /about legilens/i })).toBeVisible();
  await expect(page.getByRole("heading", { name: /what legilens measures/i })).toBeVisible();
  await expect(page.getByRole("heading", { name: /how minhash works/i })).toBeVisible();
  await expect(page.getByRole("img", { name: /shingl/i })).toBeVisible();
  await expectNoAxeViolations(page, "/about");
});

test("accessibility page renders WCAG statement and contact link", async ({ page }) => {
  await page.goto("/accessibility");
  await expect(page.getByText(/WCAG 2\.1.*level AA/i)).toBeVisible();
  const issuesLink = page.getByRole("link", { name: /github\.com\/EMSwank\/legilens\/issues/i });
  await expect(issuesLink).toBeVisible();
  await expectNoAxeViolations(page, "/accessibility");
});
