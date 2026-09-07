"use client";

import { useMemo, useState } from "react";
import { GripVertical, PackageSearch, Search } from "lucide-react";
import type { NodeData } from "@/types/workflow";
import { Input } from "@/components/ui/input";
import { StaggerList } from "@/components/motion";
import {
  categorize,
  CATEGORY_COLOR_VAR,
  CATEGORY_LABEL,
  type NodeCategory,
} from "@/components/canvas/nodes/category";
import { EXPRESSION_HINT, NODE_REGISTRY } from "@/lib/node-registry";
import { cn } from "@/lib/utils";

export const DRAG_TYPE = "application/aegis-node";

const ALL_CATS: NodeCategory[] = [
  "trigger",
  "logic",
  "llm",
  "data",
  "integration",
  "quality",
  "flow",
];

const pillClasses =
  "focus-ring shrink-0 rounded-md border border-border bg-surface px-3 py-1 text-xs font-medium text-muted transition-colors hover:border-border-strong hover:bg-surface-hover hover:text-foreground";
const pillActive = "border-border-strong bg-surface-hover text-foreground";

interface NodePaletteProps {
  onAddNode: (data: NodeData) => void;
}

export function NodePalette({ onAddNode }: NodePaletteProps) {
  const [query, setQuery] = useState("");
  const [activeCat, setActiveCat] = useState<NodeCategory | "all">("all");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    let list = NODE_REGISTRY;
    if (activeCat !== "all") {
      list = list.filter((def) => categorize(def.type) === activeCat);
    }
    if (!q) return list;
    return list.filter(
      (def) =>
        def.label.toLowerCase().includes(q) ||
        def.description.toLowerCase().includes(q) ||
        def.type.toLowerCase().includes(q) ||
        def.category.toLowerCase().includes(q)
    );
  }, [query, activeCat]);

  const categoryCounts = useMemo(() => {
    const counts = new Map<NodeCategory, number>();
    for (const item of NODE_REGISTRY) {
      const cat = categorize(item.type);
      counts.set(cat, (counts.get(cat) || 0) + 1);
    }
    return counts;
  }, []);

  const onDragStart = (event: React.DragEvent, data: NodeData) => {
    event.dataTransfer.setData(DRAG_TYPE, JSON.stringify(data));
    event.dataTransfer.effectAllowed = "move";

    // Custom drag image: a mini node card mirroring the palette-row styling.
    if (typeof document !== "undefined") {
      const catColor = CATEGORY_COLOR_VAR[categorize(data.nodeType)];
      const ghost = document.createElement("div");
      ghost.className =
        "pointer-events-none relative flex items-center overflow-hidden rounded-lg border border-border bg-surface px-3 py-2 text-sm text-foreground shadow-elev-2";
      ghost.style.position = "fixed";
      ghost.style.top = "-1000px";
      ghost.style.left = "-1000px";
      ghost.style.width = "200px";

      const strip = document.createElement("span");
      strip.style.position = "absolute";
      strip.style.insetBlock = "0";
      strip.style.left = "0";
      strip.style.width = "3px";
      strip.style.background = catColor;
      ghost.appendChild(strip);

      const label = document.createElement("span");
      label.className = "truncate pl-2 font-medium";
      label.textContent = data.label;
      ghost.appendChild(label);

      document.body.appendChild(ghost);
      event.dataTransfer.setDragImage(ghost, 24, 24);
      setTimeout(() => {
        ghost.remove();
      }, 0);
    }
  };

  return (
    <div className="space-y-4">
      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search nodes… (drag or click to add)"
          aria-label="Search nodes"
          className="h-9 pl-9 text-xs"
        />
      </div>

      {/* Chips scroll horizontally; the right-edge mask signals there is more. */}
      <div className="border-y border-border bg-background/20">
        <div
          role="group"
          aria-label="Filter nodes by category"
          className="flex gap-2 overflow-x-auto px-1 py-2 [mask-image:linear-gradient(to_right,#000_0%,#000_calc(100%_-_24px),transparent_100%)] [scrollbar-width:thin] [scrollbar-color:var(--border-strong)_transparent] [&::-webkit-scrollbar]:h-1.5 [&::-webkit-scrollbar-track]:bg-transparent [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-border-strong"
        >
          <button
            type="button"
            onClick={() => setActiveCat("all")}
            aria-pressed={activeCat === "all"}
            className={cn(pillClasses, activeCat === "all" && pillActive)}
          >
            All
          </button>
          {ALL_CATS.map((c) => (
            <button
              key={c}
              type="button"
              onClick={() => setActiveCat(c)}
              aria-pressed={activeCat === c}
              className={cn(pillClasses, activeCat === c && pillActive)}
            >
              {CATEGORY_LABEL[c]} {categoryCounts.get(c) || 0}
            </button>
          ))}
        </div>
      </div>

      <StaggerList key={activeCat} className="space-y-1.5">
        {filtered.map((item) => {
          const cat = categorize(item.type);
          const catColor = CATEGORY_COLOR_VAR[cat];
          return (
            <button
              key={`${item.type}-${item.label}`}
              type="button"
              draggable
              onDragStart={(e) => onDragStart(e, item.defaultData)}
              onClick={() => onAddNode(item.defaultData)}
              className={cn(
                "focus-ring group relative flex w-full cursor-grab items-center gap-3 overflow-hidden rounded-md border border-border bg-surface-input px-3 py-2.5 active:cursor-grabbing",
                "text-left transition-colors duration-fast hover:border-border-strong hover:bg-surface-hover"
              )}
            >
              <span
                className="absolute inset-y-0 left-0 w-0.5 opacity-80 transition-opacity group-hover:opacity-100"
                style={{ background: catColor }}
                aria-hidden
              />
              <GripVertical
                className="h-3.5 w-3.5 shrink-0 text-subtle opacity-0 transition-opacity group-hover:opacity-70"
                aria-hidden
              />
              {/* Monochrome chip — category hue lives only in the 2px left rule. */}
              <div className="rounded-md bg-background p-1.5 text-muted">
                <item.icon className="h-4 w-4" />
              </div>
              <div className="min-w-0">
                <p className="text-sm font-medium text-foreground">{item.label}</p>
                <p className="truncate text-xs text-muted">{item.description}</p>
              </div>
            </button>
          );
        })}
      </StaggerList>

      {filtered.length === 0 && (
        <div className="rounded-lg border border-dashed border-border bg-surface-input px-4 py-6 text-center">
          <PackageSearch className="mx-auto h-5 w-5 text-muted" />
          <p className="mt-2 text-sm font-medium text-foreground">No nodes found</p>
          <p className="mt-1 text-xs text-muted">Try another search term or category.</p>
        </div>
      )}

      <p className="text-caption rounded-md border border-dashed border-border bg-surface-input px-3 py-2.5 leading-relaxed">
        {EXPRESSION_HINT}
      </p>
    </div>
  );
}
