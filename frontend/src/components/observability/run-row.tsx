"use client";

import Link from "next/link";
import { memo, useMemo } from "react";
import { ArrowDownRight, ArrowUpRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { useNow } from "@/hooks/use-now";
import { formatFullTimestamp, formatRelativeTime } from "@/lib/format-date";
import { formatDurationMs } from "@/lib/format";
import { runStatusDotClass, runStatusLabel } from "@/lib/run-status";
import { Sparkline } from "@/components/ui/sparkline";
import type { api } from "@/lib/api";

type ObservabilitySummary = Awaited<ReturnType<typeof api.getObservabilitySummary>>;
export type RecentRun = ObservabilitySummary["recent_runs"][number];

/**
 * Braintrust-style column summary for the eval column: mean, a tiny trend
 * sparkline, and a semantic delta glyph (first→last direction). Computed from
 * whatever rows are in memory; renders nothing without >=2 scored runs.
 */
function EvalColumnSummary({ runs }: { runs: RecentRun[] }) {
  const summary = useMemo(() => {
    // Rows arrive newest-first; reverse to oldest→newest for a readable trend.
    const series = runs
      .map((r) => r.eval_aggregate)
      .filter((v): v is number => typeof v === "number" && Number.isFinite(v))
      .reverse();
    if (series.length < 2) return null;
    const mean = series.reduce((a, b) => a + b, 0) / series.length;
    const delta = series[series.length - 1] - series[0];
    return { series, mean, delta };
  }, [runs]);

  // No scored runs in memory → keep the plain column label.
  if (!summary) return <span>eval · lat</span>;
  const { series, mean, delta } = summary;
  const flat = Math.abs(delta) < 0.005;

  return (
    <span className="flex items-center gap-1.5 normal-case tracking-normal">
      <span className="tabular-nums text-muted">{mean.toFixed(2)}</span>
      <Sparkline
        data={series}
        label={`Eval score trend, mean ${mean.toFixed(2)}`}
        width={40}
        height={14}
        strokeWidth={1.25}
        className="text-subtle"
      />
      {!flat &&
        (delta > 0 ? (
          <ArrowUpRight className="h-3 w-3 text-success" aria-label="trending up" />
        ) : (
          <ArrowDownRight className="h-3 w-3 text-destructive" aria-label="trending down" />
        ))}
    </span>
  );
}

/** Column-header row so the mono run columns read as a table. */
export function RunColumnHeader({ runs }: { runs?: RecentRun[] }) {
  return (
    <div className="flex items-center gap-3 border-b border-border bg-surface px-3 py-1.5 font-mono text-2xs uppercase tracking-wide text-subtle sm:px-4">
      <span className="w-1.5 shrink-0" aria-hidden />
      <span className="min-w-0 flex-1">workflow</span>
      <span className="hidden w-16 shrink-0 sm:inline">id</span>
      <span className="w-16 shrink-0">status</span>
      <span className="w-16 shrink-0 text-right">time</span>
      <span className="hidden shrink-0 items-center justify-end gap-1.5 text-right sm:flex sm:min-w-[3.5rem]">
        {runs ? <EvalColumnSummary runs={runs} /> : <span>eval · lat</span>}
      </span>
    </div>
  );
}

export const StreamRunRow = memo(function StreamRunRow({ run }: { run: RecentRun }) {
  const now = useNow();
  return (
    <Link
      href={`/runs/${run.run_id}`}
      className="focus-ring flex min-h-[48px] items-center gap-3 border-b border-border-mid px-3 py-2.5 text-sm transition-[background-color,box-shadow] duration-1 ease-out hover:bg-surface-hover hover:shadow-[inset_2px_0_0_0_var(--border-strong)] sm:px-4"
    >
      <span
        className={cn("h-1.5 w-1.5 shrink-0 rounded-full", runStatusDotClass(run.status))}
        aria-hidden
      />
      <span className="min-w-0 flex-1 truncate font-medium text-foreground">
        {run.workflow_name || "Workflow"}
      </span>
      <span className="hidden w-16 shrink-0 font-mono text-2xs tabular-nums text-subtle sm:inline">
        {run.run_id.slice(0, 8)}
      </span>
      <span className="w-16 shrink-0 font-mono text-2xs text-muted">
        {runStatusLabel(run.status)}
      </span>
      <time
        className="w-16 shrink-0 text-right font-mono text-2xs tabular-nums text-subtle"
        dateTime={run.created_at}
        title={formatFullTimestamp(run.created_at)}
      >
        {formatRelativeTime(run.created_at, now)}
      </time>
      <span className="hidden w-14 shrink-0 text-right font-mono text-2xs tabular-nums text-muted sm:inline">
        {run.eval_aggregate != null
          ? run.eval_aggregate.toFixed(2)
          : formatDurationMs(run.latency_ms)}
      </span>
    </Link>
  );
});
