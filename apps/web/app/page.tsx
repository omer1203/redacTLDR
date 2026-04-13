import Link from "next/link";

export default function HomePage() {
  return (
    <main className="mx-auto max-w-3xl p-8">
      <h1 className="text-3xl font-semibold">redactldr</h1>
      <p className="mt-4 text-slate-700">
        Upload, review, truly redact, and safely summarize sensitive PDFs.
      </p>
      <div className="mt-6">
        <Link className="rounded bg-slate-900 px-4 py-2 text-white" href="/dashboard">
          Open dashboard
        </Link>
      </div>
    </main>
  );
}
