"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { BackLink } from "@/components/back-link";
import { StatusBadge } from "@/components/documents/status-badge";
import { ExportDialog } from "@/components/exports/export-dialog";
import { ExportHistory } from "@/components/exports/export-history";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { getDocument, listDetections, listJobs } from "@/lib/api";
import { modeMeta } from "@/lib/modes";
import { useApiToken } from "@/lib/review/token";
import { statusMeta, timelineState, type TimelineStep } from "@/lib/status";
import type { DocumentStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

// Mirrors `_PROCESS_ALREADY_DONE` in services/api/app/routes/documents.py; the API rejects export otherwise.
const EXPORTABLE: ReadonlySet<DocumentStatus> = new Set<DocumentStatus>([
  "READY_FOR_REVIEW",
  "DETECTED",
  "EXPORT_QUEUED",
  "EXPORTED",
  "SUMMARY_QUEUED",
  "SUMMARIZED",
]);

const STEPS: { id: TimelineStep; label: string }[] = [
  { id: "uploaded", label: "Uploaded" },
  { id: "reading", label: "Reading document (OCR)" },
  { id: "detecting", label: "Detecting" },
  { id: "ready", label: "Ready" },
];

export function DocumentOverview({ documentId }: { documentId: string }) {
  const getToken = useApiToken();
  const documentQuery = useQuery({
    queryKey: ["document", documentId],
    queryFn: async () => getDocument(await getToken(), documentId),
    refetchInterval: (query) => (query.state.data && statusMeta(query.state.data.status).inProgress ? 3000 : false),
  });
  const inProgress = documentQuery.data ? statusMeta(documentQuery.data.status).inProgress : false;
  const jobsQuery = useQuery({
    queryKey: ["jobs", documentId],
    queryFn: async () => listJobs(await getToken(), documentId),
    enabled: documentQuery.isSuccess,
    refetchInterval: inProgress ? 3000 : false,
  });
  const detectionsQuery = useQuery({
    queryKey: ["detections", documentId],
    queryFn: async () => listDetections(await getToken(), documentId),
    // Wait until processing finishes. Fetching during OCR returns an empty
    // list that then sits in the cache after the document becomes ready.
    enabled: documentQuery.isSuccess && !inProgress,
  });

  if (documentQuery.isLoading) {
    return (
      <div className="flex flex-col gap-4">
        <BackLink href="/dashboard">Documents</BackLink>
        <p className="text-sm text-muted-foreground">Loading document…</p>
      </div>
    );
  }
  if (documentQuery.isError || !documentQuery.data) {
    return (
      <div className="flex flex-col gap-4">
        <BackLink href="/dashboard">Documents</BackLink>
        <p className="text-sm text-destructive">{(documentQuery.error as Error).message}</p>
      </div>
    );
  }

  const document = documentQuery.data;
  const mode = modeMeta(document.mode);
  const timeline = timelineState(document.status, document.processingStage);
  const entityCount = detectionsQuery.data?.length;

  return (
    <div className="flex w-full flex-col gap-8">
      <BackLink href="/dashboard">Documents</BackLink>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm text-muted-foreground">{mode.label}</p>
          <h1 className="font-display text-[clamp(1.9rem,2.6vw,2.9rem)] font-medium tracking-tight">{document.filename}</h1>
        </div>
        <StatusBadge status={document.status} stage={document.processingStage} />
      </div>
      <ol className="grid gap-3 sm:grid-cols-4">
        {STEPS.map((step) => {
          const state = timeline[step.id];
          return (
            <li
              key={step.id}
              className={cn(
                "rounded-lg border px-3 py-3 text-sm",
                state === "current" && "border-primary bg-accent",
                state === "failed" && "border-destructive text-destructive",
                state === "upcoming" && "text-muted-foreground",
              )}
            >
              <span className="font-medium">{step.label}</span>
              <p className="mt-1 text-xs capitalize text-muted-foreground">{state}</p>
            </li>
          );
        })}
      </ol>
      <div className="grid gap-3 sm:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium text-muted-foreground">Pages</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-semibold">{document.pageCount ?? "—"}</p>
            <p className="mt-1 text-xs text-muted-foreground">
              {document.pageCount == null ? "Page count appears after the document is read." : "Pages read from the PDF."}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium text-muted-foreground">Sensitive items</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-semibold">{entityCount ?? "—"}</p>
          </CardContent>
        </Card>
      </div>
      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="jobs">Jobs</TabsTrigger>
        </TabsList>
        <TabsContent value="overview" className="text-sm text-muted-foreground">
          {document.status === "FAILED" && document.errorMessage
            ? document.errorMessage
            : statusMeta(document.status).description}
        </TabsContent>
        <TabsContent value="jobs">
          <ul className="space-y-2 text-sm">
            {(jobsQuery.data ?? []).map((job) => (
              <li key={`${job.jobType}-${job.startedAt ?? job.status}`} className="rounded-md border px-3 py-2">
                <span className="font-medium">{job.jobType}</span>
                <span className="text-muted-foreground"> · {job.status}</span>
                {job.lastError ? <p className="text-destructive">{job.lastError}</p> : null}
              </li>
            ))}
            {jobsQuery.isSuccess && (jobsQuery.data?.length ?? 0) === 0 ? (
              <li className="text-muted-foreground">No jobs yet.</li>
            ) : null}
          </ul>
        </TabsContent>
      </Tabs>
      <div className="flex flex-wrap gap-2">
        <Button asChild>
          <Link href={`/documents/${document.id}/review`}>Review</Link>
        </Button>
        <ExportDialog
          documentId={document.id}
          disabled={!EXPORTABLE.has(document.status)}
          triggerLabel="Export"
          triggerVariant="outline"
        />
        {EXPORTABLE.has(document.status) ? (
          <Button variant="outline" asChild>
            <Link href={`/documents/${document.id}/summary`}>Summary</Link>
          </Button>
        ) : (
          <Button variant="outline" disabled>
            Summary
          </Button>
        )}
      </div>
      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-semibold">Exports</h2>
        <ExportHistory documentId={document.id} />
      </section>
    </div>
  );
}
