import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";

import { DashboardClient } from "@/components/dashboard-client";

export default async function DashboardPage() {
  const { userId, getToken } = await auth();
  if (!userId) {
    redirect("/");
  }

  const token = await getToken();
  if (!token) {
    redirect("/");
  }

  return (
    <main className="mx-auto max-w-5xl p-8">
      <h1 className="text-2xl font-semibold">Dashboard</h1>
      <p className="mt-2 text-sm text-slate-600">
        Review uploads, detections, redactions, exports, and summaries.
      </p>
      <DashboardClient token={token} />
    </main>
  );
}
