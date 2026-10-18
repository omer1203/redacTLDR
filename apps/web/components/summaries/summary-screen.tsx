"use client";

import { SummaryView } from "@/components/summaries/summary-view";
import { ApiTokenProvider } from "@/lib/review/token";

export function SummaryScreen({
  documentId,
  clerkEnabled,
  jwtTemplate,
}: {
  documentId: string;
  clerkEnabled: boolean;
  jwtTemplate: string | null;
}) {
  return (
    <ApiTokenProvider clerkEnabled={clerkEnabled} jwtTemplate={jwtTemplate}>
      <SummaryView documentId={documentId} />
    </ApiTokenProvider>
  );
}
