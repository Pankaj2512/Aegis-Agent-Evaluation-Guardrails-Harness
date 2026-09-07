"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ShieldCheck } from "lucide-react";
import { StatCard } from "@/components/ui/stat-card";
import { SectionCard } from "@/components/ui/section-card";
import { Sparkline } from "@/components/ui/sparkline";
import { LoadingState } from "@/components/ui/loading-state";
import { EmptyState } from "@/components/ui/empty-state";
import { Button } from "@/components/ui/button";
import { SeverityBar } from "@/components/ui/severity-bar";
import { ApiConnectionState } from "@/components/ui/connection-state";
import { FailureClusters } from "@/components/observability/FailureClusters";
import { ViolationBreakdown } from "@/components/observability/ViolationBreakdown";
import { formatCostUsd, formatDurationMs, formatTokens } from "@/lib/format";
import { queryKeys } from "@/lib/query-keys";
import { api } from "@/lib/api";

/** Percentage label from a 0..1 rate. */
function pct(rate: number | null): string {
  return rate == null ? "—" : `${Math.round(rate * 100)}%`;
}

/** Higher-is-better tone (eval pass rate). */
function highTone(rate: number | null): string {
  if (rate == null) return "text-foreground";
  if (rate >= 0.9) return "text-success";
  if (rate >= 0.7) return "text-warning";
  return "text-destructive";
}

/** Lower-is-better tone (failure rate). */
function lowTone(rate: number | null, good: number, warn: number): string {
  if (rate == null) return "text-foreground";
  if (rate <= good) return "text-success";
  if (rate <= warn) return "text-warning";
  return "text-destructive";
}

/**
 * The unified Trust surface: quality + safety + cost + reliability on one
 * screen. Every SLO rate is read from a single consistent-window endpoint
 * (build_trust), so tiles never mix recent and all-time denominators. Chroma
 * stays data-only (eval pass / guardrail severity / failure); chrome stays mono.
 */
export function TrustDashboard({ onOpenTriage }: { onOpenTriage?: () => void } = {}) {
  const { data: trust, isLoading, isError, error, refetch } = useQuery({
    queryKey: queryKeys.trustDashboard(""),
    queryFn: api.getObservabilityTrust,
    refetchInterval: 60_000,
  });

  const {
    data: errors,
    isLoading: errorsLoading,
    isError: errorsIsError,
    refetch: refetchErrors,
  } = useQuery({
    queryKey: queryKeys.observabilityErrors,
    queryFn: api.getObservabilityErrors,
    refetchInterval: 60_000,
  });

  if (isLoading) {
    return <LoadingState label="Loading trust metrics…" />;
  }

  // Without this branch a rejected /trust left the whole tab on the loading
  // copy forever — an error dressed up as work in progress.
  if (isError || !trust) {
    return (
      <ApiConnectionState
        description="Trust metrics could not be loaded. Check the API target, then retry."
        error={error}
        onRetry={() => {
          void refetch();
        }}
      />
    );
  }

  const scanned = trust.runs_scanned;
  const g = trust.guardrail_events;
  const eventTotal = g.passed + g.warned + g.failed;
  const topCost = trust.top_workflows_by_cost ?? [];
  const windowLabel = `last ${scanned.toLocaleString()} runs`;

  // Nothing has ever been scanned — dash tiles over "last 0 runs" read as a
  // broken dashboard rather than an empty one.
  if (scanned === 0 && g.total === 0) {
    return (
      <EmptyState
        icon={ShieldCheck}
        title="Run a workflow to start building trust metrics"
        description="Eval pass rates, guardrail verdicts, latency percentiles, and spend all populate from real runs. Nothing has been scanned yet."
        action={
          <Button asChild>
            <Link href="/workflows/new">Build a workflow</Link>
          </Button>
        }
      />
    );
  }

  return (
    <div className="space-y-5">
      {/* One window for every headline tile — stated out loud so the numbers
          here can be compared against the Triage / Cost tabs. */}
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-micro">Trust SLOs</p>
        <p className="font-mono text-2xs tabular-nums text-subtle">Window: {windowLabel}</p>
      </div>

      {/* SLO tiles — all rates over the same recent-run window. */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        <StatCard
          label="Eval pass rate"
          value={
            <span className={highTone(trust.eval_pass_rate)}>{pct(trust.eval_pass_rate)}</span>
          }
          trend={
            trust.eval_pass_rate != null
              ? `${trust.eval_passed}/${trust.eval_passed + (trust.eval_failed ?? 0)} judged · ${windowLabel}`
              : trust.eval_evaluated > 0
                ? `${trust.eval_evaluated} scored · no pass/fail thresholds set`
                : windowLabel
          }
          chart={
            trust.eval_trend.length >= 2 ? (
              <Sparkline
                data={trust.eval_trend}
                label="Eval score trend over recent runs"
                className="text-success"
                showLastDot
              />
            ) : undefined
          }
        />
        <StatCard
          label="Guardrail block rate"
          value={pct(trust.guardrail_block_rate)}
          trend={`${trust.guardrail_blocked_runs} blocked · ${g.warned} warned`}
        />
        <StatCard
          label="Latency p99"
          value={formatDurationMs(trust.latency_p99_ms)}
          trend={`p95 ${formatDurationMs(trust.latency_p95_ms)} · p50 ${formatDurationMs(
            trust.latency_p50_ms
          )}`}
        />
        <StatCard
          label="Cost total"
          value={formatCostUsd(trust.total_cost_usd)}
          trend={windowLabel}
        />
        <StatCard
          className="col-span-2 sm:col-span-1"
          label="Failure rate"
          value={
            <span className={lowTone(trust.failure_rate, 0.02, 0.1)}>
              {pct(trust.failure_rate)}
            </span>
          }
          trend={`${trust.failed_runs} failed of ${scanned.toLocaleString()}`}
        />
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        {/* Quality pillar */}
        <SectionCard title="Quality" description={`LLM-judge evaluation · ${windowLabel}`}>
          <div className="space-y-4">
            <div className="flex items-baseline gap-4">
              <div>
                <p className="font-mono text-2xl font-semibold tabular-nums text-foreground">
                  {pct(trust.eval_pass_rate)}
                </p>
                <p className="text-2xs text-muted">pass rate</p>
              </div>
              <div className="flex gap-3 font-mono text-2xs tabular-nums text-subtle">
                <span className="text-success">{trust.eval_passed} pass</span>
                <span className="text-destructive">{trust.eval_failed ?? 0} fail</span>
                {trust.avg_eval != null && <span>avg {trust.avg_eval.toFixed(2)}</span>}
              </div>
            </div>
            {trust.eval_evaluated === 0 && (
              <p className="text-sm text-subtle">No evaluation scores in this window.</p>
            )}
            {trust.eval_evaluated > 0 &&
              trust.eval_pass_rate == null &&
              (trust.eval_failed ?? 0) === 0 &&
              trust.eval_passed === 0 && (
                <p className="text-sm text-subtle">
                  {trust.eval_evaluated} scored · no pass/fail thresholds set
                </p>
              )}
          </div>
        </SectionCard>

        {/* Safety pillar */}
        <SectionCard
          title="Safety"
          description={`Guardrail verdicts · ${windowLabel}`}
          actions={<ShieldCheck className="h-4 w-4 text-muted" aria-hidden />}
        >
          <div className="space-y-4">
            <div className="flex items-baseline gap-4">
              <div>
                <p className="font-mono text-2xl font-semibold tabular-nums text-foreground">
                  {g.total.toLocaleString()}
                </p>
                <p className="text-2xs text-muted">guardrail events</p>
              </div>
              <div className="font-mono text-2xs tabular-nums text-destructive">
                {trust.guardrail_blocked_runs} blocked runs
              </div>
            </div>
            {eventTotal > 0 ? (
              <div className="space-y-1.5">
                <SeverityBar passed={g.passed} warned={g.warned} failed={g.failed} />
                <div className="flex flex-wrap gap-3 font-mono text-2xs tabular-nums">
                  <span className="text-success">{g.passed} passed</span>
                  <span className="text-warning">{g.warned} warned</span>
                  <span className="text-destructive">{g.failed} failed</span>
                </div>
              </div>
            ) : (
              <p className="text-sm text-subtle">No guardrail events in this window.</p>
            )}
          </div>
        </SectionCard>
      </div>

      {/* Safety drill-down — guardrail violations by rail type + recent log. */}
      <ViolationBreakdown />

      {/* Reliability pillar — reuse the failure-clustering surface. */}
      <FailureClusters
        clusters={errors?.clusters ?? []}
        failedRunsScanned={errors?.failed_runs_scanned ?? 0}
        loading={errorsLoading}
        error={errorsIsError}
        onRetry={() => {
          void refetchErrors();
        }}
      />

      {/* Cost & latency pillar */}
      <SectionCard
        title="Cost & latency"
        description={`Spend and speed · ${windowLabel}`}
        actions={
          <span className="font-mono text-2xs tabular-nums text-subtle">
            {scanned.toLocaleString()} runs
          </span>
        }
      >
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div>
              <p className="text-2xs text-muted">Total cost</p>
              <p className="font-mono text-lg tabular-nums text-foreground">
                {formatCostUsd(trust.total_cost_usd)}
              </p>
            </div>
            <div>
              <p className="text-2xs text-muted">Total tokens</p>
              <p className="font-mono text-lg tabular-nums text-foreground">
                {formatTokens(trust.total_tokens)}
              </p>
            </div>
            <div>
              <p className="text-2xs text-muted">Latency p95</p>
              <p className="font-mono text-lg tabular-nums text-foreground">
                {formatDurationMs(trust.latency_p95_ms)}
              </p>
            </div>
            <div>
              <p className="text-2xs text-muted">Latency p99</p>
              <p className="font-mono text-lg tabular-nums text-foreground">
                {formatDurationMs(trust.latency_p99_ms)}
              </p>
            </div>
          </div>
          {topCost.length > 0 && (
            <ul className="divide-y divide-border rounded-md border border-border">
              {topCost.slice(0, 5).map((row) => (
                <li
                  key={row.workflow}
                  className="flex items-center justify-between gap-3 px-3 py-2"
                >
                  <span className="min-w-0 truncate text-sm text-foreground">{row.workflow}</span>
                  <span className="flex shrink-0 items-center gap-3 font-mono text-2xs tabular-nums text-subtle">
                    <span>{row.runs} runs</span>
                    {row.failures > 0 && (
                      <span className="text-destructive">{row.failures} failed</span>
                    )}
                    <span className="text-foreground">{formatCostUsd(row.cost_usd)}</span>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </SectionCard>

      <p className="text-2xs text-subtle">
        Drill into per-run traces from the{" "}
        {onOpenTriage ? (
          <button
            type="button"
            onClick={onOpenTriage}
            className="focus-ring underline-offset-4 hover:underline"
          >
            Triage run list
          </button>
        ) : (
          <Link
            href="/observability?view=triage"
            className="focus-ring underline-offset-4 hover:underline"
          >
            Triage run list
          </Link>
        )}{" "}
        to see eval scores and guardrail verdicts on the glass-box timeline.
      </p>
    </div>
  );
}
