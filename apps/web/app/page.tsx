import { auth } from "@clerk/nextjs/server";
import { ArrowRight, EyeOff, FileSearch, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { redirect } from "next/navigation";

import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DOCUMENT_MODES } from "@/lib/modes";

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
    <div className="min-h-screen">
      <header className="flex w-full items-center justify-between px-[clamp(1.25rem,4vw,4.5rem)] py-6">
        <span className="text-2xl font-semibold">RedacTLDR</span>
        <div className="flex items-center gap-2">
          <ThemeToggle />
          {clerkEnabled ? (
            <Button variant="outline" asChild>
              <Link href="/sign-in">Sign in</Link>
            </Button>
          ) : null}
          <Button asChild>
            <Link href={primaryHref}>
              {clerkEnabled ? "Get started" : "Open dashboard"}
              <ArrowRight className="h-4 w-4" />
            </Link>
          </Button>
        </div>
      </header>
      <main className="flex w-full flex-col gap-[clamp(3rem,6vw,6rem)] px-[clamp(1.25rem,4vw,4.5rem)] pb-24">
        <section className="max-w-5xl pt-10">
          <p className="text-base font-medium text-primary">Privacy-first document sharing</p>
          <h1 className="mt-4 max-w-[16ch] text-[clamp(3rem,6vw,6.25rem)] font-semibold leading-[1.02] tracking-tight">
            Share documents without sharing yourself
          </h1>
          <p className="mt-6 max-w-3xl text-[clamp(1.2rem,1.6vw,1.6rem)] leading-relaxed text-muted-foreground">
            Upload a PDF, review what is sensitive, and export a copy that no longer contains that text.
          </p>
          <div className="mt-6">
            <Button size="lg" asChild>
              <Link href={primaryHref}>{clerkEnabled ? "Sign in to upload" : "Try the local dashboard"}</Link>
            </Button>
          </div>
        </section>
        <section className="grid gap-4 md:grid-cols-3">
          {STEPS.map((step) => {
            const Icon = step.icon;
            return (
              <Card key={step.title}>
                <CardHeader>
                  <Icon className="h-5 w-5 text-primary" />
                  <CardTitle>{step.title}</CardTitle>
                </CardHeader>
                <CardContent className="text-base text-muted-foreground">{step.body}</CardContent>
              </Card>
            );
          })}
        </section>
        <section>
          <h2 className="text-[clamp(1.75rem,3vw,2.75rem)] font-semibold">Built for the document in front of you</h2>
          <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {DOCUMENT_MODES.map((mode) => {
              const Icon = mode.icon;
              return (
                <Card key={mode.id}>
                  <CardHeader>
                    <div className="flex items-center gap-2">
                      <Icon className="h-4 w-4 text-primary" />
                      <CardTitle className="text-base">{mode.label}</CardTitle>
                    </div>
                  </CardHeader>
                  <CardContent className="text-base text-muted-foreground">{mode.description}</CardContent>
                </Card>
              );
            })}
          </div>
        </section>
        <section className="rounded-xl bg-sidebar px-[clamp(1.5rem,3vw,3rem)] py-10 text-sidebar-foreground">
          <h2 className="text-[clamp(1.75rem,3vw,2.75rem)] font-semibold">What stays private</h2>
          <ul className="mt-6 grid gap-3 text-lg text-sidebar-foreground/80 md:grid-cols-3">
            <li>Original files stay in your storage bucket.</li>
            <li>Safe mode builds summaries from redacted text.</li>
            <li>You can delete a document and its stored files.</li>
          </ul>
        </section>
      </main>
    </div>
  );
}
