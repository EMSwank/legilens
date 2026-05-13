import { test, expect, type Page } from "@playwright/test";
import { expectNoAxeViolations } from "./axe-helper";

const statsFixture = { total_co_bills: 342, copycat_alerts: 17, bills_analyzed: 289 };

const billsFixture = [
  {
    id: "bill-1",
    bill_number: "HB24-1234",
    title: "Concerning Digital Privacy",
    state: "CO",
    session: "2024A",
    status: "Introduced",
    copycat_alert: true,
  },
  {
    id: "bill-2",
    bill_number: "SB24-005",
    title: "Concerning Water Rights",
    state: "CO",
    session: "2024A",
    status: "Passed",
    copycat_alert: false,
  },
];

const searchResultsFixture = [
  {
    id: "bill-1",
    bill_number: "HB24-1234",
    title: "Concerning Digital Privacy",
    state: "CO",
    session: "2024A",
    status: "Introduced",
    copycat_alert: false,
  },
];

async function interceptDefault(page: Page) {
  await page.route("**/stats", (route) => route.fulfill({ json: statsFixture }));
  await page.route("**/bills", (route) => route.fulfill({ json: billsFixture }));
}

test("stats grid renders 3 cards with numeric values", async ({ page }) => {
  await interceptDefault(page);
  await page.goto("/");
  await expect(page.getByText("289")).toBeVisible();
  await expect(page.getByText("17")).toBeVisible();
  await expect(page.getByText("342")).toBeVisible();
});

test("bills list renders rows with links to /bills/[id]", async ({ page }) => {
  await interceptDefault(page);
  await page.goto("/");
  await expect(page.getByText("HB24-1234")).toBeVisible();
  await expect(
    page.getByRole("link", { name: /Concerning Digital Privacy/i })
  ).toHaveAttribute("href", "/bills/bill-1");
});

test("copycat badge visible on flagged bills", async ({ page }) => {
  await interceptDefault(page);
  await page.goto("/");
  await expect(page.getByText("Source-Cloned")).toBeVisible();
});

test("search: 2+ chars triggers search results", async ({ page }) => {
  await interceptDefault(page);
  await page.route("**/bills/search*", (route) =>
    route.fulfill({ json: searchResultsFixture })
  );
  await page.goto("/");
  await page.getByRole("searchbox").fill("privacy");
  await expect(page.getByText("Concerning Digital Privacy")).toBeVisible();
  await expect(page.getByText("Concerning Water Rights")).not.toBeVisible();
});

test("search: 1 char does not trigger search", async ({ page }) => {
  await interceptDefault(page);
  let searchFired = false;
  await page.route("**/bills/search*", (route) => {
    searchFired = true;
    route.fulfill({ json: [] });
  });
  await page.goto("/");
  await page.getByRole("searchbox").fill("p");
  await page.waitForTimeout(400);
  expect(searchFired).toBe(false);
  await expect(page.getByText("Concerning Water Rights")).toBeVisible();
});

test("search: clearing input resets to default bills list", async ({ page }) => {
  await interceptDefault(page);
  await page.route("**/bills/search*", (route) =>
    route.fulfill({ json: searchResultsFixture })
  );
  await page.goto("/");
  const searchbox = page.getByRole("searchbox");
  await searchbox.fill("privacy");
  await expect(page.getByText("Concerning Water Rights")).not.toBeVisible();
  await searchbox.clear();
  await expect(page.getByText("Concerning Water Rights")).toBeVisible();
});

test("/stats API error shows error alert", async ({ page }) => {
  await page.route("**/stats", (route) => route.fulfill({ status: 500 }));
  await page.route("**/bills", (route) => route.fulfill({ json: billsFixture }));
  await page.goto("/");
  await expect(page.getByRole("alert")).toBeVisible();
});

test("/bills API error shows error alert", async ({ page }) => {
  await page.route("**/stats", (route) => route.fulfill({ json: statsFixture }));
  await page.route("**/bills", (route) => route.fulfill({ status: 500 }));
  await page.goto("/");
  await expect(page.getByRole("alert")).toBeVisible();
});

test("dashboard has no axe violations", async ({ page }) => {
  await interceptDefault(page);
  await page.goto("/");
  await expectNoAxeViolations(page, "/");
});
