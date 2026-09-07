"use client";

import { ChevronRight, Crosshair, ShieldAlert, ShieldCheck } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Chip, type ChipTone } from "@/components/ui/chip";
import { EvalScoresChart } from "@/components/results/EvalScoresChart";
import { categorize, CATEGORY_COLOR_VAR } from "@/components/canvas/nodes/category";
import { formatCostUsd, formatDurationMs, formatTokens } from "@/lib/format";
import {
  guardrailStatusTone,
  runStatusLabel,
  runStatusRingClass,
  runStatusTone,
  runStatusVariant,
} from "@/lib/run-status";
import { cn } from "@/lib/utils";
import type { RunSpan } from "@/lib/api";
import type { EvalScores, LlmCall, NodeResult } from "@/types/workflow";

/** Geometry for a single span on the shared time axis (0..100, %). */
export interface TraceBarGeometry {
  /** Left edge as a percentage of total run duration. */
  leftPct: number;
  /** Bar width as a percentage of total run duration (already floored). */
  widthPct: number;
  /** Real span duration in ms (from the timeline endpoint), if known. */
  durationMs: number | null;
  /** Start offset in ms from run start, if known. */
  startOffsetMs: number | null;
}

interface TraceNodeRowProps {
  node: NodeResult;
  llmCalls: LlmCall[];
  /** Span placement on the shared left-to-right time axis. */
  geometry: TraceBarGeometry;
  /** Nested child spans (llm_call / tool_call) under this node, from the trace
   *  tree — the agent-step drill-down. Undefined until the trace loads. */
  childSpans?: RunSpan[];
  /** Whether this is the last row (hides the trailing rail segment). */
  isLast: boolean;
  /** True while the run is still live (pending/running/awaiting_approval). */
  runLive: boolean;
  /** Optional: focus/select this node on the canvas. Control renders only when set. */
  onJumpToNode?: (nodeId: string) => void;
}

/** Node status → glyph ring. Hue comes from the canonical status map; this row
 *  owns the ring width and the live pulse (only while the run is still live —
 *  a node stuck at "running" on a finished run shouldn't keep breathing). */
function statusRing(status: string, runLive: boolean): string {
  const tone = runStatusTone(status);
  if (tone === "muted") return "ring-1 ring-border";
  return cn(
    "ring-2",
    runStatusRingClass(status),
    tone === "warning" && runLive && "animate-pulse"
  );
}

/** Aggregate eval score if the node carries one — no recompute, so we never
 *  invent a number the judge didn't return. Every producer in this app emits a
 *  1..5 aggregate (LLM judge: weighted mean of 1–5 dimensions; deterministic:
 *  1 + match×4), so 1.0 is a floor, not a perfect score. */
function evalAggregate(scores: NodeResult["evaluation_scores"]): number | null {
  if (!scores) return null;
  const agg = (scores as EvalScores).aggregate_score;
  return typeof agg === "number" ? agg : null;
}

/** True when the aggregate is on the 1..5 judge scale rather than a legacy
 *  0..1 ratio — the whole band depends on which scale the number is on. */
function isFiveScale(score: number): boolean {
  return score >= 1;
}

/** Band an eval aggregate into a quality tone, on the value's actual scale. */
function evalTone(score: number): ChipTone {
  if (isFiveScale(score)) {
    if (score >= 3.5) return "success";
    if (score >= 2.5) return "warning";
    return "destructive";
  }
  if (score >= 0.7) return "success";
  if (score >= 0.4) return "warning";
  return "destructive";
}

/** Self-describing chip copy: "3.40/5" for judge scores, bare ratio otherwise. */
function evalLabel(score: number): string {
  return `${score.toFixed(2)}${isFiveScale(score) ? "/5" : ""}`;
}

export function TraceNodeRow({
  node,
  llmCalls,
  geometry,
  childSpans,
  isLast,
  runLive,
  onJumpToNode,
}: TraceNodeRowProps) {
  const colorVar = CATEGORY_COLOR_VAR[categorize(node.node_type)];
  const status = node.status?.toLowerCase() ?? "";
  const isFailed = status === "failed" || status === "error";
  const defaultOpen = isFailed || Boolean(node.guardrail_status);
  const nodeCalls = llmCalls.filter((call) => call.node_id === node.node_id);
  const steps = childSpans ?? [];

  const leftPct = Math.max(0, Math.min(100, geometry.leftPct));
  // Keep the bar inside the axis: clamp width to the remaining track.
  const widthPct = Math.max(0, Math.min(100 - leftPct, geometry.widthPct));
  // Prefer the timeline's real span duration; fall back to the node's latency.
  const durationMs = geometry.durationMs ?? node.latency_ms ?? null;

  // Glass-box overlay: quality + safety + cost carried inline on the span.
  const evalScore = evalAggregate(node.evaluation_scores);
  const guardrail = node.guardrail_status ?? null;
  const rawCost = node.token_usage?.cost_usd;
  const nodeCost = typeof rawCost === "number" && rawCost > 0 ? rawCost : null;

  return (
    <li className="relative flex gap-3 pb-4 last:pb-0">
      {/* Left rail: continuous vertical line + glyph */}
      <div className="relative flex w-7 shrink-0 flex-col items-center">
        {!isLast && (
          <span
            aria-hidden
            className="absolute left-1/2 top-7 h-[calc(100%-1rem)] w-px -translate-x-1/2 bg-border"
          />
        )}
        <span
          className={cn(
            "relative z-10 flex h-7 w-7 items-center justify-center rounded-full border border-border bg-surface",
            statusRing(status, runLive)
          )}
        >
          {/* Category hue stays a <=2px rule: a hollow 2px ring, never a fill. */}
          <span
            aria-hidden
            className="h-1.5 w-1.5 rounded-full"
            style={{ boxShadow: `0 0 0 2px ${colorVar}` }}
          />
        </span>
      </div>

      {/* Row content */}
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <h3 className="truncate text-sm font-medium text-foreground">
              {node.node_label}
            </h3>
            <p className="truncate font-mono text-2xs lowercase text-subtle">
              {node.node_type}
            </p>
          </div>
          <div className="flex min-w-0 flex-wrap items-center justify-end gap-1.5">
            {evalScore != null && (
              <Chip
                tone={evalTone(evalScore)}
                title={`Evaluation aggregate ${evalLabel(evalScore)}`}
              >
                eval {evalLabel(evalScore)}
              </Chip>
            )}
            {guardrail && (
              <Chip
                tone={guardrailStatusTone(guardrail)}
                title={`Guardrail: ${runStatusLabel(guardrail)}`}
              >
                {guardrailStatusTone(guardrail) === "destructive" ? (
                  <ShieldAlert className="h-3 w-3 shrink-0" aria-hidden />
                ) : (
                  <ShieldCheck className="h-3 w-3 shrink-0" aria-hidden />
                )}
                {runStatusLabel(guardrail)}
              </Chip>
            )}
            {nodeCost != null && (
              <span
                title="Node cost"
                className="font-mono text-2xs tabular-nums text-subtle"
              >
                {formatCostUsd(nodeCost)}
              </span>
            )}
            {/* Duration lives once, at the right end of the span bar below. */}
            <Badge variant={runStatusVariant(node.status)}>
              {runStatusLabel(node.status)}
            </Badge>
            {onJumpToNode && (
              <button
                type="button"
                onClick={() => onJumpToNode(node.node_id)}
                title="Jump to node on canvas"
                aria-label={`Jump to ${node.node_label} on canvas`}
                className="focus-ring rounded p-1 text-subtle transition-colors duration-1 hover:text-foreground"
              >
                <Crosshair className="h-3.5 w-3.5" aria-hidden />
              </button>
            )}
          </div>
        </div>

        {/* True span bar — placed on the shared left-to-right time axis.
            Neutral fill; category hue only as a <=2px left rule. */}
        <div className="mt-2 flex items-center gap-2">
          <div className="relative h-1.5 flex-1 overflow-hidden rounded-full bg-surface-input">
            <div
              className={cn(
                "absolute inset-y-0 rounded-full",
                isFailed ? "bg-destructive/45" : "bg-foreground/25"
              )}
              style={{
                left: `${leftPct}%`,
                width: `${widthPct}%`,
                minWidth: "2px",
              }}
            >
              {/* Category hue as a <=2px left rule on the bar */}
              <span
                aria-hidden
                className="absolute inset-y-0 left-0 w-0.5 rounded-l-full"
                style={{ backgroundColor: colorVar }}
              />
            </div>
          </div>
          <span className="w-16 shrink-0 text-right font-mono text-2xs tabular-nums text-subtle">
            {formatDurationMs(durationMs)}
          </span>
        </div>
        {geometry.startOffsetMs != null && geometry.startOffsetMs > 0 && (
          <p className="mt-1 font-mono text-2xs tabular-nums text-subtle">
            +{formatDurationMs(geometry.startOffsetMs)} offset
          </p>
        )}

        {/* Collapsible payload */}
        <details className="group mt-2" open={defaultOpen}>
          <summary className="focus-ring flex cursor-pointer list-none items-center gap-2 rounded font-mono text-2xs text-subtle transition-colors hover:text-foreground [&::-webkit-details-marker]:hidden">
            <ChevronRight
              className="h-3 w-3 shrink-0 transition-transform group-open:rotate-90"
              aria-hidden
            />
            <span>details</span>
          </summary>
          <div className="mt-2 space-y-3 text-sm text-muted">
            {steps.length > 0 && (
              <div className="rounded-lg border border-border bg-surface-input p-2.5">
                <p className="mb-2 font-mono text-2xs uppercase tracking-wide text-subtle">
                  {steps.length} step{steps.length === 1 ? "" : "s"}
                </p>
                <ol className="space-y-1.5">
                  {steps.map((sp) => {
                    const nodeWindow = Math.max(
                      geometry.durationMs ?? node.latency_ms ?? 0,
                      1
                    );
                    const nodeOffset = geometry.startOffsetMs ?? 0;
                    const rel = Math.max(0, (sp.offset_ms ?? nodeOffset) - nodeOffset);
                    const spLeft = Math.min(100, (rel / nodeWindow) * 100);
                    const spWidth = Math.max(
                      2,
                      Math.min(100 - spLeft, ((sp.duration_ms ?? 0) / nodeWindow) * 100)
                    );
                    const isTool = sp.kind === "tool_call";
                    const spFailed = sp.status === "failed" || sp.status === "error";
                    const cost =
                      typeof sp.cost_usd === "number" && sp.cost_usd > 0
                        ? formatCostUsd(sp.cost_usd)
                        : null;
                    const tokens = sp.tokens?.total ?? null;
                    const attrs = sp.attributes ?? {};
                    return (
                      <li key={sp.id} className="font-mono text-2xs">
                        <details className="group/step">
                          <summary className="focus-ring flex cursor-pointer list-none items-center gap-2 [&::-webkit-details-marker]:hidden">
                            <ChevronRight
                              className="h-3 w-3 shrink-0 text-subtle transition-transform group-open/step:rotate-90"
                              aria-hidden
                            />
                            <span className="shrink-0 rounded bg-surface px-1 py-0.5 text-micro uppercase text-subtle">
                              {isTool ? "tool" : "llm"}
                            </span>
                            <span className="min-w-0 flex-1 truncate text-muted">
                              {sp.name}
                            </span>
                            <span className="shrink-0 tabular-nums text-subtle">
                              {formatDurationMs(sp.duration_ms)}
                              {tokens != null ? ` · ${formatTokens(tokens)} tok` : ""}
                              {cost ? ` · ${cost}` : ""}
                            </span>
                          </summary>
                          <div className="ml-5 mt-1 h-1 overflow-hidden rounded-full bg-surface">
                            <div
                              className={cn(
                                "h-full rounded-full",
                                spFailed ? "bg-destructive/45" : "bg-foreground/25"
                              )}
                              style={{ marginLeft: `${spLeft}%`, width: `${spWidth}%` }}
                            />
                          </div>
                          <div className="ml-5 mt-1.5 space-y-1">
                            {typeof attrs.args === "string" && (
                              <pre className="max-h-32 overflow-auto whitespace-pre-wrap rounded border border-border bg-background p-2 text-xs leading-5 text-foreground/80">
                                args: {attrs.args}
                              </pre>
                            )}
                            {typeof attrs.result === "string" && (
                              <pre className="max-h-32 overflow-auto whitespace-pre-wrap rounded border border-border bg-background p-2 text-xs leading-5 text-foreground/80">
                                result: {attrs.result}
                              </pre>
                            )}
                            {typeof attrs.error === "string" && (
                              <pre className="max-h-32 overflow-auto whitespace-pre-wrap rounded border border-destructive/30 bg-background p-2 text-xs leading-5 text-destructive">
                                {attrs.error}
                              </pre>
                            )}
                            {typeof attrs.completion === "string" && (
                              <pre className="max-h-32 overflow-auto whitespace-pre-wrap rounded border border-border bg-background p-2 text-xs leading-5 text-foreground/80">
                                {attrs.completion}
                              </pre>
                            )}
                          </div>
                        </details>
                      </li>
                    );
                  })}
                </ol>
              </div>
            )}
            {node.output && (
              <p className="whitespace-pre-wrap break-words rounded-lg border border-border bg-background p-3 leading-6 text-foreground/90">
                {node.output}
              </p>
            )}
            {node.evaluation_scores && (
              <div className="rounded-lg border border-border bg-surface-input p-3">
                <EvalScoresChart
                  scores={node.evaluation_scores as EvalScores}
                  compact
                />
              </div>
            )}
            {node.guardrail_status && (
              <Badge variant={runStatusVariant(node.guardrail_status)}>
                Guardrail: {runStatusLabel(node.guardrail_status)}
              </Badge>
            )}
            {nodeCalls.map((call, callIndex) => (
              <details
                key={call.id}
                className="group/call rounded-lg border border-border bg-surface"
              >
                <summary className="focus-ring flex cursor-pointer list-none items-center justify-between gap-2 px-3 py-2 font-mono text-xs text-muted transition-colors hover:text-foreground [&::-webkit-details-marker]:hidden">
                  <ChevronRight
                    className="h-3 w-3 shrink-0 transition-transform group-open/call:rotate-90"
                    aria-hidden
                  />
                  <span>
                    llm call {callIndex + 1} · {call.model ?? "model"}
                  </span>
                  <span className="tabular-nums">
                    {formatTokens(call.total_tokens)} tok
                    {typeof call.cost_usd === "number" && call.cost_usd > 0
                      ? ` · ${formatCostUsd(call.cost_usd)}`
                      : ""}
                    {call.latency_ms != null
                      ? ` · ${formatDurationMs(call.latency_ms)}`
                      : ""}
                  </span>
                </summary>
                <div className="space-y-2 border-t border-border px-3 py-2">
                  {call.prompt_text && (
                    <div>
                      <p className="text-micro mb-1">Prompt</p>
                      <pre className="max-h-48 overflow-auto whitespace-pre-wrap rounded border border-border bg-background p-2 font-mono text-xs leading-5 text-foreground/85">
                        {call.prompt_text}
                      </pre>
                    </div>
                  )}
                  {call.completion_text && (
                    <div>
                      <p className="text-micro mb-1">Completion</p>
                      <pre className="max-h-48 overflow-auto whitespace-pre-wrap rounded border border-border bg-background p-2 font-mono text-xs leading-5 text-foreground/85">
                        {call.completion_text}
                      </pre>
                    </div>
                  )}
                  <p className="font-mono text-2xs tabular-nums text-subtle">
                    prompt {formatTokens(call.prompt_tokens)} · completion{" "}
                    {formatTokens(call.completion_tokens)}
                    {call.thinking_tokens
                      ? ` · thinking ${formatTokens(call.thinking_tokens)}`
                      : ""}
                  </p>
                </div>
              </details>
            ))}
          </div>
        </details>
      </div>
    </li>
  );
}
