"use client";

import { useQueryClient } from "@tanstack/react-query";
import { Check, Copy, Loader2, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { BackLink } from "@/components/back-link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { isSummaryActive, type CitedItem, type SummaryCitation } from "@/lib/api/summaries";
import { modeMeta } from "@/lib/modes";
import { summaryKey, useLatestSummary, useQueueSummary } from "@/lib/summaries/queries";
import type { DocumentMode } from "@/lib/types";

const FIELD_LABELS: Record<string, string> = {
  experienceSummary: "Experience",
  yearsExperience: "Years of experience",
  startDate: "Start date",
  visitSummary: "Visit",
  whatToShare: "Safe to share",
  importantDates: "Important dates",
  riskyClauses: "Risky clauses",
  dataCollected: "Data collected",
  dataSharing: "Data sharing",
  autoRenewal: "Auto-renewal",
  dataUse: "Data use",
};

function labelFor(key: string): string {
  if (FIELD_LABELS[key]) return FIELD_LABELS[key];
  const spaced = key.replace(/([A-Z])/g, " $1");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

function isCited(value: unknown): value is CitedItem {
  return Boolean(value && typeof value === "object" && "text" in value);
}

function Citations({ documentId, citations }: { documentId: string; citations: SummaryCitation[] }) {
  if (!citations.length) return null;
  return (
    <span className="ml-2 inline-flex flex-wrap gap-1">
      {citations.map((citation, index) => (
        <Link
          key={`${citation.page}-${index}`}
          href={`/documents/${documentId}/review?page=${citation.page}`}
          className="rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground hover:text-foreground"
          title={citation.quoteSnippet || undefined}
        >
          p. {citation.page}
        </Link>
      ))}
    </span>
  );
}

function FieldValue({ documentId, value }: { documentId: string; value: unknown }) {
  if (value == null || value === "" || (Array.isArray(value) && value.length === 0)) {
    return <p className="text-sm text-muted-foreground">None found.</p>;
  }
  if (typeof value === "string" || typeof value === "number") {
    return <p className="text-sm">{String(value)}</p>;
  }
  if (Array.isArray(value)) {
    return (
      <ul className="space-y-2 text-sm">
        {value.map((item, index) =>
          typeof item === "string" ? (
            <li key={index}>{item}</li>
          ) : isCited(item) ? (
            <li key={index}>
              {item.text || "—"}
              <Citations documentId={documentId} citations={item.citations ?? []} />
            </li>
          ) : (
            <li key={index}>{JSON.stringify(item)}</li>
          ),
        )}
      </ul>
    );
  }
  return <p className="text-sm">{JSON.stringify(value)}</p>;
}

export function SummaryView({ documentId }: { documentId: string }) {
  const queryClient = useQueryClient();
  const summary = useLatestSummary(documentId);
  const queue = useQueueSummary(documentId);
  const [copied, setCopied] = useState(false);
  const record = summary.data;
  const running = queue.isPending || isSummaryActive(record);

  const finishedId = useRef<string | null>(null);
  useEffect(() => {
    if (record && !isSummaryActive(record) && finishedId.current !== record.id) {
      finishedId.current = record.id;
      void queryClient.invalidateQueries({ queryKey: ["document"] });
      void queryClient.invalidateQueries({ queryKey: summaryKey(documentId) });
    }
  }, [record, documentId, queryClient]);

  async function copyMarkdown() {
    if (!record?.markdown) return;
    await navigator.clipboard.writeText(record.markdown);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1500);
  }

  const body = record?.json.summary;
  const mode = record ? modeMeta(record.mode as DocumentMode) : null;
  const safe = record?.safeMode ?? record?.json.safeMode;

  return (
    <div className="flex w-full flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <BackLink href={`/documents/${documentId}`} label="Back to document" />
          <h1 className="font-display text-[clamp(1.9rem,2.6vw,2.9rem)] font-medium tracking-tight">Summary</h1>
        </div>
        <div className="flex flex-wrap gap-2">
          {record?.status === "SUMMARIZED" && record.markdown ? (
            <Button variant="outline" onClick={() => void copyMarkdown()}>
              {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
              {copied ? "Copied" : "Copy as markdown"}
            </Button>
          ) : null}
          <Button disabled={running} onClick={() => queue.mutate()}>
            {record ? "Regenerate" : "Generate summary"}
          </Button>
        </div>
      </div>

      {running ? (
        <p className="flex items-center gap-2 text-sm" aria-live="polite">
          <Loader2 className="h-4 w-4 animate-spin" />
          {record?.status === "PROCESSING" ? "Writing the summary…" : "Waiting for a worker…"}
        </p>
      ) : null}

      {summary.isError ? <p className="text-sm text-destructive">{(summary.error as Error).message}</p> : null}

      {record?.status === "FAILED" ? (
        <p className="text-sm text-destructive" aria-live="polite">
          {record.errorMessage ?? "The summary failed. Nothing was saved."}
        </p>
      ) : null}

      {record?.status === "SUMMARIZED" && body ? (
        <>
          <div className="flex flex-wrap items-center gap-2">
            {mode ? <Badge variant="secondary">{mode.label}</Badge> : null}
            {safe ? (
              <Badge className="gap-1 bg-primary/15 text-primary">
                <ShieldCheck className="h-3 w-3" /> Generated from redacted text
              </Badge>
            ) : (
              <Badge variant="outline">Generated from the full text</Badge>
            )}
            {record.json.truncated ? <Badge variant="outline">Later pages were not included</Badge> : null}
          </div>
          <div className="grid gap-3">
            {Object.entries(body)
              .filter(([key]) => key !== "confidence" && key !== "citations")
              .map(([key, value]) => (
                <Card key={key}>
                  <CardHeader>
                    <CardTitle className="text-sm font-medium text-muted-foreground">{labelFor(key)}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <FieldValue documentId={documentId} value={value} />
                  </CardContent>
                </Card>
              ))}
          </div>
          {typeof body.confidence === "number" ? (
            <p className="text-xs text-muted-foreground">Confidence {Math.round(body.confidence * 100)}%.</p>
          ) : null}
        </>
      ) : null}

      {record?.status === "SUMMARIZED" && !body && record.markdown ? (
        <pre className="whitespace-pre-wrap text-sm">{record.markdown}</pre>
      ) : null}

      {!summary.isLoading && !record && !running ? (
        <p className="text-sm text-muted-foreground">
          No summary yet. Generating one reads the document as it is now. With safe mode on, redacted values are
          replaced by tokens before the model sees the text.
        </p>
      ) : null}
    </div>
  );
}
