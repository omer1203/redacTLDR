"use client";

import { useQueryClient } from "@tanstack/react-query";
import { AlertCircle, Download, Loader2, ShieldCheck } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Button, type ButtonProps } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Switch } from "@/components/ui/switch";
import { isExportActive } from "@/lib/api";
import { exportsKey, useDownloadExport, useExport, useQueueExport } from "@/lib/exports/queries";
import { formatBytes } from "@/lib/format";

interface ExportDialogProps {
  documentId: string;
  disabled?: boolean;
  /** Shown in the description when the caller knows it (the review screen does). */
  redactionCount?: number;
  triggerLabel?: string;
  triggerVariant?: ButtonProps["variant"];
}

export function ExportDialog({
  documentId,
  disabled = false,
  redactionCount,
  triggerLabel = "Export redacted PDF",
  triggerVariant = "default",
}: ExportDialogProps) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [includeLabels, setIncludeLabels] = useState(false);
  const [exportId, setExportId] = useState<string | null>(null);
  const queue = useQueueExport(documentId, setExportId);
  const current = useExport(documentId, exportId);
  const download = useDownloadExport(documentId);

  const record = current.data;
  const running = queue.isPending || isExportActive(record);

  // Refresh the history and the document badge once, when this export finishes.
  const finishedId = useRef<string | null>(null);
  useEffect(() => {
    if (record && !isExportActive(record) && finishedId.current !== record.id) {
      finishedId.current = record.id;
      void queryClient.invalidateQueries({ queryKey: exportsKey(documentId) });
      void queryClient.invalidateQueries({ queryKey: ["document"] });
    }
  }, [record, documentId, queryClient]);

  function onOpenChange(next: boolean) {
    setOpen(next);
    // A finished result is cleared on close; a running export is still shown when reopened.
    if (!next && !running) {
      setExportId(null);
    }
  }

  const description =
    redactionCount === undefined
      ? "Everything selected in review is removed from the file."
      : `${redactionCount} ${redactionCount === 1 ? "item is" : "items are"} removed from the file.`;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogTrigger asChild>
        <Button variant={triggerVariant} disabled={disabled}>
          {triggerLabel}
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Export redacted PDF</DialogTitle>
          <DialogDescription>
            {description} Text under each box is deleted, not covered, and the file&apos;s metadata, links, and
            attachments are cleared. The result is checked before you can download it.
          </DialogDescription>
        </DialogHeader>

        <label className="flex items-center justify-between gap-4 rounded-md border px-3 py-2 text-sm">
          <span>
            <span className="font-medium">Show the item type on each box</span>
            <span className="block text-xs text-muted-foreground">For example &quot;Email&quot;. Never the value itself.</span>
          </span>
          <Switch checked={includeLabels} onCheckedChange={setIncludeLabels} disabled={running} />
        </label>

        {running ? (
          <p className="flex items-center gap-2 text-sm" aria-live="polite">
            <Loader2 className="h-4 w-4 animate-spin" />
            {record?.status === "PROCESSING" ? "Removing content and checking the result…" : "Waiting for a worker…"}
          </p>
        ) : null}

        {record?.status === "EXPORTED" ? (
          <div className="flex items-start gap-2 rounded-md bg-primary/10 px-3 py-2 text-sm" aria-live="polite">
            <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
            <span>
              Ready and verified. {record.redactionCount ?? 0} {record.redactionCount === 1 ? "area" : "areas"} removed
              across {record.pageCount ?? "—"} {record.pageCount === 1 ? "page" : "pages"}, {formatBytes(record.sizeBytes)}.
            </span>
          </div>
        ) : null}

        {record?.status === "FAILED" ? (
          <div className="flex items-start gap-2 rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive" aria-live="polite">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{record.errorMessage ?? "The export failed. No file was saved."}</span>
          </div>
        ) : null}

        <div className="flex flex-wrap justify-end gap-2">
          {record?.status === "EXPORTED" ? (
            <Button disabled={download.isPending} onClick={() => download.mutate(record.id)}>
              <Download className="h-4 w-4" /> Download
            </Button>
          ) : null}
          <Button
            variant={record?.status === "EXPORTED" ? "outline" : "default"}
            disabled={running}
            onClick={() => queue.mutate({ includeLabels })}
          >
            {record && !running ? "Export again" : "Export"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
