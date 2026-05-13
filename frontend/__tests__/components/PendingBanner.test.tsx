import { render } from "@testing-library/react";
import { axe } from "jest-axe";
import PendingBanner from "@/components/PendingBanner";

test("PendingBanner has no accessibility violations", async () => {
  const { container } = render(<PendingBanner />);
  expect(await axe(container)).toHaveNoViolations();
});

test("PendingBanner renders as status role", () => {
  const { getByRole } = render(<PendingBanner />);
  expect(getByRole("status")).toBeInTheDocument();
});
