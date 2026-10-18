"use client";

import { ArrowLeft, Check, Loader2 } from "lucide-react";
import Link from "next/link";

import { ExportDialog } from "@/components/exports/export-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { ReviewState } from "@/lib/api/review";
import { modeMeta } from "@/lib/modes";
import { redactionTotal } from "@/lib/review/derive";
import { useSavingCount } from "@/lib/review/queries";

export function ReviewTopBar({ state, documentId }: { state: ReviewState; documentId: string }) {
  const saving = useSavingCount(documentId);
  const total = redactionTotal(state);

  // Export reads the saved review from the database, so it waits for pending saves.
  const actionsDisabled = !state.reviewable || saving > 0;

  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
      <Button variant="ghost" size="sm" className="px-2" asChild>
        <Link href={`/documents/${documentId}`}>
          <ArrowLeft className="h-4 w-4" />
          Document
        </Link>
      </Button>
      <div className="min-w-0 flex-1">
        <h1 className="truncate text-xl font-semibold" title={state.filename}>
          {state.filename}
        </h1>
        <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
          <Badge variant="secondary">{modeMeta(state.mode).label}</Badge>
          {state.safeMode ? <Badge variant="outline">Safe mode</Badge> : null}
          <span>
            <span className="font-medium text-foreground">{total}</span> {total === 1 ? "item" : "items"} will be redacted
          </span>
          <span className="flex items-center gap-1" aria-live="polite">
            {saving > 0 ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin" /> Saving…
              </>
            ) : (
              <>
                <Check className="h-3.5 w-3.5" /> All changes saved
              </>
            )}
          </span>
        </div>
      </div>
      <div className="flex flex-wrap gap-2">
        {actionsDisabled ? (
          <Button variant="outline" disabled>
            Summary
          </Button>
        ) : (
          <Button variant="outline" asChild>
            <Link href={`/documents/${documentId}/summary`}>Summary</Link>
          </Button>
        )}
        <ExportDialog documentId={documentId} disabled={actionsDisabled} redactionCount={total} />
      </div>
    </div>
  );
}
