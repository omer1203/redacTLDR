import { SummaryScreen } from "@/components/summaries/summary-screen";

export default async function SummaryPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <SummaryScreen
      documentId={id}
      clerkEnabled={Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY)}
      jwtTemplate={process.env.CLERK_JWT_TEMPLATE ?? null}
    />
  );
}
