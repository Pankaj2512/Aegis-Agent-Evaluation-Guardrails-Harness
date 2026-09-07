"use client";

import { type ReactNode, useEffect, useMemo, useState } from "react";
import {
  Check,
  ChevronDown,
  ChevronUp,
  Circle,
  Clock3,
  ExternalLink,
  FileText,
  GitBranch,
  Loader2,
  Radio,
  Square,
  XCircle,
} from "lucide-react";
import { CopyButton } from "@/components/ui/copy-button";
import { formatCostUsd, formatDurationMs } from "@/lib/format";
import { formatOutput } from "@/lib/pretty-output";
import { runStatusTextClass, runStatusTone } from "@/lib/run-status";
import { cn } from "@/lib/utils";
import type { NodeResult, WorkflowRun } from "@/types/workflow";

/** A graph node distilled to the information the execution deck needs. */
export interface RunDeckNode {
  id: string;
  label: string;
}

/**
 * The canvas keeps fast, streaming node state separately from WorkflowRun.
 * This structural type intentionally mirrors that state without importing
 * React Flow or WorkflowCanvas implementation details.
 */
export interface RunDeckLiveResult {
  output?: string | null;
  latencyMs?: number | null;
  guardrailStatus?: string | null;
  status?: string;
}

export interface RunDeckProps {
  /** Ordered graph nodes. Their order becomes the run sequence. */
  nodes: readonly RunDeckNode[];
  run: WorkflowRun | null;
  /** Raw SSE records from the run stream. Timestamps are optional. */
  liveEvents: readonly Record<string, unknown>[];
  /** Persisted first-start order, retained even when the event feed is capped. */
  observedStartNodeIds?: readonly string[];
  isRunning: boolean;
  /** A create-run request is in flight; no server run id is cancellable yet. */
  isStarting?: boolean;
  activeNodeId?: string | null;
  /** Lets the canvas drive the selected payload from its existing selection. */
  selectedNodeId?: string | null;
  /** Optional streaming state, used before run.node_results is available. */
  nodeRunResults?: Readonly<Record<string, RunDeckLiveResult>>;
  /** Milliseconds since epoch; WorkflowCanvas already owns this clock origin. */
  startedAt?: number | null;
  onStop?: () => void;
  onOpenTrace?: (runId: string) => void;
  /** Slot for existing approval controls when a run is awaiting approval. */
  approvalSlot?: ReactNode;
  /** Post-run replay transport, rendered in the summary rail's right cluster. */
  replaySlot?: ReactNode;
  className?: string;
}

interface ResolvedStep extends RunDeckNode {
  status: string;
  output: string | null;
  latencyMs: number | null;
  guardrailStatus: string | null;
}

interface TraceRow {
  id: string;
  label: string;
  detail: string | null;
  status: string;
  latencyMs: number | null;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function stringAt(record: Record<string, unknown>, ...keys: string[]): string | null {
  for (const key of keys) {
    const value = record[key];
    if (typeof value === "string" && value.trim()) return value;
    if (typeof value === "number" && Number.isFinite(value)) return String(value);
  }
  return null;
}

function numberAt(record: Record<string, unknown>, ...keys: string[]): number | null {
  for (const key of keys) {
    const value = record[key];
    if (typeof value === "number" && Number.isFinite(value)) return value;
    if (typeof value === "string" && value.trim() && Number.isFinite(Number(value))) {
      return Number(value);
    }
  }
  return null;
}

function outputAt(record: Record<string, unknown>, ...keys: string[]): string | null {
  for (const key of keys) {
    const value = record[key];
    if (typeof value === "string") return value;
    if (value != null && typeof value === "object") {
      try {
        return JSON.stringify(value);
      } catch {
        return String(value);
      }
    }
  }
  return null;
}

function normalizeStatus(status: string | null | undefined): string {
  return status?.trim().toLowerCase().replace(/[\s-]+/g, "_") || "pending";
}

function eventStatus(type: string, record: Record<string, unknown>): string {
  const explicit = stringAt(record, "status");
  if (explicit) return normalizeStatus(explicit);
  if (type.includes("fail") || type.includes("error")) return "failed";
  if (type.includes("cancel")) return "cancelled";
  if (type.includes("approval")) return "awaiting_approval";
  if (type.includes("complete") || type.includes("success")) return "completed";
  if (type.includes("start") || type.includes("running")) return "running";
  return "pending";
}

function formatElapsed(value: number | null): string {
  if (value == null || value < 0) return "—";
  if (value < 60_000) return formatDurationMs(value);
  const minutes = Math.floor(value / 60_000);
  const seconds = Math.floor((value % 60_000) / 1000);
  return `${minutes}m ${String(seconds).padStart(2, "0")}s`;
}

function parseStartedAt(run: WorkflowRun | null, startedAt?: number | null): number | null {
  if (startedAt != null && Number.isFinite(startedAt)) return startedAt;
  if (!run?.started_at) return null;
  const parsed = Date.parse(run.started_at);
  return Number.isFinite(parsed) ? parsed : null;
}

function useElapsedMs(startedAt: number | null, isRunning: boolean): number | null {
  const [elapsed, setElapsed] = useState<number | null>(null);

  useEffect(() => {
    if (!isRunning || startedAt == null) {
      setElapsed(null);
      return;
    }

    const tick = () => setElapsed(Math.max(0, Date.now() - startedAt));
    tick();
    const id = window.setInterval(tick, 1000);
    return () => window.clearInterval(id);
  }, [isRunning, startedAt]);

  return elapsed;
}

function resultRuntime(result: NodeResult | RunDeckLiveResult): Omit<ResolvedStep, "id" | "label"> {
  const isNodeResult = "node_id" in result;
  return {
    status: normalizeStatus(result.status),
    output: result.output ?? null,
    latencyMs: isNodeResult ? result.latency_ms ?? null : result.latencyMs ?? null,
    guardrailStatus: isNodeResult
      ? result.guardrail_status ?? null
      : result.guardrailStatus ?? null,
  };
}

function resolveSteps({
  nodes,
  run,
  liveEvents,
  observedStartNodeIds,
  nodeRunResults,
  activeNodeId,
  isRunning,
}: Pick<
  RunDeckProps,
  | "nodes"
  | "run"
  | "liveEvents"
  | "observedStartNodeIds"
  | "nodeRunResults"
  | "activeNodeId"
  | "isRunning"
>): ResolvedStep[] {
  const runtimeById = new Map<string, Omit<ResolvedStep, "id" | "label">>();
  // A graph can branch and execute in parallel, so document order is not an
  // execution claim. Preserve it only as a stable fallback, then promote steps
  // in the order their first `node_started` event was actually observed.
  const observedStartOrder = new Map<string, number>();

  for (const nodeId of observedStartNodeIds ?? []) {
    if (!observedStartOrder.has(nodeId)) {
      observedStartOrder.set(nodeId, observedStartOrder.size);
    }
  }

  for (const result of run?.node_results ?? []) {
    runtimeById.set(result.node_id, resultRuntime(result));
  }

  for (const [nodeId, result] of Object.entries(nodeRunResults ?? {})) {
    runtimeById.set(nodeId, resultRuntime(result));
  }

  for (const event of liveEvents) {
    const type = normalizeStatus(stringAt(event, "type", "event_type") ?? "");
    const nodeId = stringAt(event, "node_id", "nodeId");
    if (!nodeId) continue;

    if (type === "node_started" && !observedStartOrder.has(nodeId)) {
      observedStartOrder.set(nodeId, observedStartOrder.size);
    }

    const prior = runtimeById.get(nodeId);
    const isNodeEvent = type.startsWith("node_") || type.includes("approval");
    if (!isNodeEvent) continue;

    runtimeById.set(nodeId, {
      status: eventStatus(type, event),
      output: outputAt(event, "output", "result") ?? prior?.output ?? null,
      latencyMs: numberAt(event, "latency_ms", "duration_ms", "duration") ?? prior?.latencyMs ?? null,
      guardrailStatus: stringAt(event, "guardrail_status") ?? prior?.guardrailStatus ?? null,
    });
  }

  const listedNodes: readonly RunDeckNode[] =
    nodes.length > 0
      ? nodes
      : (run?.node_results ?? []).map((result) => ({
          id: result.node_id,
          label: result.node_label || result.node_id,
        }));

  return listedNodes
    .map((node, documentOrder) => ({ node, documentOrder }))
    .sort((left, right) => {
      const leftObserved = observedStartOrder.get(left.node.id);
      const rightObserved = observedStartOrder.get(right.node.id);
      if (leftObserved != null && rightObserved != null) return leftObserved - rightObserved;
      if (leftObserved != null) return -1;
      if (rightObserved != null) return 1;
      return left.documentOrder - right.documentOrder;
    })
    .map(({ node }) => {
      const runtime = runtimeById.get(node.id);
      const active = isRunning && activeNodeId === node.id;
      return {
        ...node,
        status: active ? "running" : runtime?.status ?? (run ? "pending" : "idle"),
        output: runtime?.output ?? null,
        latencyMs: runtime?.latencyMs ?? null,
        guardrailStatus: runtime?.guardrailStatus ?? null,
      };
    });
}

/**
 * Live state tint, delegated to the canonical status→tone map so a running run
 * reads the same amber here as it does in the trace and on /observability.
 * Only the neutral fallback stays deck-local: an unstarted step should recede
 * into the strip rather than sit at the muted body weight.
 */
function statusClass(status: string): string {
  const normalized = normalizeStatus(status);
  return runStatusTone(normalized) === "muted" ? "text-subtle" : runStatusTextClass(normalized);
}

function StatusGlyph({ status, className }: { status: string; className?: string }) {
  const normalized = normalizeStatus(status);
  const classes = cn("h-3.5 w-3.5 shrink-0", statusClass(normalized), className);

  if (normalized === "completed" || normalized === "success" || normalized === "passed") {
    return <Check className={classes} aria-hidden />;
  }
  if (normalized === "failed" || normalized === "error" || normalized === "cancelled") {
    return <XCircle className={classes} aria-hidden />;
  }
  if (normalized === "starting" || normalized === "running") {
    return <Loader2 className={cn(classes, "animate-spin")} aria-hidden />;
  }
  if (normalized === "awaiting_approval") {
    return <Clock3 className={classes} aria-hidden />;
  }
  return <Circle className={classes} aria-hidden />;
}

/**
 * Tint for a row in the chronological event LOG. Unlike statusClass, a `.started`
 * entry is a historical moment, not live state — every tone the canonical map
 * calls "live" (running/pending/starting) reads muted here, so a finished run's
 * log doesn't look stuck mid-flight. Outcomes keep their canonical hue.
 */
function eventClass(status: string): string {
  const normalized = normalizeStatus(status);
  const tone = runStatusTone(normalized);
  if (tone === "muted" || tone === "warning") return "text-subtle";
  return runStatusTextClass(normalized);
}

/**
 * Glyph for the event LOG. StatusGlyph animates "running" (correct for a live
 * node), but a `.started` log row is a past moment: rendering an eternal spinner
 * makes a completed run's feed look unfinished (LLM Agent.started / End.started
 * kept spinning after run_completed). Started/neutral events get a static dot.
 */
function EventGlyph({ status, className }: { status: string; className?: string }) {
  const normalized = normalizeStatus(status);
  const classes = cn("h-3 w-3 shrink-0", eventClass(normalized), className);
  if (normalized === "completed" || normalized === "success" || normalized === "passed") {
    return <Check className={classes} aria-hidden />;
  }
  if (normalized === "failed" || normalized === "error" || normalized === "cancelled") {
    return <XCircle className={classes} aria-hidden />;
  }
  if (normalized === "awaiting_approval") {
    return <Clock3 className={classes} aria-hidden />;
  }
  return <Circle className={classes} aria-hidden />;
}

function eventLabel(event: Record<string, unknown>, labels: ReadonlyMap<string, string>): string {
  const type = normalizeStatus(stringAt(event, "type", "event_type") ?? "event");
  const nodeId = stringAt(event, "node_id", "nodeId");
  const nodeLabel = stringAt(event, "node_label", "nodeLabel") ?? (nodeId ? labels.get(nodeId) : null);

  if (nodeLabel && type.startsWith("node_")) {
    return `${nodeLabel}.${type.slice("node_".length)}`;
  }
  if (nodeLabel && type === "approval_required") return `${nodeLabel}.approval_required`;
  return type;
}

function eventTime(event: Record<string, unknown>): string {
  const value = stringAt(
    event,
    "timestamp",
    "created_at",
    "occurred_at",
    "received_at",
    "receivedAt",
    "time"
  );
  if (!value) return "—";
  // ISO timestamps stay stable between SSR and client hydration without relying
  // on locale or timezone formatting.
  const match = /T(\d{2}:\d{2}:\d{2}(?:\.\d{1,3})?)/.exec(value);
  return match?.[1] ?? value;
}

function outputLines(output: string): { lines: string[]; truncated: boolean } {
  const maxLines = 18;
  const maxChars = 3_000;
  const clipped = output.length > maxChars ? output.slice(0, maxChars) : output;
  const lines = clipped.split("\n");
  return {
    lines: lines.slice(0, maxLines),
    truncated: output.length > maxChars || lines.length > maxLines,
  };
}

function traceRowsFrom(
  metrics: Record<string, unknown> | null | undefined,
  steps: readonly ResolvedStep[]
): TraceRow[] {
  const rawTrace = metrics?.trace ?? metrics?.trace_steps ?? metrics?.steps;
  if (Array.isArray(rawTrace)) {
    const rows = rawTrace
      .map((entry, index) => {
        const record = asRecord(entry);
        if (!record) return null;
        return {
          id: stringAt(record, "id", "node_id", "name") ?? `trace-${index}`,
          label: stringAt(record, "label", "node_label", "name", "node_id") ?? "trace step",
          detail: stringAt(record, "kind", "node_type", "type"),
          status: eventStatus(normalizeStatus(stringAt(record, "type") ?? ""), record),
          latencyMs: numberAt(record, "latency_ms", "duration_ms", "duration"),
        } satisfies TraceRow;
      })
      .filter((row): row is TraceRow => row !== null);
    if (rows.length > 0) return rows;
  }

  return steps.map((step) => ({
    id: step.id,
    label: step.label,
    detail: step.guardrailStatus ? `guardrail: ${step.guardrailStatus}` : null,
    status: step.status,
    latencyMs: step.latencyMs,
  }));
}

function metricNumber(metrics: Record<string, unknown> | null | undefined, ...keys: string[]): number | null {
  return metrics ? numberAt(metrics, ...keys) : null;
}

function totalTokens(run: WorkflowRun | null): number | null {
  const metrics = run?.metrics_json;
  const direct = metricNumber(metrics, "total_tokens", "tokens", "token_count");
  if (direct != null) return direct;

  let total = 0;
  let found = false;
  for (const result of run?.node_results ?? []) {
    const usage = result.token_usage;
    if (!usage) continue;
    const value = numberAt(usage, "total_tokens", "tokens", "token_count");
    if (value != null) {
      total += value;
      found = true;
    }
  }
  return found ? total : null;
}

/**
 * A canvas-docked execution lens. It stays deliberately independent from the
 * React Flow canvas: WorkflowCanvas supplies graph labels and its existing run
 * state, while this component owns only presentation and small local timers.
 */
const COLLAPSE_STORAGE_KEY = "aegis:run-deck-collapsed";

export function RunDeck({
  nodes,
  run,
  liveEvents,
  observedStartNodeIds,
  isRunning,
  isStarting = false,
  activeNodeId = null,
  selectedNodeId = null,
  nodeRunResults,
  startedAt = null,
  onStop,
  onOpenTrace,
  approvalSlot,
  replaySlot,
  className,
}: RunDeckProps) {
  // Collapsing hides the events/output/trace grid and keeps just the progress
  // strip, handing vertical space back to the canvas. Persisted so the choice
  // survives reloads and future runs.
  const [collapsed, setCollapsed] = useState<boolean>(() => {
    // Default to the slim rail: run lens keeps the canvas the primary surface,
    // so the events/output/trace grid is opt-in. A stored choice still wins.
    if (typeof window === "undefined") return true;
    try {
      const stored = window.localStorage.getItem(COLLAPSE_STORAGE_KEY);
      return stored == null ? true : stored === "1";
    } catch {
      return true;
    }
  });

  const toggleCollapsed = () => {
    setCollapsed((prev) => {
      const next = !prev;
      try {
        window.localStorage.setItem(COLLAPSE_STORAGE_KEY, next ? "1" : "0");
      } catch {
        /* storage unavailable — non-fatal */
      }
      return next;
    });
  };

  const steps = useMemo(
    () =>
      resolveSteps({
        nodes,
        run,
        liveEvents,
        observedStartNodeIds,
        nodeRunResults,
        activeNodeId,
        isRunning,
      }),
    [activeNodeId, isRunning, liveEvents, nodeRunResults, nodes, observedStartNodeIds, run]
  );
  const labelById = useMemo(() => new Map(steps.map((step) => [step.id, step.label])), [steps]);
  const activeStep = steps.find((step) => step.id === activeNodeId) ?? null;
  const completedCount = steps.filter((step) => {
    const status = normalizeStatus(step.status);
    return status === "completed" || status === "success" || status === "passed";
  }).length;
  const selectedStep = useMemo(() => {
    if (selectedNodeId) {
      const explicit = steps.find((step) => step.id === selectedNodeId);
      if (explicit) return explicit;
    }
    if (activeStep) return activeStep;
    return [...steps].reverse().find((step) => step.output?.trim()) ?? null;
  }, [activeStep, selectedNodeId, steps]);
  const effectiveStartedAt = parseStartedAt(run, startedAt);
  const elapsedMs = useElapsedMs(effectiveStartedAt, isRunning);
  const selectedRawOutput = selectedStep?.output ?? (selectedStep ? null : run?.final_output ?? null);
  const selectedHasOutput = Boolean(selectedRawOutput?.trim());
  const formattedOutput = selectedHasOutput ? formatOutput(selectedRawOutput ?? "") : null;
  const renderedOutput = formattedOutput ? outputLines(formattedOutput.text) : null;
  const traceRows = useMemo(() => traceRowsFrom(run?.metrics_json, steps), [run?.metrics_json, steps]);

  const metrics = useMemo(() => {
    const rawMetrics = run?.metrics_json;
    const summedLatency = steps.reduce((total, step) => total + (step.latencyMs ?? 0), 0);
    const latency =
      metricNumber(rawMetrics, "latency_ms", "total_duration_ms", "duration_ms") ??
      (isRunning ? elapsedMs : null) ??
      (summedLatency > 0 ? summedLatency : null);
    return {
      tokens: totalTokens(run),
      cost: metricNumber(rawMetrics, "total_cost_usd", "cost_usd", "cost"),
      latency,
    };
  }, [elapsedMs, isRunning, run, steps]);

  const visibleEvents = liveEvents.slice(-6);
  const runStatus = isStarting ? "starting" : isRunning ? "running" : normalizeStatus(run?.status);

  return (
    <section
      aria-label="Run execution details"
      className={cn(
        "surface-card flex shrink-0 flex-col border-t border-border bg-surface shadow-[inset_0_1px_0_var(--surface-highlight)]",
        // Collapsed: drop the caller's fixed height (h-[42%]/min-h) so the section
        // shrinks to just the strip and docks to the bottom, handing the freed
        // space back to the canvas above (which is flex-1). Expanded: full height.
        collapsed
          ? "min-h-0"
          : cn("min-h-[320px] overflow-y-auto lg:overflow-hidden", className)
      )}
    >
      {/* Slim summary rail. Per-stage state now lives on the canvas nodes
          themselves (inline telemetry + active glow + wavefront dimming), so the
          rail carries only the run-level read: status, progress, aggregate
          metrics, and the transport/expand controls. */}
      <div
        className={cn(
          "flex min-h-[52px] items-center gap-3 px-4 py-2.5 sm:px-6",
          !collapsed && "border-b border-border"
        )}
      >
        <div className="flex min-w-0 items-center gap-2.5">
          <span className={cn("flex shrink-0 items-center gap-1.5 text-xs font-medium", statusClass(runStatus))}>
            <StatusGlyph status={runStatus} className="h-3.5 w-3.5" />
            {isStarting
              ? "Starting"
              : isRunning
                ? `Live ${formatElapsed(elapsedMs)}`
                : run
                  ? run.status.replace(/_/g, " ")
                  : "Idle"}
          </span>
          {steps.length > 0 ? (
            <span className="shrink-0 font-mono text-2xs tabular-nums text-subtle">
              {completedCount}/{steps.length}
            </span>
          ) : (
            <span className="truncate text-xs text-subtle">Run the workflow to trace its execution.</span>
          )}
        </div>

        {/* Aggregate metrics — the one place the run's totals live now that the
            per-node footer is gone. Hidden on narrow widths where the controls
            need the room. */}
        <div className="ml-1 hidden min-w-0 items-center gap-3.5 font-mono text-2xs tabular-nums text-subtle md:flex">
          <span>
            Tokens <span className="text-muted">{metrics.tokens?.toLocaleString() ?? "—"}</span>
          </span>
          <span aria-hidden className="text-border-strong">·</span>
          <span>
            Cost <span className="text-muted">{formatCostUsd(metrics.cost)}</span>
          </span>
          <span aria-hidden className="text-border-strong">·</span>
          <span>
            Latency <span className={cn("font-medium", statusClass(runStatus))}>{formatElapsed(metrics.latency)}</span>
          </span>
        </div>

        <div className="ml-auto flex shrink-0 items-center gap-2">
          {replaySlot}
          {isRunning && !isStarting && onStop && (
            <button
              type="button"
              onClick={onStop}
              className="focus-ring inline-flex h-7 items-center gap-1.5 rounded-md border border-border px-2 text-2xs font-medium text-muted transition-colors duration-1 hover:border-destructive/50 hover:bg-destructive/10 hover:text-destructive"
            >
              <Square className="h-3 w-3" aria-hidden />
              Stop
            </button>
          )}
          <button
            type="button"
            onClick={toggleCollapsed}
            aria-expanded={!collapsed}
            aria-controls="run-deck-body"
            aria-label={collapsed ? "Expand run details" : "Collapse run details"}
            title={collapsed ? "Expand run details" : "Collapse run details"}
            className="focus-ring inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-muted transition-colors duration-1 hover:bg-surface-hover hover:text-foreground"
          >
            {collapsed ? (
              <ChevronUp className="h-4 w-4" aria-hidden />
            ) : (
              <ChevronDown className="h-4 w-4" aria-hidden />
            )}
          </button>
        </div>
      </div>

      {!collapsed && (
      <div id="run-deck-body" className="grid flex-none grid-cols-1 lg:min-h-0 lg:flex-1 lg:grid-cols-[minmax(0,0.94fr)_minmax(0,1.1fr)_minmax(0,1fr)]">
        <section aria-labelledby="run-deck-events" className="min-h-0 border-b border-border p-4 sm:p-5 lg:overflow-y-auto lg:border-b-0 lg:border-r">
          <div className="mb-3 flex items-center gap-2">
            <Radio className="h-3.5 w-3.5 text-muted" aria-hidden />
            <h2 id="run-deck-events" className="text-2xs font-semibold uppercase tracking-[0.12em] text-foreground">
              Live events
            </h2>
          </div>
          {visibleEvents.length > 0 ? (
            <ol className="space-y-1 font-mono text-2xs leading-5">
              {visibleEvents.map((event, index) => {
                const type = normalizeStatus(stringAt(event, "type", "event_type") ?? "event");
                const status = eventStatus(type, event);
                const duration = numberAt(event, "latency_ms", "duration_ms", "duration");
                return (
                  <li key={`${type}-${index}`} className="grid grid-cols-[3.6rem_0.9rem_minmax(0,1fr)_auto] items-center gap-x-2">
                    <span className="truncate tabular-nums text-subtle">{eventTime(event)}</span>
                    <EventGlyph status={status} className="h-3 w-3" />
                    <span className={cn("truncate", eventClass(status))}>{eventLabel(event, labelById)}</span>
                    <span className="tabular-nums text-subtle">{formatDurationMs(duration)}</span>
                  </li>
                );
              })}
            </ol>
          ) : (
            <p className="font-mono text-2xs leading-5 text-subtle">No execution events yet.</p>
          )}
        </section>

        <section aria-labelledby="run-deck-output" className="min-h-0 border-b border-border p-4 sm:p-5 lg:overflow-y-auto lg:border-b-0 lg:border-r">
          <div className="mb-3 flex items-center justify-between gap-3">
            <div className="flex min-w-0 items-center gap-2">
              <FileText className="h-3.5 w-3.5 shrink-0 text-muted" aria-hidden />
              <div className="min-w-0">
                <h2 id="run-deck-output" className="text-2xs font-semibold uppercase tracking-[0.12em] text-foreground">
                  Selected output
                </h2>
                <p className="truncate font-mono text-2xs text-subtle">
                  {selectedStep?.label ?? (run?.final_output ? "Final output" : "Select a step")}
                </p>
              </div>
            </div>
            {selectedHasOutput && <CopyButton text={selectedRawOutput ?? ""} label="Copy selected output" />}
          </div>

          {renderedOutput ? (
            <div className="max-h-44 overflow-auto rounded-md border border-border bg-surface-input/70 py-2 shadow-[inset_0_1px_0_var(--surface-highlight)]">
              <ol className="min-w-max font-mono text-xs leading-5 text-foreground/90">
                {renderedOutput.lines.map((line, index) => (
                  <li key={`${index}-${line}`} className="grid grid-cols-[2.25rem_minmax(0,1fr)] px-3">
                    <span className="select-none pr-3 text-right text-subtle">{String(index + 1).padStart(2, "0")}</span>
                    <code className="whitespace-pre">{line || " "}</code>
                  </li>
                ))}
                {renderedOutput.truncated && (
                  <li className="grid grid-cols-[2.25rem_minmax(0,1fr)] px-3 text-subtle">
                    <span className="pr-3 text-right">…</span>
                    <code>output truncated</code>
                  </li>
                )}
              </ol>
            </div>
          ) : (
            <div className="flex min-h-24 items-center gap-2 rounded-md border border-dashed border-border bg-surface-input/45 px-3 font-mono text-2xs leading-5 text-subtle">
              {activeStep ? <Loader2 className="h-3.5 w-3.5 animate-spin text-active" aria-hidden /> : <FileText className="h-3.5 w-3.5" aria-hidden />}
              {activeStep ? `Waiting for ${activeStep.label} output…` : "Select a completed step to inspect its payload."}
            </div>
          )}
        </section>

        <section aria-labelledby="run-deck-trace" className="min-h-0 p-4 sm:p-5 lg:overflow-y-auto">
          <div className="mb-3 flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <GitBranch className="h-3.5 w-3.5 text-muted" aria-hidden />
              <h2 id="run-deck-trace" className="text-2xs font-semibold uppercase tracking-[0.12em] text-foreground">
                Trace
              </h2>
            </div>
            {run && onOpenTrace && !isRunning && (
              <button
                type="button"
                onClick={() => onOpenTrace(run.id)}
                className="focus-ring inline-flex h-7 items-center gap-1.5 rounded-md border border-border px-2 text-2xs font-medium text-muted transition-colors duration-1 hover:border-border-strong hover:bg-surface-hover hover:text-foreground"
              >
                <ExternalLink className="h-3 w-3" aria-hidden />
                Inspect trace
              </button>
            )}
          </div>

          {traceRows.length > 0 ? (
            <ol className="space-y-1.5">
              {traceRows.slice(0, 5).map((row) => (
                <li key={row.id} className="grid grid-cols-[0.9rem_minmax(0,1fr)_auto] items-center gap-x-2 font-mono text-2xs leading-5">
                  <StatusGlyph status={row.status} className="h-3 w-3" />
                  <span className="min-w-0 truncate text-muted">
                    {row.label}
                    {row.detail && <span className="ml-1 text-subtle">{row.detail}</span>}
                  </span>
                  <span className="tabular-nums text-subtle">{formatDurationMs(row.latencyMs)}</span>
                </li>
              ))}
            </ol>
          ) : (
            <p className="font-mono text-2xs leading-5 text-subtle">Trace details appear once the run starts.</p>
          )}
          {approvalSlot && <div className="mt-3 border-t border-border pt-3">{approvalSlot}</div>}
        </section>
      </div>
      )}
    </section>
  );
}
