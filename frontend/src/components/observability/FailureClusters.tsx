"use client";

import Link from "next/link";
import { CheckCircle2, RefreshCw } from "lucide-react";
import { SectionCard } from "@/components/ui/section-card";
import { Button } from "@/components/ui/button";
import { formatRelativeTime } from "@/lib/format-date";
import type { ObservabilityErrors } from "@/types/workflow";

interface FailureClustersProps {
  clusters: ObservabilityErrors["clusters"];
  failedRunsScanned: number;
  loading: boolean;
  /** The clusters query failed — never claim the system is clean. */
  error?: boolean;
  onRetry?: () => void;
}

/**
 * Single-column ranked list of failure clusters. One column so the horizontal
 * weight bars share a scale — each bar is count/maxCount of the row width.
 */
export function FailureClusters({
  clusters,
  failedRunsScanned,
  loading,
  error = false,
  onRetry,
}: FailureClustersProps) {
  const ranked = [...clusters].sort((a, b) => b.count - a.count).slice(0, 8);
  const maxCount = ranked.reduce((m, c) => Math.max(m, c.count), 0) || 1;

  return (
    <SectionCard
      title="Failure clusters"
      flush
      actions={
        <span className="font-mono text-2xs text-muted tabular-nums">
          {loading ? "…" : error ? "—" : `${failedRunsScanned} failed scanned`}
        </span>
      }
    >
      {loading ? (
        <p className="px-4 py-6 text-sm text-muted">Loading clusters…</p>
      ) : error ? (
        // A failed health check must never render the green all-clear below.
        <div className="flex flex-wrap items-center gap-3 px-4 py-6">
          <p className="text-sm text-destructive">Couldn&apos;t load failure clusters.</p>
          {onRetry && (
            <Button variant="outline" size="sm" onClick={onRetry}>
              <RefreshCw aria-hidden />
              Retry
            </Button>
          )}
        </div>
      ) : ranked.length === 0 ? (
        <p className="flex items-center gap-2 px-4 py-6 text-sm text-muted">
          <CheckCircle2 className="h-4 w-4 text-success" aria-hidden />
          No failure clusters in the recent window.
        </p>
      ) : (
        <ul className="divide-y divide-border">
          {ranked.map((cluster) => {
            const pct = Math.max(4, Math.round((cluster.count / maxCount) * 100));
            return (
              <li key={cluster.signature}>
                <Link
                  href={`/runs/${cluster.sample_run_id}`}
                  className="focus-ring flex gap-3 px-4 py-3 transition-colors hover:bg-surface-hover"
                >
                  <span className="shrink-0 pt-0.5 font-mono text-xs font-semibold text-destructive tabular-nums">
                    {cluster.count}×
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-mono text-xs text-foreground">
                      {cluster.signature}
                    </span>
                    <span
                      className="mt-1.5 block h-1 rounded-full bg-destructive/50"
                      style={{ width: `${pct}%` }}
                      aria-hidden
                    />
                    <span className="mt-1 block truncate text-2xs text-subtle">
                      {(cluster.workflows || []).slice(0, 3).join(", ")}
                      {cluster.last_seen
                        ? ` · ${formatRelativeTime(cluster.last_seen)}`
                        : ""}
                    </span>
                  </span>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </SectionCard>
  );
}
