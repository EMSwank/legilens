import { render } from "@testing-library/react";
import { axe } from "jest-axe";
import GhostAlert from "@/components/GhostAlert";

test("GhostAlert has no accessibility violations", async () => {
  const { container } = render(<GhostAlert matchedBill="TX HB-1" />);
  expect(await axe(container)).toHaveNoViolations();
});

test("GhostAlert renders as alert role", () => {
  const { getByRole } = render(<GhostAlert matchedBill="TX HB-1" />);
  expect(getByRole("alert")).toBeInTheDocument();
});
