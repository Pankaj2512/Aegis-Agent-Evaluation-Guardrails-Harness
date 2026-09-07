"use client";

import { ChevronRight } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { CopyButton } from "@/components/ui/copy-button";
import { EvalScoresChart } from "@/components/results/EvalScoresChart";
import { categorize, CATEGORY_COLOR_VAR } from "@/components/canvas/nodes/category";
import { formatOutput } from "@/lib/pretty-output";
import { runStatusLabel, runStatusVariant } from "@/lib/run-status";
import { cn } from "@/lib/utils";
import type { EvalScores, NodeResult } from "@/types/workflow";

interface NodeResultRowProps {
  node: NodeResult;
  /** node.latency_ms / Σ(latency_ms) — 0..1. */
  durationShare: number;
}

/** Maps a node status onto a ring/tint token used on the glyph. */
function statusRing(status: string): string {
  const s = status.toLowerCase();
  if (s === "failed" || s === "error") return "ring-2 ring-destructive/60";
  if (s === "running" || s === "pending") return "ring-2 ring-warning/60 animate-pulse";
  if (s === "completed" || s === "success" || s === "passed") return "ring-2 ring-success/40";
  return "ring-1 ring-border";
}

/**
 * Compact node-result row for the canvas results panel — a trimmed
 * TraceNodeRow with no llm-call drilldown and no timeline rail.
 */
export function NodeResultRow({ node, durationShare }: NodeResultRowProps) {
  const colorVar = CATEGORY_COLOR_VAR[categorize(node.node_type)];
  const status = node.status?.toLowerCase() ?? "";
  const isFailed = status === "failed" || status === "error";
  const defaultOpen = isFailed || Boolean(node.guardrail_status);
  const barPct = Math.max(0, Math.min(1, durationShare)) * 100;

  const rawOutput = node.output ?? "";
  const { text: formattedOutput, isJson } = formatOutput(rawOutput);
  const hasOutput = rawOutput.trim().length > 0;

  return (
    <li className="rounded-lg border border-border bg-surface-input/60 p-3">
      <div className="flex items-center gap-3">
        <span
          className={cn(
            "relative z-10 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-border bg-surface",
            statusRing(status)
          )}
        >
          <span
            aria-hidden
            className="h-2 w-2 rounded-full"
            style={{ backgroundColor: colorVar }}
          />
        </span>

        <div className="min-w-0 flex-1">
          <h4 className="truncate text-sm font-medium text-foreground">{node.node_label}</h4>
          <p className="truncate font-mono text-2xs lowercase text-subtle">{node.node_type}</p>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          {node.latency_ms != null && (
            <span className="font-mono text-2xs text-muted">{node.latency_ms} ms</span>
          )}
          <Badge variant={runStatusVariant(node.status)}>{runStatusLabel(node.status)}</Badge>
        </div>
      </div>

      {/* Proportional duration bar — share of run time */}
      {node.latency_ms != null && (
        <div className="mt-2 h-1 overflow-hidden rounded-full bg-surface-input">
          <div
            className="h-1 rounded-full"
            style={{
              width: `${barPct}%`,
              minWidth: barPct > 0 ? "2px" : undefined,
              backgroundColor: `color-mix(in srgb, ${colorVar} 35%, transparent)`,
            }}
          />
        </div>
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
          {hasOutput && (
            <div className="space-y-1.5">
              <div className="flex items-center justify-between gap-2">
                {isJson ? (
                  <Badge variant="outline">json</Badge>
                ) : (
                  <span aria-hidden />
                )}
                <CopyButton text={rawOutput} label="Copy output" />
              </div>
              <pre className="whitespace-pre-wrap break-words rounded-lg border border-border bg-background p-3 font-mono text-xs leading-5 text-foreground/90">
                {formattedOutput}
              </pre>
            </div>
          )}
          {node.evaluation_scores && (
            <div className="rounded-lg border border-border bg-surface-input p-3">
              <EvalScoresChart scores={node.evaluation_scores as EvalScores} compact />
            </div>
          )}
          {node.guardrail_status && (
            <Badge variant={runStatusVariant(node.guardrail_status)}>
              Guardrail: {runStatusLabel(node.guardrail_status)}
            </Badge>
          )}
        </div>
      </details>
    </li>
  );
}
