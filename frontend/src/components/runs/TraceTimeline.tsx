"use client";

import { useMemo } from "react";
import { Badge } from "@/components/ui/badge";
import { SectionCard } from "@/components/ui/section-card";
import { TraceNodeRow, type TraceBarGeometry } from "@/components/runs/TraceNodeRow";
import { formatDurationMs } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { RunTimeline, RunTrace } from "@/lib/api";
import type { LlmCall, NodeResult } from "@/types/workflow";

interface TraceTimelineProps {
  nodes: NodeResult[];
  llmCalls: LlmCall[];
  /** Real span geometry from api.getRunTimeline; undefined until it loads. */
  timeline?: RunTimeline | null;
  /** Nested trace tree from api.getRunTrace; drives the agent-step drill-down. */
  trace?: RunTrace | null;
  /** True while the run is still live (pending/running/awaiting_approval). */
  runLive: boolean;
  /** True when no results yet but the run is still producing them. */
  awaitingResults: boolean;
  /** Optional: focus/select a node on the canvas (M3 wiring). */
  onJumpToNode?: (nodeId: string) => void;
}

const GRID_STEPS = 4;

export function TraceTimeline({
  nodes,
  llmCalls,
  timeline,
  trace,
  runLive,
  awaitingResults,
  onJumpToNode,
}: TraceTimelineProps) {
  // Map each node's child spans (llm_call / tool_call) from the trace tree.
  const childSpansByNode = useMemo(() => {
    const map = new Map<string, RunTrace["spans"][number]["children"]>();
    for (const node of trace?.spans ?? []) {
      if (node.node_id) map.set(node.node_id, node.children);
    }
    return map;
  }, [trace]);
  // Total run duration drives the shared axis. Fall back to the sum of the
  // real spans (or node latencies) when the endpoint reports 0/null.
  const total = useMemo(() => {
    if (timeline?.total_duration_ms && timeline.total_duration_ms > 0) {
      return timeline.total_duration_ms;
    }
    if (timeline?.nodes.length) {
      const span = Math.max(
        ...timeline.nodes.map((n) => n.start_offset_ms + Math.max(n.duration_ms, 0))
      );
      if (span > 0) return span;
    }
    return 0;
  }, [timeline]);

  const hasAxis = total > 0;

  // Merge real geometry into node payloads, keyed by node_id. Keeps the
  // ordering + expandable payloads from `nodes`; layers offset+width on top.
  const geometryByNode = useMemo(() => {
    const map = new Map<string, TraceBarGeometry>();
    if (!timeline || total <= 0) return map;
    for (const tn of timeline.nodes) {
      const width = Math.max(tn.duration_ms, 0);
      map.set(tn.node_id, {
        leftPct: (tn.start_offset_ms / total) * 100,
        // Floor to a hairline so instantaneous spans stay visible.
        widthPct: Math.max((width / total) * 100, 0.5),
        durationMs: tn.duration_ms,
        startOffsetMs: tn.start_offset_ms,
      });
    }
    return map;
  }, [timeline, total]);

  // Fallback: equal-width bars in completion order when we have no axis.
  const fallbackGeometry = (index: number): TraceBarGeometry => {
    const slice = nodes.length > 0 ? 100 / nodes.length : 100;
    return {
      leftPct: slice * index,
      widthPct: Math.max(slice - 1, 1),
      durationMs: nodes[index]?.latency_ms ?? null,
      startOffsetMs: null,
    };
  };

  const description = hasAxis
    ? "true span waterfall on a shared time axis"
    : "node execution order";

  return (
    <SectionCard
      title="Node timeline"
      description={description}
      actions={<Badge variant="outline">{nodes.length} results</Badge>}
    >
      {awaitingResults && (
        <div className="mb-3 flex items-center gap-3 rounded-lg border border-border bg-surface-input px-3 py-2.5 text-sm text-muted">
          <span className="h-2 w-2 animate-pulse rounded-full bg-warning" />
          Waiting for node results…
        </div>
      )}
      {nodes.length === 0 && !awaitingResults ? (
        <p className="text-sm text-subtle">No node results recorded for this run.</p>
      ) : (
        <>
          {hasAxis && (
            // Bar track sits after the 2.5rem rail (left) and before the
            // 4.5rem duration label (right); mirror that inset for the axis.
            <div className="relative mb-3 ml-10 mr-[4.5rem]">
              {/* Tick labels sit on the same percent geometry as the gridlines
                  below, so a label always names the rule it is above. */}
              <div className="relative h-4 font-mono text-2xs tabular-nums text-subtle">
                {Array.from({ length: GRID_STEPS + 1 }).map((_, i) => (
                  <span
                    key={i}
                    className={cn(
                      "absolute top-0 whitespace-nowrap",
                      i === 0
                        ? "translate-x-0"
                        : i === GRID_STEPS
                          ? "-translate-x-full"
                          : "-translate-x-1/2"
                    )}
                    style={{ left: `${(i / GRID_STEPS) * 100}%` }}
                  >
                    {formatDurationMs((total * i) / GRID_STEPS)}
                  </span>
                ))}
              </div>
            </div>
          )}
          <div className="relative">
            {/* Faint vertical gridlines spanning the rows, aligned to the axis */}
            {hasAxis && (
              <div
                aria-hidden
                className="pointer-events-none absolute inset-y-0 left-10 right-[4.5rem]"
              >
                {Array.from({ length: GRID_STEPS + 1 }).map((_, i) => (
                  <span
                    key={i}
                    className="absolute inset-y-0 w-px bg-border-mid"
                    style={{
                      left: `${(i / GRID_STEPS) * 100}%`,
                      opacity: i === 0 || i === GRID_STEPS ? 0.6 : 0.35,
                    }}
                  />
                ))}
              </div>
            )}
            <ol className="relative">
              {nodes.map((node, index) => (
                <TraceNodeRow
                  key={node.id}
                  node={node}
                  llmCalls={llmCalls}
                  geometry={geometryByNode.get(node.node_id) ?? fallbackGeometry(index)}
                  childSpans={childSpansByNode.get(node.node_id)}
                  isLast={index === nodes.length - 1}
                  runLive={runLive}
                  onJumpToNode={onJumpToNode}
                />
              ))}
            </ol>
          </div>
        </>
      )}
    </SectionCard>
  );
}
