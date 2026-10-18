"use client";

import { useEffect } from "react";

import type { ReviewState } from "@/lib/api/review";
import { useDeleteManualRedaction, useSetDetectionAccepted, useSetEntityTypeAccepted } from "@/lib/review/queries";
import { useReviewStore } from "@/lib/review/store";

/**
 * Review keyboard shortcuts:
 *   D            toggle the draw tool
 *   Esc          back to select, clear the selection
 *   Delete / ⌫   delete the selected box, or turn off the selected detection
 *   ← / →        previous / next page
 *   A            redact every item of the selected detection's type
 * Ignored while typing in a field or with a modifier held, so browser shortcuts still work.
 */

function isTyping(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) {
    return false;
  }
  return target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName);
}

export function useReviewShortcuts(state: ReviewState | undefined, documentId: string): void {
  const tool = useReviewStore((s) => s.tool);
  const selection = useReviewStore((s) => s.selection);
  const setTool = useReviewStore((s) => s.setTool);
  const select = useReviewStore((s) => s.select);
  const nextPage = useReviewStore((s) => s.nextPage);
  const previousPage = useReviewStore((s) => s.previousPage);
  // `mutate` is stable across renders; the mutation objects are not.
  const { mutate: setAccepted } = useSetDetectionAccepted(documentId);
  const { mutate: setTypeAccepted } = useSetEntityTypeAccepted(documentId);
  const { mutate: deleteBox } = useDeleteManualRedaction(documentId);

  useEffect(() => {
    if (!state) {
      return;
    }
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.defaultPrevented || event.metaKey || event.ctrlKey || event.altKey || isTyping(event.target)) {
        return;
      }
      const editable = state.reviewable;
      switch (event.key) {
        case "d":
        case "D":
          if (editable) {
            setTool(tool === "draw" ? "select" : "draw");
            event.preventDefault();
          }
          return;
        case "Escape":
          setTool("select");
          select(null);
          return;
        case "ArrowLeft":
          previousPage();
          event.preventDefault();
          return;
        case "ArrowRight":
          nextPage();
          event.preventDefault();
          return;
        case "Delete":
        case "Backspace": {
          if (!editable || !selection) {
            return;
          }
          event.preventDefault();
          if (selection.kind === "manual") {
            deleteBox({ id: selection.id });
            select(null);
            return;
          }
          const detection = state.detections.find((item) => item.id === selection.id);
          if (detection?.accepted) {
            setAccepted({ detectionId: detection.id, accepted: false });
          }
          return;
        }
        case "a":
        case "A": {
          if (!editable || selection?.kind !== "detection") {
            return;
          }
          const detection = state.detections.find((item) => item.id === selection.id);
          if (detection) {
            setTypeAccepted({ entityType: detection.entityType, accepted: true });
            event.preventDefault();
          }
          return;
        }
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [state, tool, selection, setTool, select, nextPage, previousPage, setAccepted, setTypeAccepted, deleteBox]);
}
