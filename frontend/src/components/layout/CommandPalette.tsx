"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  BarChart3,
  Download,
  LayoutTemplate,
  Maximize2,
  MessageSquarePlus,
  Play,
  Plus,
  RotateCw,
  Settings,
  Shield,
  Sparkles,
  SunMoon,
  Wand2,
  Workflow,
} from "lucide-react";
import {
  Command,
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandShortcut,
} from "@/components/ui/command";
import { isEditableTarget } from "@/lib/shortcuts";
import { api } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import { createWorkflowFromTemplate } from "@/lib/create-from-template";
import { getRecentWorkflows, recordWorkflowVisit, type RecentWorkflow } from "@/lib/recent-workflows";
import { NODE_REGISTRY, NODE_CATEGORIES, getNodeDefinition } from "@/lib/node-registry";
import { categorize, CATEGORY_COLOR_VAR } from "@/components/canvas/nodes/category";
import { getCanvasNodeIndex, type CanvasNodeEntry } from "@/lib/canvas-node-index";
import { useTheme } from "@/providers/ThemeProvider";
import { openShortcutsHelp } from "@/components/layout/ShortcutsHelp";

const RECENTS_KEY = "aegis:command-recents";
const MAX_RECENTS = 5;
const OPEN_EVENT = "aegis:open-command-palette";
const MAX_WORKFLOW_RESULTS = 30;
const MAX_CANVAS_NODES = 30;

/* ---------------------------------------------------------------------------
 * Window events the palette dispatches. WorkflowCanvas / run surfaces add the
 * matching listeners in M3. Each is documented in the agent's m3_wiring return.
 * ------------------------------------------------------------------------- */

/** { detail: { nodeType: string } } — add a node of the given registry type to the canvas. */
export const ADD_NODE_EVENT = "aegis:add-node";
/** (no detail) — run the current workflow from the canvas. */
export const RUN_WORKFLOW_EVENT = "aegis:run-workflow";
/** (no detail) — auto-layout / tidy the current canvas graph. */
export const TIDY_CANVAS_EVENT = "aegis:tidy-canvas";
/** (no detail) — fit the current graph to the viewport. */
export const FIT_VIEW_EVENT = "aegis:fit-view";
/** (no detail) — re-run the currently open run with the same inputs. */
export const RERUN_EVENT = "aegis:rerun";
/** (no detail) — export the currently open run's trace. */
export const EXPORT_TRACE_EVENT = "aegis:export-trace";
/** (no detail) — open the Assist panel. */
export const OPEN_ASSIST_EVENT = "aegis:open-assist";
/** { detail: { nodeId: string } } — focus + select a node on the current canvas. */
export const FOCUS_NODE_EVENT = "aegis:focus-node";

/** Dispatch an add-node request for the given registry node type. */
function emitAddNode(nodeType: string) {
  window.dispatchEvent(new CustomEvent(ADD_NODE_EVENT, { detail: { nodeType } }));
}

type PaletteMode = "root" | "add-node";

type Action = {
  id: string;
  label: string;
  description: string;
  group: "Navigate" | "Create" | "Canvas" | "Run" | "Global";
  icon: React.ComponentType<{ className?: string }>;
  shortcut?: string;
  perform: (router: ReturnType<typeof useRouter>) => void;
};

const NAV_ACTIONS: Action[] = [
  {
    id: "nav:workflows",
    label: "Workflows",
    description: "Browse, edit, and version workflow graphs",
    group: "Navigate",
    icon: Workflow,
    perform: (r) => r.push("/"),
  },
  {
    id: "nav:templates",
    label: "Templates",
    description: "Clone production-ready workflow patterns",
    group: "Navigate",
    icon: LayoutTemplate,
    perform: (r) => r.push("/templates"),
  },
  {
    id: "nav:observability",
    label: "Observability",
    description: "Inspect runs, quality, traces, and scheduler health",
    group: "Navigate",
    icon: BarChart3,
    perform: (r) => r.push("/observability"),
  },
  {
    id: "nav:guardrails",
    label: "Guardrails",
    description: "Preview policy checks before wiring nodes",
    group: "Navigate",
    icon: Shield,
    perform: (r) => r.push("/guardrails"),
  },
  {
    id: "nav:settings",
    label: "Settings",
    description: "Credentials, API auth, and eval rubrics",
    group: "Navigate",
    icon: Settings,
    perform: (r) => r.push("/settings"),
  },
  {
    id: "create:workflow",
    label: "New workflow",
    description: "Start a blank workflow on the visual canvas",
    group: "Create",
    icon: Plus,
    shortcut: "N",
    perform: (r) => r.push("/workflows/new"),
  },
];

function CommandActionRow({ action }: { action: Action }) {
  const Icon = action.icon;
  return (
    <>
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-accent/25 bg-accent-muted text-accent shadow-[inset_0_1px_0_var(--surface-highlight)] transition-colors group-data-[selected=true]/command-item:border-primary/35 group-data-[selected=true]/command-item:bg-primary-muted group-data-[selected=true]/command-item:text-primary">
        <Icon className="h-4 w-4" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-medium text-foreground">{action.label}</span>
        <span className="block truncate text-xs text-muted">{action.description}</span>
      </span>
      {action.shortcut && <CommandShortcut>{action.shortcut}</CommandShortcut>}
    </>
  );
}

function WorkflowRow({ name, meta }: { name: string; meta?: string }) {
  return (
    <>
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-border bg-surface-input text-muted">
        <Workflow className="h-4 w-4" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-medium text-foreground">{name}</span>
        {meta && <span className="block truncate text-xs text-muted">{meta}</span>}
      </span>
    </>
  );
}

export function openCommandPalette() {
  window.dispatchEvent(new Event(OPEN_EVENT));
}

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<PaletteMode>("root");
  const [query, setQuery] = useState("");
  const [recents, setRecents] = useState<string[]>([]);
  const [recentWorkflows, setRecentWorkflows] = useState<RecentWorkflow[]>([]);
  // Snapshot of the current canvas's nodes, captured when the palette opens on a
  // canvas route (see the canvas-node-index bridge). Includes unsaved edits.
  const [canvasNodes, setCanvasNodes] = useState<CanvasNodeEntry[]>([]);
  const router = useRouter();
  const pathname = usePathname();
  const queryClient = useQueryClient();
  const { toggleTheme } = useTheme();
  const templateCreatingRef = useRef(false);

  const trimmedQuery = query.trim();
  const hasQuery = trimmedQuery.length > 0;

  // Context surfaces mirror AppShell's onCanvas detection.
  const onCanvas = pathname.startsWith("/workflows/") && pathname !== "/workflows/new";
  const onRun = pathname.startsWith("/runs/");

  const { data: workflows = [] } = useQuery({
    queryKey: queryKeys.workflows,
    queryFn: api.listWorkflows,
    enabled: open,
    staleTime: 30_000,
  });

  const { data: templates = [] } = useQuery({
    queryKey: queryKeys.templates,
    queryFn: api.listTemplates,
    enabled: open && mode === "root" && hasQuery,
    staleTime: 30_000,
  });

  useEffect(() => {
    try {
      const raw = localStorage.getItem(RECENTS_KEY);
      if (raw) setRecents(JSON.parse(raw) as string[]);
    } catch {}
  }, []);

  // Reset query/mode + refresh recent workflows whenever the palette opens.
  useEffect(() => {
    if (open) {
      setQuery("");
      setMode("root");
      setRecentWorkflows(getRecentWorkflows());
      // Load the full index; filtering + slice happens at render time so nodes
      // beyond the first 30 remain findable via the query.
      setCanvasNodes(onCanvas ? getCanvasNodeIndex() : []);
    }
  }, [open, onCanvas]);

  // Clear the query when drilling between modes so the sub-menu starts fresh.
  useEffect(() => {
    setQuery("");
  }, [mode]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        if (e.repeat) return;
        if (isEditableTarget(e.target)) return;
        e.preventDefault();
        setOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  // Plain "n" jumps to the new-workflow canvas (advertised in the palette).
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key.toLowerCase() !== "n") return;
      if (e.repeat) return;
      if (e.metaKey || e.ctrlKey || e.altKey || e.shiftKey) return;
      if (isEditableTarget(e.target)) return;
      e.preventDefault();
      setOpen(false);
      router.push("/workflows/new");
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [router]);

  useEffect(() => {
    const handler = () => setOpen(true);
    window.addEventListener(OPEN_EVENT, handler);
    return () => window.removeEventListener(OPEN_EVENT, handler);
  }, []);

  const recordRecent = (id: string) => {
    const next = [id, ...recents.filter((r) => r !== id)].slice(0, MAX_RECENTS);
    setRecents(next);
    try {
      localStorage.setItem(RECENTS_KEY, JSON.stringify(next));
    } catch {}
  };

  const run = (action: Action) => {
    recordRecent(action.id);
    setOpen(false);
    action.perform(router);
  };

  const openWorkflow = (id: string, name: string) => {
    setOpen(false);
    recordWorkflowVisit(id, name);
    router.push(`/workflows/${id}`);
  };

  const applyTemplate = async (templateId: string) => {
    if (templateCreatingRef.current) return;
    const template = templates.find((t) => t.id === templateId);
    if (!template) return;
    templateCreatingRef.current = true;
    setOpen(false);
    try {
      const workflow = await createWorkflowFromTemplate(queryClient, template);
      router.push(`/workflows/${workflow.id}`);
    } catch {
      // toast surfaced by createWorkflowFromTemplate
    } finally {
      templateCreatingRef.current = false;
    }
  };

  const addNode = (nodeType: string) => {
    setOpen(false);
    emitAddNode(nodeType);
  };

  const focusCanvasNode = (nodeId: string) => {
    setOpen(false);
    window.dispatchEvent(new CustomEvent(FOCUS_NODE_EVENT, { detail: { nodeId } }));
  };

  // ── Root-mode action groups (context aware) ──────────────────────────────

  const canvasActions: Action[] = onCanvas
    ? [
        {
          id: "canvas:run",
          label: "Run workflow",
          description: "Execute the current workflow from the canvas",
          group: "Canvas",
          icon: Play,
          perform: () => window.dispatchEvent(new Event(RUN_WORKFLOW_EVENT)),
        },
        {
          id: "canvas:tidy",
          label: "Tidy layout",
          description: "Auto-arrange nodes into a clean graph",
          group: "Canvas",
          icon: Wand2,
          perform: () => window.dispatchEvent(new Event(TIDY_CANVAS_EVENT)),
        },
        {
          id: "canvas:fit",
          label: "Fit view",
          description: "Zoom to fit the whole graph on screen",
          group: "Canvas",
          icon: Maximize2,
          perform: () => window.dispatchEvent(new Event(FIT_VIEW_EVENT)),
        },
      ]
    : [];

  const runActions: Action[] = onRun
    ? [
        {
          id: "run:rerun",
          label: "Re-run",
          description: "Run this workflow again with the same inputs",
          group: "Run",
          icon: RotateCw,
          perform: () => window.dispatchEvent(new Event(RERUN_EVENT)),
        },
        {
          id: "run:export",
          label: "Export trace",
          description: "Download the full trace for this run",
          group: "Run",
          icon: Download,
          perform: () => window.dispatchEvent(new Event(EXPORT_TRACE_EVENT)),
        },
      ]
    : [];

  const globalActions: Action[] = [
    {
      id: "global:toggle-theme",
      label: "Toggle theme",
      description: "Switch between dark and light",
      group: "Global",
      icon: SunMoon,
      perform: () => toggleTheme(),
    },
    {
      id: "global:shortcuts",
      label: "Keyboard shortcuts",
      description: "View all keyboard shortcuts",
      group: "Global",
      icon: Sparkles,
      shortcut: "?",
      perform: () => openShortcutsHelp(),
    },
    {
      id: "global:assist",
      label: "Ask Assist",
      description: "Open the AI assistant panel",
      group: "Global",
      icon: MessageSquarePlus,
      perform: () => window.dispatchEvent(new Event(OPEN_ASSIST_EVENT)),
    },
  ];

  // The "Add node" verb (only meaningful on the canvas) drills into a sub-menu.
  const addNodeVerb: Action | null = onCanvas
    ? {
        id: "verb:add-node",
        label: "Add node…",
        description: "Insert a node from the taxonomy",
        group: "Create",
        icon: Plus,
        perform: () => setMode("add-node"),
      }
    : null;

  const rootActions: Action[] = useMemo(
    () => [
      ...NAV_ACTIONS.filter((a) => a.group === "Navigate"),
      ...(addNodeVerb ? [addNodeVerb] : []),
      ...NAV_ACTIONS.filter((a) => a.group === "Create"),
      ...canvasActions,
      ...runActions,
      ...globalActions,
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [onCanvas, onRun]
  );

  const groupBy = (items: Action[]) => {
    const map = new Map<string, Action[]>();
    for (const a of items) {
      const arr = map.get(a.group) ?? [];
      arr.push(a);
      map.set(a.group, arr);
    }
    return Array.from(map.entries());
  };

  const runAction = (action: Action) => {
    // Verbs (like Add node) drill instead of closing; they own their perform.
    if (action.id.startsWith("verb:")) {
      recordRecent(action.id);
      action.perform(router);
      return;
    }
    run(action);
  };

  const recentActions = recents
    .map((id) => rootActions.find((a) => a.id === id))
    .filter((a): a is Action => !!a);

  // When the workflows cache is loaded, drop recent entries that no longer exist.
  const workflowIds = new Set(workflows.map((w) => w.id));
  const visibleRecentWorkflows =
    workflows.length > 0
      ? recentWorkflows.filter((rw) => workflowIds.has(rw.id))
      : recentWorkflows;

  const visibleWorkflows = workflows.slice(0, MAX_WORKFLOW_RESULTS);

  // Find-node: filter the FULL canvas index first, then cap. Slicing before
  // filter made every node past the first 30 unfindable.
  const visibleCanvasNodes = useMemo(() => {
    if (!onCanvas || canvasNodes.length === 0) return [];
    const q = trimmedQuery.toLowerCase();
    if (!q) return canvasNodes.slice(0, MAX_CANVAS_NODES);
    return canvasNodes
      .filter(
        (n) =>
          (n.label || "").toLowerCase().includes(q) ||
          n.nodeType.toLowerCase().includes(q) ||
          n.id.toLowerCase().includes(q)
      )
      .slice(0, MAX_CANVAS_NODES);
  }, [onCanvas, canvasNodes, trimmedQuery]);

  // Node taxonomy grouped by registry category for the add-node sub-menu.
  const nodeGroups = useMemo(
    () =>
      NODE_CATEGORIES.map((cat) => ({
        ...cat,
        nodes: NODE_REGISTRY.filter((def) => def.category === cat.id),
      })).filter((group) => group.nodes.length > 0),
    []
  );

  const backToRoot = () => setMode("root");

  const headerCopy =
    mode === "add-node"
      ? { kicker: "Add node", sub: "Pick a node type to drop onto the canvas." }
      : { kicker: "Command", sub: "Jump across the workbench or start a new workflow." };

  return (
    <CommandDialog open={open} onOpenChange={setOpen} title="Aegis command center">
      <Command>
        <div className="flex items-center gap-2 border-b border-border px-3 pb-2 pt-3">
          {mode === "add-node" && (
            <button
              type="button"
              onClick={backToRoot}
              className="flex h-6 w-6 shrink-0 items-center justify-center rounded border border-border bg-surface-input text-muted transition-colors hover:text-foreground"
              aria-label="Back to commands"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
            </button>
          )}
          <div className="min-w-0">
            <p className="text-micro">{headerCopy.kicker}</p>
            <p className="mt-0.5 truncate text-xs text-subtle">{headerCopy.sub}</p>
          </div>
        </div>
        <CommandInput
          placeholder={
            mode === "add-node"
              ? "Search node types…"
              : "Search navigation, workflows, templates…"
          }
          value={query}
          onValueChange={setQuery}
          onKeyDown={(e) => {
            // Backspace on an empty query in a sub-menu returns to root.
            if (mode === "add-node" && e.key === "Backspace" && query.length === 0) {
              e.preventDefault();
              backToRoot();
            }
          }}
        />
        <CommandList className="max-h-[420px]">
          <CommandEmpty>No matches. Try a different search.</CommandEmpty>

          {mode === "add-node" ? (
            nodeGroups.map((group) => (
              <CommandGroup key={group.id} heading={group.label}>
                {group.nodes.map((def) => {
                  const cat = categorize(def.type);
                  const catColor = CATEGORY_COLOR_VAR[cat];
                  const Icon = def.icon;
                  return (
                    <CommandItem
                      key={`${def.type}-${def.label}`}
                      value={`node:${def.type} ${def.label} ${def.description}`}
                      onSelect={() => addNode(def.type)}
                    >
                      {/* Category hue appears ONLY as this tiny swatch — data semantics. */}
                      <span
                        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border"
                        style={{
                          borderColor: `color-mix(in srgb, ${catColor} 32%, transparent)`,
                          background: `color-mix(in srgb, ${catColor} 12%, transparent)`,
                          color: catColor,
                        }}
                      >
                        <Icon className="h-4 w-4" />
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-medium text-foreground">
                          {def.label}
                        </span>
                        <span className="block truncate text-xs text-muted">
                          {def.description}
                        </span>
                      </span>
                    </CommandItem>
                  );
                })}
              </CommandGroup>
            ))
          ) : (
            <>
              {!hasQuery && visibleRecentWorkflows.length > 0 && (
                <CommandGroup heading="Recent workflows">
                  {visibleRecentWorkflows.map((rw) => (
                    <CommandItem
                      key={rw.id}
                      value={`recent-workflow:${rw.id} ${rw.name}`}
                      onSelect={() => openWorkflow(rw.id, rw.name)}
                    >
                      <WorkflowRow name={rw.name} />
                    </CommandItem>
                  ))}
                </CommandGroup>
              )}

              {onCanvas && visibleCanvasNodes.length > 0 && (
                <CommandGroup heading="Canvas nodes">
                  {visibleCanvasNodes.map((n) => {
                    const cat = categorize(n.nodeType);
                    const catColor = CATEGORY_COLOR_VAR[cat];
                    const Icon = getNodeDefinition(n.nodeType)?.icon ?? Workflow;
                    return (
                      <CommandItem
                        key={`canvas-node:${n.id}`}
                        value={`canvas-node:${n.id} ${n.label} ${n.nodeType}`}
                        onSelect={() => focusCanvasNode(n.id)}
                      >
                        <span
                          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border"
                          style={{
                            borderColor: `color-mix(in srgb, ${catColor} 32%, transparent)`,
                            background: `color-mix(in srgb, ${catColor} 12%, transparent)`,
                            color: catColor,
                          }}
                        >
                          <Icon className="h-4 w-4" />
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-sm font-medium text-foreground">
                            {n.label || n.id}
                          </span>
                          <span className="block truncate font-mono text-xs lowercase text-muted">
                            {n.nodeType}
                          </span>
                        </span>
                      </CommandItem>
                    );
                  })}
                </CommandGroup>
              )}

              {recentActions.length > 0 && (
                <CommandGroup heading="Recent">
                  {recentActions.map((a) => (
                    <CommandItem key={a.id} onSelect={() => runAction(a)}>
                      <CommandActionRow action={a} />
                    </CommandItem>
                  ))}
                </CommandGroup>
              )}

              {groupBy(rootActions).map(([group, items]) => (
                <CommandGroup key={group} heading={group}>
                  {items.map((a) => (
                    <CommandItem key={a.id} onSelect={() => runAction(a)}>
                      <CommandActionRow action={a} />
                    </CommandItem>
                  ))}
                </CommandGroup>
              ))}

              {hasQuery && visibleWorkflows.length > 0 && (
                <CommandGroup heading="Workflows">
                  {visibleWorkflows.map((w) => {
                    const version =
                      w.latest_version_number != null ? `v${w.latest_version_number}` : null;
                    const meta = version
                      ? `${version}${w.published ? " · published" : ""}`
                      : w.published
                        ? "published"
                        : undefined;
                    return (
                      <CommandItem
                        key={w.id}
                        value={`workflow:${w.id} ${w.name} ${w.description ?? ""}`}
                        onSelect={() => openWorkflow(w.id, w.name)}
                      >
                        <WorkflowRow name={w.name} meta={meta} />
                      </CommandItem>
                    );
                  })}
                </CommandGroup>
              )}

              {hasQuery && templates.length > 0 && (
                <CommandGroup heading="Templates">
                  {templates.map((t) => (
                    <CommandItem
                      key={t.id}
                      value={`template:${t.id} ${t.name}`}
                      onSelect={() => void applyTemplate(t.id)}
                    >
                      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-border bg-surface-input text-muted">
                        <LayoutTemplate className="h-4 w-4" />
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-medium text-foreground">
                          Use template: {t.name}
                        </span>
                        <span className="block truncate text-xs text-muted">{t.description}</span>
                      </span>
                    </CommandItem>
                  ))}
                </CommandGroup>
              )}
            </>
          )}
        </CommandList>
      </Command>
    </CommandDialog>
  );
}
