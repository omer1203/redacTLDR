import { apiFetch } from "@/lib/api/client";

export type ExportStatus = "QUEUED" | "PROCESSING" | "EXPORTED" | "FAILED";

/** Mirrors `ExportOut` in services/api/app/schemas.py. */
export interface ExportRecord {
  id: string;
  documentId: string;
  status: ExportStatus;
  includeLabels: boolean;
  pageCount: number | null;
  redactionCount: number | null;
  sizeBytes: number | null;
  errorCode: string | null;
  errorMessage: string | null;
  createdAt: string;
  completedAt: string | null;
  /** Presigned, about 5 minutes. Only set when the verified file is stored. */
  downloadUrl: string | null;
}

export interface ExportOptions {
  includeLabels: boolean;
}

export function isExportActive(record: ExportRecord | undefined | null): boolean {
  return record?.status === "QUEUED" || record?.status === "PROCESSING";
}

/** Returns the export already running for this document instead of queueing a second one. */
export function queueExport(
  token: string,
  documentId: string,
  options: ExportOptions = { includeLabels: false },
): Promise<ExportRecord> {
  return apiFetch<ExportRecord>(`/v1/documents/${documentId}/export`, token, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ includeLabels: options.includeLabels }),
  });
}

export function getExport(token: string, documentId: string, exportId: string): Promise<ExportRecord> {
  return apiFetch<ExportRecord>(`/v1/documents/${documentId}/exports/${exportId}`, token);
}

export function listExports(token: string, documentId: string): Promise<ExportRecord[]> {
  return apiFetch<ExportRecord[]>(`/v1/documents/${documentId}/exports`, token);
}
