import { test, expect } from "@playwright/test";
import { expectNoAxeViolations } from "./axe-helper";

test("user can navigate tags → dashboard filtered → dismiss chip", async ({ page }) => {
  await page.goto("/tags");
  const firstCard = page.getByRole("main").getByRole("link").first();
  if ((await page.getByRole("main").getByRole("link").count()) === 0) {
    test.skip(true, "no tags seeded; skip filter journey");
  }
  const href = await firstCard.getAttribute("href");
  await firstCard.click();
  await expect(page).toHaveURL(/tag_type=/);

  const chip = page.getByRole("button", { name: /remove tag filter/i });
  await expect(chip).toBeVisible();
  await chip.click();
  await expect(page).not.toHaveURL(/tag_type=/);

  await expectNoAxeViolations(page, "dashboard with filters");
});

test("deep link with tag_type + session renders both chips", async ({ page }) => {
  await page.goto("/?tag_type=source_cloned&session=2025A");
  await expect(page.getByRole("button", { name: /remove tag filter/i })).toBeVisible();
  await expect(page.getByRole("button", { name: /remove session filter/i })).toBeVisible();

  await page.getByRole("button", { name: /remove tag filter/i }).click();
  await expect(page).toHaveURL(/session=2025A/);
  await expect(page).not.toHaveURL(/tag_type=/);
  await expect(page.getByRole("button", { name: /remove session filter/i })).toBeVisible();
});

test("session dropdown updates URL and triggers refetch", async ({ page }) => {
  await page.goto("/");
  const select = page.getByRole("combobox", { name: /session/i });
  const options = await select.locator("option").allTextContents();
  const realOption = options.find((o) => o !== "All sessions");
  if (!realOption) {
    test.skip(true, "No sessions in DB; skip dropdown round-trip");
  } else {
    await select.selectOption(realOption);
    await expect(page).toHaveURL(new RegExp(`session=${realOption}`));
  }
});

test("filter chips meet 24px touch target on mobile viewport", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 667 });
  await page.goto("/?tag_type=source_cloned");
  const chipBtn = page.getByRole("button", { name: /remove tag filter/i });
  const box = await chipBtn.boundingBox();
  expect(box).not.toBeNull();
  expect(box!.width).toBeGreaterThanOrEqual(24);
  expect(box!.height).toBeGreaterThanOrEqual(24);
});
