"use client";

import { memo, type ReactNode, useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import {
  AlertCircle,
  Check,
  Copy,
  FileText,
  MessageSquare,
  Pin,
  Plus,
  StickyNote,
  Trash2,
  TriangleAlert,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { formatCostUsd, formatDurationMs } from "@/lib/format";
import type { NodeData } from "@/types/workflow";
import { useReducedMotionStrict } from "@/components/motion";
import { categorize, supportsErrorBranch, type NodeCategory } from "./category";
import { useEntryStagger } from "./useEntryStagger";

/**
 * Per-node run telemetry surfaced as mono footer chips when the display overlay
 * is on. Injected onto node.data by the integrator (WorkflowCanvas) from
 * nodeRunResults / the run timeline. Kept optional so nodes render standalone.
 */
export interface NodeTelemetry {
  tokens?: number;
  costUsd?: number;
  latencyMs?: number;
}

export type NodeRuntimeState =
  | "idle"
  | "selected"
  | "running"
  | "completed"
  | "failed"
  | "awaiting_approval";

type ExtendedNodeData = NodeData & {
  isActive?: boolean;
  hasError?: boolean;
  errorMessage?: string;
  runtimeState?: NodeRuntimeState;
  startedAt?: number;
  category?: NodeCategory;
  diffKind?: "added" | "removed" | "changed";
  // Canvas-injected interaction hooks (present on display nodes only).
  onQuickAdd?: (nodeId: string) => void;
  onDuplicate?: (nodeId: string) => void;
  onDelete?: (nodeId: string) => void;
  // Inline rename (label editing in place).
  isRenaming?: boolean;
  onRenameCommit?: (id: string, label: string) => void;
  onRenameCancel?: () => void;
  // Output peek chip (view a completed/failed node's output).
  peekAvailable?: boolean;
  onPeekOutput?: (id: string) => void;
  // Per-node run telemetry overlay (M2-3). `showTelemetry` is the display
  // toggle (owned by CanvasToolbar / WorkflowCanvas); telemetry is the payload.
  telemetry?: NodeTelemetry;
  showTelemetry?: boolean;
  // Pinned-output state: when true the node header shows a pin glyph + dashed
  // accent underline (reuses the awaiting_approval dashed idiom). The pinned
  // map + api.createRun(pinned_outputs) is owned by WorkflowCanvas.
  pinned?: boolean;
  // Run-lens focus: while an earlier node is active, upcoming (not-yet-run)
  // nodes recede so the run reads as a moving wavefront. Applied as an opacity
  // multiplier, reduced-motion-gated, kept independent of the entry transition.
  dimmed?: boolean;
  // Registry-driven config lint (Feature 4): missing-required-field messages,
  // injected by WorkflowCanvas. Surfaced as a quiet glyph only while idle —
  // runtime state cues always win.
  lintIssues?: string[];
};

type Props = NodeProps & {
  icon: ReactNode;
  footer?: ReactNode;
};

const BORDER_BY_STATE: Record<NodeRuntimeState, string> = {
  idle: "border-border",
  selected: "border-primary/50",
  running: "border-active/55",
  completed: "border-success",
  failed: "border-destructive/50",
  awaiting_approval: "border-active border-dashed",
};

const SHADOW_BY_STATE: Record<NodeRuntimeState, string> = {
  idle: "shadow-elev-1",
  selected: "shadow-elev-2",
  running: "shadow-glow-active",
  completed: "shadow-glow-success",
  failed: "shadow-glow-destructive",
  awaiting_approval: "shadow-glow-active",
};

function CSSVar(name: string): string {
  return `var(--${name})`;
}

/**
 * Runtime state is independent of selection. Selection is a composable overlay
 * (a ring) applied on top so selecting a failed/running node keeps its red
 * border / progress sweep visible instead of masking it.
 */
function resolveRuntimeState(data: ExtendedNodeData): NodeRuntimeState {
  if (data.runtimeState) return data.runtimeState;
  if (data.hasError) return "failed";
  if (data.isActive) return "running";
  return "idle";
}

export const BaseNode = memo(function BaseNode({ id, data, selected, icon, footer }: Props) {
  const nodeData = data as unknown as ExtendedNodeData;
  const isNote = nodeData.nodeType === "note";
  // Only true triggers lack a target handle; input_schema receives edges
  // (the starter templates wire trigger -> input_schema).
  const isTrigger = nodeData.nodeType === "trigger";
  const isEnd = nodeData.nodeType === "end";

  const cat: NodeCategory = nodeData.category ?? categorize(nodeData.nodeType);
  const runtimeState = resolveRuntimeState(nodeData);
  const entryDelay = useEntryStagger();
  const reduceMotion = useReducedMotionStrict();
  // Hover affordances (lift + border/shadow pickup) are reserved for the idle
  // state. A running/completed/failed node must keep its data-semantic border
  // and status glow — hover chrome never overrides a state cue, and the card
  // never lifts underneath the running progress sweep.
  const idle = runtimeState === "idle";
  // Config-lint glyph is idle-only: a running/completed/failed state cue must
  // never share the header with a "missing field" warning.
  const lintIssues = nodeData.lintIssues ?? [];
  const showLint = idle && lintIssues.length > 0;
  // Node-anchored comments (Tier-4). Unlike lint, the count is an annotation —
  // not a state cue — so it may show in every runtime state, but stays quiet
  // (muted, no chroma). Rendered after the lint glyph when both are present.
  const commentCount = nodeData.comments?.length ?? 0;
  // A quiet error-branch source handle on the bottom edge, for the node types
  // the backend accepts an error edge from (Feature 2).
  const showErrorHandle = !isEnd && !isTrigger && supportsErrorBranch(nodeData.nodeType, nodeData);

  const [elapsedSec, setElapsedSec] = useState(0);
  useEffect(() => {
    if (runtimeState !== "running") return;
    const startedAt = nodeData.startedAt ?? Date.now();
    const tick = () => setElapsedSec(Math.floor((Date.now() - startedAt) / 1000));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [runtimeState, nodeData.startedAt]);

  if (isNote) {
    return (
      <div
        className={cn(
          "max-w-[220px] rounded-xl border border-dashed border-border bg-surface-elevated px-4 py-3",
          selected && "ring-1 ring-primary",
          nodeData.diffKind === "added" && "ring-2 ring-success/70",
          nodeData.diffKind === "removed" && "ring-2 ring-destructive/70 opacity-80",
          nodeData.diffKind === "changed" && "ring-2 ring-warning/70"
        )}
      >
        <div className="flex items-start gap-2">
          <StickyNote className="h-4 w-4 shrink-0 text-accent" />
          <div className="min-w-0">
            <p className="max-w-full break-words text-sm font-medium text-foreground">{nodeData.label}</p>
            <p className="mt-1 max-w-full break-words text-xs leading-relaxed text-muted">
              {nodeData.noteText || "Add a note…"}
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <motion.div
      layout="size"
      initial={{ opacity: 0, scale: 0.96 }}
      animate={{ opacity: nodeData.dimmed ? 0.5 : 1, scale: 1 }}
      // Scale keeps the staggered mount delay; opacity gets its own delay-free
      // (reduced-motion-gated) transition so run-lens dimming toggles crisply
      // instead of inheriting the entry stagger every time the wavefront moves.
      transition={{
        duration: 0.18,
        ease: "easeOut",
        delay: entryDelay,
        opacity: { duration: reduceMotion ? 0 : 0.16, ease: "easeOut" },
      }}
      // A precise -1px pickup on hover. Driven by framer (not a Tailwind
      // translate util) because framer owns the card's inline transform via
      // layout/animate — a CSS transform class would be overridden. Scoped
      // transition keeps the entry delay from leaking onto the hover; gated
      // off under strict reduced motion and outside the idle state.
      whileHover={
        reduceMotion || !idle
          ? undefined
          : { y: -1, transition: { duration: 0.14, ease: [0.16, 1, 0.3, 1] } }
      }
      className={cn(
        // No overflow-hidden: it would clip the connection handles' outer
        // half, shrinking their hit area to a sliver.
        "node-card group relative min-h-[72px] w-[200px] rounded-lg border bg-surface shadow-elev-1",
        "transition-[border-color,box-shadow] duration-fast",
        // Idle-only hover pickup so a state border/glow is never masked.
        idle && "hover:border-border-strong hover:shadow-elev-2",
        BORDER_BY_STATE[runtimeState],
        SHADOW_BY_STATE[runtimeState],
        // Selection is a composable ring overlaid on the runtime state so a
        // failed/running node keeps its own border+glow while selected.
        selected && "ring-1 ring-primary/60",
        nodeData.diffKind === "added" && "ring-2 ring-success/70",
        nodeData.diffKind === "removed" && "ring-2 ring-destructive/70 opacity-80",
        nodeData.diffKind === "changed" && "ring-2 ring-warning/70"
      )}
    >
      <span
        className="absolute bottom-0 left-0 top-0 z-[1] w-[2px] rounded-l-lg"
        style={{
          // A 2px colored *rule*, not a saturated stripe: blended toward the
          // chrome border so the category reads as a hairline seam. Honors the
          // <=2px category-hue contract.
          background: `color-mix(in srgb, ${CSSVar(`cat-${cat}`)} 72%, var(--border-strong))`,
        }}
        aria-hidden
      />

      {runtimeState === "running" && (
        // The 2px strip is overflow-hidden, but the CARD is not (would clip
        // handle hit areas). Indeterminate sweep animated via framer.
        <div className="pointer-events-none absolute inset-x-0 top-0 z-[2] h-[2px] overflow-hidden rounded-t-lg">
          <motion.span
            className="absolute top-0 h-full w-1/3 rounded-full bg-active"
            initial={{ x: "-100%" }}
            animate={{ x: "300%" }}
            transition={{ duration: 1.1, ease: "easeInOut", repeat: Infinity }}
          />
        </div>
      )}

      {(nodeData.onDuplicate || nodeData.onDelete) && (
        <div
          className={cn(
            "nodrag nopan absolute -top-9 right-0 z-10 flex items-center gap-0.5 rounded-md border border-border bg-surface-elevated p-0.5 shadow-elev-2 transition-opacity",
            selected ? "opacity-100" : "opacity-0 group-hover:opacity-100"
          )}
        >
          {nodeData.onDuplicate && (
            <button
              type="button"
              title="Duplicate (⌘D)"
              aria-label="Duplicate node"
              onClick={(e) => {
                e.stopPropagation();
                nodeData.onDuplicate?.(id);
              }}
              className="rounded p-1 text-muted transition-colors hover:bg-surface-hover hover:text-foreground"
            >
              <Copy className="h-3 w-3" />
            </button>
          )}
          {nodeData.onDelete && (
            <button
              type="button"
              title="Delete"
              aria-label="Delete node"
              onClick={(e) => {
                e.stopPropagation();
                nodeData.onDelete?.(id);
              }}
              className="rounded p-1 text-muted transition-colors hover:bg-surface-hover hover:text-destructive"
            >
              <Trash2 className="h-3 w-3" />
            </button>
          )}
        </div>
      )}

      {!isEnd && nodeData.onQuickAdd && (
        <button
          type="button"
          title="Add next node"
          aria-label="Add next node"
          onClick={(e) => {
            e.stopPropagation();
            nodeData.onQuickAdd?.(id);
          }}
          className={cn(
            "nodrag nopan absolute -right-7 top-1/2 z-10 flex h-5 w-5 -translate-y-1/2 items-center justify-center rounded-full border border-border bg-surface-elevated text-muted shadow-elev-1 transition-[opacity,color,border-color]",
            "hover:border-border-strong hover:text-foreground",
            selected ? "opacity-100" : "opacity-0 group-hover:opacity-100"
          )}
        >
          <Plus className="h-3 w-3" />
        </button>
      )}

      {!isTrigger && (
        <Handle
          type="target"
          position={Position.Left}
          className="!border-2 !bg-surface-elevated !shadow-elev-1"
          style={{
            borderColor: `color-mix(in srgb, ${CSSVar(`cat-${cat}`)} 72%, var(--border-strong))`,
          }}
        />
      )}

      <div
        className={cn(
          "flex items-center justify-between gap-2 rounded-t-lg border-b px-3 py-2 pl-3.5",
          // Pinned output reuses the awaiting_approval dashed idiom as an accent
          // underline on the header (data-semantic accent, not chrome color).
          // The header only carries a bottom border, so border-dashed styles it.
          nodeData.pinned && "border-dashed !border-b-accent"
        )}
        style={{
          // Top-lit category wash: the hue is strongest at the header's top
          // edge and resolves to plain surface by its baseline, so it reads as
          // light catching the rim rather than a colored panel. Integrated
          // exposure stays under the ~10% low-alpha wash budget, and the card's
          // achromatic ::before paints a crisp 1px highlight over the top edge.
          background: `linear-gradient(180deg, color-mix(in srgb, ${CSSVar(`cat-${cat}`)} 10%, var(--surface)) 0%, color-mix(in srgb, ${CSSVar(`cat-${cat}`)} 6%, var(--surface)) 52%, var(--surface) 100%)`,
          borderBottomColor: nodeData.pinned
            ? undefined
            : `color-mix(in srgb, ${CSSVar(`cat-${cat}`)} 18%, var(--border))`,
        }}
      >
        <div
          className="flex h-6 w-6 shrink-0 items-center justify-center rounded-[5px]"
          style={{
            // A quiet inset token: low-alpha category bed + a 1px inner top
            // highlight so the chip catches the card's top light, plus a
            // hairline category ring. The glyph itself is the one place full
            // hue is legitimate — a small, data-semantic category mark.
            background: `color-mix(in srgb, ${CSSVar(`cat-${cat}`)} 16%, transparent)`,
            boxShadow: `inset 0 1px 0 0 var(--node-highlight), inset 0 0 0 1px color-mix(in srgb, ${CSSVar(`cat-${cat}`)} 28%, transparent)`,
            color: CSSVar(`cat-${cat}`),
          }}
        >
          {icon}
        </div>
        <div className="flex min-w-0 items-center gap-1">
          <AnimatePresence>
            {runtimeState === "completed" && (
              <motion.span
                key="check"
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.8 }}
                className="flex items-center"
              >
                <Check className="h-3 w-3 text-success" />
              </motion.span>
            )}
            {runtimeState === "failed" && (
              <motion.span
                key="failed"
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.8 }}
                className="flex items-center"
              >
                <AlertCircle className="h-3 w-3 text-destructive" />
              </motion.span>
            )}
          </AnimatePresence>
          <span className="truncate font-mono text-2xs lowercase tracking-[0.01em] text-subtle">
            {nodeData.nodeType}
          </span>
          {showLint && (
            <span
              role="img"
              className="flex shrink-0 items-center text-warning"
              title={`Needs configuration: ${lintIssues.join("; ")}`}
              aria-label={`Needs configuration: ${lintIssues.join("; ")}`}
            >
              <TriangleAlert className="h-3 w-3" aria-hidden />
            </span>
          )}
          {commentCount > 0 && (
            <span
              role="img"
              className="flex shrink-0 items-center gap-0.5 text-muted"
              title={`${commentCount} comment${commentCount === 1 ? "" : "s"}`}
              aria-label={`${commentCount} comment${commentCount === 1 ? "" : "s"}`}
            >
              <MessageSquare className="h-3 w-3" aria-hidden />
              <span className="font-mono text-2xs tabular-nums" aria-hidden>
                {commentCount}
              </span>
            </span>
          )}
          {nodeData.peekAvailable &&
            (runtimeState === "completed" || runtimeState === "failed") &&
            nodeData.onPeekOutput && (
              <button
                type="button"
                title="View output"
                aria-label="View output"
                onClick={(e) => {
                  e.stopPropagation();
                  nodeData.onPeekOutput?.(id);
                }}
                className="nodrag nopan flex shrink-0 items-center rounded p-0.5 text-muted transition-colors hover:text-foreground"
              >
                <FileText className="h-3 w-3" />
              </button>
            )}
          {nodeData.pinned && (
            <span
              className="flex shrink-0 items-center text-accent"
              title="Output pinned for run-from-here"
              aria-label="Output pinned"
            >
              <Pin className="h-3 w-3 fill-current" />
            </span>
          )}
        </div>
      </div>

      <div className="px-3 py-2.5 pl-3.5">
        {nodeData.isRenaming ? (
          <input
            autoFocus
            defaultValue={nodeData.label ?? ""}
            onFocus={(e) => e.currentTarget.select()}
            onClick={(e) => e.stopPropagation()}
            onKeyDown={(e) => {
              e.stopPropagation();
              if (e.key === "Enter") {
                e.preventDefault();
                const next = e.currentTarget.value.trim();
                if (next) nodeData.onRenameCommit?.(id, next);
                else nodeData.onRenameCancel?.();
              } else if (e.key === "Escape") {
                e.preventDefault();
                nodeData.onRenameCancel?.();
              }
            }}
            onBlur={(e) => {
              const next = e.currentTarget.value.trim();
              if (next) nodeData.onRenameCommit?.(id, next);
              else nodeData.onRenameCancel?.();
            }}
            className="nodrag w-full border-b border-primary/40 bg-transparent text-sm font-medium leading-5 tracking-[-0.006em] text-foreground focus:outline-none"
          />
        ) : (
          <div className="max-w-full break-words line-clamp-2 text-sm font-medium leading-5 tracking-[-0.006em] text-foreground">
            {nodeData.label || "Untitled"}
          </div>
        )}
        {runtimeState === "running" && (
          <div className="mt-2 flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-active" />
            <span className="font-mono text-2xs tabular-nums text-active">{elapsedSec}s</span>
          </div>
        )}
        {footer && <div className="mt-2">{footer}</div>}
        {nodeData.showTelemetry &&
          (runtimeState === "completed" || runtimeState === "failed") && (
            <div className="mt-2">
              <TelemetryFooter
                failed={runtimeState === "failed"}
                telemetry={nodeData.telemetry}
              />
            </div>
          )}
        {nodeData.diffKind && (
          <div
            className={cn(
              "mt-2 font-mono text-2xs uppercase tracking-widest",
              nodeData.diffKind === "added" && "text-success",
              nodeData.diffKind === "removed" && "text-destructive",
              nodeData.diffKind === "changed" && "text-warning"
            )}
          >
            {nodeData.diffKind}
          </div>
        )}
      </div>

      <AnimatePresence>
        {runtimeState === "failed" && nodeData.errorMessage && (
          <motion.div
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 4 }}
            className="text-caption pointer-events-none absolute -bottom-2 left-2 right-2 translate-y-full rounded-md border border-destructive/40 bg-surface-elevated p-2 shadow-elev-2"
          >
            {nodeData.errorMessage}
          </motion.div>
        )}
      </AnimatePresence>

      {!isEnd && (
        <Handle
          type="source"
          position={Position.Right}
          className="!border-2 !bg-surface-elevated !shadow-elev-1"
          style={{
            borderColor: `color-mix(in srgb, ${CSSVar(`cat-${cat}`)} 72%, var(--border-strong))`,
          }}
        />
      )}

      {showErrorHandle && (
        // A second, quieter source handle on the bottom edge: small + square-ish
        // with a low-alpha destructive ring. Connections from it are stamped
        // data.route = "error" by WorkflowCanvas onConnect. Sits at bottom-center,
        // clear of the left category seam and the right success/data source.
        <Handle
          id="error"
          type="source"
          position={Position.Bottom}
          title="On error"
          className="!h-2 !w-2 !min-w-0 !rounded-[3px] !border !bg-surface-elevated"
          style={{
            borderColor: "color-mix(in srgb, var(--destructive) 60%, var(--border-strong))",
          }}
        />
      )}
    </motion.div>
  );
});

/**
 * A small mono chip for the node footer. Renders config summaries (model,
 * provider, policy names). Truncates long values to keep the 200px width.
 */
export function NodeChip({ children }: { children: ReactNode }) {
  return (
    <span className="inline-block max-w-full truncate rounded-[4px] border border-border bg-surface-overlay px-1.5 py-[1px] font-mono text-2xs leading-[14px] tabular-nums text-muted">
      {children}
    </span>
  );
}

/** A wrapping row of NodeChips. Renders nothing when there are no chips. */
export function NodeChipRow({ chips }: { chips: ReactNode[] }) {
  const items = chips.filter(Boolean);
  if (items.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-1">
      {items.map((chip, i) => (
        <NodeChip key={i}>{chip}</NodeChip>
      ))}
    </div>
  );
}

/** Compact integer formatting for token counts (1234 -> 1.2k). Cheap. */
function formatTokens(n: number): string {
  if (n < 1000) return String(n);
  return `${(n / 1000).toFixed(n < 10000 ? 1 : 0)}k`;
}

/**
 * Per-node telemetry footer (M2-3). Completed nodes get mono tokens / ms / cost
 * chips; a failed node gets a single destructive chip. Rendered only when the
 * display overlay is on — kept as a light presentational component so BaseNode's
 * memoized re-render during runs stays cheap.
 */
function TelemetryFooter({
  failed,
  telemetry,
}: {
  failed: boolean;
  telemetry?: NodeTelemetry;
}) {
  if (failed) {
    return (
      <span className="inline-block rounded-[4px] border border-destructive/40 bg-destructive/10 px-1.5 py-[1px] font-mono text-2xs leading-[14px] text-destructive">
        failed
      </span>
    );
  }
  const chips: ReactNode[] = [];
  if (telemetry?.tokens != null && telemetry.tokens > 0) {
    chips.push(`${formatTokens(telemetry.tokens)} tok`);
  }
  if (telemetry?.latencyMs != null) {
    // A measured-but-sub-millisecond step reads as "<1ms", never a bare "0ms":
    // an instant node should still show it ran, not look like missing data.
    chips.push(telemetry.latencyMs >= 1 ? formatDurationMs(telemetry.latencyMs) : "<1ms");
  }
  if (telemetry?.costUsd != null && telemetry.costUsd > 0) {
    chips.push(formatCostUsd(telemetry.costUsd));
  }
  return <NodeChipRow chips={chips} />;
}
