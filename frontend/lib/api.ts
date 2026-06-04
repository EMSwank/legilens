import type { BillListItem, BillDetail, Match, Stats, TagCount, Coverage } from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const HEADERS = { "User-Agent": "LegiLens-Frontend/1.0" };

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { headers: HEADERS });
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`);
  return res.json() as Promise<T>;
}

export const api = {
  bills: (params?: { session?: string; status?: string; tag_type?: string; page?: number }): Promise<BillListItem[]> => {
    const q = new URLSearchParams();
    if (params?.session) q.set("session", params.session);
    if (params?.status) q.set("status", params.status);
    if (params?.tag_type) q.set("tag_type", params.tag_type);
    if (params?.page !== undefined) q.set("page", String(params.page));
    const qs = q.toString();
    return get<BillListItem[]>(qs ? `/bills?${qs}` : "/bills");
  },
  searchBills: (q: string): Promise<BillListItem[]> =>
    get<BillListItem[]>(`/bills/search?q=${encodeURIComponent(q)}`),
  bill: (id: string): Promise<BillDetail> =>
    get<BillDetail>(`/bills/${id}`),
  matches: (billId: string): Promise<Match[]> =>
    get<Match[]>(`/bills/${billId}/matches`),
  stats: (): Promise<Stats> =>
    get<Stats>("/stats"),
  tags: (): Promise<TagCount[]> => get<TagCount[]>("/tags"),
  sessions: (): Promise<string[]> => get<string[]>("/bills/sessions"),
  coverage: (): Promise<Coverage> => get<Coverage>("/coverage"),
};
