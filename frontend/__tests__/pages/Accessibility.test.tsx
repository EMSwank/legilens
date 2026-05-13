import { render, screen } from "@testing-library/react";
import { axe } from "jest-axe";
import Accessibility from "@/app/accessibility/page";

test("Accessibility page has no axe violations", async () => {
  const { container } = render(<Accessibility />);
  expect(await axe(container)).toHaveNoViolations();
});

test("Accessibility page renders single h1 with descriptive text", () => {
  render(<Accessibility />);
  const h1 = screen.getByRole("heading", { level: 1 });
  expect(h1).toHaveTextContent(/accessibility/i);
});

test("Accessibility page states WCAG 2.1 AA conformance target", () => {
  render(<Accessibility />);
  expect(screen.getByText(/WCAG 2\.1.*level AA/i)).toBeInTheDocument();
});

test("Accessibility page provides a contact link", () => {
  render(<Accessibility />);
  const links = screen.getAllByRole("link");
  const contactLink = links.find((l) =>
    /github\.com.*issues|mailto:/i.test(l.getAttribute("href") ?? "")
  );
  expect(contactLink).toBeDefined();
});
