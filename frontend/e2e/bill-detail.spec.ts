import { test, expect, type Page } from "@playwright/test";
import type { BillDetail, Match } from "@/lib/types";

const billFixture: BillDetail = {
  id: "bill-1",
  bill_number: "HB24-1234",
  title: "Concerning Digital Privacy Requirements",
  description: "A privacy bill.",
  state: "CO",
  session: "2024A",
  status: "Introduced",
  sponsors: null,
  ist_score: {
    source_authenticity_score: 73.4,
    copycat_alert: true,
    analyzed_at: "2024-01-15T00:00:00Z",
  },
  tags: [
    { tag_type: "source_cloned", confidence: 0.95 },
    { tag_type: "technical_conflict", confidence: 0.7 },
  ],
};

const matchesFixture: Match[] = [
  {
    id: "match-1",
    matched_bill_title: "Texas Digital Data Rights Act",
    matched_state: "TX",
    similarity_score: 87.3,
    snippet_status: "verified",
    matched_snippets: [
      {
        kind: "snippet" as const,
        co_context_before: "",
        co_match: "data collection by state agencies",
        co_context_after: "",
        source_context_before: "",
        source_match: "data processing by government entities",
        source_context_after: "",
      },
    ],
  },
];

const ghostMatchesFixture: Match[] = [
  {
    id: "match-2",
    matched_bill_title: "FL Ghost Bill",
    matched_state: "FL",
    similarity_score: 78.1,
    snippet_status: "source_verified_text_missing",
    matched_snippets: [{ kind: "ghost" as const, message: "Source text unavailable for extraction" as const }],
  },
];

async function interceptBill(
  page: Page,
  billOverride: BillDetail = billFixture,
  matchesOverride: Match[] = matchesFixture
) {
  await page.route("**/bills/bill-1/matches", (route) =>
    route.fulfill({ json: matchesOverride })
  );
  await page.route("**/bills/bill-1", (route) => {
    if (route.request().resourceType() === "document") return route.continue();
    route.fulfill({ json: billOverride });
  });
}

test("bill detail renders header with number, title, status", async ({ page }) => {
  await interceptBill(page);
  await page.goto("/bills/bill-1");
  await expect(page.getByText("HB24-1234")).toBeVisible();
  await expect(page.getByText("Concerning Digital Privacy Requirements")).toBeVisible();
  await expect(page.getByText("Introduced")).toBeVisible();
});

test("IST gauge has role=img with aria-label containing score", async ({ page }) => {
  await interceptBill(page);
  await page.goto("/bills/bill-1");
  const gauge = page.getByRole("img");
  await expect(gauge).toBeVisible();
  await expect(gauge).toHaveAttribute("aria-label", /73\.4/);
});

test("copycat_alert: true shows COPYCAT ALERT in sidebar", async ({ page }) => {
  await interceptBill(page);
  await page.goto("/bills/bill-1");
  await expect(page.getByText("COPYCAT ALERT")).toBeVisible();
});

test("friction tags render in sidebar", async ({ page }) => {
  await interceptBill(page);
  await page.goto("/bills/bill-1");
  await expect(page.getByText("Source-Cloned")).toBeVisible();
  await expect(page.getByText("Technical Conflict")).toBeVisible();
});

test("similarity match cards render with title and score", async ({ page }) => {
  await interceptBill(page);
  await page.goto("/bills/bill-1");
  await expect(page.getByText("Texas Digital Data Rights Act")).toBeVisible();
  await expect(page.getByText(/87\.3/)).toBeVisible();
});

test("ghost match renders alert", async ({ page }) => {
  await interceptBill(page, billFixture, ghostMatchesFixture);
  await page.goto("/bills/bill-1");
  await expect(page.getByRole("alert").filter({ hasText: /match verified/i })).toBeVisible();
});

test("ist_score null renders status banner in sidebar", async ({ page }) => {
  await interceptBill(page, { ...billFixture, ist_score: null }, []);
  await page.goto("/bills/bill-1");
  await expect(page.getByRole("status")).toBeVisible();
});

test("no matches renders empty state message", async ({ page }) => {
  await interceptBill(page, billFixture, []);
  await page.goto("/bills/bill-1");
  await expect(page.getByText(/no similarity matches/i)).toBeVisible();
});

test("/bills/bad-id 404 renders error state with back link", async ({ page }) => {
  await page.route("**/bills/bad-id/matches", (route) => route.fulfill({ json: [] }));
  await page.route("**/bills/bad-id", (route) => {
    if (route.request().resourceType() === "document") return route.continue();
    route.fulfill({ status: 404, json: { detail: "Bill not found" } });
  });
  await page.goto("/bills/bad-id");
  await expect(page.getByRole("link", { name: /back/i })).toBeVisible();
});
