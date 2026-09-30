import { SignIn } from "@clerk/nextjs";
import Link from "next/link";

export default function SignInPage() {
  const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY);
  if (!clerkEnabled) {
    return (
      <main className="mx-auto max-w-xl p-8">
        <h1 className="text-2xl font-semibold">Sign in unavailable</h1>
        <p className="mt-3 text-slate-700">
          Clerk is disabled in this environment. Use the local demo dashboard flow instead.
        </p>
        <Link className="mt-6 inline-block rounded bg-slate-900 px-4 py-2 text-white" href="/dashboard">
          Go to dashboard
        </Link>
      </main>
    );
  }
  return (
    <main className="mx-auto flex min-h-[70vh] max-w-md items-center justify-center p-8">
      <SignIn />
    </main>
  );
}
