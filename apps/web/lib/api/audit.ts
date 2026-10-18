import { apiFetch } from "@/lib/api/client";

export interface AuditEvent {
  id: string;
  eventType: string;
  payload: Record<string, unknown>;
  documentId: string | null;
  createdAt: string;
}

export async function listAuditEvents(token: string, eventType?: string): Promise<AuditEvent[]> {
  const query = eventType ? `?eventType=${encodeURIComponent(eventType)}` : "";
  return apiFetch<AuditEvent[]>(`/v1/audit${query}`, token);
}
