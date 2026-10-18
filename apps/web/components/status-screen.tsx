import { Wordmark } from "@/components/wordmark";

export function StatusScreen({
  code,
  title,
  body,
  children,
}: {
  code?: string;
  title: string;
  body: string;
  children: React.ReactNode;
}) {
  return (
    <main className="surface-glow flex min-h-[70vh] flex-col items-center justify-center px-6 py-20 text-center">
      <Wordmark href="/" />
      {code ? <p className="mt-10 font-mono text-xs tracking-[0.22em] text-primary">{code}</p> : null}
      <h1 className="mt-3 max-w-[14ch] font-display text-[clamp(2.5rem,5vw,4.25rem)] font-medium leading-[1.05] tracking-tight">
        {title}
      </h1>
      <p className="mt-4 max-w-md text-base leading-relaxed text-muted-foreground">{body}</p>
      <div className="mt-8 flex flex-wrap items-center justify-center gap-3">{children}</div>
    </main>
  );
}
