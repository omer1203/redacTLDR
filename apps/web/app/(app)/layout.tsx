import { AppShell } from "@/components/app-shell/app-shell";
import { ApiTokenProvider } from "@/lib/review/token";

export default function SignedInLayout({ children }: { children: React.ReactNode }) {
  // Middleware already checks the session. Pages mint a token in the browser,
  // so navigating does not wait on Clerk before the screen can render.
  const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY);
  const jwtTemplate = process.env.CLERK_JWT_TEMPLATE ?? null;
  return (
    <ApiTokenProvider clerkEnabled={clerkEnabled} jwtTemplate={jwtTemplate}>
      <AppShell>{children}</AppShell>
    </ApiTokenProvider>
  );
}
