import { DOCUMENT_MODES } from "@/lib/modes";
import type { DocumentMode } from "@/lib/types";

const STORAGE_KEY = "redactldr.preferences";

export interface Preferences {
  defaultMode: DocumentMode;
  safeMode: boolean;
}

export const DEFAULT_PREFERENCES: Preferences = {
  defaultMode: "resume_anonymization",
  safeMode: true,
};

export function readPreferences(): Preferences {
  if (typeof window === "undefined") {
    return DEFAULT_PREFERENCES;
  }
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return DEFAULT_PREFERENCES;
    }
    const parsed = JSON.parse(raw) as Partial<Preferences>;
    const mode = DOCUMENT_MODES.some((item) => item.id === parsed.defaultMode)
      ? (parsed.defaultMode as DocumentMode)
      : DEFAULT_PREFERENCES.defaultMode;
    return {
      defaultMode: mode,
      safeMode: parsed.safeMode ?? DEFAULT_PREFERENCES.safeMode,
    };
  } catch {
    return DEFAULT_PREFERENCES;
  }
}

export function writePreferences(next: Preferences): void {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
}
