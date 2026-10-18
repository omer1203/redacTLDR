"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { listAuditEvents } from "@/lib/api";
import { formatUtc } from "@/lib/format";
import { useApiToken } from "@/lib/review/token";

const FILTERS: { id: string; label: string }[] = [
  { id: "", label: "All" },
  { id: "document.created", label: "Created" },
  { id: "document.upload.completed", label: "Uploaded" },
  { id: "document.export.completed", label: "Exported" },
  { id: "document.summary.completed", label: "Summary" },
  { id: "document.deleted", label: "Deleted" },
];

export function ActivityView() {
  const getToken = useApiToken();
  const [eventType, setEventType] = useState("");
  const query = useQuery({
    queryKey: ["audit", eventType],
    queryFn: async () => listAuditEvents(await getToken(), eventType || undefined),
    placeholderData: keepPreviousData,
    staleTime: 60_000,
  });

  return (
    <div className="flex w-full flex-col gap-6">
      <div>
        <h1 className="font-display text-[clamp(1.9rem,2.6vw,2.9rem)] font-medium tracking-tight">Activity</h1>
        <p className="mt-1 text-sm text-muted-foreground">Uploads, exports, summaries, and deletes for your account.</p>
      </div>
      <div className="flex flex-wrap gap-2">
        {FILTERS.map((filter) => (
          <Button
            key={filter.id || "all"}
            size="sm"
            variant={eventType === filter.id ? "default" : "outline"}
            onClick={() => setEventType(filter.id)}
          >
            {filter.label}
          </Button>
        ))}
      </div>
      {query.isLoading ? (
        <div className="space-y-2">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
        </div>
      ) : null}
      {query.isError ? <p className="text-sm text-destructive">{(query.error as Error).message}</p> : null}
      {query.data?.length === 0 ? <p className="text-sm text-muted-foreground">No activity for this filter.</p> : null}
      {query.data && query.data.length > 0 ? (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Event</TableHead>
              <TableHead>When</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {query.data.map((event) => (
              <TableRow key={event.id}>
                <TableCell className="font-medium">{event.eventType}</TableCell>
                <TableCell className="text-muted-foreground">{formatUtc(event.createdAt)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      ) : null}
    </div>
  );
}
