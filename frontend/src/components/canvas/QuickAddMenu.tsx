"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Blocks, Clock, Search, Sparkles, X, Zap } from "lucide-react";
import { Input } from "@/components/ui/input";
import { getNodeDefinition, NODE_REGISTRY, type NodeDefinition } from "@/lib/node-registry";
import { categorize, CATEGORY_COLOR_VAR, CATEGORY_LABEL } from "@/components/canvas/nodes/category";
import { api, type NodeSuggestion } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import { getRecentNodes, recordNodePick } from "@/lib/recent-nodes";
import { hashString } from "@/lib/utils";
import type { Snippet } from "@/lib/snippets";
import type { NodeData } from "@/types/workflow";

interface GraphContext {
  nodes: { id: string; nodeType: string; label: string }[];
  edges: { source: string; target: string; route?: string }[];
}

interface QuickAddMenuProps {
  /** Screen (client) coordinates to anchor the menu at. */
  position: { x: number; y: number };
  /** When adding the first node, surface triggers at the top. */
  preferTriggers?: boolean;
  onSelect: (data: NodeData) => void;
  onClose: () => void;
  /** Optional: enables AI node suggestions when combined with graphContext. */
  workflowId?: string;
  /** Optional: the source node the picker was opened from. */
  sourceNodeId?: string;
  /** Optional: current graph shape used to ground suggestions. */
  graphContext?: GraphContext;
  /** Optional: saved snippets, surfaced in a "Snippets" section when non-empty. */
  snippets?: Snippet[];
  /** Insert the given snippet at the quick-add position. */
  onInsertSnippet?: (snippetId: string) => void;
  /** Delete a snippet (hover-revealed × on each row). */
  onDeleteSnippet?: (snippetId: string) => void;
}

const MENU_W = 288;
const MENU_H = 380;
const MAX_SUGGESTIONS = 3;

/** Resolve a suggestion to a concrete icon + node data using the frontend registry. */
function resolveSuggestion(suggestion: NodeSuggestion): { def: NodeDefinition; data: NodeData } | null {
  const registryDef = getNodeDefinition(suggestion.node_type, {
    label: suggestion.label,
    toolType: (suggestion.default_data?.toolType as NodeData["toolType"]) ?? undefined,
    integrationType:
      (suggestion.default_data?.integrationType as NodeData["integrationType"]) ?? undefined,
  });
  if (!registryDef) return null;
  const base = (suggestion.default_data as NodeData | null) ?? registryDef.defaultData;
  const data: NodeData = {
    ...structuredClone(base),
    nodeType: registryDef.type,
    label: suggestion.label,
  };
  return { def: registryDef, data };
}

/**
 * n8n-style node picker: opened from a node's "+" button, by dropping a
 * connection on empty canvas, or from the empty-state CTA. Selecting an item
 * places the node and (when opened from a source) auto-connects it.
 *
 * When workflowId/sourceNodeId/graphContext are supplied, a grounded "Suggested"
 * group appears above the main list while the search box is empty. All AI props
 * are optional — the picker behaves identically to before when they are absent.
 */
export function QuickAddMenu({
  position,
  preferTriggers = false,
  onSelect,
  onClose,
  workflowId,
  sourceNodeId,
  graphContext,
  snippets,
  onInsertSnippet,
  onDeleteSnippet,
}: QuickAddMenuProps) {
  const [query, setQuery] = useState("");
  const [highlight, setHighlight] = useState(0);
  // Recent picks are localStorage-backed — read after mount so the server and
  // first client paint agree (hydration-safe), matching FirstRunHero.
  const [recentTypes, setRecentTypes] = useState<string[]>([]);
  const containerRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setRecentTypes(getRecentNodes().map((entry) => entry.type));
  }, []);

  const trimmedQuery = query.trim();
  const suggestionsEnabled = !!sourceNodeId && !!graphContext && trimmedQuery === "";

  const suggestionsQuery = useQuery({
    queryKey: queryKeys.assistSuggestions(
      workflowId ?? "adhoc",
      sourceNodeId ?? "",
      graphContext ? hashString(JSON.stringify(graphContext)) : ""
    ),
    queryFn: () =>
      api.suggestNodes({
        workflow_id: workflowId,
        graph: graphContext!,
        selected_node_id: sourceNodeId,
      }),
    enabled: suggestionsEnabled,
    staleTime: 5 * 60_000,
    retry: false,
  });

  const items = useMemo(() => {
    const q = query.trim().toLowerCase();
    let list = NODE_REGISTRY;
    if (q) {
      list = list.filter(
        (def) =>
          def.label.toLowerCase().includes(q) ||
          def.description.toLowerCase().includes(q) ||
          def.type.toLowerCase().includes(q)
      );
    }
    if (preferTriggers) {
      list = [...list].sort((a, b) => {
        const at = categorize(a.type) === "trigger" ? 0 : 1;
        const bt = categorize(b.type) === "trigger" ? 0 : 1;
        return at - bt;
      });
    }
    return list;
  }, [query, preferTriggers]);

  // Recent picks resolve against the registry and only show while the search
  // box is empty. Capped by lib/recent-nodes MAX_RECENT.
  const recent = useMemo(() => {
    if (trimmedQuery !== "") return [];
    return recentTypes
      .map((type) => NODE_REGISTRY.find((def) => def.type === type))
      .filter((def): def is NodeDefinition => Boolean(def));
  }, [recentTypes, trimmedQuery]);

  // Suggestions only render when the search box is empty and results resolved.
  const suggestions = useMemo(() => {
    if (!suggestionsEnabled || !suggestionsQuery.data) return [];
    return suggestionsQuery.data.suggestions
      .slice(0, MAX_SUGGESTIONS)
      .map((s) => ({ suggestion: s, resolved: resolveSuggestion(s) }))
      .filter((entry): entry is { suggestion: NodeSuggestion; resolved: NonNullable<ReturnType<typeof resolveSuggestion>> } =>
        entry.resolved !== null
      );
  }, [suggestionsEnabled, suggestionsQuery.data]);

  // Snippets sit at the top of the index space and, like Recent, only show while
  // the search box is empty (they don't participate in node-type filtering).
  const visibleSnippets = useMemo(
    () => (trimmedQuery === "" && onInsertSnippet ? (snippets ?? []) : []),
    [trimmedQuery, onInsertSnippet, snippets]
  );
  const showSnippets = visibleSnippets.length > 0;
  const snippetCount = showSnippets ? visibleSnippets.length : 0;
  const showRecent = recent.length > 0;
  const recentCount = showRecent ? recent.length : 0;
  const showSuggestions = suggestions.length > 0;
  const suggestionCount = showSuggestions ? suggestions.length : 0;
  const totalCount = snippetCount + recentCount + suggestionCount + items.length;

  // Only show a shimmer row while a suggestion request is actually in flight.
  const suggestionsLoading = suggestionsEnabled && suggestionsQuery.isFetching && !showSuggestions;

  useEffect(() => setHighlight(0), [query]);

  useEffect(() => {
    const onPointerDown = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, [onClose]);

  const clampedX = Math.max(8, Math.min(position.x, window.innerWidth - MENU_W - 8));
  const clampedY = Math.max(8, Math.min(position.y, window.innerHeight - MENU_H - 8));

  // Clone so callers never mutate the shared module-level defaultData object.
  const pick = (def: NodeDefinition) => {
    recordNodePick(def.type, def.label);
    onSelect(structuredClone(def.defaultData));
  };
  const pickSuggestion = (data: NodeData) => {
    recordNodePick(data.nodeType, data.label);
    onSelect(structuredClone(data));
  };

  const insertSnippet = (snippetId: string) => {
    onInsertSnippet?.(snippetId);
  };

  // Global index space: snippets, then recent, then suggestions, then the list.
  const pickIndex = (index: number) => {
    if (showSnippets && index < snippetCount) {
      insertSnippet(visibleSnippets[index].id);
      return;
    }
    const afterSnip = index - snippetCount;
    if (showRecent && afterSnip < recentCount) {
      pick(recent[afterSnip]);
      return;
    }
    const afterRecent = afterSnip - recentCount;
    if (showSuggestions && afterRecent < suggestionCount) {
      pickSuggestion(suggestions[afterRecent].resolved.data);
      return;
    }
    const def = items[afterRecent - suggestionCount];
    if (def) pick(def);
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      e.preventDefault();
      onClose();
      return;
    }
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      const next =
        e.key === "ArrowDown"
          ? Math.min(highlight + 1, totalCount - 1)
          : Math.max(highlight - 1, 0);
      setHighlight(next);
      listRef.current
        ?.querySelector(`[data-index="${next}"]`)
        ?.scrollIntoView({ block: "nearest" });
      return;
    }
    if (e.key === "Enter" && highlight < totalCount) {
      e.preventDefault();
      pickIndex(highlight);
    }
  };

  return (
    <div
      ref={containerRef}
      className="glass-panel fixed z-50 flex w-72 flex-col overflow-hidden rounded-lg shadow-elev-3"
      style={{ left: clampedX, top: clampedY, maxHeight: MENU_H }}
      onKeyDown={onKeyDown}
      role="dialog"
      aria-label="Add node"
    >
      <div className="relative border-b border-border p-2">
        <Search className="pointer-events-none absolute left-4 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted" />
        <Input
          autoFocus
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={preferTriggers ? "Search for a trigger…" : "Search nodes…"}
          size="sm"
          className="border-0 bg-transparent pl-7 shadow-none focus-visible:ring-0"
          aria-label="Search nodes"
        />
      </div>
      <div ref={listRef} className="flex-1 overflow-y-auto p-1">
        {showSnippets && (
          <div className="pb-1">
            <p className="flex items-center gap-1 px-2 pb-0.5 pt-1 font-mono text-2xs uppercase tracking-wide text-subtle">
              <Blocks className="h-3 w-3" />
              Snippets
            </p>
            {visibleSnippets.map((snip, i) => {
              const globalIndex = i;
              const nodeCount = snip.payload.nodes.length;
              return (
                <div
                  key={`snip-${snip.id}`}
                  className={`group/snip flex w-full items-center gap-2.5 rounded-md pr-1 transition-colors ${
                    globalIndex === highlight ? "bg-surface-hover" : ""
                  }`}
                  onMouseEnter={() => setHighlight(globalIndex)}
                >
                  <button
                    type="button"
                    data-index={globalIndex}
                    onClick={() => insertSnippet(snip.id)}
                    className="flex min-w-0 flex-1 items-center gap-2.5 rounded-md px-2 py-1.5 text-left"
                  >
                    <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded border border-border bg-surface-input text-muted">
                      <Blocks className="h-3.5 w-3.5" />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-xs font-medium text-foreground">
                        {snip.name}
                      </span>
                      <span className="block truncate text-xs text-muted">
                        {nodeCount} node{nodeCount === 1 ? "" : "s"}
                      </span>
                    </span>
                  </button>
                  {onDeleteSnippet && (
                    <button
                      type="button"
                      aria-label={`Delete snippet ${snip.name}`}
                      title="Delete snippet"
                      onClick={(e) => {
                        e.stopPropagation();
                        onDeleteSnippet(snip.id);
                      }}
                      className="shrink-0 rounded p-1 text-muted opacity-0 transition-[opacity,color] hover:text-destructive group-hover/snip:opacity-100"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  )}
                </div>
              );
            })}
            <div className="mx-2 my-1 border-t border-border" aria-hidden />
          </div>
        )}

        {showRecent && (
          <div className="pb-1">
            <p className="flex items-center gap-1 px-2 pb-0.5 pt-1 font-mono text-2xs uppercase tracking-wide text-subtle">
              <Clock className="h-3 w-3" />
              Recent
            </p>
            {recent.map((def, i) => {
              const cat = categorize(def.type);
              const catColor = CATEGORY_COLOR_VAR[cat];
              const isTrigger = cat === "trigger";
              const globalIndex = snippetCount + i;
              return (
                <button
                  key={`recent-${def.type}`}
                  type="button"
                  data-index={globalIndex}
                  onClick={() => pick(def)}
                  onMouseEnter={() => setHighlight(globalIndex)}
                  className={`flex w-full items-center gap-2.5 rounded-md px-2 py-1.5 text-left transition-colors ${
                    globalIndex === highlight ? "bg-surface-hover" : ""
                  }`}
                >
                  <span
                    className="flex h-6 w-6 shrink-0 items-center justify-center rounded"
                    style={{
                      background: `color-mix(in srgb, ${catColor} 14%, transparent)`,
                      color: catColor,
                    }}
                  >
                    <def.icon className="h-3.5 w-3.5" />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="flex items-center gap-1 truncate text-xs font-medium text-foreground">
                      {def.label}
                      {isTrigger && (
                        <Zap className="h-3 w-3 shrink-0 text-muted" aria-label="Trigger" />
                      )}
                    </span>
                    <span className="block truncate text-xs text-muted">{def.description}</span>
                  </span>
                </button>
              );
            })}
            <div className="mx-2 my-1 border-t border-border" aria-hidden />
          </div>
        )}

        {suggestionsLoading && (
          <div className="px-2 pb-1 pt-1.5">
            <p className="px-1 pb-1 font-mono text-2xs uppercase tracking-wide text-subtle">Suggested</p>
            <div className="flex items-center gap-2.5 rounded-md px-2 py-1.5">
              <span className="h-6 w-6 shrink-0 animate-pulse rounded bg-surface-hover" />
              <span className="min-w-0 flex-1 space-y-1.5">
                <span className="block h-2.5 w-2/3 animate-pulse rounded bg-surface-hover" />
                <span className="block h-2 w-1/2 animate-pulse rounded bg-surface-hover" />
              </span>
            </div>
          </div>
        )}

        {showSuggestions && (
          <div className="pb-1">
            <p className="flex items-center gap-1 px-2 pb-0.5 pt-1 font-mono text-2xs uppercase tracking-wide text-subtle">
              <Sparkles className="h-3 w-3" />
              Suggested
            </p>
            {suggestions.map((entry, i) => {
              const { def } = entry.resolved;
              const cat = categorize(def.type);
              const catColor = CATEGORY_COLOR_VAR[cat];
              const globalIndex = snippetCount + recentCount + i;
              return (
                <button
                  key={`sugg-${i}`}
                  type="button"
                  data-index={globalIndex}
                  onClick={() => pickSuggestion(entry.resolved.data)}
                  onMouseEnter={() => setHighlight(globalIndex)}
                  className={`flex w-full items-center gap-2.5 rounded-md px-2 py-1.5 text-left transition-colors ${
                    globalIndex === highlight ? "bg-surface-hover" : ""
                  }`}
                >
                  <span
                    className="flex h-6 w-6 shrink-0 items-center justify-center rounded"
                    style={{
                      background: `color-mix(in srgb, ${catColor} 14%, transparent)`,
                      color: catColor,
                    }}
                  >
                    <def.icon className="h-3.5 w-3.5" />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-xs font-medium text-foreground">
                      {entry.suggestion.label}
                    </span>
                    <span className="block truncate text-xs text-muted">{entry.suggestion.reason}</span>
                  </span>
                </button>
              );
            })}
            <div className="mx-2 my-1 border-t border-border" aria-hidden />
          </div>
        )}

        {items.length === 0 && (
          <p className="px-3 py-4 text-center text-xs text-muted">No matching nodes.</p>
        )}
        {items.map((def, index) => {
          const globalIndex = snippetCount + recentCount + suggestionCount + index;
          const cat = categorize(def.type);
          const catColor = CATEGORY_COLOR_VAR[cat];
          const isTrigger = cat === "trigger";
          return (
            <button
              key={`${def.type}-${def.label}`}
              type="button"
              data-index={globalIndex}
              onClick={() => pick(def)}
              onMouseEnter={() => setHighlight(globalIndex)}
              className={`flex w-full items-center gap-2.5 rounded-md px-2 py-1.5 text-left transition-colors ${
                globalIndex === highlight ? "bg-surface-hover" : ""
              }`}
            >
              <span
                className="flex h-6 w-6 shrink-0 items-center justify-center rounded"
                style={{
                  background: `color-mix(in srgb, ${catColor} 14%, transparent)`,
                  color: catColor,
                }}
              >
                <def.icon className="h-3.5 w-3.5" />
              </span>
              <span className="min-w-0 flex-1">
                <span className="flex items-center gap-1 truncate text-xs font-medium text-foreground">
                  {def.label}
                  {isTrigger && (
                    <Zap className="h-3 w-3 shrink-0 text-muted" aria-label="Trigger" />
                  )}
                </span>
                <span className="block truncate text-xs text-muted">{def.description}</span>
              </span>
              <span className="shrink-0 font-mono text-2xs lowercase text-subtle">
                {CATEGORY_LABEL[cat]}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
