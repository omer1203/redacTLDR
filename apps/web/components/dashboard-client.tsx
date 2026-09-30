"use client";

/**
 * Client-side dashboard view.
 *
 * Uses React Query for API state management and renders a minimal document list.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { completeIngest, createDocument, listDocuments, uploadFileToPresignedUrl } from "@/lib/api";
import type { DocumentMode, DocumentRecord, DocumentStatus } from "@/lib/types";

const ACTIVE_STATUSES: ReadonlySet<DocumentStatus> = new Set([
  "CREATED",
  "UPLOADED",
  "DETECT_QUEUED",
  "EXPORT_QUEUED",
  "SUMMARY_QUEUED",
]);

const DOCUMENT_MODES: DocumentMode[] = [
  "resume_anonymization",
  "employment_paperwork_review",
  "medical_paperwork_safe_sharing",
  "legal_contract_review",
  "terms_and_conditions_summarization",
];

function formatDateTime(value: string): string {
  const timestamp = Date.parse(value);
  if (Number.isNaN(timestamp)) {
    return value;
  }
  return new Date(timestamp).toLocaleString();
}

function DocumentRow({ doc }: { doc: DocumentRecord }) {
  // Small presentational row used by dashboard list rendering.
  return (
    <li className="rounded border bg-white p-3 text-sm">
      <div className="font-medium">{doc.filename}</div>
      <div className="text-slate-600">{doc.mode}</div>
      <div className="text-slate-600">{doc.status}</div>
      <div className="text-slate-500">Created: {formatDateTime(doc.createdAt)}</div>
      <div className="text-slate-500">Updated: {formatDateTime(doc.updatedAt)}</div>
    </li>
  );
}

interface UploadInput {
  file: File;
  mode: DocumentMode;
  safeMode: boolean;
}

export function DashboardClient({ token, userId }: { token: string; userId: string }) {
  const queryClient = useQueryClient();
  const [mode, setMode] = useState<DocumentMode>("resume_anonymization");
  const [safeMode, setSafeMode] = useState(true);
  const [file, setFile] = useState<File | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const documentsQueryKey = useMemo(() => ["documents", userId], [userId]);

  // Token comes from server-side Clerk auth in dashboard page.
  const documentsQuery = useQuery({
    queryKey: documentsQueryKey,
    // Query function delegates to typed API wrapper.
    queryFn: () => listDocuments(token),
    refetchInterval: (query) => {
      const documents = query.state.data ?? [];
      return documents.some((doc) => ACTIVE_STATUSES.has(doc.status)) ? 5_000 : false;
    },
  });

  const uploadMutation = useMutation({
    mutationFn: async ({ file: pendingFile, mode: selectedMode, safeMode: enabledSafeMode }: UploadInput) => {
      const contentType = pendingFile.type || "application/pdf";
      const created = await createDocument(token, {
        filename: pendingFile.name,
        contentType,
        mode: selectedMode,
        safeMode: enabledSafeMode,
        sizeBytes: pendingFile.size,
      });
      await uploadFileToPresignedUrl(created.presignedPutUrl, pendingFile);
      return completeIngest(token, created.id);
    },
    onSuccess: async () => {
      setFile(null);
      await queryClient.invalidateQueries({ queryKey: documentsQueryKey });
    },
    onError: (error) => {
      setUploadError((error as Error).message);
    },
  });

  function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setUploadError(null);
    if (!file) {
      setUploadError("Select a PDF before uploading.");
      return;
    }
    if (file.type && file.type !== "application/pdf") {
      setUploadError("Only PDF files are supported.");
      return;
    }
    uploadMutation.mutate({ file, mode, safeMode });
  }

  // Render loading fallback while initial fetch is in flight.
  if (documentsQuery.isLoading) {
    return <p className="mt-6">Loading documents...</p>;
  }

  // Render error details for troubleshooting auth/API connectivity.
  if (documentsQuery.isError) {
    return (
      <p className="mt-6 text-red-600">
        Failed to load documents: {(documentsQuery.error as Error).message}
      </p>
    );
  }

  // Safe default keeps render stable if API returns null/undefined unexpectedly.
  const documents = documentsQuery.data ?? [];

  return (
    <section className="mt-6 space-y-3">
      <form className="space-y-3 rounded border bg-white p-4" onSubmit={onSubmit}>
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="pdf-file">
            Upload PDF
          </label>
          <input
            id="pdf-file"
            type="file"
            accept="application/pdf,.pdf"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="mode">
            Processing mode
          </label>
          <select
            className="rounded border px-2 py-1"
            id="mode"
            value={mode}
            onChange={(event) => setMode(event.target.value as DocumentMode)}
          >
            {DOCUMENT_MODES.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </div>
        <label className="flex items-center gap-2 text-sm text-slate-700">
          <input checked={safeMode} type="checkbox" onChange={(event) => setSafeMode(event.target.checked)} />
          Safe mode
        </label>
        <button
          className="rounded bg-slate-900 px-3 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:bg-slate-500"
          disabled={uploadMutation.isPending}
          type="submit"
        >
          {uploadMutation.isPending ? "Uploading..." : "Upload document"}
        </button>
        {uploadError ? <p className="text-sm text-red-600">{uploadError}</p> : null}
      </form>

      {documents.length === 0 ? (
        <p className="text-slate-600">No documents yet. Upload a PDF to start ingestion.</p>
      ) : (
        <ul className="space-y-2">
          {documents.map((doc) => (
            <DocumentRow doc={doc} key={doc.id} />
          ))}
        </ul>
      )}
    </section>
  );
}
