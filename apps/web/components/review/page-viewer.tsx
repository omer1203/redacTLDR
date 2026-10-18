"use client";

import { ChevronLeft, ChevronRight, MousePointer2, SquareDashedMousePointer } from "lucide-react";
import { useRef } from "react";

import { Page } from "@/components/review/pdf";
import { PageOverlay } from "@/components/review/page-overlay";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { ReviewState } from "@/lib/api/review";
import { pageWidthFor } from "@/lib/review/geometry";
import { ZOOM_OPTIONS, useReviewStore, type Zoom } from "@/lib/review/store";
import { useElementWidth } from "@/lib/review/use-element-width";
import { cn } from "@/lib/utils";

// US Letter, used only until page sizes are known (documents from before R2).
const DEFAULT_PAGE = { width: 612, height: 792 };
// Matches the scroll container's p-4 on both sides.
const VIEWPORT_PADDING = 32;

export function PageViewer({ state, documentId }: { state: ReviewState; documentId: string }) {
  const page = useReviewStore((s) => s.page);
  const pageCount = useReviewStore((s) => s.pageCount);
  const zoom = useReviewStore((s) => s.zoom);
  const tool = useReviewStore((s) => s.tool);
  const showRejected = useReviewStore((s) => s.showRejected);
  const setZoom = useReviewStore((s) => s.setZoom);
  const setTool = useReviewStore((s) => s.setTool);
  const setShowRejected = useReviewStore((s) => s.setShowRejected);
  const nextPage = useReviewStore((s) => s.nextPage);
  const previousPage = useReviewStore((s) => s.previousPage);

  const scrollRef = useRef<HTMLDivElement>(null);
  const available = useElementWidth(scrollRef);
  const size = state.pages.find((item) => item.pageNumber === page) ?? DEFAULT_PAGE;
  const width = pageWidthFor(zoom, size.width || DEFAULT_PAGE.width, available - VIEWPORT_PADDING);
  const placeholderHeight = Math.round((width * (size.height || DEFAULT_PAGE.height)) / (size.width || DEFAULT_PAGE.width));

  return (
    <div className="flex h-full min-h-0 flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex items-center gap-1">
          <Button variant="outline" size="icon" aria-label="Previous page" disabled={page <= 1} onClick={previousPage}>
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <span className="min-w-[6.5rem] text-center text-sm tabular-nums">
            Page {page} of {pageCount}
          </span>
          <Button variant="outline" size="icon" aria-label="Next page" disabled={page >= pageCount} onClick={nextPage}>
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
        <Select value={String(zoom)} onValueChange={(value) => setZoom(value === "fit" ? "fit" : (Number(value) as Zoom))}>
          <SelectTrigger className="h-9 w-[8.5rem]" aria-label="Zoom">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {ZOOM_OPTIONS.map((option) => (
              <SelectItem key={String(option.value)} value={String(option.value)}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <div className="flex items-center rounded-md border p-0.5">
          <ToolButton active={tool === "select"} label="Select (Esc)" onClick={() => setTool("select")}>
            <MousePointer2 className="h-4 w-4" />
          </ToolButton>
          <ToolButton
            active={tool === "draw"}
            label={state.reviewable ? "Draw a box (D)" : "Drawing opens when the document is ready"}
            disabled={!state.reviewable}
            onClick={() => setTool(tool === "draw" ? "select" : "draw")}
          >
            <SquareDashedMousePointer className="h-4 w-4" />
          </ToolButton>
        </div>
        <label className="ml-auto flex items-center gap-2 text-sm text-muted-foreground">
          <Switch checked={showRejected} onCheckedChange={setShowRejected} aria-label="Show rejected items" />
          Show rejected
        </label>
      </div>
      <div ref={scrollRef} className="min-h-0 flex-1 overflow-auto rounded-lg border bg-muted/40 p-4">
        {available > 0 ? (
          <div className="mx-auto w-fit shadow-md">
            <Page
              pageNumber={page}
              width={width}
              renderTextLayer={false}
              renderAnnotationLayer={false}
              loading={<div className="animate-pulse bg-white" style={{ width, height: placeholderHeight }} />}
              error={<PageMessage width={width} height={placeholderHeight} text="This page could not be drawn." />}
            >
              <PageOverlay state={state} documentId={documentId} pageNumber={page} />
            </Page>
          </div>
        ) : null}
      </div>
    </div>
  );
}

function ToolButton({
  active,
  label,
  disabled,
  onClick,
  children,
}: {
  active: boolean;
  label: string;
  disabled?: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          aria-label={label}
          aria-pressed={active}
          disabled={disabled}
          className={cn("h-8 w-8", active && "bg-accent text-accent-foreground")}
          onClick={onClick}
        >
          {children}
        </Button>
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  );
}

function PageMessage({ width, height, text }: { width: number; height: number; text: string }) {
  return (
    <div className="flex items-center justify-center bg-white text-sm text-slate-500" style={{ width, height }}>
      {text}
    </div>
  );
}
