import { ArrowLeft } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";

export function BackLink({ href, children }: { href: string; children: string }) {
  return (
    <Button variant="ghost" size="sm" className="-ml-2 h-9 px-2" asChild>
      <Link href={href}>
        <ArrowLeft className="h-4 w-4" />
        {children}
      </Link>
    </Button>
  );
}
