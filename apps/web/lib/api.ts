/**
 * Frontend API client helpers.
 *
 * Centralizes URL construction, auth headers, response error handling, and
 * payload typing for the web app.
 */
import { toDocumentRecord, type DocumentApiDto, type DocumentMode, type DocumentRecord, type DocumentStatus } from "@/lib/types";

// Public API base URL (defaults to local API during development).
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const DEMO_USER_ID = process.env.NEXT_PUBLIC_DEMO_USER ?? "demo-user";

interface ApiErrorBody {
  detail?: unknown;
  error?: {
    code?: string;
    message?: string;
  };
}

async function parseOrThrow(response: Response): Promise<unknown> {
  // Normalize non-2xx responses into explicit thrown errors for React Query.
  if (!response.ok) {
    let message = "Request failed";
    const rawBody = await response.text();
    try {
      const payload = JSON.parse(rawBody) as ApiErrorBody;
      if (typeof payload.detail === "string") {
        message = payload.detail;
      } else if (payload.error?.message) {
        message = payload.error.message;
      }
    } catch {
      if (rawBody) {
        message = rawBody;
      }
    }
    throw new Error(`API ${response.status}: ${message}`);
  }
  // Caller performs final type assertion per endpoint contract.
  return response.json();
}

async function apiFetch<T>(
  path: string,
  token: string,
  init?: Omit<RequestInit, "headers"> & { headers?: HeadersInit },
): Promise<T> {
  const authHeaders: HeadersInit =
    token.trim().length > 0
      ? { Authorization: `Bearer ${token}` }
      : {
          // Local developer mode: API accepts x-demo-user when ENVIRONMENT=local.
          "x-demo-user": DEMO_USER_ID,
        };
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      ...authHeaders,
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
  return parseOrThrow(response) as Promise<T>;
}

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

export async function listDocuments(token: string): Promise<DocumentRecord[]> {
  const records = await apiFetch<DocumentApiDto[]>("/v1/documents", token);
  return records.map(toDocumentRecord);
}

export async function createDocument(
  token: string,
  payload: CreateDocumentInput,
): Promise<CreateDocumentOutput> {
  return apiFetch<CreateDocumentOutput>("/v1/documents", token, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function completeIngest(token: string, documentId: string): Promise<{ id: string; status: DocumentStatus }> {
  return apiFetch<{ id: string; status: DocumentStatus }>(`/v1/documents/${documentId}/ingest-complete`, token, {
    method: "POST",
  });
}

export async function uploadFileToPresignedUrl(url: string, file: File): Promise<void> {
  const response = await fetch(url, {
    method: "PUT",
    body: await file.arrayBuffer(),
  });
  if (!response.ok) {
    throw new Error(`Upload failed with status ${response.status}`);
  }
}
