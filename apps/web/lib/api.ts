import type { DocumentMode, DocumentRecord } from "@/lib/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function parseOrThrow(response: Response): Promise<unknown> {
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`API ${response.status}: ${text}`);
  }
  return response.json();
}

export interface CreateDocumentInput {
  filename: string;
  contentType: string;
  mode: DocumentMode;
  safeMode: boolean;
}

export interface CreateDocumentOutput {
  id: string;
  s3Key: string;
  presignedPutUrl: string;
  status: string;
}

export async function listDocuments(token: string): Promise<DocumentRecord[]> {
  const response = await fetch(`${API_URL}/v1/documents`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
    cache: "no-store",
  });
  return parseOrThrow(response) as Promise<DocumentRecord[]>;
}

export async function createDocument(
  token: string,
  payload: CreateDocumentInput,
): Promise<CreateDocumentOutput> {
  const response = await fetch(`${API_URL}/v1/documents`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  return parseOrThrow(response) as Promise<CreateDocumentOutput>;
}
