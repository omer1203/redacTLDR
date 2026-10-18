import { DocumentOverview } from "@/components/documents/document-overview";

export default async function DocumentPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <DocumentOverview documentId={id} />;
}
