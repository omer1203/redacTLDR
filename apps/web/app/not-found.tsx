import Link from "next/link";

import { StatusScreen } from "@/components/status-screen";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <StatusScreen code="404" title="Page not found" body="That address is not part of RedacTLDR.">
      <Button asChild>
        <Link href="/">Go home</Link>
      </Button>
    </StatusScreen>
  );
}
