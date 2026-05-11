import { render } from "@testing-library/react";
import { axe } from "jest-axe";
import ISTScoreGauge from "@/components/ISTScoreGauge";

jest.mock("recharts", () => ({
  RadialBarChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  RadialBar: () => null,
  PolarAngleAxis: () => null,
}));

test("ISTScoreGauge has no accessibility violations", async () => {
  const { container } = render(<ISTScoreGauge score={42} copycatAlert={false} />);
  expect(await axe(container)).toHaveNoViolations();
});

test("ISTScoreGauge aria-label includes score", () => {
  const { getByRole } = render(<ISTScoreGauge score={42} copycatAlert={false} />);
  expect(getByRole("img")).toHaveAttribute("aria-label", expect.stringContaining("42.00"));
});

test("ISTScoreGauge aria-label includes copycat warning when alert active", () => {
  const { getByRole } = render(<ISTScoreGauge score={12} copycatAlert={true} />);
  expect(getByRole("img").getAttribute("aria-label")).toContain("Copycat alert triggered");
});
