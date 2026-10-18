"use client";

import { Download } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useDownloadExport, useExports } from "@/lib/exports/queries";
import { formatBytes, formatUtc } from "@/lib/format";
import { EXPORT_STATUS_META } from "@/lib/status";
import { cn } from "@/lib/utils";

export function ExportHistory({ documentId }: { documentId: string }) {
  const exports = useExports(documentId);
  const download = useDownloadExport(documentId);

  if (exports.isLoading) {
    return <Skeleton className="h-24 w-full" />;
  }
  if (exports.isError) {
    return <p className="text-sm text-destructive">{(exports.error as Error).message}</p>;
  }
  if (!exports.data?.length) {
    return <p className="text-sm text-muted-foreground">No exports yet.</p>;
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Created</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>Removed</TableHead>
          <TableHead>Labels</TableHead>
          <TableHead>Size</TableHead>
          <TableHead className="text-right">File</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {exports.data.map((item) => {
          const meta = EXPORT_STATUS_META[item.status] ?? EXPORT_STATUS_META.FAILED;
          const Icon = meta.icon;
          return (
            <TableRow key={item.id}>
              <TableCell className="whitespace-nowrap">{formatUtc(item.createdAt)}</TableCell>
              <TableCell>
                <Badge className={cn("gap-1", meta.badgeClass)} title={meta.description}>
                  <Icon className={cn("h-3 w-3", item.status === "PROCESSING" && "animate-spin")} /> {meta.label}
                </Badge>
                {item.status === "FAILED" && item.errorMessage ? (
                  <p className="mt-1 max-w-sm text-xs text-destructive">{item.errorMessage}</p>
                ) : null}
              </TableCell>
              <TableCell>{item.redactionCount ?? "—"}</TableCell>
              <TableCell>{item.includeLabels ? "On" : "Off"}</TableCell>
              <TableCell>{formatBytes(item.sizeBytes)}</TableCell>
              <TableCell className="text-right">
                {item.status === "EXPORTED" ? (
                  <Button size="sm" variant="outline" disabled={download.isPending} onClick={() => download.mutate(item.id)}>
                    <Download className="h-4 w-4" /> Download
                  </Button>
                ) : null}
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}
