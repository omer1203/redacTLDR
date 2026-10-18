"use client";

import { ChevronDown, Search, Trash2 } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import type { ManualRedaction, ReviewDetection, ReviewGroup, ReviewState } from "@/lib/api/review";
import { detectionView, type DetectionView } from "@/lib/review/derive";
import {
  useDeleteManualRedaction,
  useSetDetectionAccepted,
  useSetEntityTypeAccepted,
} from "@/lib/review/queries";
import { useReviewStore } from "@/lib/review/store";
import { cn } from "@/lib/utils";

const VIEW_LABEL: Record<DetectionView, string> = {
  redact: "Redact",
  suggested: "Suggested",
  rejected: "Off",
};

function matches(detection: ReviewDetection, group: ReviewGroup, query: string): boolean {
  if (!query) {
    return true;
  }
  const haystack = `${group.label} ${detection.entityType} ${detection.maskedText ?? ""} page ${detection.pageNumber}`;
  return haystack.toLowerCase().includes(query);
}

export function ItemsPanel({ state, documentId }: { state: ReviewState; documentId: string }) {
  const search = useReviewStore((s) => s.search);
  const setSearch = useReviewStore((s) => s.setSearch);
  const selection = useReviewStore((s) => s.selection);
  const focusItem = useReviewStore((s) => s.focusItem);
  const [collapsed, setCollapsed] = useState<Set<string>>(() => new Set());
  const listRef = useRef<HTMLDivElement>(null);

  const setAccepted = useSetDetectionAccepted(documentId);
  const setTypeAccepted = useSetEntityTypeAccepted(documentId);
  const deleteBox = useDeleteManualRedaction(documentId);
  const editable = state.reviewable;

  const query = search.trim().toLowerCase();
  const sections = useMemo(
    () =>
      state.groups
        .map((group) => ({
          group,
          items: state.detections.filter(
            (item) => item.entityType === group.entityType && matches(item, group, query),
          ),
        }))
        .filter((section) => section.items.length > 0),
    [state.groups, state.detections, query],
  );
  const boxes = query
    ? state.manualRedactions.filter((box) => `${box.label} page ${box.pageNumber}`.toLowerCase().includes(query))
    : state.manualRedactions;

  // Keep the row for a box clicked on the page in view.
  useEffect(() => {
    if (selection) {
      listRef.current?.querySelector(`[data-panel-id="${selection.id}"]`)?.scrollIntoView({ block: "nearest" });
    }
  }, [selection]);

  const toggleCollapsed = (entityType: string) =>
    setCollapsed((current) => {
      const next = new Set(current);
      if (next.has(entityType)) {
        next.delete(entityType);
      } else {
        next.add(entityType);
      }
      return next;
    });

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <label className="relative block">
        <span className="sr-only">Search items</span>
        <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <input
          type="search"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search items"
          className="h-9 w-full rounded-md border bg-background pl-8 pr-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
      </label>
      <div ref={listRef} className="min-h-0 flex-1 space-y-3 overflow-y-auto pr-1">
        {sections.length === 0 && boxes.length === 0 ? (
          <p className="px-1 text-sm text-muted-foreground">
            {query ? "No items match that search." : "No sensitive items were found. Draw a box to redact anything by hand."}
          </p>
        ) : null}
        {sections.map(({ group, items }) => {
          const allOn = group.acceptedCount === group.count;
          const isCollapsed = collapsed.has(group.entityType);
          return (
            <section key={group.entityType} className="rounded-lg border">
              <header className="flex items-center gap-2 px-3 py-2">
                <button
                  type="button"
                  className="flex min-w-0 flex-1 items-center gap-2 text-left"
                  aria-expanded={!isCollapsed}
                  onClick={() => toggleCollapsed(group.entityType)}
                >
                  <ChevronDown className={cn("h-4 w-4 shrink-0 transition-transform", isCollapsed && "-rotate-90")} />
                  <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ backgroundColor: group.color }} />
                  <span className="truncate text-sm font-medium">{group.label}</span>
                  <span className="ml-auto shrink-0 text-xs tabular-nums text-muted-foreground">
                    {group.acceptedCount}/{group.count}
                  </span>
                </button>
                <Switch
                  checked={allOn}
                  disabled={!editable}
                  aria-label={`${allOn ? "Keep" : "Redact"} every ${group.label}`}
                  onCheckedChange={(checked) => setTypeAccepted.mutate({ entityType: group.entityType, accepted: checked })}
                />
              </header>
              {!isCollapsed ? (
                <ul className="border-t">
                  {items.map((item) => (
                    <DetectionRow
                      key={item.id}
                      item={item}
                      selected={selection?.kind === "detection" && selection.id === item.id}
                      editable={editable}
                      onFocus={() => focusItem({ kind: "detection", id: item.id }, item.pageNumber)}
                      onToggle={(accepted) => setAccepted.mutate({ detectionId: item.id, accepted })}
                    />
                  ))}
                </ul>
              ) : null}
            </section>
          );
        })}
        {boxes.length > 0 ? (
          <section className="rounded-lg border">
            <header className="flex items-center gap-2 px-3 py-2 text-sm font-medium">
              <span className="h-2.5 w-2.5 rounded-full bg-black dark:bg-white" />
              Your boxes
              <span className="ml-auto text-xs tabular-nums text-muted-foreground">{boxes.length}</span>
            </header>
            <ul className="border-t">
              {boxes.map((box) => (
                <BoxRow
                  key={box.id}
                  box={box}
                  selected={selection?.kind === "manual" && selection.id === box.id}
                  editable={editable}
                  onFocus={() => focusItem({ kind: "manual", id: box.id }, box.pageNumber)}
                  onDelete={() => deleteBox.mutate({ id: box.id })}
                />
              ))}
            </ul>
          </section>
        ) : null}
      </div>
    </div>
  );
}

function DetectionRow({
  item,
  selected,
  editable,
  onFocus,
  onToggle,
}: {
  item: ReviewDetection;
  selected: boolean;
  editable: boolean;
  onFocus: () => void;
  onToggle: (accepted: boolean) => void;
}) {
  const view = detectionView(item);
  return (
    <li data-panel-id={item.id} className={cn("flex items-center gap-2 px-3 py-2", selected && "bg-accent")}>
      <button type="button" className="min-w-0 flex-1 text-left" onClick={onFocus}>
        <span className="block truncate font-mono text-sm">{item.maskedText ?? "Hidden value"}</span>
        <span className="text-xs text-muted-foreground">
          Page {item.pageNumber} ·{" "}
          <span className={cn(view === "redact" && "text-foreground", view === "suggested" && "text-amber-600 dark:text-amber-400")}>
            {VIEW_LABEL[view]}
          </span>
        </span>
      </button>
      <Switch
        checked={item.accepted}
        disabled={!editable}
        aria-label={item.accepted ? "Keep this item" : "Redact this item"}
        onCheckedChange={onToggle}
      />
    </li>
  );
}

function BoxRow({
  box,
  selected,
  editable,
  onFocus,
  onDelete,
}: {
  box: ManualRedaction;
  selected: boolean;
  editable: boolean;
  onFocus: () => void;
  onDelete: () => void;
}) {
  return (
    <li data-panel-id={box.id} className={cn("flex items-center gap-2 px-3 py-2", selected && "bg-accent")}>
      <button type="button" className="min-w-0 flex-1 text-left" onClick={onFocus}>
        <span className="block text-sm">{box.label}</span>
        <span className="text-xs text-muted-foreground">Page {box.pageNumber}</span>
      </button>
      <Button variant="ghost" size="icon" aria-label="Delete box" disabled={!editable} onClick={onDelete}>
        <Trash2 className="h-4 w-4" />
      </Button>
    </li>
  );
}
