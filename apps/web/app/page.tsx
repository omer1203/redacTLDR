import Link from "next/link";

export default function HomePage() {
  const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY);
  return (
    <main className="mx-auto max-w-3xl p-8">
      <h1 className="text-3xl font-semibold">RedacTLDR</h1>
      <p className="mt-4 text-slate-700">
        Upload, review, truly redact, and safely summarize sensitive PDFs.
      </p>
      <div className="mt-6 flex flex-wrap items-center gap-3">
        <Link className="rounded bg-slate-900 px-4 py-2 text-white" href="/dashboard">
          Open dashboard
        </Link>
        {clerkEnabled ? (
          <>
            <Link className="rounded border border-slate-300 px-4 py-2" href="/sign-in">
              Sign in
            </Link>
            <Link className="rounded border border-slate-300 px-4 py-2" href="/sign-up">
              Sign up
            </Link>
          </>
        ) : (
          <p className="text-sm text-slate-600">Local demo auth is enabled (no Clerk sign-in required).</p>
        )}
      </div>
    </main>
  );
}
