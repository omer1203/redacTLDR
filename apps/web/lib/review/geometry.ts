import type { CSSProperties } from "react";

import type { NormalizedRect } from "@/lib/api/review";

/**
 * Page geometry for the review overlay.
 *
 * Every box is stored as fractions of the rendered page (0–1, origin top-left),
 * the same space Textract and the detection engine use. Positioning boxes with
 * percentages of the page element keeps them aligned at every zoom level
 * without recomputing anything when the page is resized.
 */

/** Smallest side the API accepts (`MIN_RECT_SIDE` in services/api/app/schemas.py). */
export const MIN_SERVER_SIDE = 0.002;
/** Drags smaller than this are treated as clicks, not boxes. */
export const MIN_DRAW_SIDE = 0.005;
/** CSS pixels per PDF point at 100% zoom (96 dpi screen, 72 pt per inch). */
export const CSS_PX_PER_PT = 96 / 72;

export interface Point {
  x: number;
  y: number;
}

export type ResizeHandle = "nw" | "ne" | "sw" | "se";

export const RESIZE_HANDLES: ResizeHandle[] = ["nw", "ne", "sw", "se"];

export function clamp01(value: number): number {
  if (Number.isNaN(value)) {
    return 0;
  }
  return Math.min(1, Math.max(0, value));
}

/** Pointer position as a page fraction, clamped to the page. */
export function pointInBox(clientX: number, clientY: number, box: DOMRect): Point {
  if (box.width <= 0 || box.height <= 0) {
    return { x: 0, y: 0 };
  }
  return {
    x: clamp01((clientX - box.left) / box.width),
    y: clamp01((clientY - box.top) / box.height),
  };
}

/** Rectangle spanned by two corners, in any drag direction. */
export function rectFromPoints(a: Point, b: Point): NormalizedRect {
  const x = Math.min(a.x, b.x);
  const y = Math.min(a.y, b.y);
  return { x, y, width: Math.abs(a.x - b.x), height: Math.abs(a.y - b.y) };
}

export function isDrawable(rect: NormalizedRect): boolean {
  return rect.width >= MIN_DRAW_SIDE && rect.height >= MIN_DRAW_SIDE;
}

/** Shift a box by a page-fraction delta without letting any edge leave the page. */
export function moveRect(rect: NormalizedRect, dx: number, dy: number): NormalizedRect {
  return {
    ...rect,
    x: Math.min(Math.max(0, rect.x + dx), 1 - rect.width),
    y: Math.min(Math.max(0, rect.y + dy), 1 - rect.height),
  };
}

function oppositeCorner(rect: NormalizedRect, handle: ResizeHandle): Point {
  const right = rect.x + rect.width;
  const bottom = rect.y + rect.height;
  switch (handle) {
    case "nw":
      return { x: right, y: bottom };
    case "ne":
      return { x: rect.x, y: bottom };
    case "sw":
      return { x: right, y: rect.y };
    case "se":
      return { x: rect.x, y: rect.y };
  }
}

/** Resize by dragging one corner; the opposite corner stays fixed and the box keeps a usable size. */
export function resizeRect(rect: NormalizedRect, handle: ResizeHandle, point: Point): NormalizedRect {
  const anchor = oppositeCorner(rect, handle);
  const next = rectFromPoints(anchor, { x: clamp01(point.x), y: clamp01(point.y) });
  const width = Math.max(next.width, MIN_DRAW_SIDE);
  const height = Math.max(next.height, MIN_DRAW_SIDE);
  return {
    x: Math.min(next.x, 1 - width),
    y: Math.min(next.y, 1 - height),
    width,
    height,
  };
}

const PRECISION = 1e6;

/**
 * Six decimals, matching what the API stores. x and y round down and the size is
 * capped so rounding can never push an edge past the page.
 */
export function roundRect(rect: NormalizedRect): NormalizedRect {
  const x = Math.floor(clamp01(rect.x) * PRECISION) / PRECISION;
  const y = Math.floor(clamp01(rect.y) * PRECISION) / PRECISION;
  const width = Math.min(Math.round(rect.width * PRECISION) / PRECISION, 1 - x);
  const height = Math.min(Math.round(rect.height * PRECISION) / PRECISION, 1 - y);
  return { x, y, width, height };
}

export function sameRect(a: NormalizedRect, b: NormalizedRect): boolean {
  const close = (p: number, q: number) => Math.abs(p - q) < 1 / PRECISION;
  return close(a.x, b.x) && close(a.y, b.y) && close(a.width, b.width) && close(a.height, b.height);
}

export function rectStyle(rect: NormalizedRect): CSSProperties {
  return {
    left: `${rect.x * 100}%`,
    top: `${rect.y * 100}%`,
    width: `${rect.width * 100}%`,
    height: `${rect.height * 100}%`,
  };
}

/** Rendered page width in CSS px for a zoom setting. "fit" fills the available width. */
export function pageWidthFor(zoom: "fit" | number, pageWidthPt: number, availableWidth: number): number {
  if (zoom === "fit") {
    return Math.max(200, Math.floor(availableWidth));
  }
  return Math.round(pageWidthPt * CSS_PX_PER_PT * zoom);
}
