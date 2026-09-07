"use client";

import { useId, useRef, type KeyboardEvent } from "react";
import {
  Database,
  GitCompare,
  History,
  Layers,
  Sparkles,
  type LucideIcon,
} from "lucide-react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

/** The tool set currently exposed by the canvas workspace. */
export type CanvasRailTab = "nodes" | "data" | "quality" | "versions" | "compare";

export interface CanvasRailItem {
  id: CanvasRailTab;
  label: string;
  icon: LucideIcon;
}

/**
 * Kept in lockstep with CanvasSidebar so callers can swap the persistent
 * sidebar for this compact tool navigator without remapping their state.
 */
export const CANVAS_RAIL_ITEMS: readonly CanvasRailItem[] = [
  { id: "nodes", label: "Nodes", icon: Layers },
  { id: "data", label: "Data", icon: Database },
  { id: "quality", label: "Quality", icon: Sparkles },
  { id: "versions", label: "Versions", icon: History },
  { id: "compare", label: "Compare", icon: GitCompare },
];

export interface CanvasRailProps {
  /** Controlled active tool. */
  activeTab: CanvasRailTab;
  /** Called when a tool is selected by mouse, touch, or keyboard. */
  onSelect: (tab: CanvasRailTab) => void;
  /**
   * Optional active-tab action. A parent can use this to collapse or reopen
   * its adjacent panel without giving the rail ownership of panel visibility.
   */
  onToggle?: (tab: CanvasRailTab) => void;
  /** The label announced for this vertical tool group. */
  ariaLabel?: string;
  className?: string;
}

/**
 * A compact, keyboard-navigable canvas tool rail. It intentionally owns only
 * tool selection; the consuming canvas decides where (and whether) to render
 * the associated drawer.
 */
export function CanvasRail({
  activeTab,
  onSelect,
  onToggle,
  ariaLabel = "Canvas tools",
  className,
}: CanvasRailProps) {
  const railId = useId();
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([]);

  const activeIndex = Math.max(
    0,
    CANVAS_RAIL_ITEMS.findIndex((item) => item.id === activeTab)
  );

  const activate = (id: CanvasRailTab) => {
    // An active tool owns drawer visibility. Calling both callbacks in the
    // same React event would make a closed drawer open and close immediately.
    if (id === activeTab) {
      onToggle?.(id);
      return;
    }
    onSelect(id);
  };

  const selectAt = (index: number) => {
    const normalizedIndex =
      (index + CANVAS_RAIL_ITEMS.length) % CANVAS_RAIL_ITEMS.length;
    const item = CANVAS_RAIL_ITEMS[normalizedIndex];
    activate(item.id);
    tabRefs.current[normalizedIndex]?.focus();
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    switch (event.key) {
      case "ArrowDown":
      case "ArrowRight":
        event.preventDefault();
        selectAt(index + 1);
        break;
      case "ArrowUp":
      case "ArrowLeft":
        event.preventDefault();
        selectAt(index - 1);
        break;
      case "Home":
        event.preventDefault();
        selectAt(0);
        break;
      case "End":
        event.preventDefault();
        selectAt(CANVAS_RAIL_ITEMS.length - 1);
        break;
      default:
        break;
    }
  };

  return (
    <nav
      aria-label={ariaLabel}
      className={cn(
        "flex w-[58px] shrink-0 flex-col items-center border-r border-border bg-surface-elevated py-3",
        className
      )}
    >
      <div className="flex w-full flex-col items-center gap-1" role="toolbar" aria-orientation="vertical">
        {CANVAS_RAIL_ITEMS.map(({ id, label, icon: Icon }, index) => {
          const isActive = activeIndex === index;
          const tabId = `canvas-rail-tab-${railId}-${id}`;

          return (
            <Tooltip key={id}>
              <TooltipTrigger asChild>
                <button
                  ref={(element) => {
                    tabRefs.current[index] = element;
                  }}
                  id={tabId}
                  type="button"
                  aria-label={label}
                  aria-pressed={isActive}
                  tabIndex={isActive ? 0 : -1}
                  onClick={() => activate(id)}
                  onKeyDown={(event) => handleKeyDown(event, index)}
                  className={cn(
                    "focus-ring flex h-9 w-9 items-center justify-center rounded-md border transition-[background-color,border-color,color,box-shadow] duration-1",
                    isActive
                      ? "border-active/35 bg-active/5 text-foreground shadow-elev-1"
                      : "border-transparent text-muted hover:border-border hover:bg-surface-hover hover:text-foreground"
                  )}
                >
                  <Icon aria-hidden="true" className="h-[17px] w-[17px]" strokeWidth={1.65} />
                  <span className="sr-only">{label}</span>
                </button>
              </TooltipTrigger>
              <TooltipContent side="right">
                {isActive ? `${label} · selected` : label}
              </TooltipContent>
            </Tooltip>
          );
        })}
      </div>
    </nav>
  );
}
