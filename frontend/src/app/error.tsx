"use client";

import { useEffect } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { RecoveryState } from "@/components/ui/recovery-state";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Route error:", error);
  }, [error]);

  return (
    <div className="page-container flex min-h-[60vh] items-center justify-center">
      <RecoveryState
        title="This surface hit a runtime fault"
        description="The workspace caught the failure before it could affect saved workflows. Retry the route, reload the app shell, or return to workflows."
        diagnostic={error.digest}
        primaryAction={
          <Button onClick={reset}>
            Try again
          </Button>
        }
        secondaryAction={
          <Button variant="outline" onClick={() => window.location.reload()}>
            Reload page
          </Button>
        }
        tertiaryAction={
          <Button variant="outline" asChild>
            <Link href="/">Back to workflows</Link>
          </Button>
        }
      />
    </div>
  );
}
