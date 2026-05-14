import { render, screen, fireEvent } from "@testing-library/react";
import { axe } from "jest-axe";
import SessionDropdown from "@/components/SessionDropdown";

test("SessionDropdown has no axe violations", async () => {
  const { container } = render(
    <SessionDropdown sessions={["2025A", "2024A"]} current={null} onChange={() => {}} />
  );
  expect(await axe(container)).toHaveNoViolations();
});

test("SessionDropdown renders 'All sessions' plus one option per session", () => {
  render(
    <SessionDropdown sessions={["2025A", "2024A"]} current={null} onChange={() => {}} />
  );
  const select = screen.getByRole("combobox", { name: /session/i });
  expect(select).toBeInTheDocument();
  expect(screen.getByRole("option", { name: /all sessions/i })).toBeInTheDocument();
  expect(screen.getByRole("option", { name: "2025A" })).toBeInTheDocument();
  expect(screen.getByRole("option", { name: "2024A" })).toBeInTheDocument();
});

test("SessionDropdown calls onChange with selected session", () => {
  const onChange = jest.fn();
  render(
    <SessionDropdown sessions={["2025A", "2024A"]} current={null} onChange={onChange} />
  );
  fireEvent.change(screen.getByRole("combobox", { name: /session/i }), {
    target: { value: "2025A" },
  });
  expect(onChange).toHaveBeenCalledWith("2025A");
});

test("SessionDropdown calls onChange(null) when 'All sessions' selected", () => {
  const onChange = jest.fn();
  render(
    <SessionDropdown sessions={["2025A", "2024A"]} current="2025A" onChange={onChange} />
  );
  fireEvent.change(screen.getByRole("combobox", { name: /session/i }), {
    target: { value: "" },
  });
  expect(onChange).toHaveBeenCalledWith(null);
});

test("SessionDropdown reflects current selection", () => {
  render(
    <SessionDropdown sessions={["2025A", "2024A"]} current="2024A" onChange={() => {}} />
  );
  const select = screen.getByRole("combobox", { name: /session/i }) as HTMLSelectElement;
  expect(select.value).toBe("2024A");
});
