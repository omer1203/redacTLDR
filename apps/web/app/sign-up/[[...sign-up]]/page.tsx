import { SignUp } from "@clerk/nextjs";
import Link from "next/link";

import { AuthFrame, clerkAppearance } from "@/components/auth-frame";
import { Button } from "@/components/ui/button";

export default function SignUpPage() {
  const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY);
  if (!clerkEnabled) {
    return (
      <AuthFrame>
        <div className="max-w-md">
          <h1 className="font-display text-4xl font-medium tracking-tight">Sign up unavailable</h1>
          <p className="mt-3 text-base leading-relaxed text-muted-foreground">
            Clerk is disabled in this environment. Use the local demo dashboard flow instead.
          </p>
          <Button className="mt-6" asChild>
            <Link href="/dashboard">Go to dashboard</Link>
          </Button>
        </div>
      </AuthFrame>
    );
  }
  return (
    <AuthFrame>
      <SignUp
        appearance={clerkAppearance}
        fallbackRedirectUrl="/dashboard"
        forceRedirectUrl="/dashboard"
        signInUrl="/sign-in"
      />
    </AuthFrame>
  );
}
