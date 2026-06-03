import { render } from "@testing-library/react";
import { axe } from "jest-axe";
import RelatedBillCard from "@/components/RelatedBillCard";
import type { Match } from "@/lib/types";

const related: Match = {
  id: "m1",
  matched_bill_id: "00000000-0000-0000-0000-0000000000bb",
  matched_bill_number: "SB24-005",
  matched_bill_title: "Concerning Water Rights",
  matched_state: "CO",
  similarity_score: 93.2,
  snippet_status: "pending",
  matched_snippets: null,
  match_type: "co_internal",
};

test("RelatedBillCard links to the related bill and shows number + score", () => {
  const { getByRole, getByText } = render(<RelatedBillCard match={related} />);
  expect(getByRole("link")).toHaveAttribute("href", "/bills/00000000-0000-0000-0000-0000000000bb");
  expect(getByText("SB24-005")).toBeInTheDocument();
  expect(getByText(/93/)).toBeInTheDocument();
});

test("RelatedBillCard has no accessibility violations", async () => {
  const { container } = render(<RelatedBillCard match={related} />);
  expect(await axe(container)).toHaveNoViolations();
});
