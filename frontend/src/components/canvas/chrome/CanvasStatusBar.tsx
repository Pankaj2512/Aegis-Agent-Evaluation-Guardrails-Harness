"use client";

import { useViewport } from "@xyflow/react";
import { Popover as PopoverPrimitive } from "radix-ui";
import { AlertTriangle } from "lucide-react";

import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { cn } from "@/lib/utils";

const TONE_CLASSES: Record<"success" | "warning" | "active" | "muted", string> = {
  success: "text-success",
  warning: "text-warning",
  active: "text-active",
  muted: "text-muted",
};

/**
 * Reads the live zoom via useViewport() — kept inside this leaf component so
 * per-frame viewport updates re-render only the status bar, not the canvas root.
 */
function ZoomReadout() {
  const { zoom } = useViewport();
  return <span>{Math.round(zoom * 100)}%</span>;
}

export function CanvasStatusBar({
  editorStatus,
  statusTone,
  hint,
  nodeCount,
  edgeCount,
  selectionCount,
  issues,
  onIssueClick,
}: {
  editorStatus: string;
  statusTone: "success" | "warning" | "active" | "muted";
  hint: string;
  nodeCount: number;
  edgeCount: number;
  selectionCount: number;
  issues: Array<{ nodeId: string; message: string }>;
  onIssueClick: (nodeId: string) => void;
}) {
  return (
    <div data-tour="status-bar" className="flex items-center justify-between gap-3 border-t border-border bg-surface px-4 py-1.5 font-mono text-2xs text-muted">
      <div className="flex min-w-0 items-center gap-3">
        <span
          className={cn("inline-flex items-center gap-1.5", TONE_CLASSES[statusTone])}
        >
          <span className="h-1.5 w-1.5 rounded-full bg-current" />
          {editorStatus}
        </span>
        <span className="hidden truncate sm:inline">{hint}</span>
      </div>

      <div className="flex items-center gap-3">
        <span>
          {nodeCount} nodes · {edgeCount} edges
        </span>
        {selectionCount > 0 && <span>{selectionCount} selected</span>}
        <ZoomReadout />
        {issues.length > 0 && (
          <Popover>
            <PopoverTrigger asChild>
              <button
                type="button"
                className="focus-ring inline-flex items-center gap-1 rounded-md px-1 py-0.5 text-warning transition-colors hover:bg-surface-hover"
              >
                <AlertTriangle className="h-3 w-3" />
                {issues.length} issue{issues.length === 1 ? "" : "s"}
              </button>
            </PopoverTrigger>
            <PopoverContent
              align="end"
              className="w-72 gap-0 p-1 font-sans text-sm"
            >
              {issues.map((issue, index) => (
                <PopoverPrimitive.Close asChild key={`${issue.nodeId}-${index}`}>
                  <button
                    type="button"
                    onClick={() => onIssueClick(issue.nodeId)}
                    className="focus-ring flex w-full flex-col items-start gap-0.5 rounded-md px-2.5 py-1.5 text-left transition-colors hover:bg-surface-hover"
                  >
                    <span className="text-xs text-foreground">
                      {issue.message}
                    </span>
                    <span className="font-mono text-2xs text-subtle">
                      {issue.nodeId}
                    </span>
                  </button>
                </PopoverPrimitive.Close>
              ))}
            </PopoverContent>
          </Popover>
        )}
      </div>
    </div>
  );
}
