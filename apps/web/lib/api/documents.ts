import { apiFetch } from "@/lib/api/client";
import { toDocumentRecord, type DocumentApiDto, type DocumentMode, type DocumentRecord, type DocumentStatus } from "@/lib/types";

export interface CreateDocumentInput {
  filename: string;
  contentType: string;
  mode: DocumentMode;
  safeMode: boolean;
  sizeBytes?: number;
}

export interface CreateDocumentOutput {
  id: string;
  s3Key: string;
  presignedPutUrl: string;
  status: DocumentStatus;
}

export interface JobRecord {
  jobType: string;
  status: string;
  attemptCount: number;
  lastError: string | null;
  startedAt: string | null;
  finishedAt: string | null;
}

export interface DetectionRect {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface DetectionRecord {
  id: string;
  entity_type: string;
  page_number: number;
  confidence: number;
  accepted: boolean;
  source: string;
  rects: DetectionRect[];
  masked_text: string | null;
  policy_action: "auto" | "suggested" | null;
  rule_id: string | null;
}

export interface DetectionGroup {
  entity_type: string;
  label: string;
  color: string;
  count: number;
  accepted_count: number;
}

export interface DetectionList {
  document_id: string;
  mode: DocumentMode;
  safe_mode: boolean;
  page: number | null;
  total: number;
  items: DetectionRecord[];
  groups: DetectionGroup[];
}

export async function listDocuments(token: string): Promise<DocumentRecord[]> {
  const records = await apiFetch<DocumentApiDto[]>("/v1/documents", token);
  return records.map(toDocumentRecord);
}

export async function getDocument(token: string, documentId: string): Promise<DocumentRecord> {
  const record = await apiFetch<DocumentApiDto>(`/v1/documents/${documentId}`, token);
  return toDocumentRecord(record);
}

export async function createDocument(token: string, payload: CreateDocumentInput): Promise<CreateDocumentOutput> {
  return apiFetch<CreateDocumentOutput>("/v1/documents", token, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function completeIngest(
  token: string,
  documentId: string,
): Promise<{ id: string; status: DocumentStatus }> {
  return apiFetch<{ id: string; status: DocumentStatus }>(`/v1/documents/${documentId}/ingest-complete`, token, {
    method: "POST",
  });
}

export async function listJobs(token: string, documentId: string): Promise<JobRecord[]> {
  return apiFetch<JobRecord[]>(`/v1/documents/${documentId}/jobs`, token);
}

export async function getDetections(token: string, documentId: string, page?: number): Promise<DetectionList> {
  const query = page ? `?page=${page}` : "";
  return apiFetch<DetectionList>(`/v1/documents/${documentId}/detections${query}`, token);
}

export async function listDetections(token: string, documentId: string): Promise<DetectionRecord[]> {
  const body = await getDetections(token, documentId);
  return body.items;
}

export async function reprocessDocument(
  token: string,
  documentId: string,
): Promise<{ id: string; status: DocumentStatus }> {
  return apiFetch<{ id: string; status: DocumentStatus }>(`/v1/documents/${documentId}/process`, token, {
    method: "POST",
  });
}

export async function deleteDocument(token: string, documentId: string): Promise<void> {
  await apiFetch<void>(`/v1/documents/${documentId}`, token, { method: "DELETE" });
}
