import { apiFetch } from "@/lib/api/client";
import type { DocumentMode, DocumentStatus } from "@/lib/types";

/** Box in fractions (0–1) of page width and height, origin top-left. */
export interface NormalizedRect {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface ReviewPage {
  pageNumber: number;
  width: number;
  height: number;
  wordCount: number;
  hasTextLayer: boolean;
}

export interface ReviewGroup {
  entityType: string;
  label: string;
  color: string;
  count: number;
  acceptedCount: number;
}

export interface ReviewDetection {
  id: string;
  entityType: string;
  pageNumber: number;
  blockRef: string;
  bbox: Partial<NormalizedRect>;
  rects: NormalizedRect[];
  maskedText: string | null;
  policyAction: "auto" | "suggested" | null;
  confidence: number;
  accepted: boolean;
  source: string;
}

export interface ManualRedaction {
  id: string;
  pageNumber: number;
  entityType: string;
  label: string;
  color: string;
  kind: string;
  bbox: NormalizedRect;
  status: string;
  createdAt: string;
}

export interface ReviewState {
  documentId: string;
  filename: string;
  status: DocumentStatus;
  processingStage: string | null;
  mode: DocumentMode;
  safeMode: boolean;
  pageCount: number | null;
  reviewable: boolean;
  pages: ReviewPage[];
  groups: ReviewGroup[];
  detections: ReviewDetection[];
  manualRedactions: ManualRedaction[];
  activity: unknown[];
}

const json = { "Content-Type": "application/json" };

export function getReviewState(token: string, documentId: string): Promise<ReviewState> {
  return apiFetch<ReviewState>(`/v1/documents/${documentId}/review-state`, token);
}

export async function getOriginalUrl(token: string, documentId: string): Promise<string> {
  const body = await apiFetch<{ url: string }>(`/v1/documents/${documentId}/original-url`, token);
  return body.url;
}

export async function setDetectionAccepted(
  token: string,
  documentId: string,
  detectionId: string,
  accepted: boolean,
): Promise<void> {
  await apiFetch(`/v1/documents/${documentId}/detections/${detectionId}`, token, {
    method: "PATCH",
    headers: json,
    body: JSON.stringify({ accepted }),
  });
}

export async function setEntityTypeAccepted(
  token: string,
  documentId: string,
  entityType: string,
  accepted: boolean,
): Promise<void> {
  await apiFetch(`/v1/documents/${documentId}/detections/bulk`, token, {
    method: "POST",
    headers: json,
    body: JSON.stringify({ entityType, accepted }),
  });
}

export function createManualRedaction(
  token: string,
  documentId: string,
  input: { id: string; pageNumber: number; bbox: NormalizedRect },
): Promise<ManualRedaction> {
  return apiFetch<ManualRedaction>(`/v1/documents/${documentId}/redactions`, token, {
    method: "POST",
    headers: json,
    body: JSON.stringify(input),
  });
}

export function updateManualRedaction(
  token: string,
  documentId: string,
  redactionId: string,
  bbox: NormalizedRect,
): Promise<ManualRedaction> {
  return apiFetch<ManualRedaction>(`/v1/documents/${documentId}/redactions/${redactionId}`, token, {
    method: "PATCH",
    headers: json,
    body: JSON.stringify({ bbox }),
  });
}

export async function deleteManualRedaction(token: string, documentId: string, redactionId: string): Promise<void> {
  await apiFetch<void>(`/v1/documents/${documentId}/redactions/${redactionId}`, token, { method: "DELETE" });
}
