import { render, screen } from "@testing-library/react";
import { axe } from "jest-axe";
import About from "@/app/about/page";

test("About page has no axe violations", async () => {
  const { container } = render(<About />);
  expect(await axe(container)).toHaveNoViolations();
});

test("About page renders single h1", () => {
  render(<About />);
  const headings = screen.getAllByRole("heading", { level: 1 });
  expect(headings).toHaveLength(1);
});

test("About page renders all 5 main sections", () => {
  render(<About />);
  expect(screen.getByRole("heading", { name: /what legilens measures/i })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: /how minhash works/i })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: /score interpretation/i })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: /friction tag glossary/i })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: /data sources/i })).toBeInTheDocument();
});

test("About page contains the Jaccard formula with accessible name", () => {
  render(<About />);
  const formula = screen.getByLabelText(/jaccard similarity formula/i);
  expect(formula).toBeInTheDocument();
});

test("About page includes the ShingleDiagram", () => {
  render(<About />);
  expect(screen.getByRole("img", { name: /shingl/i })).toBeInTheDocument();
});

test("About page lists all 6 friction tags in the glossary", () => {
  render(<About />);
  const tags = [
    /technical conflict/i,
    /spatial inconsistency/i,
    /expert defiance/i,
    /regressive burden/i,
    /source-cloned/i,
    /legal hallucination/i,
  ];
  for (const tag of tags) {
    expect(screen.getByText(tag)).toBeInTheDocument();
  }
});
