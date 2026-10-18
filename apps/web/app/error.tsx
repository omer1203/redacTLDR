"use client";

import Link from "next/link";
import { useEffect } from "react";

import { StatusScreen } from "@/components/status-screen";
import { Button } from "@/components/ui/button";

export default function RootError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  const detail = error.message?.trim().slice(0, 280) || "The page could not be loaded.";

  return (
    <StatusScreen title="Something went wrong" body={detail}>
      <Button onClick={reset}>Try again</Button>
      <Button variant="outline" asChild>
        <Link href="/">Go home</Link>
      </Button>
    </StatusScreen>
  );
}
