"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Activity, DollarSign, ShieldCheck, Workflow } from "lucide-react";
import { NumberTween } from "@/components/motion";
import { Sparkline } from "@/components/ui/sparkline";
import { StatCard } from "@/components/ui/stat-card";
import { api } from "@/lib/api";
import { formatCostUsd } from "@/lib/format";
import { queryKeys } from "@/lib/query-keys";
import { timeBuckets } from "@/lib/time-buckets";
import { partitionByLifecycle } from "@/lib/workflow-lifecycle";
import type { WorkflowListItem } from "@/types/workflow";

/** Number of sparkline buckets for the run-volume mini chart. */
const RUN_BUCKETS = 20;

const DASH = <span className="text-muted">—</span>;

export function HomeOverviewStrip({ workflows }: { workflows: WorkflowListItem[] }) {
  // Observability queries degrade to "—"/no-chart on error and never block or
  // error-flash the lifecycle board below (that board owns the workflows query).
  const summaryQuery = useQuery({
    queryKey: queryKeys.observabilitySummary,
    queryFn: api.getObservabilitySummary,
    retry: 1,
    staleTime: 30_000,
  });
  const costsQuery = useQuery({
    queryKey: queryKeys.observabilityCosts,
    queryFn: api.getObservabilityCosts,
    retry: 1,
    staleTime: 30_000,
  });
  const runsQuery = useQuery({
    queryKey: ["observability-runs", 100],
    queryFn: () => api.listObservabilityRuns(100),
    retry: 1,
    staleTime: 30_000,
  });

  const summary = summaryQuery.data;
  const costs = costsQuery.data;

  const liveCount = useMemo(
    () => partitionByLifecycle(workflows).published.length,
    [workflows]
  );

  const runSampleCount = runsQuery.data?.recent_runs?.length ?? 0;

  const runVolume = useMemo(() => {
    const rows = runsQuery.data?.recent_runs ?? [];
    if (rows.length === 0) return [] as number[];
    const stamped = rows.map((r) => ({
      created_at: typeof r.created_at === "string" ? r.created_at : null,
    }));
    return timeBuckets(stamped, RUN_BUCKETS);
  }, [runsQuery.data]);

  const passTrend = useMemo(() => {
    const trend = summary?.quality.eval_trend ?? [];
    return trend
      .map((t) => t.aggregate)
      .filter((n): n is number => typeof n === "number" && Number.isFinite(n));
  }, [summary]);

  const passRate = summary?.quality.eval_pass_rate ?? null;
  const evalRunCount = summary?.quality.eval_run_count ?? 0;
  // A pass rate needs verdicts, and verdicts need thresholds. Scored-but-
  // unjudged runs must say so — "—" over "15 eval runs" reads as broken data.
  const evalsUnjudged = passRate == null && evalRunCount > 0;

  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      {/* Workflows — from the already-loaded list; no network of its own. */}
      <StatCard
        label="Workflows"
        icon={Workflow}
        value={<NumberTween value={workflows.length} />}
        trend={`${liveCount} live`}
      />

      {/* Runs — count + volume sparkline over the last 100 runs. */}
      <StatCard
        label="Runs"
        icon={Activity}
        value={
          summary ? <NumberTween value={summary.run_count} /> : DASH
        }
        chart={
          runSampleCount >= 2 && runVolume.length >= 2 ? (
            <Sparkline
              data={runVolume}
              label="Run volume over recent runs"
              fill
              className="text-primary/70"
            />
          ) : undefined
        }
        trend={
          summary
            ? `${summary.active_runs} active · last 100 runs`
            : undefined
        }
      />

      {/* Pass rate — eval pass rate + aggregate trend sparkline. */}
      <StatCard
        label="Pass rate"
        icon={ShieldCheck}
        value={
          passRate != null ? (
            <span className="text-success">
              <NumberTween value={passRate * 100} suffix="%" />
            </span>
          ) : (
            DASH
          )
        }
        chart={
          passTrend.length >= 2 ? (
            <Sparkline
              data={passTrend}
              label="Eval pass-rate trend"
              showLastDot
              className="text-success"
            />
          ) : undefined
        }
        trend={
          summary
            ? evalsUnjudged
              ? `${evalRunCount} scored · no pass/fail thresholds set`
              : `${evalRunCount} eval runs`
            : undefined
        }
      />

      {/* Cost — no time series exists, so no sparkline. */}
      <StatCard
        label="Cost"
        icon={DollarSign}
        value={costs ? formatCostUsd(costs.total_cost_usd) : DASH}
        trend={
          costs ? `last ${costs.runs_scanned} runs scanned` : undefined
        }
      />
    </div>
  );
}
