"use client";

import { BackLink } from "@/components/back-link";
import { useEffect, useRef, useState } from "react";

import { ItemsPanel } from "@/components/review/items-panel";
import { PageThumbnails } from "@/components/review/page-thumbnails";
import { PageViewer } from "@/components/review/page-viewer";
import { Document, PDF_OPTIONS } from "@/components/review/pdf";
import { ReviewTopBar } from "@/components/review/review-top-bar";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { ReviewState } from "@/lib/api/review";
import { statusMeta } from "@/lib/status";
import { useOriginalUrl, useReviewState } from "@/lib/review/queries";
import { useReviewStore, type ReviewTab } from "@/lib/review/store";
import { useElementWidth } from "@/lib/review/use-element-width";
import { useReviewShortcuts } from "@/lib/review/use-review-shortcuts";

// Below this content width the three panels become tabs (tablet and narrow windows).
const THREE_PANEL_MIN_WIDTH = 900;
const THUMB_COLUMN = 132;

/**
 * Review screen body. Loaded with `ssr: false` because pdf.js needs the browser.
 * Owns data loading and layout; the panels read editor state from the store.
 */
export default function ReviewWorkspace({ documentId }: { documentId: string }) {
  const stateQuery = useReviewState(documentId);
  const state = stateQuery.data;
  useReviewShortcuts(state, documentId);

  if (stateQuery.isLoading) {
    return <ReviewSkeleton />;
  }
  if (stateQuery.isError || !state) {
    return <Notice documentId={documentId} text={(stateQuery.error as Error | null)?.message ?? "Could not load the review."} />;
  }
  if (!state.reviewable) {
    const text =
      state.status === "FAILED"
        ? "This document could not be processed, so there is nothing to review."
        : `${statusMeta(state.status).label}. The review opens when detection finishes.`;
    return <Notice documentId={documentId} text={text} />;
  }
  return <ReviewBody state={state} documentId={documentId} />;
}

function ReviewBody({ state, documentId }: { state: ReviewState; documentId: string }) {
  const urlQuery = useOriginalUrl(documentId, true);
  const setPageCount = useReviewStore((s) => s.setPageCount);
  const goToPage = useReviewStore((s) => s.goToPage);
  const openedAtPage = useRef(false);
  const [loadFailed, setLoadFailed] = useState(false);
  const retried = useRef(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const width = useElementWidth(rootRef);

  useEffect(() => {
    setPageCount(Math.max(state.pageCount ?? 0, state.pages.length, 1));
    // Citation links open /review?page=N. Apply it once; later page changes are the reviewer's.
    if (openedAtPage.current) return;
    openedAtPage.current = true;
    const raw = new URLSearchParams(window.location.search).get("page");
    const page = Number(raw);
    if (raw && Number.isFinite(page)) goToPage(page);
  }, [state.pageCount, state.pages.length, setPageCount, goToPage]);

  const onLoadError = () => {
    // The presigned URL may have expired; fetch a new one once before giving up.
    if (!retried.current) {
      retried.current = true;
      void urlQuery.refetch();
      return;
    }
    setLoadFailed(true);
  };

  const retry = () => {
    retried.current = false;
    setLoadFailed(false);
    void urlQuery.refetch();
  };

  return (
    <div className="flex h-[calc(100dvh-8rem)] min-h-[600px] flex-col gap-4">
      <ReviewTopBar state={state} documentId={documentId} />
      <div ref={rootRef} className="min-h-0 flex-1">
        {urlQuery.isError || loadFailed ? (
          <Card>
            <CardContent className="flex flex-wrap items-center justify-between gap-3 py-6 text-sm">
              <span className="text-destructive">The PDF could not be loaded from storage.</span>
              <Button variant="outline" onClick={retry}>
                Try again
              </Button>
            </CardContent>
          </Card>
        ) : !urlQuery.data || width === 0 ? (
          <Skeleton className="h-full w-full" />
        ) : (
          <Document
            file={urlQuery.data}
            options={PDF_OPTIONS}
            className="h-full min-h-0"
            loading={<Skeleton className="h-full w-full" />}
            error={null}
            // The PDF is the source of truth for how many pages can be drawn.
            onLoadSuccess={(pdf) => {
              retried.current = false;
              setPageCount(pdf.numPages);
            }}
            onLoadError={onLoadError}
          >
            {width >= THREE_PANEL_MIN_WIDTH ? (
              <div
                className="grid h-full min-h-0 gap-4"
                style={{ gridTemplateColumns: `${THUMB_COLUMN}px minmax(0, 1fr) minmax(280px, 28%)` }}
              >
                <PageThumbnails state={state} />
                <PageViewer state={state} documentId={documentId} />
                <ItemsPanel state={state} documentId={documentId} />
              </div>
            ) : (
              <TabbedLayout state={state} documentId={documentId} />
            )}
          </Document>
        )}
      </div>
    </div>
  );
}

function TabbedLayout({ state, documentId }: { state: ReviewState; documentId: string }) {
  const tab = useReviewStore((s) => s.tab);
  const setTab = useReviewStore((s) => s.setTab);
  return (
    <Tabs value={tab} onValueChange={(value) => setTab(value as ReviewTab)} className="flex h-full min-h-0 flex-col">
      <TabsList className="self-start">
        <TabsTrigger value="pages">Pages</TabsTrigger>
        <TabsTrigger value="viewer">Viewer</TabsTrigger>
        <TabsTrigger value="items">Items</TabsTrigger>
      </TabsList>
      <TabsContent value="pages" className="min-h-0 flex-1">
        <PageThumbnails state={state} />
      </TabsContent>
      <TabsContent value="viewer" className="min-h-0 flex-1">
        <PageViewer state={state} documentId={documentId} />
      </TabsContent>
      <TabsContent value="items" className="min-h-0 flex-1">
        <ItemsPanel state={state} documentId={documentId} />
      </TabsContent>
    </Tabs>
  );
}

export function ReviewSkeleton() {
  return (
    <div className="flex h-[calc(100dvh-8rem)] min-h-[600px] flex-col gap-4">
      <Skeleton className="h-14 w-full" />
      <Skeleton className="min-h-0 flex-1" />
    </div>
  );
}

function Notice({ documentId, text }: { documentId: string; text: string }) {
  return (
    <Card className="mx-auto max-w-xl">
      <CardContent className="flex flex-col items-start gap-4 py-8 text-sm">
        <p>{text}</p>
        <BackLink href={`/documents/${documentId}`} label="Back to document" />
      </CardContent>
    </Card>
  );
}
