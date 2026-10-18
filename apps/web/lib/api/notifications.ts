import { apiFetch } from "@/lib/api/client";

export interface NotificationItem {
  id: string;
  documentId: string | null;
  kind: string;
  title: string;
  readAt: string | null;
  createdAt: string;
}

export function listNotifications(token: string): Promise<NotificationItem[]> {
  return apiFetch<NotificationItem[]>("/v1/notifications", token);
}

export function markNotificationsRead(token: string, ids: string[] | "all"): Promise<{ updated: number }> {
  const body = ids === "all" ? { all: true } : { ids };
  return apiFetch("/v1/notifications/read", token, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}
