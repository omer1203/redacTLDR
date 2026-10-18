"use client";

import { createContext, useContext, useState, type ReactNode } from "react";
import { createStore, useStore, type StoreApi } from "zustand";

/**
 * Local editor state for one review screen: what is selected, which tool is
 * active, zoom, and the current page. Server data (detections, boxes) lives in
 * TanStack Query, not here.
 */

export type Zoom = "fit" | 1 | 1.5;
export type Tool = "select" | "draw";
export type ReviewTab = "pages" | "viewer" | "items";

export interface Selection {
  kind: "detection" | "manual";
  id: string;
}

export const ZOOM_OPTIONS: { value: Zoom; label: string }[] = [
  { value: "fit", label: "Fit width" },
  { value: 1, label: "100%" },
  { value: 1.5, label: "150%" },
];

interface ReviewEditorState {
  pageCount: number;
  page: number;
  zoom: Zoom;
  tool: Tool;
  selection: Selection | null;
  showRejected: boolean;
  search: string;
  // New object on every "jump to item" so the same item can flash twice in a row.
  // `at` lets an overlay that mounts later (page still loading) tell a fresh jump from an old one.
  flash: { id: string; at: number } | null;
  tab: ReviewTab;

  setPageCount: (count: number) => void;
  goToPage: (page: number) => void;
  nextPage: () => void;
  previousPage: () => void;
  setZoom: (zoom: Zoom) => void;
  setTool: (tool: Tool) => void;
  select: (selection: Selection | null) => void;
  focusItem: (selection: Selection, page: number) => void;
  setShowRejected: (show: boolean) => void;
  setSearch: (search: string) => void;
  setTab: (tab: ReviewTab) => void;
}

function clampPage(page: number, pageCount: number): number {
  return Math.min(Math.max(1, Math.round(page)), Math.max(1, pageCount));
}

function createReviewStore(): StoreApi<ReviewEditorState> {
  return createStore<ReviewEditorState>()((set, get) => ({
    pageCount: 1,
    page: 1,
    zoom: "fit",
    tool: "select",
    selection: null,
    showRejected: false,
    search: "",
    flash: null,
    tab: "viewer",

    setPageCount: (count) => set((state) => ({ pageCount: count, page: clampPage(state.page, count) })),
    goToPage: (page) => set((state) => ({ page: clampPage(page, state.pageCount) })),
    nextPage: () => get().goToPage(get().page + 1),
    previousPage: () => get().goToPage(get().page - 1),
    setZoom: (zoom) => set({ zoom }),
    setTool: (tool) => set({ tool, selection: tool === "draw" ? null : get().selection }),
    select: (selection) => set({ selection }),
    focusItem: (selection, page) =>
      set((state) => ({
        selection,
        page: clampPage(page, state.pageCount),
        flash: { id: selection.id, at: Date.now() },
        tool: "select",
        tab: "viewer",
      })),
    setShowRejected: (showRejected) => set({ showRejected }),
    setSearch: (search) => set({ search }),
    setTab: (tab) => set({ tab }),
  }));
}

const ReviewStoreContext = createContext<StoreApi<ReviewEditorState> | null>(null);

export function ReviewStoreProvider({ children }: { children: ReactNode }) {
  const [store] = useState(createReviewStore);
  return <ReviewStoreContext.Provider value={store}>{children}</ReviewStoreContext.Provider>;
}

export function useReviewStore<T>(selector: (state: ReviewEditorState) => T): T {
  const store = useContext(ReviewStoreContext);
  if (!store) {
    throw new Error("useReviewStore must be used inside ReviewStoreProvider");
  }
  return useStore(store, selector);
}
