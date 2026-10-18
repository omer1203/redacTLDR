import { auth } from "@clerk/nextjs/server";
import { ArrowRight, EyeOff, FileSearch, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { redirect } from "next/navigation";

import { ThemeToggle } from "@/components/theme-toggle";
import { Wordmark } from "@/components/wordmark";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DOCUMENT_MODES } from "@/lib/modes";
import { cn } from "@/lib/utils";

const STEPS = [
  { title: "Upload", body: "Drop a digital or scanned PDF and pick the kind of document it is.", icon: FileSearch },
  { title: "Review", body: "See sensitive items on the page and decide what stays hidden.", icon: EyeOff },
  { title: "Export", body: "Download a PDF with the text removed, not just covered up.", icon: ShieldCheck },
];

export default async function HomePage() {
  const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY);
  if (clerkEnabled) {
    const { userId } = await auth();
    if (userId) {
      redirect("/dashboard");
    }
  }
  const primaryHref = clerkEnabled ? "/sign-in" : "/dashboard";

  return (
    <div className="surface-glow min-h-screen">
      <header className="flex w-full items-center justify-between gap-3 px-[clamp(1rem,4vw,4.5rem)] py-5">
        <Wordmark />
        <div className="flex items-center gap-2">
          <ThemeToggle />
          {clerkEnabled ? (
            <Button variant="outline" className="hidden sm:inline-flex" asChild>
              <Link href="/sign-in">Sign in</Link>
            </Button>
          ) : null}
          <Button size="sm" className="sm:h-11 sm:px-5 sm:text-base" asChild>
            <Link href={primaryHref}>
              <span className="sm:hidden">Start</span>
              <span className="hidden sm:inline">{clerkEnabled ? "Get started" : "Open dashboard"}</span>
              <ArrowRight className="h-4 w-4" />
            </Link>
          </Button>
        </div>
      </header>
      <main className="flex w-full flex-col gap-[clamp(3.5rem,7vw,6.5rem)] px-[clamp(1.25rem,4vw,4.5rem)] pb-24">
        <section className="max-w-5xl pt-8 motion-safe:animate-in motion-safe:fade-in motion-safe:slide-in-from-bottom-2 motion-safe:duration-500">
          <p className="text-sm font-medium tracking-[0.16em] text-primary">Privacy-first document sharing</p>
          <h1 className="mt-4 max-w-[12em] font-display text-[clamp(2.5rem,4.8vw,4.75rem)] font-medium leading-[1.05] tracking-tight">
            Share documents
            <br />
            without sharing yourself
          </h1>
          <p className="mt-6 max-w-2xl text-[clamp(1.15rem,1.5vw,1.45rem)] leading-relaxed text-muted-foreground">
            Upload a PDF, review what is sensitive, and export a copy that no longer contains that text.
          </p>
          <div className="mt-8">
            <Button size="lg" asChild>
              <Link href={primaryHref}>
                {clerkEnabled ? "Sign in to upload" : "Try the local dashboard"}
                <ArrowRight className="h-4 w-4" />
              </Link>
            </Button>
          </div>
        </section>
        <section className="grid gap-4 md:grid-cols-3">
          {STEPS.map((step, index) => {
            const Icon = step.icon;
            return (
              <Card key={step.title} className="transition-transform duration-300 motion-safe:hover:-translate-y-0.5">
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <Icon className="h-5 w-5 text-primary" />
                    <span className="font-mono text-xs tracking-[0.18em] text-muted-foreground">0{index + 1}</span>
                  </div>
                  <CardTitle className="font-display text-2xl font-medium">{step.title}</CardTitle>
                </CardHeader>
                <CardContent className="text-base leading-relaxed text-muted-foreground">{step.body}</CardContent>
              </Card>
            );
          })}
        </section>
        <section>
          <h2 className="font-display text-[clamp(1.9rem,3vw,3rem)] font-medium tracking-tight">
            Built for the document in front of you
          </h2>
          <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-6">
            {DOCUMENT_MODES.map((mode, index) => {
              const Icon = mode.icon;
              return (
                <Card
                  key={mode.id}
                  className={cn(
                    "transition-transform duration-300 motion-safe:hover:-translate-y-0.5 md:col-span-2",
                    index === 3 && "md:col-start-2",
                  )}
                >
                  <CardHeader>
                    <div className="flex items-center gap-2">
                      <span className="grid h-8 w-8 place-items-center rounded-lg bg-accent text-accent-foreground">
                        <Icon className="h-4 w-4" />
                      </span>
                      <CardTitle className="text-base">{mode.label}</CardTitle>
                    </div>
                  </CardHeader>
                  <CardContent className="text-base leading-relaxed text-muted-foreground">{mode.description}</CardContent>
                </Card>
              );
            })}
          </div>
        </section>
        <section className="rounded-2xl bg-sidebar px-[clamp(1.5rem,3vw,3rem)] py-12 text-sidebar-foreground">
          <h2 className="font-display text-[clamp(1.9rem,3vw,3rem)] font-medium tracking-tight">What stays private</h2>
          <ul className="mt-6 grid gap-4 text-lg leading-relaxed text-sidebar-foreground/80 md:grid-cols-3">
            <li>Original files stay in your storage bucket.</li>
            <li>Safe mode builds summaries from redacted text.</li>
            <li>You can delete a document and its stored files.</li>
          </ul>
        </section>
      </main>
    </div>
  );
}
