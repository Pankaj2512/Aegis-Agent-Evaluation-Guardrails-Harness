"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Activity, ArrowLeft, Download, ThumbsDown, ThumbsUp } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ApiConnectionState } from "@/components/ui/connection-state";
import { SectionCard } from "@/components/ui/section-card";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { EvalScoresChart } from "@/components/results/EvalScoresChart";
import { GuardrailEventsPanel } from "@/components/results/GuardrailEventsPanel";
import { TraceIdBadge } from "@/components/observability/TraceIdBadge";
import { TraceTimeline } from "@/components/runs/TraceTimeline";
import { ExplainFailureCallout } from "@/components/runs/ExplainFailureCallout";
import { api } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import { formatCostUsd, formatDurationMs } from "@/lib/format";
import { formatFullTimestamp, formatRelativeTime } from "@/lib/format-date";
import { runStatusLabel, runStatusVariant } from "@/lib/run-status";
import type { EvalScores, LlmCall, NodeResult, WorkflowRun } from "@/types/workflow";

function mergeNodeResult(existing: NodeResult[], event: Record<string, unknown>): NodeResult[] {
  const nodeId = String(event.node_id);
  const next: NodeResult = {
    id: nodeId,
    node_id: nodeId,
    node_type: "unknown",
    node_label: String(event.node_label || nodeId),
    status: (event.status as string | undefined) ?? "completed",
    output: (event.output as string | null | undefined) ?? null,
    evaluation_scores: (event.evaluation_scores as Record<string, unknown> | null) ?? null,
    guardrail_status: (event.guardrail_status as string | null) ?? null,
    latency_ms: (event.latency_ms as number | null) ?? null,
  };
  const without = existing.filter((item) => item.node_id !== nodeId);
  return [...without, next];
}

function formatDuration(start?: string | null, end?: string | null) {
  if (!start || !end) return "—";
  const durationMs = new Date(end).getTime() - new Date(start).getTime();
  if (!Number.isFinite(durationMs) || durationMs < 0) return "—";
  return formatDurationMs(durationMs);
}

export function RunDetailView({ runId }: { runId: string }) {
  const router = useRouter();
  const [run, setRun] = useState<WorkflowRun | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<unknown>(null);
  const [traceUiBase, setTraceUiBase] = useState<string | null>(null);
  const [llmCalls, setLlmCalls] = useState<LlmCall[]>([]);
  const [feedbackGiven, setFeedbackGiven] = useState<1 | -1 | null>(null);
  // In-flight approval decision — gates BOTH buttons so a double-click (or an
  // Approve-then-Reject) can't race two contradictory decisions on the gate.
  const [deciding, setDeciding] = useState<"approve" | "reject" | null>(null);
  const streamAttached = useRef(false);
  const [statusAnnouncement, setStatusAnnouncement] = useState("");
  const prevStatusRef = useRef<string | null>(null);

  useEffect(() => {
    if (!run?.status) return;
    if (prevStatusRef.current && prevStatusRef.current !== run.status) {
      setStatusAnnouncement(`Run status: ${runStatusLabel(run.status)}`);
    }
    prevStatusRef.current = run.status;
  }, [run?.status]);

  useEffect(() => {
    if (!run?.status || ["pending", "running"].includes(run.status)) return;
    api
      .getRunLlmCalls(runId)
      .then(setLlmCalls)
      .catch(() => setLlmCalls([]));
  }, [runId, run?.status]);

  // Real span geometry for the true waterfall. Fetched once the run has
  // loaded; refetched when a live run settles into a terminal status so the
  // axis reflects final offsets/durations.
  const runStatus = run?.status;
  const timelineQuery = useQuery({
    queryKey: queryKeys.runTimeline(runId),
    queryFn: () => api.getRunTimeline(runId),
    enabled: Boolean(run),
    retry: 1,
    staleTime: 30_000,
  });
  // Nested trace tree (node → llm_call / tool_call) for the agent-step
  // drill-down; only meaningful once the run is terminal (spans are persisted
  // at finalization), so it is gated on a non-live run.
  const traceQuery = useQuery({
    queryKey: queryKeys.runTrace(runId),
    queryFn: () => api.getRunTrace(runId),
    enabled: Boolean(run),
    retry: 1,
    staleTime: 30_000,
  });
  const { refetch: refetchTimeline } = timelineQuery;
  const { refetch: refetchTrace } = traceQuery;
  useEffect(() => {
    if (!runStatus) return;
    if (["completed", "failed", "cancelled"].includes(runStatus)) {
      refetchTimeline();
      refetchTrace();
    }
  }, [runStatus, refetchTimeline, refetchTrace]);

  const applyStreamEvent = useCallback((event: Record<string, unknown>) => {
    setRun((current) => {
      if (!current) return current;

      if (event.type === "node_completed") {
        return {
          ...current,
          node_results: mergeNodeResult(current.node_results || [], event),
        };
      }

      if (event.type === "run_started" && typeof event.trace_id === "string") {
        return {
          ...current,
          metrics_json: {
            ...(current.metrics_json || {}),
            trace_id: event.trace_id,
          },
        };
      }

      if (event.type === "run_completed") {
        return {
          ...current,
          status: "completed",
          final_output: (event.final_output as string | null) ?? current.final_output,
          metrics_json: (event.metrics as Record<string, unknown> | null) ?? current.metrics_json,
          node_results:
            (event.node_results as NodeResult[] | undefined) ?? current.node_results,
        };
      }

      if (event.type === "run_failed") {
        return {
          ...current,
          status: "failed",
          final_output: String(event.error || current.final_output || "Workflow failed"),
        };
      }

      if (event.type === "run_cancelled") {
        return { ...current, status: "cancelled" };
      }

      if (event.type === "approval_required") {
        const pending = {
          node_id: String(event.node_id || ""),
          review: String(event.review || ""),
        };
        return {
          ...current,
          status: "awaiting_approval",
          metrics_json: {
            ...(current.metrics_json || {}),
            pending_approval: pending,
          },
        };
      }

      return current;
    });
  }, []);

  const loadRun = useCallback((signal?: AbortSignal) => {
    setLoading(true);
    setLoadError(null);
    Promise.all([
      api.getRun(runId, signal ? { signal } : undefined),
      api.getTracingConfig().catch(() => null),
    ])
      .then(([runData, tracing]) => {
        setRun(runData);
        setTraceUiBase(tracing?.ui_base_url ?? null);
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        if (error instanceof Error && error.name === "AbortError") return;
        setRun(null);
        setLoadError(error);
      })
      .finally(() => {
        if (!signal?.aborted) {
          setLoading(false);
        }
      });
  }, [runId]);

  useEffect(() => {
    const controller = new AbortController();
    loadRun(controller.signal);
    return () => controller.abort();
  }, [loadRun]);

  const streamableStatus = run?.status;
  const [streamEpoch, setStreamEpoch] = useState(0);
  // Debounce reconnect toasts — while the backend is unreachable the stream
  // loops every ~3s; surface the warning at most once per 30s.
  const lastDisconnectToastAt = useRef(0);

  useEffect(() => {
    if (
      !streamableStatus ||
      !["pending", "running", "awaiting_approval"].includes(streamableStatus)
    ) {
      streamAttached.current = false;
      return;
    }
    if (streamAttached.current) return;
    streamAttached.current = true;

    const stream = api.streamRun(
      runId,
      applyStreamEvent,
      () => {
        streamAttached.current = false;
        setStreamEpoch((n) => n + 1);
        const now = Date.now();
        if (now - lastDisconnectToastAt.current >= 30_000) {
          lastDisconnectToastAt.current = now;
          toast.error("Lost connection to run stream");
        }
      }
    );

    return () => {
      stream.close();
      streamAttached.current = false;
    };
  }, [runId, streamableStatus, applyStreamEvent, streamEpoch]);

  if (loading) {
    return <RunDetailSkeleton />;
  }

  if (loadError) {
    return (
      <div className="page-container">
        <ApiConnectionState
          title="Run request failed"
          description="Run details could not be loaded. Check the API target, then retry."
          error={loadError}
          onRetry={() => loadRun()}
        />
      </div>
    );
  }

  if (!run) {
    return (
      <div className="page-container">
        <EmptyState
          icon={Activity}
          title="Run not found"
          description="This run may have been deleted or you may not have access."
          action={
            <Button asChild variant="outline">
              <Link href="/">Back to workflows</Link>
            </Button>
          }
        />
      </div>
    );
  }

  const guardrailEvents =
    (run.metrics_json?.guardrail_events as Array<{
      node_id: string;
      node_label?: string;
      status: string;
      message?: string;
    }>) || [];
  const hasGuardrails =
    guardrailEvents.length > 0 ||
    ((run.metrics_json?.failed_guardrails as string[] | undefined)?.length ?? 0) > 0;
  const evalPassed = run.metrics_json?.eval_passed;
  const metrics = run.metrics_json || {};
  const nodeResults = run.node_results || [];
  const duration = formatDuration(run.started_at, run.completed_at);
  const evalAggregate =
    typeof metrics.eval_aggregate === "number" ? metrics.eval_aggregate : null;
  const failedGuardrails = (metrics.failed_guardrails as string[] | undefined) || [];
  const resultCount = nodeResults.length;

  return (
    <div className="page-container space-y-6">
      <p className="sr-only" aria-live="polite" aria-atomic="true">
        {statusAnnouncement || `Run status: ${runStatusLabel(run.status)}`}
      </p>
      <PageHeader
        title="Run details"
        description={<span className="font-mono text-xs text-muted">{run.id}</span>}
        actions={
          <>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                if (typeof window !== "undefined" && window.history.length > 1) {
                  router.back();
                } else {
                  router.push("/observability");
                }
              }}
            >
              <ArrowLeft className="h-4 w-4" />
              Back
            </Button>
            <div className="flex items-center gap-1 rounded-md border border-border p-0.5">
              <button
                type="button"
                aria-label="Good result"
                aria-pressed={feedbackGiven === 1}
                title="Good result"
                disabled={feedbackGiven !== null}
                onClick={() => {
                  setFeedbackGiven(1);
                  api
                    .submitFeedback({ run_id: run.id, rating: 1 })
                    .then(() => toast.success("Feedback recorded"))
                    .catch(() => {
                      setFeedbackGiven(null);
                      toast.error("Failed to record feedback");
                    });
                }}
                className={`rounded px-2 py-1 transition-colors ${
                  feedbackGiven === 1 ? "bg-success/15 text-success" : "text-muted hover:text-foreground"
                } focus-ring disabled:cursor-default`}
              >
                <ThumbsUp className="h-4 w-4" aria-hidden />
              </button>
              <button
                type="button"
                aria-label="Bad result"
                aria-pressed={feedbackGiven === -1}
                title="Bad result"
                disabled={feedbackGiven !== null}
                onClick={() => {
                  setFeedbackGiven(-1);
                  api
                    .submitFeedback({ run_id: run.id, rating: -1 })
                    .then(() => toast.success("Feedback recorded"))
                    .catch(() => {
                      setFeedbackGiven(null);
                      toast.error("Failed to record feedback");
                    });
                }}
                className={`rounded px-2 py-1 transition-colors ${
                  feedbackGiven === -1 ? "bg-destructive/15 text-destructive" : "text-muted hover:text-foreground"
                } focus-ring disabled:cursor-default`}
              >
                <ThumbsDown className="h-4 w-4" aria-hidden />
              </button>
            </div>
            <Badge variant={runStatusVariant(run.status)}>{runStatusLabel(run.status)}</Badge>
            {typeof run.metrics_json?.trace_id === "string" && (
              <TraceIdBadge
                traceId={run.metrics_json.trace_id}
                uiBaseUrl={traceUiBase}
              />
            )}
            <Button
              variant="outline"
              onClick={async () => {
                try {
                  const blob = await api.exportRun(runId);
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement("a");
                  a.href = url;
                  a.download = `run-${runId}.json`;
                  a.click();
                  URL.revokeObjectURL(url);
                  toast.success("Run exported");
                } catch {
                  toast.error("Export failed");
                }
              }}
            >
              <Download className="h-4 w-4" />
              Export
            </Button>
            <Button asChild variant="outline">
              <Link href="/">Workflows</Link>
            </Button>
          </>
        }
      />

      <div className="dashboard-panel overflow-hidden rounded-lg">
        {/* gap-px over a border-colored grid: hairlines land on both axes, so
            wrapped rows below lg get rules instead of stray left borders. */}
        <div className="grid grid-cols-2 gap-px border-b border-border bg-border sm:grid-cols-3 lg:grid-cols-6">
          {[
            { label: "Status", value: runStatusLabel(run.status), mono: false },
            { label: "Duration", value: duration, mono: true },
            { label: "Nodes", value: String(metrics.node_count ?? resultCount), mono: true },
            {
              label: "Tokens",
              value:
                typeof metrics.total_tokens === "number" && metrics.total_tokens > 0
                  ? metrics.total_tokens.toLocaleString()
                  : "—",
              mono: true,
            },
            {
              label: "Cost",
              value:
                formatCostUsd(metrics.total_cost_usd as number | undefined),
              mono: true,
            },
            {
              label: "Eval",
              // Aggregates may be 0..1 (normalized) or 1..5 (rubric scale).
              // Match the trace row: sub-1 scores render without a "/ 5" suffix.
              value:
                evalAggregate == null
                  ? "—"
                  : evalAggregate <= 1
                    ? evalAggregate.toFixed(2)
                    : `${evalAggregate.toFixed(2)} / 5`,
              mono: true,
            },
          ].map((item) => (
            <div key={item.label} className="bg-surface px-4 py-3">
              <p className="text-micro">{item.label}</p>
              <p
                className={`mt-1 truncate text-base font-semibold text-foreground${
                  item.mono ? " font-mono tabular-nums" : ""
                }`}
              >
                {item.value}
              </p>
            </div>
          ))}
        </div>
        <div className="flex flex-wrap gap-x-6 gap-y-2 bg-background/20 px-4 py-2.5 font-mono text-xs text-muted">
          <span>
            created{" "}
            <time dateTime={run.created_at} title={formatFullTimestamp(run.created_at)}>
              {formatRelativeTime(run.created_at)}
            </time>
          </span>
          {run.completed_at && (
            <span>
              completed{" "}
              <time dateTime={run.completed_at} title={formatFullTimestamp(run.completed_at)}>
                {formatRelativeTime(run.completed_at)}
              </time>
            </span>
          )}
          {typeof metrics.trace_id === "string" && (
            <span className="truncate">trace:{metrics.trace_id}</span>
          )}
        </div>
      </div>

      {run.status === "awaiting_approval" && (
        <div className="mb-6 rounded-lg border border-warning/50 bg-surface p-4">
          <h2 className="text-heading mb-2">Approval required</h2>
          <div className="space-y-4">
            <p className="text-sm text-muted">
              Node{" "}
              <span className="font-medium text-foreground">
                {String(
                  (run.metrics_json?.pending_approval as { node_id?: string } | undefined)?.node_id ||
                    "human_approval"
                )}
              </span>{" "}
              is waiting for your decision.
            </p>
            {(run.metrics_json?.pending_approval as { review?: string } | undefined)?.review && (
              <p className="whitespace-pre-wrap break-words rounded-lg border border-border bg-surface p-3 text-sm text-foreground/90">
                {String((run.metrics_json?.pending_approval as { review?: string }).review)}
              </p>
            )}
            <div className="flex flex-wrap gap-2">
              <Button
                disabled={deciding !== null}
                onClick={async () => {
                  setDeciding("approve");
                  try {
                    await api.approveRun(runId, { approved: true });
                    setRun((current) =>
                      current ? { ...current, status: "running" } : current
                    );
                    toast.success("Approval sent");
                  } catch (error) {
                    toast.error(error instanceof Error ? error.message : "Approval failed");
                  } finally {
                    setDeciding(null);
                  }
                }}
              >
                {deciding === "approve" ? "Approving…" : "Approve"}
              </Button>
              <Button
                variant="outline"
                disabled={deciding !== null}
                onClick={async () => {
                  setDeciding("reject");
                  try {
                    await api.approveRun(runId, { approved: false, comment: "Rejected by reviewer" });
                    setRun((current) =>
                      current ? { ...current, status: "failed" } : current
                    );
                    toast.message("Run rejected");
                  } catch (error) {
                    toast.error(error instanceof Error ? error.message : "Rejection failed");
                  } finally {
                    setDeciding(null);
                  }
                }}
              >
                {deciding === "reject" ? "Rejecting…" : "Reject"}
              </Button>
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[minmax(0,1fr)_380px]">
        <div className="space-y-4">
          <SectionCard
            title="Input"
            description="Payload used for this run"
            actions={
              <Badge variant="outline">
                {run.input_text.length.toLocaleString()} chars
              </Badge>
            }
          >
            <p className="whitespace-pre-wrap break-words rounded-lg border border-border bg-background p-3 text-sm leading-6 text-foreground/90">
              {run.input_text}
            </p>
          </SectionCard>

          <TraceTimeline
            nodes={nodeResults}
            llmCalls={llmCalls}
            timeline={timelineQuery.data}
            trace={traceQuery.data}
            runLive={["pending", "running", "awaiting_approval"].includes(run.status)}
            awaitingResults={
              resultCount === 0 && ["pending", "running"].includes(run.status)
            }
          />
        </div>

        <aside className="space-y-4 lg:sticky lg:top-6 lg:self-start">
          {run.status === "failed" && <ExplainFailureCallout runId={run.id} />}

          {evalAggregate != null && (
            <SectionCard
              title="Evaluation"
              actions={
                <>
                  {evalPassed === true && <Badge variant="success">Threshold passed</Badge>}
                  {evalPassed === false && <Badge variant="destructive">Below threshold</Badge>}
                </>
              }
            >
              <EvalScoresChart
                scores={{
                  ...((metrics.eval_scores as EvalScores[] | undefined)?.[0] || {}),
                  aggregate_score: evalAggregate,
                }}
              />
            </SectionCard>
          )}

          {hasGuardrails && (
            <SectionCard title="Guardrails">
              <GuardrailEventsPanel
                events={guardrailEvents}
                failedNodeIds={failedGuardrails}
              />
            </SectionCard>
          )}

          {run.final_output && (
            <SectionCard title="Final output">
              <pre className="text-body whitespace-pre-wrap break-words font-mono">
                {run.final_output}
              </pre>
            </SectionCard>
          )}
        </aside>
      </div>
    </div>
  );
}

/** Layout-accurate loading state: mirrors the header, stat grid, input card,
 *  and the span waterfall (left glyph column + staggered bars) so nothing
 *  reflows when the real data lands. Static under reduced motion via .skeleton. */
function RunDetailSkeleton() {
  // Staggered widths + offsets evoke a real waterfall without faking numbers.
  const bars = [
    { left: 0, width: 34 },
    { left: 30, width: 22 },
    { left: 30, width: 40 },
    { left: 66, width: 20 },
    { left: 82, width: 16 },
  ];
  return (
    <div className="page-container space-y-6" aria-busy="true" aria-label="Loading run…">
      {/* Header */}
      <div className="flex items-center justify-between gap-4">
        <div className="space-y-2">
          <div className="skeleton h-7 w-40" />
          <div className="skeleton h-4 w-64" />
        </div>
        <div className="flex items-center gap-2">
          <div className="skeleton h-9 w-20" />
          <div className="skeleton h-9 w-24" />
        </div>
      </div>

      {/* Stat grid */}
      <div className="dashboard-panel overflow-hidden rounded-lg">
        <div className="grid grid-cols-2 gap-px border-b border-border bg-border sm:grid-cols-3 lg:grid-cols-6">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="space-y-2 bg-surface px-4 py-3">
              <div className="skeleton h-3 w-14" />
              <div className="skeleton h-5 w-20" />
            </div>
          ))}
        </div>
        <div className="flex gap-6 bg-background/20 px-4 py-2.5">
          <div className="skeleton h-3 w-28" />
          <div className="skeleton h-3 w-24" />
        </div>
      </div>

      {/* Two-column body */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[minmax(0,1fr)_380px]">
        <div className="space-y-4">
          {/* Input card */}
          <div className="dashboard-panel space-y-3 rounded-lg p-4">
            <div className="skeleton h-4 w-24" />
            <div className="skeleton h-16 w-full" />
          </div>

          {/* Waterfall */}
          <div className="dashboard-panel space-y-3 rounded-lg p-4">
            <div className="skeleton h-4 w-32" />
            {/* Axis tick row */}
            <div className="ml-10 flex justify-between">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="skeleton h-3 w-8" />
              ))}
            </div>
            {bars.map((bar, i) => (
              <div key={i} className="flex items-center gap-3">
                {/* Left glyph column */}
                <div className="flex w-7 shrink-0 justify-center">
                  <div className="skeleton h-7 w-7 rounded-full" />
                </div>
                <div className="min-w-0 flex-1 space-y-2">
                  <div className="skeleton h-4 w-40 max-w-full" />
                  {/* Bar on the shared axis */}
                  <div className="relative h-1.5 w-full overflow-hidden rounded-full bg-surface-input">
                    <div
                      className="skeleton absolute inset-y-0 rounded-full"
                      style={{ left: `${bar.left}%`, width: `${bar.width}%` }}
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <aside className="space-y-4">
          <div className="dashboard-panel space-y-3 rounded-lg p-4">
            <div className="skeleton h-4 w-28" />
            <div className="skeleton h-24 w-full" />
          </div>
        </aside>
      </div>
    </div>
  );
}
