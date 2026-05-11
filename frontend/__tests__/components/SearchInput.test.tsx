import { render, fireEvent, act } from "@testing-library/react";
import { axe } from "jest-axe";
import SearchInput from "@/components/SearchInput";

const mockPush = jest.fn();
jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

beforeEach(() => {
  jest.clearAllMocks();
  jest.useFakeTimers();
});

afterEach(() => {
  jest.useRealTimers();
});

test("SearchInput has no accessibility violations", async () => {
  jest.useRealTimers();
  const { container } = render(<SearchInput />);
  expect(await axe(container)).toHaveNoViolations();
});

test("SearchInput renders a searchbox", () => {
  const { getByRole } = render(<SearchInput />);
  expect(getByRole("searchbox")).toBeInTheDocument();
});

test("SearchInput does not push URL before 300ms", () => {
  const { getByRole } = render(<SearchInput />);
  fireEvent.change(getByRole("searchbox"), { target: { value: "privacy" } });
  act(() => { jest.advanceTimersByTime(299); });
  expect(mockPush).not.toHaveBeenCalled();
});

test("SearchInput pushes ?q= after 300ms", () => {
  const { getByRole } = render(<SearchInput />);
  fireEvent.change(getByRole("searchbox"), { target: { value: "privacy" } });
  act(() => { jest.advanceTimersByTime(300); });
  expect(mockPush).toHaveBeenCalledWith("?q=privacy");
});

test("SearchInput pushes ? when input is cleared", () => {
  const { getByRole } = render(<SearchInput />);
  const input = getByRole("searchbox");
  fireEvent.change(input, { target: { value: "privacy" } });
  act(() => { jest.advanceTimersByTime(300); });
  jest.clearAllMocks();
  fireEvent.change(input, { target: { value: "" } });
  act(() => { jest.advanceTimersByTime(300); });
  expect(mockPush).toHaveBeenCalledWith("?");
});

test("SearchInput resets debounce timer on each keystroke", () => {
  const { getByRole } = render(<SearchInput />);
  const input = getByRole("searchbox");
  fireEvent.change(input, { target: { value: "p" } });
  act(() => { jest.advanceTimersByTime(200); });
  fireEvent.change(input, { target: { value: "pr" } });
  act(() => { jest.advanceTimersByTime(200); });
  expect(mockPush).not.toHaveBeenCalled();
  act(() => { jest.advanceTimersByTime(100); });
  expect(mockPush).toHaveBeenCalledWith("?q=pr");
  expect(mockPush).toHaveBeenCalledTimes(1);
});
