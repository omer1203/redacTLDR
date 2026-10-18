"use client";

import { useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";

import type { ManualRedaction, NormalizedRect, ReviewDetection, ReviewState } from "@/lib/api/review";
import { detectionRects, detectionView, groupColor, groupLabel, withAlpha } from "@/lib/review/derive";
import {
  RESIZE_HANDLES,
  isDrawable,
  moveRect,
  pointInBox,
  rectFromPoints,
  rectStyle,
  resizeRect,
  roundRect,
  sameRect,
  type Point,
  type ResizeHandle,
} from "@/lib/review/geometry";
import { useCreateManualRedaction, useUpdateManualRedaction } from "@/lib/review/queries";
import { useReviewStore } from "@/lib/review/store";
import { cn } from "@/lib/utils";

/**
 * Boxes over one rendered page. Mounted inside react-pdf's page element, so
 * `inset-0` is exactly the canvas and percentage positions line up at any zoom.
 *
 * Pointer handling: one gesture at a time (draw, move, or resize), with pointer
 * capture on the surface so a drag keeps tracking outside the box. The drag
 * shows a local preview and saves once, on release.
 */

type Gesture =
  | { kind: "draw"; start: Point }
  | { kind: "move"; id: string; origin: Point; rect: NormalizedRect }
  | { kind: "resize"; id: string; handle: ResizeHandle; rect: NormalizedRect };

const FLASH_MS = 1200;
// The overlay remounts whenever a page finishes loading; older jumps are not replayed.
const FLASH_FRESH_MS = 4000;

const HANDLE_CLASS: Record<ResizeHandle, string> = {
  nw: "-left-1.5 -top-1.5 cursor-nwse-resize",
  ne: "-right-1.5 -top-1.5 cursor-nesw-resize",
  sw: "-bottom-1.5 -left-1.5 cursor-nesw-resize",
  se: "-bottom-1.5 -right-1.5 cursor-nwse-resize",
};

export function PageOverlay({
  state,
  documentId,
  pageNumber,
}: {
  state: ReviewState;
  documentId: string;
  pageNumber: number;
}) {
  const surfaceRef = useRef<HTMLDivElement>(null);
  const gesture = useRef<Gesture | null>(null);
  const [draft, setDraft] = useState<NormalizedRect | null>(null);
  const [preview, setPreview] = useState<{ id: string; rect: NormalizedRect } | null>(null);

  const tool = useReviewStore((s) => s.tool);
  const selection = useReviewStore((s) => s.selection);
  const showRejected = useReviewStore((s) => s.showRejected);
  const flash = useReviewStore((s) => s.flash);
  const select = useReviewStore((s) => s.select);

  const createBox = useCreateManualRedaction(documentId);
  const updateBox = useUpdateManualRedaction(documentId);
  const editable = state.reviewable;
  const drawing = tool === "draw" && editable;

  const detections = state.detections.filter(
    (item) => item.pageNumber === pageNumber && (showRejected || detectionView(item) !== "rejected"),
  );
  const boxes = state.manualRedactions.filter((box) => box.pageNumber === pageNumber);

  const [flashing, setFlashing] = useState<string | null>(null);
  useEffect(() => {
    if (!flash || Date.now() - flash.at > FLASH_FRESH_MS) {
      return;
    }
    setFlashing(flash.id);
    // Wait a frame so the boxes for a newly opened page exist before scrolling.
    const frame = requestAnimationFrame(() => {
      surfaceRef.current
        ?.querySelector(`[data-item-id="${flash.id}"]`)
        ?.scrollIntoView({ block: "center", inline: "center", behavior: "smooth" });
    });
    const timer = window.setTimeout(() => setFlashing(null), FLASH_MS);
    return () => {
      cancelAnimationFrame(frame);
      window.clearTimeout(timer);
    };
  }, [flash]);

  const pointFrom = (event: ReactPointerEvent): Point | null => {
    const surface = surfaceRef.current;
    return surface ? pointInBox(event.clientX, event.clientY, surface.getBoundingClientRect()) : null;
  };

  const begin = (event: ReactPointerEvent, next: Gesture) => {
    gesture.current = next;
    surfaceRef.current?.setPointerCapture(event.pointerId);
  };

  const finish = (event: ReactPointerEvent) => {
    gesture.current = null;
    if (surfaceRef.current?.hasPointerCapture(event.pointerId)) {
      surfaceRef.current.releasePointerCapture(event.pointerId);
    }
  };

  const onSurfacePointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (event.button !== 0) {
      return;
    }
    if (drawing) {
      const start = pointFrom(event);
      if (start) {
        event.preventDefault();
        begin(event, { kind: "draw", start });
        setDraft({ ...start, width: 0, height: 0 });
      }
      return;
    }
    if (event.target === event.currentTarget) {
      select(null);
    }
  };

  const onBoxPointerDown = (event: ReactPointerEvent, box: ManualRedaction, handle?: ResizeHandle) => {
    if (event.button !== 0 || drawing) {
      return;
    }
    event.stopPropagation();
    select({ kind: "manual", id: box.id });
    if (!editable) {
      return;
    }
    const origin = pointFrom(event);
    if (!origin) {
      return;
    }
    event.preventDefault();
    begin(
      event,
      handle ? { kind: "resize", id: box.id, handle, rect: box.bbox } : { kind: "move", id: box.id, origin, rect: box.bbox },
    );
  };

  const nextRect = (current: Gesture, point: Point): NormalizedRect => {
    switch (current.kind) {
      case "draw":
        return rectFromPoints(current.start, point);
      case "move":
        return moveRect(current.rect, point.x - current.origin.x, point.y - current.origin.y);
      case "resize":
        return resizeRect(current.rect, current.handle, point);
    }
  };

  const onPointerMove = (event: ReactPointerEvent) => {
    const current = gesture.current;
    const point = current ? pointFrom(event) : null;
    if (!current || !point) {
      return;
    }
    const rect = nextRect(current, point);
    if (current.kind === "draw") {
      setDraft(rect);
    } else {
      setPreview({ id: current.id, rect });
    }
  };

  const onPointerUp = (event: ReactPointerEvent) => {
    const current = gesture.current;
    const point = current ? pointFrom(event) : null;
    finish(event);
    setDraft(null);
    setPreview(null);
    if (!current || !point) {
      return;
    }
    const rect = nextRect(current, point);
    if (current.kind === "draw") {
      if (isDrawable(rect)) {
        const id = crypto.randomUUID();
        createBox.mutate({ id, pageNumber, bbox: roundRect(rect) });
        select({ kind: "manual", id });
      }
      return;
    }
    if (!sameRect(rect, current.rect)) {
      updateBox.mutate({ id: current.id, bbox: roundRect(rect) });
    }
  };

  const onPointerCancel = (event: ReactPointerEvent) => {
    finish(event);
    setDraft(null);
    setPreview(null);
  };

  return (
    <div
      ref={surfaceRef}
      className={cn("absolute inset-0 select-none", drawing && "cursor-crosshair touch-none")}
      onPointerDown={onSurfacePointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={onPointerCancel}
    >
      {detections.map((detection) => (
        <DetectionBoxes
          key={detection.id}
          detection={detection}
          label={groupLabel(state.groups, detection.entityType)}
          color={groupColor(state.groups, detection.entityType)}
          selected={selection?.kind === "detection" && selection.id === detection.id}
          flashing={flashing === detection.id}
          passive={drawing}
          onSelect={() => select({ kind: "detection", id: detection.id })}
        />
      ))}
      {boxes.map((box) => {
        const selected = selection?.kind === "manual" && selection.id === box.id;
        const rect = preview?.id === box.id ? preview.rect : box.bbox;
        return (
          <div
            key={box.id}
            data-item-id={box.id}
            aria-label={`${box.label} on page ${box.pageNumber}`}
            className={cn(
              "group absolute bg-black",
              drawing ? "pointer-events-none" : editable ? "cursor-move touch-none" : "cursor-pointer",
              selected && "ring-2 ring-primary ring-offset-1",
              flashing === box.id && "animate-pulse ring-4 ring-amber-400",
            )}
            style={rectStyle(rect)}
            onPointerDown={(event) => onBoxPointerDown(event, box)}
          >
            <BoxLabel text={box.label} visible={selected} />
            {selected && editable && !drawing
              ? RESIZE_HANDLES.map((handle) => (
                  <span
                    key={handle}
                    aria-hidden
                    className={cn("absolute h-3 w-3 rounded-sm border border-primary bg-white", HANDLE_CLASS[handle])}
                    onPointerDown={(event) => onBoxPointerDown(event, box, handle)}
                  />
                ))
              : null}
          </div>
        );
      })}
      {draft ? (
        <div className="pointer-events-none absolute border-2 border-primary bg-black/60" style={rectStyle(draft)} />
      ) : null}
    </div>
  );
}

function DetectionBoxes({
  detection,
  label,
  color,
  selected,
  flashing,
  passive,
  onSelect,
}: {
  detection: ReviewDetection;
  label: string;
  color: string;
  selected: boolean;
  flashing: boolean;
  passive: boolean;
  onSelect: () => void;
}) {
  const view = detectionView(detection);
  const caption = detection.maskedText ? `${label} · ${detection.maskedText}` : label;
  return (
    <>
      {detectionRects(detection).map((rect, index) => (
        <button
          key={index}
          type="button"
          data-item-id={index === 0 ? detection.id : undefined}
          aria-label={`${caption}, page ${detection.pageNumber}, ${view === "redact" ? "will be redacted" : view}`}
          className={cn(
            "group absolute rounded-[2px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary",
            view === "redact" && "bg-black",
            view === "suggested" && "border-2 border-dashed",
            view === "rejected" && "border border-dotted opacity-70",
            passive && "pointer-events-none",
            selected && "ring-2 ring-primary ring-offset-1",
            flashing && "animate-pulse ring-4 ring-amber-400",
          )}
          style={{
            ...rectStyle(rect),
            borderColor: view === "redact" ? undefined : color,
            backgroundColor: view === "suggested" ? withAlpha(color, 0.12) : undefined,
          }}
          onPointerDown={(event) => event.stopPropagation()}
          onClick={onSelect}
        >
          {index === 0 ? <BoxLabel text={caption} visible={selected} /> : null}
        </button>
      ))}
    </>
  );
}

function BoxLabel({ text, visible }: { text: string; visible: boolean }) {
  return (
    <span
      className={cn(
        "pointer-events-none absolute bottom-full left-0 z-10 mb-1 whitespace-nowrap rounded bg-popover px-1.5 py-0.5 font-mono text-[11px] leading-tight text-popover-foreground shadow",
        visible ? "block" : "hidden group-hover:block",
      )}
    >
      {text}
    </span>
  );
}
