import type { ReactNode } from "react";
import Link from "next/link";
import { Activity, AlertTriangle, PlugZap, RefreshCw, ServerCrash } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { GlassCard } from "@/components/ui/glass-card";
import { cn } from "@/lib/utils";

type ConnectionStateProps = {
  title?: string;
  description?: ReactNode;
  error?: unknown;
  onRetry?: () => void;
  className?: string;
};

function errorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  if (typeof error === "string") return error;
  return "Request failed";
}

export function ApiConnectionState({
  title = "API request failed",
  description,
  error,
  onRetry,
  className,
}: ConnectionStateProps) {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  return (
    <GlassCard className={cn("overflow-hidden p-0", className)}>
      <div className="grid gap-0 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className="flex min-w-0 flex-col justify-between gap-6 p-5 sm:p-6">
          <div className="space-y-5">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start">
              <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg border border-destructive/25 bg-destructive/10 text-destructive">
                <PlugZap className="h-5 w-5" aria-hidden="true" />
              </div>
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="destructive">Backend unavailable</Badge>
                  <Badge variant="outline">Client preserved</Badge>
                </div>
                <h1 className="mt-3 text-2xl font-semibold tracking-tight text-foreground sm:text-[28px]">
                  {title}
                </h1>
                <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">
                  {description ??
                    "This view depends on backend data. Start the API on the target below, then retry."}
                </p>
              </div>
            </div>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row">
            {onRetry && (
              <Button type="button" onClick={onRetry}>
                <RefreshCw className="mr-2 h-4 w-4" />
                Retry
              </Button>
            )}
            <Button asChild variant="outline">
              <Link href="/">Workflows</Link>
            </Button>
          </div>
        </div>

        <div className="border-t border-border bg-surface-input p-5 lg:border-l lg:border-t-0">
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <ServerCrash className="h-4 w-4 text-warning" aria-hidden="true" />
              <p className="text-2xs font-medium uppercase tracking-wider text-muted">
                Connection detail
              </p>
            </div>
            <div className="rounded-md border border-border bg-background px-3 py-3">
              <div className="flex items-center gap-2 text-2xs text-muted">
                <Activity className="h-3.5 w-3.5" aria-hidden="true" />
                API target
              </div>
              <p className="mt-2 break-all font-mono text-sm text-foreground">{apiUrl}</p>
            </div>
            <div className="rounded-md border border-border bg-background px-3 py-3">
              <div className="flex items-center gap-2 text-2xs text-muted">
                <AlertTriangle className="h-3.5 w-3.5 text-destructive" aria-hidden="true" />
                Error
              </div>
              <p className="mt-2 text-sm leading-6 text-muted">{errorMessage(error)}</p>
            </div>
            <p className="text-xs leading-5 text-subtle">
              The frontend is still available. Retry after the API is reachable.
            </p>
          </div>
        </div>
      </div>
    </GlassCard>
  );
}
