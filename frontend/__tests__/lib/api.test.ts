/**
 * @jest-environment node
 */
import { api } from "@/lib/api";

const fetchMock = jest.fn();
global.fetch = fetchMock as unknown as typeof fetch;

beforeEach(() => {
  fetchMock.mockReset();
  fetchMock.mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => [],
  });
});

const lastUrl = () => fetchMock.mock.calls.at(-1)![0] as string;

test("api.bills with no params hits /bills without query string", async () => {
  await api.bills();
  expect(lastUrl()).toMatch(/\/bills$/);
});

test("api.bills with session appends session query param", async () => {
  await api.bills({ session: "2025A" });
  expect(lastUrl()).toMatch(/\/bills\?session=2025A$/);
});

test("api.bills with tag_type appends tag_type query param", async () => {
  await api.bills({ tag_type: "source_cloned" });
  expect(lastUrl()).toMatch(/\/bills\?tag_type=source_cloned$/);
});

test("api.bills with session + tag_type appends both", async () => {
  await api.bills({ session: "2025A", tag_type: "source_cloned" });
  expect(lastUrl()).toContain("session=2025A");
  expect(lastUrl()).toContain("tag_type=source_cloned");
});

test("api.tags hits /tags", async () => {
  await api.tags();
  expect(lastUrl()).toMatch(/\/tags$/);
});

test("api.sessions hits /bills/sessions", async () => {
  await api.sessions();
  expect(lastUrl()).toMatch(/\/bills\/sessions$/);
});

test("api.bills with page=0 appends page query param", async () => {
  await api.bills({ page: 0 });
  expect(lastUrl()).toMatch(/\/bills\?page=0$/);
});
