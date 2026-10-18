import Link from "next/link";

import { cn } from "@/lib/utils";

export function Wordmark({
  href = "/",
  className,
}: {
  href?: string;
  className?: string;
}) {
  return (
    <Link href={href} className={cn("inline-flex items-center gap-2", className)}>
      <img src="/logo-mark.png" alt="" className="h-9 w-auto shrink-0 sm:h-11" />
      <span className="font-display text-[1.35rem] font-medium leading-none tracking-tight sm:text-[1.65rem]">RedacTLDR</span>
    </Link>
  );
}
