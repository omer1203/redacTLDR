"use client";

import { useIsMutating, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import {
  createManualRedaction,
  deleteManualRedaction,
  getOriginalUrl,
  getReviewState,
  setDetectionAccepted,
  setEntityTypeAccepted,
  updateManualRedaction,
  type NormalizedRect,
  type ReviewState,
} from "@/lib/api/review";
import { MANUAL_COLOR, MANUAL_ENTITY_TYPE, MANUAL_LABEL, withDetections, withManualRedactions } from "@/lib/review/derive";
import { useApiToken } from "@/lib/review/token";

/**
 * Server state for the review screen.
 *
 * Every edit is applied to the cached review state immediately (optimistic),
 * then saved. All saves for one document share a mutation scope, so they reach
 * the API one at a time in the order the reviewer made them. A box can never
 * be moved before its create lands, and two quick toggles cannot arrive
 * reversed. When the last queued save settles, the state is refetched so the
 * cache matches the database.
 */

export const reviewStateKey = (documentId: string) => ["review-state", documentId] as const;
const originalUrlKey = (documentId: string) => ["review-original-url", documentId] as const;
const saveKey = (documentId: string) => ["review-save", documentId] as const;

export function useReviewState(documentId: string) {
  const getToken = useApiToken();
  return useQuery({
    queryKey: reviewStateKey(documentId),
    queryFn: async () => getReviewState(await getToken(), documentId),
    // Poll only while the pipeline is still running; once reviewable, this tab owns the edits.
    refetchInterval: (query) => {
      const data = query.state.data;
      return data && !data.reviewable && data.status !== "FAILED" ? 3000 : false;
    },
    refetchOnWindowFocus: false,
  });
}

/** Presigned original URL. Fetched once; the viewer calls `refetch` if the PDF fails to load. */
export function useOriginalUrl(documentId: string, enabled: boolean) {
  const getToken = useApiToken();
  return useQuery({
    queryKey: originalUrlKey(documentId),
    queryFn: async () => getOriginalUrl(await getToken(), documentId),
    enabled,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  });
}

export function useSavingCount(documentId: string): number {
  return useIsMutating({ mutationKey: saveKey(documentId) });
}

interface SaveSpec<TVars> {
  run: (token: string, vars: TVars) => Promise<unknown>;
  apply: (state: ReviewState, vars: TVars) => ReviewState;
  failure: string;
}

function useReviewSave<TVars>(documentId: string, spec: SaveSpec<TVars>) {
  const queryClient = useQueryClient();
  const getToken = useApiToken();
  const key = reviewStateKey(documentId);
  return useMutation({
    mutationKey: saveKey(documentId),
    scope: { id: `review-save:${documentId}` },
    mutationFn: async (vars: TVars) => spec.run(await getToken(), vars),
    onMutate: async (vars) => {
      await queryClient.cancelQueries({ queryKey: key });
      const previous = queryClient.getQueryData<ReviewState>(key);
      if (previous) {
        queryClient.setQueryData<ReviewState>(key, spec.apply(previous, vars));
      }
      return { previous };
    },
    onError: (error, _vars, context) => {
      // With later saves still queued, the snapshot would also undo them; the refetch below restores truth instead.
      if (context?.previous && queryClient.isMutating({ mutationKey: saveKey(documentId) }) === 1) {
        queryClient.setQueryData(key, context.previous);
      }
      toast.error(`${spec.failure} ${error.message}`);
    },
    onSettled: async () => {
      // This mutation still counts as pending here, so 1 means it is the last one.
      if (queryClient.isMutating({ mutationKey: saveKey(documentId) }) === 1) {
        await queryClient.invalidateQueries({ queryKey: key });
      }
    },
  });
}

export function useSetDetectionAccepted(documentId: string) {
  return useReviewSave<{ detectionId: string; accepted: boolean }>(documentId, {
    run: (token, vars) => setDetectionAccepted(token, documentId, vars.detectionId, vars.accepted),
    apply: (state, vars) =>
      withDetections(
        state,
        state.detections.map((item) => (item.id === vars.detectionId ? { ...item, accepted: vars.accepted } : item)),
      ),
    failure: "Couldn't update that item.",
  });
}

export function useSetEntityTypeAccepted(documentId: string) {
  return useReviewSave<{ entityType: string; accepted: boolean }>(documentId, {
    run: (token, vars) => setEntityTypeAccepted(token, documentId, vars.entityType, vars.accepted),
    apply: (state, vars) =>
      withDetections(
        state,
        state.detections.map((item) => (item.entityType === vars.entityType ? { ...item, accepted: vars.accepted } : item)),
      ),
    failure: "Couldn't update that type.",
  });
}

export function useCreateManualRedaction(documentId: string) {
  return useReviewSave<{ id: string; pageNumber: number; bbox: NormalizedRect }>(documentId, {
    run: (token, vars) => createManualRedaction(token, documentId, vars),
    apply: (state, vars) =>
      withManualRedactions(state, [
        ...state.manualRedactions,
        {
          id: vars.id,
          pageNumber: vars.pageNumber,
          entityType: MANUAL_ENTITY_TYPE,
          label: MANUAL_LABEL,
          color: MANUAL_COLOR,
          kind: "bbox",
          bbox: vars.bbox,
          status: "ACTIVE",
          createdAt: new Date().toISOString(),
        },
      ]),
    failure: "Couldn't save the box.",
  });
}

export function useUpdateManualRedaction(documentId: string) {
  return useReviewSave<{ id: string; bbox: NormalizedRect }>(documentId, {
    run: (token, vars) => updateManualRedaction(token, documentId, vars.id, vars.bbox),
    apply: (state, vars) =>
      withManualRedactions(
        state,
        state.manualRedactions.map((box) => (box.id === vars.id ? { ...box, bbox: vars.bbox } : box)),
      ),
    failure: "Couldn't move the box.",
  });
}

export function useDeleteManualRedaction(documentId: string) {
  return useReviewSave<{ id: string }>(documentId, {
    run: (token, vars) => deleteManualRedaction(token, documentId, vars.id),
    apply: (state, vars) =>
      withManualRedactions(
        state,
        state.manualRedactions.filter((box) => box.id !== vars.id),
      ),
    failure: "Couldn't delete the box.",
  });
}
