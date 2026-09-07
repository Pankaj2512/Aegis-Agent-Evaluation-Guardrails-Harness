"use client";

import { useEffect, useRef } from "react";
import Link from "next/link";
import { Pin, PinOff, Play, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { CopyButton } from "@/components/ui/copy-button";
import { formatOutput } from "@/lib/pretty-output";

interface NodeOutputPeekProps {
  position: { x: number; y: number };
  nodeId: string;
  nodeLabel: string;
  output: string;
  latencyMs?: number | null;
  guardrailStatus?: string | null;
  runId: string | null;
  /** Whether this node's output is currently pinned (owned by WorkflowCanvas). */
  pinned?: boolean;
  /**
   * Toggle pin on this node's output. WorkflowCanvas holds the pinned map and
   * feeds it back into api.createRun(pinned_outputs). No mutation happens here.
   */
  onPinOutput?: (nodeId: string, output: string) => void;
  /**
   * Start a run from this node. WorkflowCanvas calls api.createRun with
   * start_node_id=nodeId + its pinned_outputs. No mutation happens here.
   */
  onRunFromHere?: (nodeId: string) => void;
  onClose: () => void;
}

const PEEK_W = 320;
const PEEK_H = 260;
const MAX_CHARS = 600;

function guardrailVariant(status: string): "success" | "warning" | "destructive" | "default" {
  const s = status.toLowerCase();
  if (s.includes("pass") || s.includes("ok") || s.includes("clean")) return "success";
  if (s.includes("block") || s.includes("fail")) return "destructive";
  if (s.includes("warn") || s.includes("mask")) return "warning";
  return "default";
}

/**
 * Floating output preview for a completed node — follows the QuickAddMenu
 * house pattern: fixed, clamped to viewport, closes on outside-mousedown or
 * Escape.
 */
export function NodeOutputPeek({
  position,
  nodeId,
  nodeLabel,
  output,
  latencyMs,
  guardrailStatus,
  runId,
  pinned = false,
  onPinOutput,
  onRunFromHere,
  onClose,
}: NodeOutputPeekProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onPointerDown = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    };
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [onClose]);

  const clampedX = Math.max(8, Math.min(position.x, window.innerWidth - PEEK_W - 8));
  const clampedY = Math.max(8, Math.min(position.y, window.innerHeight - PEEK_H - 8));

  const { text: formatted, isJson } = formatOutput(output);
  const truncated =
    formatted.length > MAX_CHARS ? `${formatted.slice(0, MAX_CHARS)}…` : formatted;
  const hasOutput = output.trim().length > 0;

  return (
    <div
      ref={containerRef}
      className="glass-panel fixed z-50 flex w-80 flex-col overflow-hidden rounded-lg shadow-elev-3"
      style={{ left: clampedX, top: clampedY }}
      role="dialog"
      aria-label={`Output for ${nodeLabel}`}
    >
      <div className="flex items-center justify-between gap-2 border-b border-border px-3 py-2">
        <span className="min-w-0 flex-1 truncate text-sm font-semibold text-foreground">
          {nodeLabel}
        </span>
        <div className="flex shrink-0 items-center gap-0.5">
          {hasOutput && <CopyButton text={output} label="Copy output" />}
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="focus-ring flex h-6 w-6 shrink-0 items-center justify-center rounded-md text-muted transition-colors hover:bg-surface-hover hover:text-foreground"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      <div className="max-h-48 overflow-y-auto px-3 py-2.5">
        {truncated.trim() ? (
          <pre className="whitespace-pre-wrap break-words font-mono text-xs leading-5 text-foreground">
            {truncated}
          </pre>
        ) : (
          <p className="font-mono text-xs text-muted">No output.</p>
        )}
      </div>

      {(onPinOutput || onRunFromHere) && (
        <div className="flex items-center gap-1 border-t border-border px-2 py-1.5">
          {onPinOutput && (
            <button
              type="button"
              onClick={() => onPinOutput(nodeId, output)}
              aria-pressed={pinned}
              className={
                "focus-ring flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium transition-colors " +
                (pinned
                  ? "text-accent hover:bg-surface-hover"
                  : "text-muted hover:bg-surface-hover hover:text-foreground")
              }
            >
              {pinned ? (
                <PinOff className="h-3.5 w-3.5" />
              ) : (
                <Pin className="h-3.5 w-3.5" />
              )}
              {pinned ? "Unpin output" : "Pin output"}
            </button>
          )}
          {onRunFromHere && (
            <button
              type="button"
              onClick={() => onRunFromHere(nodeId)}
              className="focus-ring ml-auto flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium text-muted transition-colors hover:bg-surface-hover hover:text-foreground"
            >
              <Play className="h-3.5 w-3.5" />
              Run from here
            </button>
          )}
        </div>
      )}

      {(latencyMs != null || guardrailStatus || runId || isJson) && (
        <div className="flex items-center gap-2 border-t border-border px-3 py-2">
          {isJson && (
            <Badge variant="outline" className="min-h-0 py-0.5 text-2xs">
              json
            </Badge>
          )}
          {latencyMs != null && (
            <span className="rounded-md border border-border bg-surface px-1.5 py-0.5 font-mono text-2xs text-muted">
              {Math.round(latencyMs)}ms
            </span>
          )}
          {guardrailStatus && (
            <Badge variant={guardrailVariant(guardrailStatus)} className="min-h-0 py-0.5 text-2xs">
              {guardrailStatus}
            </Badge>
          )}
          {runId && (
            <Link
              href={`/runs/${runId}`}
              className="focus-ring ml-auto rounded text-xs font-medium text-primary hover:underline"
            >
              Open run →
            </Link>
          )}
        </div>
      )}
    </div>
  );
}
