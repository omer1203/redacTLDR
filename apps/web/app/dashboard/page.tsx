/**
 * Server-rendered dashboard entrypoint.
 *
 * Responsibilities:
 * - enforce authenticated access with Clerk
 * - mint a session token on the server
 * - pass token to client component for authenticated API calls
 */
import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";

import { DashboardClient } from "@/components/dashboard-client";

export default async function DashboardPage() {
  const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY);
  if (!clerkEnabled) {
    const demoUserId = process.env.NEXT_PUBLIC_DEMO_USER ?? "demo-user";
    return (
      <main className="mx-auto max-w-5xl p-8">
        <h1 className="text-2xl font-semibold">Dashboard (Local Demo Auth)</h1>
        <p className="mt-2 text-sm text-slate-600">
          Clerk is disabled in this environment. API requests use <code>x-demo-user</code> for local development.
        </p>
        <DashboardClient token="" userId={demoUserId} />
      </main>
    );
  }

  // Clerk server helper returns identity + token retrieval function.
  const { userId, getToken } = await auth();
  // Gate dashboard behind authentication.
  if (!userId) {
    redirect("/");
  }

  // Acquire bearer token to call backend API from client-side query layer.
  // This uses a named JWT template so API audience validation stays explicit.
  const jwtTemplate = process.env.CLERK_JWT_TEMPLATE;
  if (!jwtTemplate) {
    throw new Error("Missing CLERK_JWT_TEMPLATE. Set it to enforce API audience-specific tokens.");
  }
  const token = await getToken({ template: jwtTemplate });
  if (!token) {
    redirect("/");
  }

  return (
    <main className="mx-auto max-w-5xl p-8">
      <h1 className="text-2xl font-semibold">Dashboard</h1>
      <p className="mt-2 text-sm text-slate-600">
        Review uploads, detections, redactions, exports, and summaries.
      </p>
      <DashboardClient token={token} userId={userId} />
    </main>
  );
}
