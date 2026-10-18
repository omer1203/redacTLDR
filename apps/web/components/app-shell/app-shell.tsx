"use client";

import { UserButton } from "@clerk/nextjs";
import { useQueryClient } from "@tanstack/react-query";
import { Menu } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { ActivityView } from "@/components/activity-view";
import { InstantNavProvider } from "@/components/app-shell/instant-nav";
import { AppNav } from "@/components/app-shell/nav";
import { NotificationBell } from "@/components/app-shell/notification-bell";
import { DashboardView } from "@/components/documents/dashboard-view";
import { DocumentOverview } from "@/components/documents/document-overview";
import { ReviewScreen } from "@/components/review/review-screen";
import { SettingsView } from "@/components/settings-view";
import { SummaryView } from "@/components/summaries/summary-view";
import { ThemeToggle } from "@/components/theme-toggle";
import { Wordmark } from "@/components/wordmark";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { listAuditEvents } from "@/lib/api/audit";
import { getSettings } from "@/lib/api/settings";
import { useApiToken } from "@/lib/review/token";

const WARM_ROUTES = ["/dashboard", "/activity", "/settings"];

function screenFor(href: string) {
  const path = href.split("?")[0];
  if (path.startsWith("/activity")) {
    return <ActivityView />;
  }
  if (path.startsWith("/settings")) {
    return <SettingsView />;
  }
  if (path.startsWith("/dashboard")) {
    return <DashboardView />;
  }
  const document = path.match(/^\/documents\/([^/]+)(?:\/(review|summary))?$/);
  if (!document) {
    return null;
  }
  const documentId = decodeURIComponent(document[1]);
  if (document[2] === "review") {
    return <ReviewScreen documentId={documentId} />;
  }
  if (document[2] === "summary") {
    return <SummaryView documentId={documentId} />;
  }
  return <DocumentOverview documentId={documentId} />;
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY);
  const router = useRouter();
  const pathname = usePathname();
  const queryClient = useQueryClient();
  const getToken = useApiToken();
  const [open, setOpen] = useState(false);
  const [pendingHref, setPendingHref] = useState<string | null>(null);

  useEffect(() => {
    setPendingHref(null);
  }, [pathname]);

  useEffect(() => {
    for (const href of WARM_ROUTES) {
      router.prefetch(href);
    }
    let cancelled = false;
    void (async () => {
      try {
        const token = await getToken();
        if (cancelled) {
          return;
        }
        await Promise.all([
          queryClient.prefetchQuery({
            queryKey: ["audit", ""],
            queryFn: () => listAuditEvents(token),
            staleTime: 60_000,
          }),
          queryClient.prefetchQuery({
            queryKey: ["settings"],
            queryFn: () => getSettings(token),
            staleTime: 60_000,
          }),
        ]);
      } catch {
        // The screen fetches again when it opens.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [getToken, queryClient, router]);

  const shown = pendingHref && pendingHref !== pathname ? pendingHref : pathname;
  const immediate = pendingHref && pendingHref !== pathname ? screenFor(pendingHref) : null;

  const go = (href: string) => {
    setPendingHref(href);
    setOpen(false);
  };

  return (
    <InstantNavProvider go={go}>
    <div className="min-h-screen bg-background md:grid md:grid-cols-[minmax(240px,17rem)_1fr]">
      <aside className="hidden flex-col bg-sidebar text-sidebar-foreground md:flex">
        <div className="px-5 py-6" onClick={() => go("/dashboard")}>
          <Wordmark href="/dashboard" />
        </div>
        <div className="px-3">
          <AppNav pathname={shown} onNavigate={go} />
        </div>
      </aside>
      <div className="surface-glow flex min-h-screen flex-col">
        <header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b bg-background/80 px-[clamp(1rem,2vw,2rem)] backdrop-blur-md">
          <div className="flex items-center gap-2">
            <Sheet open={open} onOpenChange={setOpen}>
              <SheetTrigger asChild>
                <Button variant="ghost" size="icon" className="md:hidden" aria-label="Open menu">
                  <Menu className="h-4 w-4" />
                </Button>
              </SheetTrigger>
              <SheetContent>
                <div onClick={() => go("/dashboard")}>
                  <Wordmark href="/dashboard" />
                </div>
                <AppNav pathname={shown} onNavigate={go} />
              </SheetContent>
            </Sheet>
          </div>
          <div className="flex items-center gap-2">
            <NotificationBell />
            <ThemeToggle />
            {clerkEnabled ? <UserButton /> : <span className="text-xs text-muted-foreground">Local demo</span>}
          </div>
        </header>
        <main className="flex-1 px-[clamp(1.25rem,3vw,3.5rem)] py-8">{immediate ?? children}</main>
      </div>
    </div>
    </InstantNavProvider>
  );
}
