"use client";

import { memo, type ReactNode } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { useReducedMotionStrict } from "@/components/motion";
import type { NodeData } from "@/types/workflow";

/**
 * Grouping frame. Two presentations, driven by `data.collapsed`:
 *
 * - Expanded (default): renders BEHIND its member nodes as a labeled hairline
 *   frame — a very-low-alpha surface tint, a small mono label top-left. Members
 *   carry `parentId` pointing at this node, so React Flow moves them when the
 *   frame is dragged. It has no handles (a frame is not a wired stage).
 * - Collapsed (presentational): renders as a compact card (~200×64) with the
 *   label, a member-count chip, and an aggregate run-status dot. WorkflowCanvas
 *   hides the members and re-points boundary edges at this frame FOR DISPLAY
 *   ONLY, so the collapsed frame grows target/source handles for those edges to
 *   land on. The persisted graph is untouched.
 *
 * The chevron toggles collapse via the canvas-injected `onToggleCollapse` hook
 * (absent in the read-only run lens, so the chevron simply doesn't render).
 * Rename reuses the shared rename hooks (isRenaming / onRenameCommit /
 * onRenameCancel) that displayNodes layers onto every node's data.
 */
type FrameData = NodeData & {
  isRenaming?: boolean;
  onRenameCommit?: (id: string, label: string) => void;
  onRenameCancel?: () => void;
  onToggleCollapse?: (id: string) => void;
  /** Injected (display-only) while collapsed: member count + aggregate status. */
  memberCount?: number;
  aggregateStatus?: "failed" | "running" | "completed";
  diffKind?: "added" | "removed" | "changed";
};

function StatusDot({ status }: { status: "failed" | "running" | "completed" }) {
  return (
    <span
      className={cn(
        "h-1.5 w-1.5 shrink-0 rounded-full",
        status === "failed" && "bg-destructive",
        status === "running" && "animate-pulse bg-active",
        status === "completed" && "bg-success"
      )}
      title={`Members ${status}`}
      aria-label={`Members ${status}`}
    />
  );
}

export const GroupNode = memo(function GroupNode({ id, data, selected }: NodeProps) {
  const frame = data as FrameData;
  const reduceMotion = useReducedMotionStrict();
  const collapsed = !!frame.collapsed;

  const chevron: ReactNode = frame.onToggleCollapse ? (
    <button
      type="button"
      title={collapsed ? "Expand group" : "Collapse group"}
      aria-label={collapsed ? "Expand group" : "Collapse group"}
      aria-expanded={!collapsed}
      onClick={(e) => {
        e.stopPropagation();
        frame.onToggleCollapse?.(id);
      }}
      className="nodrag nopan pointer-events-auto flex h-4 w-4 shrink-0 items-center justify-center rounded text-subtle transition-colors hover:text-foreground"
    >
      <ChevronDown
        className={cn(
          "h-3 w-3",
          !reduceMotion && "transition-transform duration-200",
          collapsed && "-rotate-90"
        )}
        strokeWidth={2}
      />
    </button>
  ) : null;

  const labelNode: ReactNode = frame.isRenaming ? (
    <input
      autoFocus
      defaultValue={frame.label ?? ""}
      onFocus={(e) => e.currentTarget.select()}
      onClick={(e) => e.stopPropagation()}
      onKeyDown={(e) => {
        e.stopPropagation();
        if (e.key === "Enter") {
          e.preventDefault();
          const next = e.currentTarget.value.trim();
          if (next) frame.onRenameCommit?.(id, next);
          else frame.onRenameCancel?.();
        } else if (e.key === "Escape") {
          e.preventDefault();
          frame.onRenameCancel?.();
        }
      }}
      onBlur={(e) => {
        const next = e.currentTarget.value.trim();
        if (next) frame.onRenameCommit?.(id, next);
        else frame.onRenameCancel?.();
      }}
      className="nodrag pointer-events-auto min-w-0 flex-1 border-b border-primary/40 bg-transparent font-mono text-2xs uppercase tracking-wide text-muted focus:outline-none"
    />
  ) : (
    <span className="truncate font-mono text-2xs uppercase tracking-wide text-subtle">
      {frame.label || "Group"}
    </span>
  );

  if (collapsed) {
    const count = frame.memberCount ?? 0;
    return (
      <div
        className={cn(
          "relative flex h-full w-full items-center gap-2 rounded-lg border border-border bg-surface px-3 shadow-elev-1 transition-[border-color] duration-fast",
          "hover:border-border-strong",
          selected && "border-primary/50 ring-1 ring-primary/40",
          frame.diffKind === "added" && "ring-2 ring-success/70",
          frame.diffKind === "removed" && "opacity-80 ring-2 ring-destructive/70",
          frame.diffKind === "changed" && "ring-2 ring-warning/70"
        )}
      >
        <Handle
          type="target"
          position={Position.Left}
          className="!border-2 !border-border-strong !bg-surface-elevated !shadow-elev-1"
        />
        {chevron}
        <span className="flex min-w-0 flex-1 items-center gap-2">{labelNode}</span>
        {frame.aggregateStatus && <StatusDot status={frame.aggregateStatus} />}
        <span className="shrink-0 rounded-[4px] border border-border bg-surface-overlay px-1.5 py-[1px] font-mono text-2xs tabular-nums text-muted">
          {count} node{count === 1 ? "" : "s"}
        </span>
        <Handle
          type="source"
          position={Position.Right}
          className="!border-2 !border-border-strong !bg-surface-elevated !shadow-elev-1"
        />
      </div>
    );
  }

  return (
    <div
      className={cn(
        "relative h-full w-full rounded-lg border border-border/80 bg-surface/[0.03] transition-[border-color] duration-fast",
        "hover:border-border-strong",
        selected && "border-primary/50 ring-1 ring-primary/40",
        frame.diffKind === "added" && "ring-2 ring-success/70",
        frame.diffKind === "removed" && "opacity-80 ring-2 ring-destructive/70",
        frame.diffKind === "changed" && "ring-2 ring-warning/70"
      )}
    >
      <div className="pointer-events-none absolute left-2 top-1.5 flex max-w-[calc(100%-1rem)] items-center gap-1">
        {chevron}
        {labelNode}
      </div>
    </div>
  );
});
