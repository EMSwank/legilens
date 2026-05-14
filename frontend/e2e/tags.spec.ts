import { test, expect } from "@playwright/test";
import { expectNoAxeViolations } from "./axe-helper";

test("tags page lists tags and links to filtered dashboard", async ({ page }) => {
  await page.goto("/tags");
  await expect(page.getByRole("heading", { level: 1, name: /friction tags/i })).toBeVisible();
  await expectNoAxeViolations(page, "/tags");

  const cards = page.getByRole("main").getByRole("link");
  if ((await cards.count()) === 0) {
    test.skip(true, "no tags seeded; Phase 6 chip flow exercises navigation");
  }
  const firstCard = cards.first();
  const href = await firstCard.getAttribute("href");
  expect(href).toMatch(/^\/\?tag_type=/);
  await firstCard.click();
  await expect(page).toHaveURL(/tag_type=/);
});
