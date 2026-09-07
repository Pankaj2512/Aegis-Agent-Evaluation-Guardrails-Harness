"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Activity } from "lucide-react";
import { StaggerList } from "@/components/motion";
import { EmptyState } from "@/components/ui/empty-state";
import { SectionCard } from "@/components/ui/section-card";
import { api } from "@/lib/api";
import { formatRelativeTime } from "@/lib/format-date";
import { queryKeys } from "@/lib/query-keys";
import { useNow } from "@/hooks/use-now";
import { cn } from "@/lib/utils";

/** Number of recent runs to surface in the rail. */
const MAX_ROWS = 12;

function statusDotClass(status: string): string {
  const s = status.toLowerCase();
  if (s === "completed" || s === "success" || s === "passed") return "bg-success/80";
  if (s === "failed" || s === "error" || s === "cancelled") return "bg-destructive/80";
  if (s === "running" || s === "pending" || s === "queued" || s === "waiting")
    return "bg-warning/80";
  return "bg-muted/80";
}

export function RecentActivityRail() {
  // Shares the summary query with the overview strip. "No runs yet" is a claim
  // about the user's history, so it may only render once the request actually
  // succeeded — never while loading and never on failure.
  const { data: summary, isLoading, isError } = useQuery({
    queryKey: queryKeys.observabilitySummary,
    queryFn: api.getObservabilitySummary,
    retry: 1,
    staleTime: 30_000,
  });

  const now = useNow();
  const runs = (summary?.recent_runs ?? []).slice(0, MAX_ROWS);

  return (
    <SectionCard title="Recent activity" description="Latest runs across all workflows" flush>
      {isError ? (
        <p className="px-3 py-6 text-center text-xs text-muted">
          Couldn&apos;t load recent activity.
        </p>
      ) : isLoading ? (
        <p className="px-3 py-6 text-center text-xs text-muted">Loading recent activity…</p>
      ) : runs.length === 0 ? (
        <div className="p-3">
          <EmptyState
            icon={Activity}
            title="No runs yet"
            description="Trigger a workflow to see run activity here."
            compact
          />
        </div>
      ) : (
        <StaggerList className="divide-y divide-border" max={MAX_ROWS}>
          {runs.map((run) => {
            const when = run.created_at ? formatRelativeTime(run.created_at, now) : "—";
            return (
              <Link
                key={run.run_id}
                href={`/runs/${run.run_id}`}
                className={cn(
                  "group flex items-center gap-2.5 px-3 py-2 transition-colors",
                  "hover:bg-surface-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary/30"
                )}
              >
                <span
                  className={cn("h-1.5 w-1.5 shrink-0 rounded-full", statusDotClass(run.status))}
                  aria-hidden
                />
                <span className="min-w-0 flex-1 truncate text-xs text-foreground">
                  {run.workflow_name || "Untitled workflow"}
                </span>
                <span className="shrink-0 font-mono text-2xs text-muted tabular-nums">{when}</span>
              </Link>
            );
          })}
        </StaggerList>
      )}
    </SectionCard>
  );
}
