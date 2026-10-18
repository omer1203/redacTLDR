"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { getLatestSummary, isSummaryActive, queueSummary } from "@/lib/api/summaries";
import { useApiToken } from "@/lib/review/token";

const POLL_MS = 2000;

export const summaryKey = (documentId: string) => ["summary", documentId] as const;

export function useLatestSummary(documentId: string) {
  const getToken = useApiToken();
  return useQuery({
    queryKey: summaryKey(documentId),
    queryFn: async () => getLatestSummary(await getToken(), documentId),
    refetchInterval: (query) => (isSummaryActive(query.state.data) ? POLL_MS : false),
  });
}

export function useQueueSummary(documentId: string) {
  const getToken = useApiToken();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => queueSummary(await getToken(), documentId),
    onSuccess: async (record) => {
      queryClient.setQueryData(summaryKey(documentId), record);
      await queryClient.invalidateQueries({ queryKey: ["document"] });
    },
    onError: (error: Error) => toast.error(error.message),
  });
}
