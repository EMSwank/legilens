import { test, expect } from "@playwright/test";
import { expectNoAxeViolations } from "./axe-helper";

test("tags page lists tags and links to filtered dashboard", async ({ page }) => {
  await page.goto("/tags");
  await expect(page.getByRole("heading", { level: 1, name: /friction tags/i })).toBeVisible();
  // First card click navigates to /?tag_type=...
  const firstCard = page.getByRole("link").first();
  const href = await firstCard.getAttribute("href");
  expect(href).toMatch(/^\/\?tag_type=/);
  await firstCard.click();
  await expect(page).toHaveURL(/tag_type=/);
  await expectNoAxeViolations(page, "/tags");
});
