import type { ManualRedaction, NormalizedRect, ReviewDetection, ReviewGroup, ReviewState } from "@/lib/api/review";

/**
 * How a detection is shown:
 * - `redact`: accepted, drawn solid black, goes into the export.
 * - `suggested`: off by default under the mode policy, drawn dashed.
 * - `rejected`: the policy redacts it but the reviewer turned it off; hidden unless "show rejected" is on.
 * Rows without a policy action (pre-R3) count as suggestions.
 */
export type DetectionView = "redact" | "suggested" | "rejected";

export function detectionView(detection: ReviewDetection): DetectionView {
  if (detection.accepted) {
    return "redact";
  }
  return detection.policyAction === "auto" ? "rejected" : "suggested";
}

/** Mirrors MANUAL_ENTITY_INFO in services/shared/policy.py, used until the server row arrives. */
export const MANUAL_LABEL = "Manual redaction";
export const MANUAL_COLOR = "#475569";
export const MANUAL_ENTITY_TYPE = "CUSTOM";

export const FALLBACK_COLOR = "#64748b";

export function redactionTotal(state: ReviewState): number {
  return state.detections.filter((item) => item.accepted).length + state.manualRedactions.length;
}

/** Recount `acceptedCount` per group after an optimistic toggle; labels and colors are unchanged. */
export function recountGroups(groups: ReviewGroup[], detections: ReviewDetection[]): ReviewGroup[] {
  const accepted = new Map<string, number>();
  for (const item of detections) {
    if (item.accepted) {
      accepted.set(item.entityType, (accepted.get(item.entityType) ?? 0) + 1);
    }
  }
  return groups.map((group) => ({ ...group, acceptedCount: accepted.get(group.entityType) ?? 0 }));
}

export function withDetections(state: ReviewState, detections: ReviewDetection[]): ReviewState {
  return { ...state, detections, groups: recountGroups(state.groups, detections) };
}

export function withManualRedactions(state: ReviewState, manualRedactions: ManualRedaction[]): ReviewState {
  return { ...state, manualRedactions };
}

export interface PageCounts {
  detections: number;
  redacted: number;
}

/** Per-page totals for the thumbnail dots. Rejected detections are not counted. */
export function countsByPage(state: ReviewState): Map<number, PageCounts> {
  const counts = new Map<number, PageCounts>();
  const bump = (page: number, redacted: boolean) => {
    const entry = counts.get(page) ?? { detections: 0, redacted: 0 };
    entry.detections += 1;
    entry.redacted += redacted ? 1 : 0;
    counts.set(page, entry);
  };
  for (const item of state.detections) {
    if (detectionView(item) !== "rejected") {
      bump(item.pageNumber, item.accepted);
    }
  }
  for (const box of state.manualRedactions) {
    bump(box.pageNumber, true);
  }
  return counts;
}

/** Boxes to draw for a detection. Rows from before R3 have only the envelope `bbox`. */
export function detectionRects(detection: ReviewDetection): NormalizedRect[] {
  if (detection.rects.length > 0) {
    return detection.rects;
  }
  const { x, y, width, height } = detection.bbox;
  if ([x, y, width, height].every((value) => typeof value === "number") && (width ?? 0) > 0 && (height ?? 0) > 0) {
    return [{ x: x!, y: y!, width: width!, height: height! }];
  }
  return [];
}

/** `#rrggbb` plus an alpha byte, for tinted fills. Other formats are returned unchanged. */
export function withAlpha(color: string, alpha: number): string {
  if (!/^#[0-9a-f]{6}$/i.test(color)) {
    return color;
  }
  const byte = Math.round(Math.min(1, Math.max(0, alpha)) * 255)
    .toString(16)
    .padStart(2, "0");
  return `${color}${byte}`;
}

export function groupColor(groups: ReviewGroup[], entityType: string): string {
  return groups.find((group) => group.entityType === entityType)?.color ?? FALLBACK_COLOR;
}

export function groupLabel(groups: ReviewGroup[], entityType: string): string {
  return groups.find((group) => group.entityType === entityType)?.label ?? entityType;
}
