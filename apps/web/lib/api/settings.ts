import { apiFetch } from "@/lib/api/client";
import type { DocumentMode } from "@/lib/types";

export interface AccountSettings {
  defaultMode: DocumentMode;
  safeMode: boolean;
  retentionDays: number;
  storeRawDetections: boolean;
}

export function getSettings(token: string): Promise<AccountSettings> {
  return apiFetch<AccountSettings>("/v1/settings", token);
}

export function saveSettings(token: string, settings: AccountSettings): Promise<AccountSettings> {
  return apiFetch<AccountSettings>("/v1/settings", token, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(settings),
  });
}

export function deleteAccount(token: string): Promise<{ status: string }> {
  return apiFetch("/v1/account/delete", token, { method: "POST" });
}
