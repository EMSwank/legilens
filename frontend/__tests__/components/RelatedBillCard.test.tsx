import { render } from "@testing-library/react";
import { axe } from "jest-axe";
import RelatedBillCard from "@/components/RelatedBillCard";
import type { Match } from "@/lib/types";

const relatedMatchFixture: Match = {
  id: "rel-1",
  matched_bill_title: "HB 5678 - Related Water Act",
  matched_state: "CO",
  similarity_score: 82.5,
  snippet_status: "pending",
  match_type: "co_internal",
  matched_bill_id: "00000000-0000-0000-0000-000000000020",
  matched_bill_number: "HB24-5678",
  matched_snippets: null,
};

test("RelatedBillCard has no accessibility violations", async () => {
  const { container } = render(<RelatedBillCard match={relatedMatchFixture} />);
  expect(await axe(container)).toHaveNoViolations();
});

test("RelatedBillCard renders bill number and title", () => {
  const { getByText } = render(<RelatedBillCard match={relatedMatchFixture} />);
  expect(getByText("HB24-5678")).toBeInTheDocument();
  expect(getByText("HB 5678 - Related Water Act")).toBeInTheDocument();
});

test("RelatedBillCard renders similarity score in amber", () => {
  const { getByText } = render(<RelatedBillCard match={relatedMatchFixture} />);
  const score = getByText("82.50% similar");
  expect(score).toBeInTheDocument();
  expect(score.className).toContain("amber");
});

test("RelatedBillCard shows PendingBanner when snippet_status is pending", () => {
  const { getByRole } = render(<RelatedBillCard match={relatedMatchFixture} />);
  expect(getByRole("status")).toBeInTheDocument();
});
