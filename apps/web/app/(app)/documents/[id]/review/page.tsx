import { ReviewScreen } from "@/components/review/review-screen";

export default async function ReviewPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ReviewScreen documentId={id} />;
}
