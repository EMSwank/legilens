import { render, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { axe } from "jest-axe";
import BillDetailPage from "@/app/bills/[id]/page";
import type { BillDetail, Match } from "@/lib/types";

jest.mock("next/navigation", () => ({
  useParams: () => ({ id: "00000000-0000-0000-0000-000000000001" }),
}));

jest.mock("recharts", () => ({
  RadialBarChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  RadialBar: () => null,
  PolarAngleAxis: () => null,
}));

jest.mock("@/lib/api", () => ({
  api: { bill: jest.fn(), matches: jest.fn() },
}));

import { api } from "@/lib/api";

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

const billFixture: BillDetail = {
  id: "00000000-0000-0000-0000-000000000001",
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
  tags: [{ tag_type: "source_cloned", confidence: 0.95 }],
};

const matchFixture: Match = {
  id: "match-1",
  matched_bill_title: "Texas Digital Data Rights Act",
  matched_state: "TX",
  similarity_score: 87.3,
  snippet_status: "verified",
  matched_snippets: [{
    kind: "snippet",
    co_context_before: "",
    co_match: "data collection by state agencies",
    co_context_after: "",
    source_context_before: "",
    source_match: "data processing by government entities",
    source_context_after: "",
  }],
};

const ghostMatchFixture: Match = {
  id: "match-2",
  matched_bill_title: "FL Ghost Bill",
  matched_state: "FL",
  similarity_score: 78.1,
  snippet_status: "source_verified_text_missing",
  matched_snippets: [{ kind: "ghost" as const, message: "Source text unavailable for extraction" as const }],
};

const pendingMatchFixture: Match = {
  id: "match-3",
  matched_bill_title: "AZ Pending Bill",
  matched_state: "AZ",
  similarity_score: 65.0,
  snippet_status: "pending",
  matched_snippets: null,
};

beforeEach(() => jest.clearAllMocks());

test("BillDetailPage renders bill header on success", async () => {
  (api.bill as jest.Mock).mockResolvedValue(billFixture);
  (api.matches as jest.Mock).mockResolvedValue([matchFixture]);
  const { getByText } = render(<BillDetailPage />, { wrapper });
  await waitFor(() => expect(getByText("HB24-1234")).toBeInTheDocument());
  expect(getByText("Concerning Digital Privacy Requirements")).toBeInTheDocument();
});

test("BillDetailPage has no accessibility violations on success", async () => {
  (api.bill as jest.Mock).mockResolvedValue(billFixture);
  (api.matches as jest.Mock).mockResolvedValue([matchFixture]);
  const { container } = render(<BillDetailPage />, { wrapper });
  await waitFor(() => expect(container.querySelector('[aria-label*="73.4"]')).toBeInTheDocument());
  expect(await axe(container)).toHaveNoViolations();
});

test("BillDetailPage renders IST gauge when score present", async () => {
  (api.bill as jest.Mock).mockResolvedValue(billFixture);
  (api.matches as jest.Mock).mockResolvedValue([]);
  const { getByRole } = render(<BillDetailPage />, { wrapper });
  await waitFor(() => expect(getByRole("img")).toBeInTheDocument());
  expect(getByRole("img").getAttribute("aria-label")).toContain("73.4");
});

test("BillDetailPage renders PendingBanner in sidebar when ist_score is null", async () => {
  (api.bill as jest.Mock).mockResolvedValue({ ...billFixture, ist_score: null });
  (api.matches as jest.Mock).mockResolvedValue([]);
  const { getByRole, getByText } = render(<BillDetailPage />, { wrapper });
  await waitFor(() => expect(getByText("HB24-1234")).toBeInTheDocument());
  expect(getByRole("status")).toBeInTheDocument();
});

test("BillDetailPage renders error state with back link when bill fetch fails", async () => {
  (api.bill as jest.Mock).mockRejectedValue(new Error("API error 404"));
  (api.matches as jest.Mock).mockResolvedValue([]);
  const { getByRole } = render(<BillDetailPage />, { wrapper });
  await waitFor(() => expect(getByRole("link", { name: /back/i })).toBeInTheDocument());
});

test("BillDetailPage renders match cards", async () => {
  (api.bill as jest.Mock).mockResolvedValue(billFixture);
  (api.matches as jest.Mock).mockResolvedValue([matchFixture]);
  const { getByText } = render(<BillDetailPage />, { wrapper });
  await waitFor(() => expect(getByText("Texas Digital Data Rights Act")).toBeInTheDocument());
});

test("BillDetailPage renders GhostAlert for ghost match", async () => {
  (api.bill as jest.Mock).mockResolvedValue(billFixture);
  (api.matches as jest.Mock).mockResolvedValue([ghostMatchFixture]);
  const { getByRole } = render(<BillDetailPage />, { wrapper });
  await waitFor(() => expect(getByRole("alert")).toBeInTheDocument());
});

test("BillDetailPage renders PendingBanner inside pending match card", async () => {
  (api.bill as jest.Mock).mockResolvedValue(billFixture);
  (api.matches as jest.Mock).mockResolvedValue([pendingMatchFixture]);
  const { getByRole, getByText } = render(<BillDetailPage />, { wrapper });
  await waitFor(() => expect(getByText("HB24-1234")).toBeInTheDocument());
  expect(getByRole("status")).toBeInTheDocument();
});

test("BillDetailPage renders empty state when no matches", async () => {
  (api.bill as jest.Mock).mockResolvedValue(billFixture);
  (api.matches as jest.Mock).mockResolvedValue([]);
  const { getByText } = render(<BillDetailPage />, { wrapper });
  await waitFor(() => expect(getByText(/no similarity matches/i)).toBeInTheDocument());
});
