"use client";

import { UserButton } from "@clerk/nextjs";
import { Menu } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { AppNav } from "@/components/app-shell/nav";
import { NotificationBell } from "@/components/app-shell/notification-bell";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";

export function AppShell({ children }: { children: React.ReactNode }) {
  const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY);
  const [open, setOpen] = useState(false);

  return (
    <div className="min-h-screen bg-background md:grid md:grid-cols-[minmax(240px,18vw)_1fr]">
      <aside className="hidden flex-col bg-sidebar text-sidebar-foreground md:flex">
        <Link href="/dashboard" className="px-6 py-6 text-2xl font-semibold tracking-tight">
          RedacTLDR
        </Link>
        <div className="px-3">
          <AppNav />
        </div>
      </aside>
      <div className="flex min-h-screen flex-col">
        <header className="flex h-16 items-center justify-between border-b px-[clamp(1rem,2vw,2rem)]">
          <div className="flex items-center gap-2">
            <Sheet open={open} onOpenChange={setOpen}>
              <SheetTrigger asChild>
                <Button variant="ghost" size="icon" className="md:hidden" aria-label="Open menu">
                  <Menu className="h-4 w-4" />
                </Button>
              </SheetTrigger>
              <SheetContent>
                <Link href="/dashboard" className="text-lg font-semibold" onClick={() => setOpen(false)}>
                  RedacTLDR
                </Link>
                <AppNav onNavigate={() => setOpen(false)} />
              </SheetContent>
            </Sheet>
            <span className="text-sm font-medium md:hidden">RedacTLDR</span>
          </div>
          <div className="flex items-center gap-2">
            <NotificationBell />
            <ThemeToggle />
            {clerkEnabled ? <UserButton /> : <span className="text-xs text-muted-foreground">Local demo</span>}
          </div>
        </header>
        <main className="flex-1 px-[clamp(1.25rem,3vw,3.5rem)] py-8">{children}</main>
      </div>
    </div>
  );
}
