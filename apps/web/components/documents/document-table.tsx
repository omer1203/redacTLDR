"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { MoreHorizontal, Shield } from "lucide-react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { StatusBadge } from "@/components/documents/status-badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { deleteDocument, reprocessDocument } from "@/lib/api";
import { formatUtc } from "@/lib/format";
import { modeMeta } from "@/lib/modes";
import { useApiToken } from "@/lib/review/token";
import type { DocumentRecord } from "@/lib/types";

function RowActions({ doc }: { doc: DocumentRecord }) {
  const getToken = useApiToken();
  const queryClient = useQueryClient();
  const retry = useMutation({
    mutationFn: async () => reprocessDocument(await getToken(), doc.id),
    onSuccess: async () => {
      toast.success("Processing queued again");
      await queryClient.invalidateQueries({ queryKey: ["documents"] });
    },
    onError: (error: Error) => toast.error(error.message),
  });
  const remove = useMutation({
    mutationFn: async () => deleteDocument(await getToken(), doc.id),
    onSuccess: async () => {
      toast.success("Document deleted");
      await queryClient.invalidateQueries({ queryKey: ["documents"] });
    },
    onError: (error: Error) => toast.error(error.message),
  });

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" aria-label={`Actions for ${doc.filename}`}>
          <MoreHorizontal className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem disabled={retry.isPending} onSelect={() => retry.mutate()}>
          Retry
        </DropdownMenuItem>
        <DropdownMenuItem disabled={remove.isPending} onSelect={() => remove.mutate()}>
          Delete
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export function DocumentTable({ documents }: { documents: DocumentRecord[] }) {
  const router = useRouter();
  const open = (id: string) => router.push(`/documents/${id}`);

  if (documents.length === 0) {
    return (
      <Card className="flex flex-col items-center px-6 py-16 text-center">
        <Shield className="mb-3 h-10 w-10 text-primary" />
        <p className="text-base font-medium">No documents yet</p>
        <p className="mt-1 max-w-sm text-sm text-muted-foreground">
          Upload a PDF to find sensitive details, review them, and export a redacted copy.
        </p>
      </Card>
    );
  }

  return (
    <>
      <div className="hidden md:block">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>File</TableHead>
              <TableHead>Mode</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Pages</TableHead>
              <TableHead>Updated</TableHead>
              <TableHead className="w-12" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {documents.map((doc) => (
              <TableRow key={doc.id} className="cursor-pointer" onClick={() => open(doc.id)}>
                <TableCell className="font-medium">{doc.filename}</TableCell>
                <TableCell>{modeMeta(doc.mode).label}</TableCell>
                <TableCell>
                  <StatusBadge status={doc.status} stage={doc.processingStage} />
                </TableCell>
                <TableCell className="text-muted-foreground">{doc.pageCount ?? "—"}</TableCell>
                <TableCell className="text-muted-foreground">{formatUtc(doc.updatedAt)}</TableCell>
                <TableCell onClick={(event) => event.stopPropagation()}>
                  <RowActions doc={doc} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <div className="grid gap-3 md:hidden">
        {documents.map((doc) => (
          <Card
            key={doc.id}
            className="flex cursor-pointer items-start justify-between gap-3 p-4"
            onClick={() => open(doc.id)}
          >
            <div className="min-w-0 space-y-2">
              <p className="truncate font-medium">{doc.filename}</p>
              <p className="text-xs text-muted-foreground">{modeMeta(doc.mode).label}</p>
              <StatusBadge status={doc.status} stage={doc.processingStage} />
              <p className="text-xs text-muted-foreground">{formatUtc(doc.updatedAt)}</p>
            </div>
            <div onClick={(event) => event.stopPropagation()}>
              <RowActions doc={doc} />
            </div>
          </Card>
        ))}
      </div>
    </>
  );
}
