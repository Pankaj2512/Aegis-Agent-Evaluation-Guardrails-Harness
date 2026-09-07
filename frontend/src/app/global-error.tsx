"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/button";
import { RecoveryState } from "@/components/ui/recovery-state";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Global error:", error);
  }, [error]);

  return (
    <html lang="en">
      <body className="min-h-screen bg-bg font-sans text-foreground antialiased">
        <div className="page-container flex min-h-screen items-center justify-center">
          <div className="w-full">
            <div className="mb-6 flex items-center justify-center gap-2 text-center">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-primary/30 bg-primary-muted">
                <span className="text-sm font-semibold text-primary">A</span>
              </div>
              <div className="text-left leading-none">
                <p className="text-sm font-semibold text-foreground">Aegis</p>
                <p className="mt-1 text-micro text-muted">Workbench</p>
              </div>
            </div>
            <RecoveryState
              title="The app shell failed to start"
              description="Aegis caught a root-level runtime fault before the workspace could finish loading. Retry the shell or reload the page to request a fresh bundle."
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
            />
          </div>
        </div>
      </body>
    </html>
  );
}
