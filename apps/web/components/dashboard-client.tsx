"use client";

import { useQuery } from "@tanstack/react-query";

import { listDocuments } from "@/lib/api";
import type { DocumentRecord } from "@/lib/types";

function DocumentRow({ doc }: { doc: DocumentRecord }) {
  return (
    <li className="rounded border bg-white p-3 text-sm">
      <div className="font-medium">{doc.filename}</div>
      <div className="text-slate-600">{doc.mode}</div>
      <div className="text-slate-600">{doc.status}</div>
    </li>
  );
}

export function DashboardClient({ token }: { token: string }) {
  const documentsQuery = useQuery({
    queryKey: ["documents"],
    queryFn: () => listDocuments(token),
  });

  if (documentsQuery.isLoading) {
    return <p className="mt-6">Loading documents...</p>;
  }

  if (documentsQuery.isError) {
    return (
      <p className="mt-6 text-red-600">
        Failed to load documents: {(documentsQuery.error as Error).message}
      </p>
    );
  }

  const documents = documentsQuery.data ?? [];

  return (
    <section className="mt-6 space-y-3">
      {documents.length === 0 ? (
        <p className="text-slate-600">No documents yet. Upload flow is available via API.</p>
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
