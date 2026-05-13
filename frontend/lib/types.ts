export interface ISTScore {
  source_authenticity_score: number;
  copycat_alert: boolean;
  analyzed_at: string;
}

export interface FrictionTag {
  tag_type: string;
  confidence: number | null;
}

export interface BillListItem {
  id: string;
  bill_number: string;
  title: string;
  state: string;
  session: string;
  status: string | null;
  copycat_alert: boolean | null;
}

export interface BillDetail {
  id: string;
  bill_number: string;
  title: string;
  description: string | null;
  state: string;
  session: string;
  status: string | null;
  sponsors: Record<string, unknown> | null;
  ist_score: ISTScore | null;
  tags: FrictionTag[];
}

export type SnippetStatus = "pending" | "verified" | "source_verified_text_missing";

export interface SnippetItem {
  kind: "snippet";
  co_context_before: string;
  co_match: string;
  co_context_after: string;
  source_context_before: string;
  source_match: string;
  source_context_after: string;
}

export interface GhostMessage {
  kind: "ghost";
  message: "Source text unavailable for extraction";
}

export type SnippetOrGhost = SnippetItem | GhostMessage;

export interface Match {
  id: string;
  matched_bill_title: string | null;
  matched_state: string | null;
  similarity_score: number;
  snippet_status: SnippetStatus;
  matched_snippets: SnippetOrGhost[] | null;
}

export interface Stats {
  total_co_bills: number;
  copycat_alerts: number;
  bills_analyzed: number;
}

export interface TagCount {
  tag_type: string;
  count: number;
}
