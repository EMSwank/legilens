import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { axe } from "jest-axe";
import Coverage from "@/app/coverage/page";

jest.mock("@/lib/api", () => ({ api: { coverage: jest.fn() } }));
import { api } from "@/lib/api";

function withQueryClient(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{ui}</QueryClientProvider>;
}

const READY = {
  status: "ready",
  as_of: "2026-06-03T04:00:00Z",
  matchable_pct: 78.4,
  states: [
    { state: "CO", fetchable: 100, with_sig: 95, status: "complete" },
    { state: "TX", fetchable: 50, with_sig: 10, status: "in_progress" },
    { state: "WY", fetchable: 10, with_sig: 0, status: "not_started" },
  ],
};

beforeEach(() => (api.coverage as jest.Mock).mockReset());

test("Coverage page has no axe violations when data loads", async () => {
  (api.coverage as jest.Mock).mockResolvedValue(READY);
  const { container } = render(withQueryClient(<Coverage />));
  await waitFor(() => screen.getByText(/78.4%/));
  expect(await axe(container)).toHaveNoViolations();
});

test("Coverage page renders an accessible table row per state", async () => {
  (api.coverage as jest.Mock).mockResolvedValue(READY);
  render(withQueryClient(<Coverage />));
  await waitFor(() => screen.getByRole("table"));
  expect(screen.getByRole("row", { name: /CO/i })).toBeInTheDocument();
  expect(screen.getByText(/complete/i)).toBeInTheDocument();
  expect(screen.getByText(/not started/i)).toBeInTheDocument();
});

test("Coverage page shows pending state when snapshot not computed", async () => {
  (api.coverage as jest.Mock).mockResolvedValue({
    status: "pending", as_of: null, matchable_pct: null, states: [],
  });
  render(withQueryClient(<Coverage />));
  await waitFor(() => expect(screen.getByText(/computing/i)).toBeInTheDocument());
});

test("Coverage page handles null matchable_pct without printing 'null'", async () => {
  (api.coverage as jest.Mock).mockResolvedValue({
    status: "ready", as_of: "2026-06-03T04:00:00Z", matchable_pct: null,
    states: [{ state: "WY", fetchable: 0, with_sig: 0, status: "not_started" }],
  });
  render(withQueryClient(<Coverage />));
  await waitFor(() => screen.getByRole("table"));
  expect(screen.queryByText(/null/i)).not.toBeInTheDocument();
});

test("Coverage page shows loading state initially", () => {
  (api.coverage as jest.Mock).mockReturnValue(new Promise(() => {}));
  render(withQueryClient(<Coverage />));
  expect(screen.getByRole("status")).toHaveTextContent(/loading/i);
});

test("Coverage page shows error state on fetch failure", async () => {
  (api.coverage as jest.Mock).mockRejectedValue(new Error("boom"));
  render(withQueryClient(<Coverage />));
  await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
});
