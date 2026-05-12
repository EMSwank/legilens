import { render } from "@testing-library/react";
import { axe } from "jest-axe";
import SnippetDiff from "@/components/SnippetDiff";

const snippet = {
  kind: "snippet" as const,
  co_context_before: "Intro sentence.",
  co_match: "The commission shall establish fees not to exceed one hundred dollars.",
  co_context_after: "Outro sentence.",
  source_context_before: "Preamble.",
  source_match: "The commission shall establish fees not to exceed one hundred dollars.",
  source_context_after: "Closing.",
};

test("SnippetDiff has no accessibility violations", async () => {
  const { container } = render(<SnippetDiff snippet={snippet} />);
  expect(await axe(container)).toHaveNoViolations();
});

test("SnippetDiff renders Colorado and Source column headers", () => {
  const { getByText } = render(<SnippetDiff snippet={snippet} />);
  expect(getByText("Colorado")).toBeInTheDocument();
  expect(getByText("Source")).toBeInTheDocument();
});

test("SnippetDiff renders co_match and source_match text", () => {
  const { getAllByText } = render(<SnippetDiff snippet={snippet} />);
  const matches = getAllByText("The commission shall establish fees not to exceed one hundred dollars.");
  expect(matches).toHaveLength(2);
});

test("SnippetDiff renders context strings", () => {
  const { getByText } = render(<SnippetDiff snippet={snippet} />);
  expect(getByText("Intro sentence.")).toBeInTheDocument();
  expect(getByText("Preamble.")).toBeInTheDocument();
});
