import { Wordmark } from "@/components/wordmark";

export const clerkAppearance = {
  variables: {
    colorPrimary: "#7a2436",
    colorText: "#3a1c22",
    colorBackground: "#f8f4ef",
    borderRadius: "0.9rem",
    fontFamily: "var(--font-geist-sans), ui-sans-serif, system-ui, sans-serif",
  },
  elements: {
    card: "shadow-[0_20px_50px_-24px_rgba(20,30,28,0.45)]",
    headerTitle: "font-display",
  },
};

export function AuthFrame({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid min-h-screen lg:grid-cols-[minmax(20rem,0.9fr)_1.1fr]">
      <aside className="hidden flex-col justify-between bg-sidebar px-10 py-10 text-sidebar-foreground lg:flex">
        <Wordmark href="/" className="text-sidebar-foreground" />
        <div className="max-w-md">
          <p className="font-display text-[clamp(2.4rem,4vw,3.6rem)] font-medium leading-[1.08] tracking-tight">
            Share the document. Leave the person out of it.
          </p>
          <p className="mt-5 text-base leading-relaxed text-sidebar-foreground/75">
            Review what is sensitive, then export a PDF where that text is removed, not just covered.
          </p>
        </div>
        <p className="text-sm text-sidebar-foreground/55">Private files stay in your bucket.</p>
      </aside>
      <main className="surface-glow flex items-center justify-center px-6 py-16">{children}</main>
    </div>
  );
}
