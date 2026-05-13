import { render } from "@testing-library/react";
import { axe } from "jest-axe";
import TagBadge from "@/components/TagBadge";

test("TagBadge has no accessibility violations", async () => {
  const { container } = render(<TagBadge type="source_cloned" />);
  expect(await axe(container)).toHaveNoViolations();
});
