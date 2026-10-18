"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { getExport, isExportActive, listExports, queueExport, type ExportOptions } from "@/lib/api";
import { useApiToken } from "@/lib/review/token";

const POLL_MS = 2000;

/** Prefix key: invalidating it refreshes the history and every single-export query of the document. */
export const exportsKey = (documentId: string) => ["exports", documentId] as const;
const exportKey = (documentId: string, exportId: string) => ["exports", documentId, exportId] as const;

export function useExports(documentId: string) {
  const getToken = useApiToken();
  return useQuery({
    queryKey: exportsKey(documentId),
    queryFn: async () => listExports(await getToken(), documentId),
    refetchInterval: (query) => (query.state.data?.some(isExportActive) ? POLL_MS : false),
  });
}

/** Polls one export while it is queued or building. */
export function useExport(documentId: string, exportId: string | null) {
  const getToken = useApiToken();
  return useQuery({
    queryKey: exportKey(documentId, exportId ?? "none"),
    queryFn: async () => getExport(await getToken(), documentId, exportId as string),
    enabled: exportId !== null,
    refetchInterval: (query) => (isExportActive(query.state.data) ? POLL_MS : false),
  });
}

export function useQueueExport(documentId: string, onQueued: (exportId: string) => void) {
  const getToken = useApiToken();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (options: ExportOptions) => queueExport(await getToken(), documentId, options),
    onSuccess: async (record) => {
      queryClient.setQueryData(exportKey(documentId, record.id), record);
      onQueued(record.id);
      await queryClient.invalidateQueries({ queryKey: exportsKey(documentId) });
      // The document badge moves to "Exporting".
      await queryClient.invalidateQueries({ queryKey: ["document"] });
    },
    onError: (error: Error) => toast.error(error.message),
  });
}

/**
 * Download links expire after a few minutes, so every click asks for a fresh one.
 * The link sets `Content-Disposition: attachment`, so assigning it saves the file
 * without leaving the page.
 */
export function useDownloadExport(documentId: string) {
  const getToken = useApiToken();
  return useMutation({
    mutationFn: async (exportId: string) => {
      const record = await getExport(await getToken(), documentId, exportId);
      if (!record.downloadUrl) {
        throw new Error("This export has no file to download.");
      }
      window.location.assign(record.downloadUrl);
    },
    onError: (error: Error) => toast.error(error.message),
  });
}
