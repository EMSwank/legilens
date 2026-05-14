import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { axe } from "jest-axe";
import Tags from "@/app/tags/page";

jest.mock("@/lib/api", () => ({
  api: {
    tags: jest.fn(),
  },
}));
import { api } from "@/lib/api";

function withQueryClient(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{ui}</QueryClientProvider>;
}

beforeEach(() => {
  (api.tags as jest.Mock).mockReset();
});

test("Tags page has no axe violations when data loads", async () => {
  (api.tags as jest.Mock).mockResolvedValue([
    { tag_type: "source_cloned", count: 12 },
    { tag_type: "technical_conflict", count: 4 },
  ]);
  const { container } = render(withQueryClient(<Tags />));
  await waitFor(() => screen.getByText(/12 bills/i));
  expect(await axe(container)).toHaveNoViolations();
});

test("Tags page renders one card per tag with count", async () => {
  (api.tags as jest.Mock).mockResolvedValue([
    { tag_type: "source_cloned", count: 12 },
    { tag_type: "technical_conflict", count: 4 },
  ]);
  render(withQueryClient(<Tags />));
  await waitFor(() => {
    expect(screen.getByText(/source-cloned/i)).toBeInTheDocument();
    expect(screen.getByText(/12 bills/i)).toBeInTheDocument();
    expect(screen.getByText(/technical conflict/i)).toBeInTheDocument();
    expect(screen.getByText(/4 bills/i)).toBeInTheDocument();
  });
});

test("Tag cards link to dashboard with tag_type query param", async () => {
  (api.tags as jest.Mock).mockResolvedValue([
    { tag_type: "source_cloned", count: 12 },
  ]);
  render(withQueryClient(<Tags />));
  const link = await screen.findByRole("link", { name: /source-cloned/i });
  expect(link).toHaveAttribute("href", "/?tag_type=source_cloned");
});

test("Tags page shows loading state initially", () => {
  (api.tags as jest.Mock).mockReturnValue(new Promise(() => {}));
  render(withQueryClient(<Tags />));
  expect(screen.getByRole("status")).toHaveTextContent(/loading/i);
});

test("Tags page shows error state on fetch failure", async () => {
  (api.tags as jest.Mock).mockRejectedValue(new Error("boom"));
  render(withQueryClient(<Tags />));
  await waitFor(() => {
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });
});

test("Tags page shows empty state when API returns empty list", async () => {
  (api.tags as jest.Mock).mockResolvedValue([]);
  render(withQueryClient(<Tags />));
  await waitFor(() => {
    expect(screen.getByText(/no tags yet/i)).toBeInTheDocument();
  });
});
