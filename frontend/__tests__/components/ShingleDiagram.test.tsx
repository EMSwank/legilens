import { render } from "@testing-library/react";
import { axe } from "jest-axe";
import ShingleDiagram from "@/components/ShingleDiagram";

test("ShingleDiagram has no accessibility violations", async () => {
  const { container } = render(<ShingleDiagram />);
  expect(await axe(container)).toHaveNoViolations();
});

test("ShingleDiagram renders an SVG with accessible name", () => {
  const { container, getByRole } = render(<ShingleDiagram />);
  const svg = container.querySelector("svg");
  expect(svg).not.toBeNull();
  expect(getByRole("img")).toBeInTheDocument();
  expect(getByRole("img")).toHaveAccessibleName(/shingl/i);
});

test("ShingleDiagram includes a textual description for screen readers", () => {
  const { getAllByText } = render(<ShingleDiagram />);
  expect(getAllByText(/three-word window/i).length).toBeGreaterThan(0);
});
