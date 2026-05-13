import { render, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import CopyButton from "@/components/CopyButton";

const props = {
  billNumber: "SB-1", state: "CO", coMatch: "fees not to exceed",
  matchedBill: "TX HB-1", matchedState: "TX", sourceMatch: "fees not to exceed", score: 12.5,
};

beforeEach(() => {
  Object.assign(navigator, {
    clipboard: { writeText: jest.fn().mockResolvedValue(undefined) },
  });
});

test("CopyButton has no accessibility violations", async () => {
  const { container } = render(<CopyButton {...props} />);
  expect(await axe(container)).toHaveNoViolations();
});

test("CopyButton announces copy to screen readers via live region", async () => {
  const { getByRole, getByText } = render(<CopyButton {...props} />);
  await userEvent.click(getByText("Copy to Clipboard"));
  await waitFor(() => {
    expect(getByRole("status")).toHaveTextContent("Copied to clipboard");
  });
});
