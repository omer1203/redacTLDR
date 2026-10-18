"use client";

import Link from "next/link";
import { useEffect } from "react";

import { StatusScreen } from "@/components/status-screen";
import { Button } from "@/components/ui/button";

export default function AppError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  const detail = error.message?.trim().slice(0, 280) || "This screen could not be loaded.";

  return (
    <StatusScreen title="Something went wrong" body={detail}>
      <Button onClick={reset}>Try again</Button>
      <Button variant="outline" asChild>
        <Link href="/dashboard">Back to documents</Link>
      </Button>
    </StatusScreen>
  );
}
