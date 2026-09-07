"use client";

import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  isTerminalObservabilityEvent,
  useObservabilityStream,
  type ObservabilityStreamStatus,
} from "@/providers/ObservabilityStreamProvider";
import { Activity, CheckCircle2, Radio } from "lucide-react";
import { ApiConnectionState } from "@/components/ui/connection-state";
import { EmptyState } from "@/components/ui/empty-state";
import { Button } from "@/components/ui/button";
import { Chip } from "@/components/ui/chip";
import { FilterChip } from "@/components/ui/filter-chip";
import { LoadingState } from "@/components/ui/loading-state";
import { PageHeader } from "@/components/ui/page-header";
import { SectionCard } from "@/components/ui/section-card";
import { PageEnter } from "@/components/motion";
import { GettingStartedBanner } from "@/components/onboarding/GettingStartedBanner";
import { CostDashboard } from "@/components/observability/CostDashboard";
import { TrustDashboard } from "@/components/observability/TrustDashboard";
import { SessionsView } from "@/components/observability/SessionsView";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { queryKeys } from "@/lib/query-keys";
import { runStatusTextClass } from "@/lib/run-status";
import { formatRelativeTime } from "@/lib/format-date";
import { OpsStatRow } from "@/components/observability/OpsStatRow";
import { FailureClusters } from "@/components/observability/FailureClusters";
import {
  TriageStream,
  type StreamFilter,
} from "@/components/observability/TriageStream";
import { RunsTable } from "@/components/observability/RunsTable";
import type { RecentRun } from "@/components/observability/run-row";

type ObservabilitySummary = Awaited<ReturnType<typeof api.getObservabilitySummary>>;

type RegressionAlert = {
  id: string;
  workflow_id: string;
  workflow_name: string;
  run_id: string;
  message: string;
  latest_score?: number;
  baseline_score?: number;
  delta?: number;
};

type AttentionItem = {
  id: string;
  kind: "regression" | "failed" | "blocked" | "eval_fail" | "awaiting";
  title: string;
  detail: string;
  runId?: string;
  workflowId?: string;
  meta?: string;
};

const RUN_LIFECYCLE_EVENTS = new Set([
  "run_started",
  "run_updated",
  "run_completed",
  "run_failed",
  "run_cancelled",
]);

type ObservabilityView = "triage" | "trust" | "sessions" | "cost";

const VIEW_IDS = new Set<string>(["triage", "trust", "sessions", "cost"]);

/** Each view answers a different question — the page header has to say which. */
const VIEW_COPY: Record<ObservabilityView, string> = {
  triage: "Triage regressions, failures, and blocked runs — then open a run to dig in.",
  trust: "Quality, safety, cost, and reliability SLOs over the recent run window.",
  sessions: "Multi-turn runs grouped by session.",
  cost: "Spend, tokens, and latency by workflow, node, and model.",
};

/** Stream badge copy. "Connecting" covers the handshake and short reconnects,
 *  so a fresh page load never claims the just-fetched snapshot is stale. */
const STREAM_BADGE: Record<ObservabilityStreamStatus, { label: string; title: string }> = {
  connecting: {
    label: "Connecting…",
    title: "Connecting to the live update stream.",
  },
  live: {
    label: "Live updates",
    title: "Live updates connected.",
  },
  offline: {
    label: "Updates offline",
    title: "Live updates are offline. This view shows the last loaded snapshot.",
  },
};

function patchRecentRun(
  summary: ObservabilitySummary,
  event: Record<string, unknown>
): ObservabilitySummary {
  const runId = String(event.run_id);
  const previous = summary.recent_runs.find((row) => row.run_id === runId);
  // Merge over the existing row so live events never clobber fields they
  // don't carry (latency_ms, guardrail counts, etc.).
  const nextRun = {
    ...previous,
    run_id: runId,
    workflow_id:
      (event.workflow_id as string | null | undefined) ??
      previous?.workflow_id ??
      null,
    workflow_name:
      (event.workflow_name as string | null | undefined) ??
      previous?.workflow_name ??
      null,
    status: String(event.status || previous?.status || "running"),
    created_at: String(
      event.created_at || previous?.created_at || new Date().toISOString()
    ),
    eval_aggregate:
      typeof event.eval_aggregate === "number"
        ? event.eval_aggregate
        : previous?.eval_aggregate ?? null,
    eval_passed:
      typeof event.eval_passed === "boolean"
        ? event.eval_passed
        : previous?.eval_passed ?? null,
    latency_ms:
      typeof event.latency_ms === "number"
        ? event.latency_ms
        : previous?.latency_ms ?? null,
    guardrail_blocked:
      typeof event.guardrail_blocked === "boolean"
        ? event.guardrail_blocked
        : previous?.guardrail_blocked ?? false,
    guardrail_warn_count:
      typeof event.guardrail_warn_count === "number"
        ? event.guardrail_warn_count
        : previous?.guardrail_warn_count ?? 0,
    guardrail_fail_count:
      typeof event.guardrail_fail_count === "number"
        ? event.guardrail_fail_count
        : previous?.guardrail_fail_count ?? 0,
    trace_id:
      typeof event.trace_id === "string"
        ? event.trace_id
        : previous?.trace_id ?? null,
  };

  const recentRuns = [
    nextRun,
    ...summary.recent_runs.filter((row) => row.run_id !== runId),
  ].slice(0, 20);

  const statusCounts = { ...summary.status_counts };
  if (previous && previous.status !== nextRun.status) {
    statusCounts[previous.status] = Math.max(0, (statusCounts[previous.status] || 0) - 1);
    statusCounts[nextRun.status] = (statusCounts[nextRun.status] || 0) + 1;
  } else if (!previous) {
    statusCounts[nextRun.status] = (statusCounts[nextRun.status] || 0) + 1;
  }

  const activeRuns =
    event.type === "run_started"
      ? summary.active_runs + (previous ? 0 : 1)
      : ["run_completed", "run_failed", "run_cancelled"].includes(String(event.type))
        ? Math.max(0, summary.active_runs - 1)
        : summary.active_runs;

  return {
    ...summary,
    recent_runs: recentRuns,
    status_counts: statusCounts,
    active_runs: activeRuns,
  };
}

function buildAttentionItems(
  regressions: RegressionAlert[],
  runs: RecentRun[]
): AttentionItem[] {
  const items: AttentionItem[] = [];
  const seenRuns = new Set<string>();

  for (const alert of regressions) {
    const delta =
      alert.delta != null
        ? `${alert.delta > 0 ? "+" : ""}${alert.delta.toFixed(2)}`
        : alert.latest_score != null
          ? alert.latest_score.toFixed(2)
          : undefined;
    items.push({
      id: `reg-${alert.id}`,
      kind: "regression",
      title: `Eval regression · ${alert.workflow_name}`,
      detail: alert.message,
      runId: alert.run_id || undefined,
      workflowId: alert.workflow_id || undefined,
      meta: delta,
    });
    if (alert.run_id) seenRuns.add(alert.run_id);
  }

  for (const run of runs) {
    if (seenRuns.has(run.run_id)) continue;

    if (run.status === "awaiting_approval") {
      items.push({
        id: `await-${run.run_id}`,
        kind: "awaiting",
        title: run.workflow_name || "Workflow",
        detail: "Awaiting human approval",
        runId: run.run_id,
        workflowId: run.workflow_id ?? undefined,
        meta: formatRelativeTime(run.created_at),
      });
      seenRuns.add(run.run_id);
      continue;
    }

    if (run.guardrail_blocked) {
      items.push({
        id: `block-${run.run_id}`,
        kind: "blocked",
        title: run.workflow_name || "Workflow",
        detail: "Blocked by guardrail",
        runId: run.run_id,
        workflowId: run.workflow_id ?? undefined,
        meta: formatRelativeTime(run.created_at),
      });
      seenRuns.add(run.run_id);
      continue;
    }

    if (run.status === "failed" || run.status === "cancelled") {
      items.push({
        id: `fail-${run.run_id}`,
        kind: "failed",
        title: run.workflow_name || "Workflow",
        detail: run.status === "cancelled" ? "Cancelled" : "Failed",
        runId: run.run_id,
        workflowId: run.workflow_id ?? undefined,
        meta: formatRelativeTime(run.created_at),
      });
      seenRuns.add(run.run_id);
      continue;
    }

    if (run.eval_passed === false) {
      items.push({
        id: `eval-${run.run_id}`,
        kind: "eval_fail",
        title: run.workflow_name || "Workflow",
        detail: "Eval below threshold",
        runId: run.run_id,
        workflowId: run.workflow_id ?? undefined,
        meta:
          run.eval_aggregate != null
            ? run.eval_aggregate.toFixed(2)
            : formatRelativeTime(run.created_at),
      });
      seenRuns.add(run.run_id);
    }
  }

  return items.slice(0, 12);
}

function kindLabel(kind: AttentionItem["kind"]): string {
  switch (kind) {
    case "regression":
      return "regression";
    case "failed":
      return "failed";
    case "blocked":
      return "blocked";
    case "eval_fail":
      return "eval";
    case "awaiting":
      return "approval";
  }
}

/** Attention kinds map onto canonical run statuses so their hue comes from the
 *  one status→tone table instead of a local copy. */
const KIND_STATUS: Record<AttentionItem["kind"], string> = {
  regression: "warned",
  eval_fail: "warned",
  failed: "failed",
  blocked: "failed",
  awaiting: "awaiting_approval",
};

function kindClass(kind: AttentionItem["kind"]): string {
  return runStatusTextClass(KIND_STATUS[kind]);
}

export default function ObservabilityPage() {
  const { status: streamStatus, subscribe } = useObservabilityStream();
  const queryClient = useQueryClient();
  const refreshTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [regressionAlerts, setRegressionAlerts] = useState<RegressionAlert[]>([]);
  const [view, setView] = useState<ObservabilityView>("triage");
  const [streamFilter, setStreamFilter] = useState<StreamFilter>("failed");
  const [runSearch, setRunSearch] = useState("");
  const [searchResults, setSearchResults] = useState<RecentRun[] | null>(null);
  const [searchError, setSearchError] = useState<string | null>(null);
  const searchToken = useRef(0);

  // Honour an inbound ?view= so reloads, back/forward and shared links land on
  // the view the user was looking at. Read from window after mount (not
  // useSearchParams) so the route stays statically renderable.
  useEffect(() => {
    const incoming = new URLSearchParams(window.location.search).get("view");
    if (incoming && VIEW_IDS.has(incoming)) {
      setView(incoming as ObservabilityView);
    }
  }, []);

  const selectView = useCallback((next: ObservabilityView) => {
    setView(next);
    const params = new URLSearchParams(window.location.search);
    params.set("view", next);
    window.history.replaceState(
      null,
      "",
      `${window.location.pathname}?${params.toString()}`
    );
  }, []);

  useEffect(() => {
    const q = runSearch.trim();
    if (!q) {
      // A cleared search invalidates any in-flight response.
      searchToken.current += 1;
      setSearchResults(null);
      setSearchError(null);
      return;
    }
    const token = ++searchToken.current;
    const timer = window.setTimeout(() => {
      api
        .searchObservabilityRuns(q)
        .then((data) => {
          if (token !== searchToken.current) return;
          setSearchResults(data.recent_runs as unknown as RecentRun[]);
          setSearchError(null);
        })
        .catch((err: unknown) => {
          if (token !== searchToken.current) return;
          // Don't render a failed request as "no matches" — surface the error.
          setSearchError(err instanceof Error ? err.message : "Search failed");
        });
    }, 300);
    return () => window.clearTimeout(timer);
  }, [runSearch]);

  const {
    data: summary,
    isLoading: loading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: queryKeys.observabilitySummary,
    queryFn: api.getObservabilitySummary,
  });

  const { data: costs } = useQuery({
    queryKey: queryKeys.observabilityCosts,
    queryFn: api.getObservabilityCosts,
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

  const refreshSummary = useCallback(() => {
    void queryClient.invalidateQueries({
      queryKey: queryKeys.observabilitySummary,
    });
  }, [queryClient]);

  useEffect(() => {
    return () => {
      if (refreshTimer.current) clearTimeout(refreshTimer.current);
    };
  }, []);

  useEffect(() => {
    return subscribe((event) => {
      if (event.type === "heartbeat") return;

      // Backend backpressure signals: `events_dropped` means our subscriber
      // queue overflowed and increments were lost; `stream_end` means the
      // server closed us as a slow consumer. Either way the incremental cache
      // is now untrustworthy — reconcile with an authoritative refetch. The
      // provider handles reconnecting the socket itself.
      if (event.type === "events_dropped" || event.type === "stream_end") {
        refreshSummary();
        return;
      }

      if (event.type === "eval_regression") {
        const regression = (event.regression || {}) as Record<string, unknown>;
        const runId = String(event.run_id || "");
        setRegressionAlerts((current) => {
          const next: RegressionAlert = {
            id: runId || `${event.workflow_id}-${Date.now()}`,
            workflow_id: String(event.workflow_id || ""),
            workflow_name: String(event.workflow_name || "Workflow"),
            run_id: runId,
            message: String(regression.message || "Eval score dropped below recent average"),
            latest_score:
              typeof regression.latest_score === "number" ? regression.latest_score : undefined,
            baseline_score:
              typeof regression.baseline_score === "number" ? regression.baseline_score : undefined,
            delta: typeof regression.delta === "number" ? regression.delta : undefined,
          };
          return [next, ...current.filter((row) => row.id !== next.id)].slice(0, 8);
        });
        refreshSummary();
        return;
      }

      // Only run-lifecycle events with a run_id should touch the run rows;
      // other events (e.g. events_dropped) have no run_id and would fabricate
      // ghost "undefined" rows.
      if (!RUN_LIFECYCLE_EVENTS.has(String(event.type)) || !event.run_id) return;

      queryClient.setQueryData<ObservabilitySummary | undefined>(
        queryKeys.observabilitySummary,
        (current) => (current ? patchRecentRun(current, event) : current)
      );
      if (!isTerminalObservabilityEvent(event.type)) return;
      if (refreshTimer.current) clearTimeout(refreshTimer.current);
      refreshTimer.current = setTimeout(refreshSummary, 500);
    });
  }, [subscribe, queryClient, refreshSummary]);

  const attentionItems = useMemo(
    () => buildAttentionItems(regressionAlerts, summary?.recent_runs ?? []),
    [regressionAlerts, summary?.recent_runs]
  );

  const allRuns = useMemo(
    () => searchResults ?? summary?.recent_runs ?? [],
    [searchResults, summary?.recent_runs]
  );

  if (loading) {
    return <LoadingState label="Loading observability…" />;
  }

  if (isError) {
    return (
      <div className="page-container">
        <ApiConnectionState
          description="Observability data could not be loaded. Check the API target, then retry."
          error={error}
          onRetry={() => {
            void refetch();
          }}
        />
      </div>
    );
  }

  if (!summary) {
    return (
      <div className="page-container">
        <EmptyState
          icon={Activity}
          title="Couldn't load observability"
          description="Check your connection and try refreshing the page."
          action={
            <Button variant="outline" onClick={refreshSummary}>
              Retry
            </Button>
          }
        />
      </div>
    );
  }

  const hasCollectedTelemetry =
    summary.run_count > 0 || summary.recent_runs.length > 0 || summary.active_runs > 0;

  const liveBadge = (
    <span role="status" className="inline-flex">
      <Chip
        tone={streamStatus === "live" ? "success" : "outline"}
        title={STREAM_BADGE[streamStatus].title}
      >
        <Radio className="h-3 w-3" aria-hidden />
        {STREAM_BADGE[streamStatus].label}
      </Chip>
    </span>
  );

  // FilterChip is an aria-pressed toggle, not a tab — role="group" is the
  // honest container (same as the triage stream's filter row).
  const viewToggle = (
    <div className="flex items-center gap-1.5" role="group" aria-label="Observability view">
      <FilterChip
        label="Triage"
        active={view === "triage"}
        onClick={() => selectView("triage")}
      />
      <FilterChip
        label="Trust"
        active={view === "trust"}
        onClick={() => selectView("trust")}
      />
      <FilterChip
        label="Sessions"
        active={view === "sessions"}
        onClick={() => selectView("sessions")}
      />
      <FilterChip
        label="Cost & usage"
        active={view === "cost"}
        onClick={() => selectView("cost")}
      />
    </div>
  );

  return (
    <PageEnter className="page-container space-y-6">
      <PageHeader
        title="Observability"
        description={VIEW_COPY[view]}
        actions={
          <div className="flex flex-wrap items-center gap-2 sm:gap-3">
            {viewToggle}
            {liveBadge}
          </div>
        }
      />

      {/* Only after a sustained disconnect — a handshake or a short reconnect
          is not an outage worth a full-width banner. */}
      {streamStatus === "offline" && (
        <div
          role="status"
          className="flex items-center gap-2 rounded-lg border border-warning/30 bg-warning/10 px-3 py-2 text-xs text-muted"
        >
          <Radio className="h-3.5 w-3.5 shrink-0 text-warning" aria-hidden />
          Live updates are offline — showing the last loaded snapshot. Reload to refresh.
        </div>
      )}

      {!hasCollectedTelemetry && (
        <GettingStartedBanner
          onboardingKey="observability"
          title="Trace every decision your agent makes"
          description="Cost, tokens, latency, and eval outcomes for every run — sliced by workflow, node, and model. Run a workflow to start collecting telemetry."
          primaryHref="/workflows/new"
          primaryLabel="Create a workflow"
          secondaryHref="/templates"
          secondaryLabel="Start from a template"
        />
      )}

      {view === "cost" ? (
        <CostDashboard primaryCtaHref="/workflows/new" primaryCtaLabel="Create a workflow" />
      ) : view === "trust" ? (
        <TrustDashboard onOpenTriage={() => selectView("triage")} />
      ) : view === "sessions" ? (
        <SessionsView />
      ) : (
        <>
          <OpsStatRow summary={summary} costs={costs} />
          {/* Needs attention */}
      <SectionCard
        title="Needs attention"
        flush
        actions={
          <span className="font-mono text-2xs text-muted tabular-nums">
            {attentionItems.length}
          </span>
        }
      >
        {attentionItems.length === 0 ? (
          <p className="flex items-center gap-2 px-4 py-6 text-sm text-muted">
            <CheckCircle2 className="h-4 w-4 text-success" aria-hidden />
            Nothing to triage in the recent window.
          </p>
        ) : (
          <ul className="divide-y divide-border">
            {attentionItems.map((item) => (
              <li key={item.id}>
                <div className="flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span
                        className={cn(
                          "font-mono text-2xs uppercase tracking-wide",
                          kindClass(item.kind)
                        )}
                      >
                        {kindLabel(item.kind)}
                      </span>
                      <p className="truncate text-sm font-medium text-foreground">{item.title}</p>
                    </div>
                    <p className="mt-0.5 truncate text-xs text-muted">{item.detail}</p>
                  </div>
                  <div className="flex shrink-0 items-center gap-3">
                    {item.meta && (
                      <span className="font-mono text-2xs text-subtle">{item.meta}</span>
                    )}
                    {item.runId && (
                      <Link
                        href={`/runs/${item.runId}`}
                        className="focus-ring text-xs font-medium text-foreground underline-offset-4 hover:underline"
                      >
                        View run
                      </Link>
                    )}
                    {item.workflowId && (
                      <Link
                        href={`/workflows/${item.workflowId}`}
                        className="focus-ring text-xs text-muted underline-offset-4 hover:text-foreground hover:underline"
                      >
                        Workflow
                      </Link>
                    )}
                    {item.kind === "regression" && (
                      <button
                        type="button"
                        className="focus-ring text-xs text-subtle hover:text-muted"
                        onClick={() => {
                          const alertId = item.id.replace(/^reg-/, "");
                          setRegressionAlerts((cur) =>
                            cur.filter((a) => a.id !== alertId)
                          );
                        }}
                      >
                        Dismiss
                      </button>
                    )}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </SectionCard>

      <FailureClusters
        clusters={errors?.clusters ?? []}
        failedRunsScanned={errors?.failed_runs_scanned ?? 0}
        loading={errorsLoading}
        error={errorsIsError}
        onRetry={() => {
          void refetchErrors();
        }}
      />

      <TriageStream
        runs={summary.recent_runs}
        filter={streamFilter}
        onFilterChange={setStreamFilter}
      />

      {searchError && (
        <p className="px-1 text-xs text-destructive" role="status">
          Search failed: {searchError}
        </p>
      )}

          <RunsTable
            runs={allRuns}
            search={runSearch}
            onSearchChange={setRunSearch}
            isSearchResults={searchResults !== null}
            totalRunCount={summary.run_count}
            recentCount={summary.recent_runs.length}
          />
        </>
      )}
    </PageEnter>
  );
}
