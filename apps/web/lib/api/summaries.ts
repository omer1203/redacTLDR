import { ApiError, apiFetch } from "@/lib/api/client";

export type SummaryStatus = "QUEUED" | "PROCESSING" | "SUMMARIZED" | "FAILED";

export interface SummaryCitation {
  page: number;
  quoteSnippet?: string;
}

export interface CitedItem {
  text: string;
  citations?: SummaryCitation[];
}

/** Mirrors `SummaryOut`. `json.summary` is the mode-specific body once R6 has run. */
export interface SummaryRecord {
  id: string;
  mode: string;
  status: SummaryStatus;
  schemaVersion: number;
  safeMode: boolean | null;
  json: {
    schemaVersion?: number;
    safeMode?: boolean;
    truncated?: boolean;
    pagesUsed?: number;
    summary?: Record<string, unknown>;
  };
  markdown: string;
  tokenUsage: { inputTokens?: number; outputTokens?: number; calls?: number; model?: string };
  errorCode: string | null;
  errorMessage: string | null;
  createdAt: string | null;
  completedAt: string | null;
}

export function isSummaryActive(record: SummaryRecord | null | undefined): boolean {
  return record?.status === "QUEUED" || record?.status === "PROCESSING";
}

export function queueSummary(token: string, documentId: string): Promise<SummaryRecord> {
  return apiFetch<SummaryRecord>(`/v1/documents/${documentId}/summaries`, token, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ includeMarkdown: true }),
  });
}

export async function getLatestSummary(token: string, documentId: string): Promise<SummaryRecord | null> {
  try {
    return await apiFetch<SummaryRecord>(`/v1/documents/${documentId}/summaries/latest`, token);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}
