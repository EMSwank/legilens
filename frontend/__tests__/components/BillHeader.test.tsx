import { render } from "@testing-library/react";
import { axe } from "jest-axe";
import BillHeader from "@/components/BillHeader";
import type { BillDetail } from "@/lib/types";

const bill: BillDetail = {
  id: "00000000-0000-0000-0000-000000000001",
  bill_number: "HB24-1234",
  title: "Concerning Digital Privacy Requirements for State Agencies",
  description: "A privacy bill.",
  state: "CO",
  session: "2024A",
  status: "Introduced",
  sponsors: null,
  ist_score: null,
  tags: [],
};

test("BillHeader has no accessibility violations", async () => {
  const { container } = render(<BillHeader bill={bill} />);
  expect(await axe(container)).toHaveNoViolations();
});

test("BillHeader renders bill number", () => {
  const { getByText } = render(<BillHeader bill={bill} />);
  expect(getByText("HB24-1234")).toBeInTheDocument();
});

test("BillHeader renders title", () => {
  const { getByText } = render(<BillHeader bill={bill} />);
  expect(getByText("Concerning Digital Privacy Requirements for State Agencies")).toBeInTheDocument();
});

test("BillHeader renders state and session", () => {
  const { getByText } = render(<BillHeader bill={bill} />);
  expect(getByText(/CO/)).toBeInTheDocument();
  expect(getByText(/2024A/)).toBeInTheDocument();
});

test("BillHeader renders status pill when status present", () => {
  const { getByText } = render(<BillHeader bill={bill} />);
  expect(getByText("Introduced")).toBeInTheDocument();
});

test("BillHeader omits status pill when status is null", () => {
  const { queryByText } = render(<BillHeader bill={{ ...bill, status: null }} />);
  expect(queryByText("Introduced")).not.toBeInTheDocument();
});
