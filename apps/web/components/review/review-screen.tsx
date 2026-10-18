"use client";

import dynamic from "next/dynamic";

import { ReviewStoreProvider } from "@/lib/review/store";

// pdf.js touches browser-only APIs at import time, so the workspace never renders on the server.
const ReviewWorkspace = dynamic(() => import("@/components/review/review-workspace"), {
  ssr: false,
  loading: () => (
    <div className="flex h-[calc(100dvh-8rem)] min-h-[600px] animate-pulse flex-col gap-4">
      <div className="h-14 rounded-lg bg-muted" />
      <div className="flex-1 rounded-lg bg-muted" />
    </div>
  ),
});

export function ReviewScreen({ documentId }: { documentId: string }) {
  // The signed-in layout already provides the API token. A second provider
  // here subscribed to Clerk again and re-rendered the whole review tree.
  return (
    <ReviewStoreProvider>
      <ReviewWorkspace documentId={documentId} />
    </ReviewStoreProvider>
  );
}
