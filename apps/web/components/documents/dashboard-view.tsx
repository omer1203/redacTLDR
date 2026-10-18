"use client";

import { useQuery } from "@tanstack/react-query";

import { DocumentTable } from "@/components/documents/document-table";
import { UploadPanel } from "@/components/documents/upload-panel";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { listDocuments } from "@/lib/api";
import { useApiToken } from "@/lib/review/token";
import { statusMeta } from "@/lib/status";

export function DashboardView() {
  const getToken = useApiToken();
  const documentsQuery = useQuery({
    queryKey: ["documents"],
    queryFn: async () => listDocuments(await getToken()),
    refetchInterval: (query) => {
      const rows = query.state.data ?? [];
      return rows.some((doc) => statusMeta(doc.status).inProgress) ? 3000 : false;
    },
  });

  const documents = documentsQuery.data ?? [];
  const ready = documents.filter((doc) => doc.status === "READY_FOR_REVIEW" || doc.status === "DETECTED").length;
  const exported = documents.filter((doc) => doc.status === "EXPORTED" || doc.status === "SUMMARIZED").length;

  return (
    <div className="flex w-full flex-col gap-8">
      <div>
        <h1 className="text-[clamp(1.75rem,2.5vw,2.75rem)] font-semibold">Documents</h1>
        <p className="mt-1 text-sm text-muted-foreground">Upload a PDF, then open it when it is ready for review.</p>
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        {[
          ["Documents", documentsQuery.isLoading ? null : documents.length],
          ["Ready for review", documentsQuery.isLoading ? null : ready],
          ["Exported", documentsQuery.isLoading ? null : exported],
        ].map(([label, value]) => (
          <Card key={String(label)}>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">{label}</CardTitle>
            </CardHeader>
            <CardContent>
              {value === null ? <Skeleton className="h-8 w-12" /> : <p className="text-2xl font-semibold">{value}</p>}
            </CardContent>
          </Card>
        ))}
      </div>
      <UploadPanel />
      {documentsQuery.isLoading ? (
        <div className="space-y-2">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
        </div>
      ) : documentsQuery.isError ? (
        <p className="text-sm text-destructive">{(documentsQuery.error as Error).message}</p>
      ) : (
        <DocumentTable documents={documents} />
      )}
    </div>
  );
}
