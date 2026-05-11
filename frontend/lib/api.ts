import type { BillListItem, BillDetail, Match, Stats, TagCount } from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const HEADERS = { "User-Agent": "LegiLens-Frontend/1.0" };

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { headers: HEADERS });
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`);
  return res.json() as Promise<T>;
}

export const api = {
  bills: (params?: { session?: string; status?: string; page?: number }): Promise<BillListItem[]> => {
    const q = new URLSearchParams();
    if (params?.session) q.set("session", params.session);
    if (params?.status) q.set("status", params.status);
    if (params?.page) q.set("page", String(params.page));
    return get<BillListItem[]>(`/bills?${q}`);
  },
  searchBills: (q: string): Promise<BillListItem[]> =>
    get<BillListItem[]>(`/bills/search?q=${encodeURIComponent(q)}`),
  bill: (id: string): Promise<BillDetail> =>
    get<BillDetail>(`/bills/${id}`),
  matches: (billId: string): Promise<Match[]> =>
    get<Match[]>(`/bills/${billId}/matches`),
  stats: (): Promise<Stats> =>
    get<Stats>("/stats"),
  tags: (): Promise<TagCount[]> =>
    get<TagCount[]>("/tags"),
};
