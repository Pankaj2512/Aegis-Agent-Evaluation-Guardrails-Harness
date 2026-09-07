"use client";

import { memo, useEffect, useId, useRef, useState } from "react";
import {
  BaseEdge,
  EdgeLabelRenderer,
  getBezierPath,
  type EdgeProps,
} from "@xyflow/react";
import { categorize, CATEGORY_COLOR_VAR } from "../nodes/category";
import { cn } from "@/lib/utils";

type EdgeData = {
  active?: boolean;
  failed?: boolean;
  sourceCompleted?: boolean;
  route?: string;
  sourceNodeType?: string;
  targetNodeType?: string;
  /** Drag-to-splice: this edge is the drop target under a dragged node. */
  spliceCandidate?: boolean;
};

function GradientEdgeImpl({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
  label,
  selected,
  interactionWidth,
}: EdgeProps) {
  const rawId = useId();
  const markerId = `${rawId}-arrow`;
  const drawId = `${rawId}-draw`;
  const [hovered, setHovered] = useState(false);

  const [path, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  const edgeData = data as EdgeData | undefined;
  const sCat = edgeData?.sourceNodeType ? categorize(edgeData.sourceNodeType) : "flow";
  const sColor = CATEGORY_COLOR_VAR[sCat];

  const active = !!edgeData?.active;
  const failed = !!edgeData?.failed;
  const spliceCandidate = !!edgeData?.spliceCandidate;
  // Error-branch edge (Feature 2): the source handed this route a
  // {error, node_id, node_type} payload. Rendered dashed + muted destructive.
  const isErrorRoute = edgeData?.route === "error";
  const sourceCompleted = edgeData?.sourceCompleted ?? false;
  const emphasized = selected || active || hovered || spliceCandidate;

  // A completed-but-quiet edge keeps a faint source-color tint so a finished
  // run reads as "settled" rather than reverting to neutral gray.
  const settled = sourceCompleted && !failed && !active;

  // One-shot completion pulse: fire an overlay stroke on the false→true edge of
  // sourceCompleted. Gated on `active` (mirrors WorkflowCanvas' skipEdgeAnim,
  // which forces active=false / sourceCompleted off for >80-edge graphs).
  const [pulsing, setPulsing] = useState(false);
  const prevCompleted = useRef(false);
  useEffect(() => {
    if (sourceCompleted && !prevCompleted.current) {
      setPulsing(true);
      const t = setTimeout(() => setPulsing(false), 700);
      prevCompleted.current = sourceCompleted;
      return () => clearTimeout(t);
    }
    prevCompleted.current = sourceCompleted;
  }, [sourceCompleted]);

  // Quiet gray at rest; the source category color appears when the edge is
  // selected, hovered, or carrying a live run. Failed always reads red. A
  // settled (completed) edge keeps a faint source-color tint. An error-route
  // edge reads muted-destructive at rest and full destructive when emphasized —
  // but spliceCandidate (primary) and a live failure both win over it.
  const stroke = spliceCandidate
    ? "var(--primary)"
    : failed
      ? "var(--canvas-edge-failed)"
      : isErrorRoute
        ? emphasized
          ? "var(--destructive)"
          : "color-mix(in srgb, var(--destructive) 60%, var(--canvas-edge))"
        : selected || active
          ? sColor
          : hovered
            ? "var(--canvas-edge-active)"
            : settled
              ? `color-mix(in srgb, ${sColor} 55%, var(--canvas-edge))`
              : "var(--canvas-edge)";

  // Edge label comes from the branch route (IF/Switch/Router/Classifier).
  // WorkflowCanvas sets edge.label = route (see makeEdge/graphToEdges) and
  // mirrors it onto data.route; prefer the explicit label prop.
  const rawLabel =
    (typeof label === "string" ? label : undefined) ?? edgeData?.route ?? "";
  // The dashed destructive stroke already signals an error route, so suppress the
  // redundant "error" floating label (EdgeInspector shows the chip instead).
  const labelText = isErrorRoute ? "" : rawLabel.trim();

  return (
    <>
      <defs>
        <marker
          id={markerId}
          viewBox="0 0 10 10"
          refX="7.5"
          refY="5"
          markerWidth="7"
          markerHeight="7"
          orient="auto-start-reverse"
        >
          <path d="M 0.5 1.5 L 8.5 5 L 0.5 8.5 z" fill={stroke} />
        </marker>
      </defs>

      {/* One-shot draw-in on mount; disabled under reduced motion. */}
      <style>{`
        @keyframes ${drawId} {
          from { stroke-dashoffset: var(--edge-draw-len); }
          to { stroke-dashoffset: 0; }
        }
        .edge-draw-${rawId.replace(/[:]/g, "")} {
          stroke-dasharray: var(--edge-draw-len);
          animation: ${drawId} 0.25s var(--ease-out, ease-out) forwards;
        }
        @media (prefers-reduced-motion: reduce) {
          .edge-draw-${rawId.replace(/[:]/g, "")} {
            stroke-dasharray: none;
            animation: none;
          }
        }
      `}</style>

      {/* Wide invisible hit path — generous hover/selection affordance. */}
      <path
        d={path}
        fill="none"
        stroke="transparent"
        strokeWidth={interactionWidth ?? 20}
        strokeLinecap="round"
        style={{ cursor: "pointer" }}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
      />

      <BaseEdge
        id={id}
        path={path}
        markerEnd={`url(#${markerId})`}
        className={`edge-draw-${rawId.replace(/[:]/g, "")}`}
        style={{
          // Draw length ≥ any realistic bezier so the dashoffset trick fully
          // conceals then reveals the path on mount.
          ["--edge-draw-len" as string]: "2000",
          stroke,
          strokeWidth: spliceCandidate ? 3 : emphasized ? 2.5 : 2,
          strokeOpacity: failed || emphasized ? 1 : settled ? 0.95 : 0.9,
          strokeLinecap: "round",
          // Dash to distinguish beyond color alone (failed run, or error route).
          // spliceCandidate wins — it stays solid while a node is dropped on it.
          strokeDasharray: spliceCandidate
            ? undefined
            : failed
              ? "6 4"
              : isErrorRoute
                ? "5 4"
                : undefined,
          fill: "none",
          transition:
            "stroke 0.18s var(--ease-out), stroke-width 0.18s var(--ease-out), stroke-opacity 0.18s var(--ease-out)",
        }}
      />

      {pulsing && !failed && (
        <BaseEdge
          id={`${id}-pulse`}
          path={path}
          className="animate-edge-settle"
          style={{
            stroke: sColor,
            strokeLinecap: "round",
            fill: "none",
            pointerEvents: "none",
          }}
        />
      )}

      {active && !failed && (
        <BaseEdge
          id={`${id}-flow`}
          path={path}
          className="animate-edge-flow"
          style={{
            stroke: "var(--canvas-edge-active)",
            strokeWidth: 2,
            strokeDasharray: "1 11",
            strokeLinecap: "round",
            fill: "none",
          }}
        />
      )}

      {labelText && (
        <EdgeLabelRenderer>
          <div
            className={cn(
              "nodrag nopan absolute -translate-x-1/2 -translate-y-1/2 rounded border border-border bg-surface-elevated px-1.5 py-0.5 font-mono text-2xs lowercase transition-colors",
              emphasized ? "text-foreground" : "text-muted"
            )}
            style={{
              transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
              pointerEvents: "all",
            }}
            onMouseEnter={() => setHovered(true)}
            onMouseLeave={() => setHovered(false)}
          >
            {labelText}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
}

export const GradientEdge = memo(GradientEdgeImpl);
