"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";

import { useScheduleNav } from "@/components/app-shell/instant-nav";
import { Button } from "@/components/ui/button";

export function BackLink({ href, label }: { href: string; label: string }) {
  const go = useScheduleNav();
  return (
    <Button variant="ghost" size="icon" className="-ml-2 self-start" asChild>
      <Link href={href} aria-label={label} onClick={() => go(href)}>
        <ArrowLeft className="h-4 w-4" />
      </Link>
    </Button>
  );
}
