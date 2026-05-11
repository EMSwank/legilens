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
