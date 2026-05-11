import { render } from "@testing-library/react";
import { axe } from "jest-axe";
import BillSidebar from "@/components/BillSidebar";
import type { ISTScore, FrictionTag } from "@/lib/types";

jest.mock("recharts", () => ({
  RadialBarChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  RadialBar: () => null,
  PolarAngleAxis: () => null,
}));

const istScore: ISTScore = {
  source_authenticity_score: 73.4,
  copycat_alert: true,
  analyzed_at: "2024-01-15T00:00:00Z",
};

const tags: FrictionTag[] = [
  { tag_type: "source_cloned", confidence: 0.95 },
  { tag_type: "technical_conflict", confidence: 0.7 },
];

test("BillSidebar has no accessibility violations when score present", async () => {
  const { container } = render(<BillSidebar istScore={istScore} tags={tags} />);
  expect(await axe(container)).toHaveNoViolations();
});

test("BillSidebar has no accessibility violations when score null", async () => {
  const { container } = render(<BillSidebar istScore={null} tags={[]} />);
  expect(await axe(container)).toHaveNoViolations();
});

test("BillSidebar renders ISTScoreGauge when score present", () => {
  const { getByRole } = render(<BillSidebar istScore={istScore} tags={tags} />);
  expect(getByRole("img")).toBeInTheDocument();
});

test("BillSidebar renders PendingBanner when ist_score is null", () => {
  const { getByRole } = render(<BillSidebar istScore={null} tags={[]} />);
  expect(getByRole("status")).toBeInTheDocument();
});

test("BillSidebar renders all friction tags", () => {
  const { getByText } = render(<BillSidebar istScore={istScore} tags={tags} />);
  expect(getByText("Source-Cloned")).toBeInTheDocument();
  expect(getByText("Technical Conflict")).toBeInTheDocument();
});

test("BillSidebar renders no tags when tags array is empty", () => {
  const { queryByText } = render(<BillSidebar istScore={istScore} tags={[]} />);
  expect(queryByText("Source-Cloned")).not.toBeInTheDocument();
});
