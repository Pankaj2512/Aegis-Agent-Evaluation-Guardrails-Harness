"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Pin, PinOff, Play, type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

export type ContextMenuItem =
  | {
      label: string;
      icon?: LucideIcon;
      shortcut?: string;
      danger?: boolean;
      disabled?: boolean;
      onSelect: () => void;
    }
  | "separator";

/**
 * Node-run menu items (M2-3): "Pin output" and "Run from here". WorkflowCanvas
 * (M3) spreads these into its node context-menu items so the presentation stays
 * owned here while the handlers (pinned map + api.createRun) live in the canvas.
 *
 * - `onPinOutput`/`onRunFromHere` mirror NodeOutputPeek's callbacks.
 * - "Pin output" is disabled when there is no output to pin.
 * - "Run from here" is always offered for a node that has produced output.
 */
export function buildNodeRunMenuItems(opts: {
  nodeId: string;
  /** The node's captured output, if any (null/empty disables pinning). */
  output: string | null;
  /** Whether this node's output is currently pinned. */
  pinned: boolean;
  onPinOutput?: (nodeId: string, output: string) => void;
  onRunFromHere?: (nodeId: string) => void;
}): ContextMenuItem[] {
  const { nodeId, output, pinned, onPinOutput, onRunFromHere } = opts;
  const items: ContextMenuItem[] = [];
  const hasOutput = !!output && output.trim().length > 0;

  if (onPinOutput) {
    items.push({
      label: pinned ? "Unpin output" : "Pin output",
      icon: pinned ? PinOff : Pin,
      disabled: !pinned && !hasOutput,
      onSelect: () => onPinOutput(nodeId, output ?? ""),
    });
  }
  if (onRunFromHere) {
    items.push({
      label: "Run from here",
      icon: Play,
      onSelect: () => onRunFromHere(nodeId),
    });
  }
  return items;
}

interface CanvasContextMenuProps {
  /** Screen (client) coordinates to anchor the menu at. */
  position: { x: number; y: number };
  items: ContextMenuItem[];
  onClose: () => void;
}

const MENU_W = 208;
/** Fallback height used before we can measure the rendered menu. */
const MENU_H_FALLBACK = 260;

function isSeparator(item: ContextMenuItem): item is "separator" {
  return item === "separator";
}

function firstEnabledIndex(items: ContextMenuItem[], from: number, dir: 1 | -1): number {
  const n = items.length;
  for (let step = 0; step < n; step++) {
    const i = from + dir * step;
    if (i < 0 || i >= n) break;
    const item = items[i];
    if (!isSeparator(item) && !item.disabled) return i;
  }
  return -1;
}

/**
 * Controlled, arbitrary-position context menu for the workflow canvas. Follows
 * the QuickAddMenu house pattern: fixed positioning, viewport clamping,
 * outside-mousedown + Escape close, and ArrowUp/ArrowDown/Enter keyboard nav.
 */
export function CanvasContextMenu({ position, items, onClose }: CanvasContextMenuProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  // Element that had focus when the menu opened — restored on close so focus
  // isn't dropped to <body> (usually the canvas wrapper).
  const restoreFocusRef = useRef<HTMLElement | null>(null);
  const [highlight, setHighlight] = useState(() =>
    firstEnabledIndex(items, 0, 1)
  );
  const [menuH, setMenuH] = useState(MENU_H_FALLBACK);

  // Measure the rendered menu so clamping/flip use the real height.
  useLayoutEffect(() => {
    if (containerRef.current) {
      setMenuH(containerRef.current.offsetHeight);
    }
  }, [items]);

  // Focus the menu so keyboard nav works immediately; restore prior focus on close.
  useEffect(() => {
    restoreFocusRef.current =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const container = containerRef.current;
    container?.focus();
    return () => {
      const target =
        restoreFocusRef.current ??
        (container?.closest(".canvas-bg") as HTMLElement | null);
      target?.focus?.();
    };
  }, []);

  useEffect(() => {
    const onPointerDown = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, [onClose]);

  // Close when focus leaves the menu (e.g. Tab out) instead of leaving a
  // detached, keyboard-invisible menu behind.
  useEffect(() => {
    const onFocusOut = (e: FocusEvent) => {
      const next = e.relatedTarget as Node | null;
      if (containerRef.current && next && !containerRef.current.contains(next)) {
        onClose();
      }
    };
    const el = containerRef.current;
    el?.addEventListener("focusout", onFocusOut);
    return () => el?.removeEventListener("focusout", onFocusOut);
  }, [onClose]);

  const clampedX = Math.max(8, Math.min(position.x, window.innerWidth - MENU_W - 8));
  // Flip above the cursor when the menu would overflow the bottom edge.
  const overflowsBottom = position.y + menuH + 8 > window.innerHeight;
  const rawY = overflowsBottom ? position.y - menuH : position.y;
  const clampedY = Math.max(8, Math.min(rawY, window.innerHeight - menuH - 8));

  const select = (item: Exclude<ContextMenuItem, "separator">) => {
    if (item.disabled) return;
    item.onSelect();
    onClose();
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      e.preventDefault();
      onClose();
      return;
    }
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      const dir = e.key === "ArrowDown" ? 1 : -1;
      const start = highlight < 0 ? (dir === 1 ? -1 : items.length) : highlight;
      const next = firstEnabledIndex(items, start + dir, dir);
      if (next !== -1) setHighlight(next);
      return;
    }
    if (e.key === "Home") {
      e.preventDefault();
      const first = firstEnabledIndex(items, 0, 1);
      if (first !== -1) setHighlight(first);
      return;
    }
    if (e.key === "End") {
      e.preventDefault();
      const last = firstEnabledIndex(items, items.length - 1, -1);
      if (last !== -1) setHighlight(last);
      return;
    }
    if (e.key === "Enter") {
      const item = items[highlight];
      if (item && !isSeparator(item)) {
        e.preventDefault();
        select(item);
      }
    }
  };

  return (
    <div
      ref={containerRef}
      tabIndex={-1}
      role="menu"
      aria-label="Canvas actions"
      className="animate-fade-in fixed z-50 flex w-52 flex-col rounded-lg glass-panel p-1 shadow-elev-2 focus:outline-none focus-ring"
      style={{ left: clampedX, top: clampedY }}
      onKeyDown={onKeyDown}
    >
      {items.map((item, index) => {
        if (isSeparator(item)) {
          return <div key={`sep-${index}`} className="my-1 border-t border-border" />;
        }
        const Icon = item.icon;
        const active = index === highlight && !item.disabled;
        return (
          <button
            key={`${item.label}-${index}`}
            type="button"
            role="menuitem"
            disabled={item.disabled}
            data-index={index}
            onClick={() => select(item)}
            onMouseEnter={() => {
              if (!item.disabled) setHighlight(index);
            }}
            className={cn(
              "flex w-full items-center gap-2.5 rounded-md px-2 py-1.5 text-left text-xs transition-colors",
              item.disabled && "cursor-not-allowed opacity-40",
              !item.disabled && item.danger && "text-destructive",
              !item.disabled && !item.danger && "text-foreground",
              active && item.danger && "bg-destructive/10",
              active && !item.danger && "bg-surface-hover"
            )}
          >
            {Icon ? (
              <Icon className="h-3.5 w-3.5 shrink-0" />
            ) : (
              <span className="h-3.5 w-3.5 shrink-0" aria-hidden />
            )}
            <span className="min-w-0 flex-1 truncate font-medium">{item.label}</span>
            {item.shortcut && (
              <span className="shrink-0 font-mono text-2xs text-subtle">{item.shortcut}</span>
            )}
          </button>
        );
      })}
    </div>
  );
}
