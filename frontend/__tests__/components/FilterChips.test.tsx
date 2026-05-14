import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import FilterChips from "@/components/FilterChips";

const TAG_LABELS: Record<string, string> = { source_cloned: "Source-Cloned" };

test("FilterChips renders nothing when no filters active", () => {
  const { container } = render(
    <FilterChips
      session={null}
      tagType={null}
      tagLabels={TAG_LABELS}
      onRemoveSession={() => {}}
      onRemoveTag={() => {}}
    />
  );
  expect(container).toBeEmptyDOMElement();
});

test("FilterChips renders one chip when only session is set", () => {
  render(
    <FilterChips
      session="2025A"
      tagType={null}
      tagLabels={TAG_LABELS}
      onRemoveSession={() => {}}
      onRemoveTag={() => {}}
    />
  );
  expect(screen.getByRole("button", { name: /remove session filter: 2025A/i })).toBeInTheDocument();
});

test("FilterChips renders one chip when only tag_type is set", () => {
  render(
    <FilterChips
      session={null}
      tagType="source_cloned"
      tagLabels={TAG_LABELS}
      onRemoveSession={() => {}}
      onRemoveTag={() => {}}
    />
  );
  expect(screen.getByRole("button", { name: /remove tag filter: source-cloned/i })).toBeInTheDocument();
});

test("FilterChips renders two chips when both set", () => {
  render(
    <FilterChips
      session="2025A"
      tagType="source_cloned"
      tagLabels={TAG_LABELS}
      onRemoveSession={() => {}}
      onRemoveTag={() => {}}
    />
  );
  expect(screen.getAllByRole("button")).toHaveLength(2);
});

test("Clicking session chip × calls onRemoveSession only", () => {
  const onRemoveSession = jest.fn();
  const onRemoveTag = jest.fn();
  render(
    <FilterChips
      session="2025A"
      tagType="source_cloned"
      tagLabels={TAG_LABELS}
      onRemoveSession={onRemoveSession}
      onRemoveTag={onRemoveTag}
    />
  );
  fireEvent.click(screen.getByRole("button", { name: /remove session filter/i }));
  expect(onRemoveSession).toHaveBeenCalled();
  expect(onRemoveTag).not.toHaveBeenCalled();
});

test("Clicking tag chip × calls onRemoveTag only", () => {
  const onRemoveSession = jest.fn();
  const onRemoveTag = jest.fn();
  render(
    <FilterChips
      session="2025A"
      tagType="source_cloned"
      tagLabels={TAG_LABELS}
      onRemoveSession={onRemoveSession}
      onRemoveTag={onRemoveTag}
    />
  );
  fireEvent.click(screen.getByRole("button", { name: /remove tag filter/i }));
  expect(onRemoveTag).toHaveBeenCalled();
  expect(onRemoveSession).not.toHaveBeenCalled();
});

test("FilterChips chip × is keyboard accessible (Enter dismisses)", async () => {
  const user = userEvent.setup();
  const onRemoveTag = jest.fn();
  render(
    <FilterChips
      session={null}
      tagType="source_cloned"
      tagLabels={TAG_LABELS}
      onRemoveSession={() => {}}
      onRemoveTag={onRemoveTag}
    />
  );
  const btn = screen.getByRole("button", { name: /remove tag filter/i });
  btn.focus();
  await user.keyboard("{Enter}");
  expect(onRemoveTag).toHaveBeenCalledTimes(1);
});

test("FilterChips has no axe violations with two chips", async () => {
  const { container } = render(
    <FilterChips
      session="2025A"
      tagType="source_cloned"
      tagLabels={TAG_LABELS}
      onRemoveSession={() => {}}
      onRemoveTag={() => {}}
    />
  );
  expect(await axe(container)).toHaveNoViolations();
});
