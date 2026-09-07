"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Background,
  BackgroundVariant,
  MiniMap,
  Panel,
  ReactFlow,
  ReactFlowProvider,
  SelectionMode,
  addEdge,
  reconnectEdge,
  useEdgesState,
  useNodesState,
  useReactFlow,
  type Connection,
  type Edge,
  type FinalConnectionState,
  type Node,
  type NodeChange,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import Link from "next/link";
import {
  ArrowLeft,
  Bookmark,
  Copy,
  ClipboardPaste,
  Group,
  Maximize2,
  MousePointer2,
  PanelLeft,
  PenLine,
  Play,
  Plus,
  Settings2,
  Trash2,
  Ungroup,
  Wand2,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { ConnectionLine } from "@/components/canvas/edges/ConnectionLine";
import { GradientEdge } from "@/components/canvas/edges/GradientEdge";
import { canvasNodeTypes, flowNodeTypeForData } from "@/components/canvas/nodes/node-types";
import { CanvasSidebar } from "@/components/canvas/CanvasSidebar";
import { type CanvasRailTab } from "@/components/canvas/CanvasRail";
import { categorize, CATEGORY_COLOR_VAR, supportsErrorBranch } from "@/components/canvas/nodes/category";
import type { DiffKind } from "@/components/canvas/VersionDiffView";
import { EdgeInspector } from "@/components/canvas/EdgeInspector";
import { DRAG_TYPE } from "@/components/canvas/NodePalette";
import { QuickAddMenu } from "@/components/canvas/QuickAddMenu";
import {
  CanvasContextMenu,
  buildNodeRunMenuItems,
  type ContextMenuItem,
} from "@/components/canvas/CanvasContextMenu";
import { useGraphHistory } from "@/components/canvas/useGraphHistory";
import {
  copyToClipboard,
  hasClipboard,
  materializeClipboard,
  materializeFragmentAt,
  serializeSelection,
  duplicateFragment,
} from "@/components/canvas/clipboard";
import { SnippetNameDialog } from "@/components/canvas/SnippetNameDialog";
import {
  getSnippets,
  saveSnippet,
  deleteSnippet,
  type Snippet,
} from "@/lib/snippets";
import {
  setCanvasNodeIndex,
  clearCanvasNodeIndex,
} from "@/lib/canvas-node-index";
import { WorkflowNameEditor } from "@/components/canvas/chrome/WorkflowNameEditor";
import { HeaderActions } from "@/components/canvas/chrome/HeaderActions";
import { CanvasStatusBar } from "@/components/canvas/chrome/CanvasStatusBar";
import { CanvasToolbar } from "@/components/canvas/chrome/CanvasToolbar";
import { RunControl } from "@/components/canvas/run/RunControl";
import { useRunInput } from "@/components/canvas/run/useRunInput";
import { NodeOutputPeek } from "@/components/canvas/run/NodeOutputPeek";
import { PostRunTransport } from "@/components/canvas/run/RunProgressStrip";
import { RunDeck } from "@/components/canvas/run/RunDeck";
import { useRunReplay } from "@/components/canvas/run/useRunReplay";
import { useResizablePanel } from "@/hooks/use-resizable-panel";
const NodeInspector = dynamic(
  () => import("@/components/canvas/NodeInspector").then((mod) => mod.NodeInspector),
  { ssr: false }
);
const RunResultsPanel = dynamic(
  () => import("@/components/results/RunResultsPanel").then((mod) => mod.RunResultsPanel),
  { ssr: false }
);
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { api } from "@/lib/api";
import type { GraphDiff } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import {
  getNodeDefinition,
  getNodeLintIssues,
  describeKindMismatch,
  resolveNodeOutputKind,
  resolveNodeAcceptsKind,
} from "@/lib/node-registry";
import { isEditableTarget, isInOverlay } from "@/lib/shortcuts";
import {
  formatValidationToast,
  getWorkflowValidationIssues,
} from "@/lib/workflow-validation";
import { readWorkflowExportFile, WorkflowImportError } from "@/lib/workflow-import";
import type {
  NodeData,
  Workflow,
  WorkflowGraph,
  WorkflowRun,
  WorkflowVersion,
} from "@/types/workflow";
import { cn } from "@/lib/utils";
import { useReducedMotionStrict } from "@/components/motion";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { flushSync } from "react-dom";
import { flushDraftTextareas } from "@/components/canvas/NodeInspector";
import { AssistRail } from "@/components/canvas/AssistRail";
import {
  ADD_NODE_EVENT,
  RUN_WORKFLOW_EVENT,
  TIDY_CANVAS_EVENT,
  FIT_VIEW_EVENT,
  OPEN_ASSIST_EVENT,
  FOCUS_NODE_EVENT,
} from "@/components/layout/CommandPalette";

const edgeTypes = { default: GradientEdge, smoothstep: GradientEdge };

function minimapNodeColor(node: Node): string {
  const nodeType = (node.data as NodeData)?.nodeType;
  return CATEGORY_COLOR_VAR[categorize(nodeType ?? "agent")];
}

function nextNodeId(existingNodes: Node[]): string {
  let max = 0;
  for (const node of existingNodes) {
    const match = /^node_(\d+)$/.exec(node.id);
    if (match) {
      max = Math.max(max, Number.parseInt(match[1], 10));
    }
  }
  return `node_${max + 1}`;
}

function isTerminalRunStatus(status: string | null | undefined): boolean {
  return status === "completed" || status === "failed" || status === "cancelled";
}

const DEFAULT_NODE_W = 200;
const DEFAULT_NODE_H = 90;

// Grouping-frame geometry (shared by creation + live refit so they stay in sync).
const GROUP_PAD = 28;
const GROUP_LABEL_ROOM = 16; // extra top padding so the label clears members
const MIN_GROUP_W = 180;
const MIN_GROUP_H = 120;
// A collapsed frame renders as a compact card (display-only size override).
const COLLAPSED_GROUP_W = 200;
const COLLAPSED_GROUP_H = 64;

/** Node types that cannot be spliced into an edge (no free source+target pair). */
const SPLICE_INELIGIBLE = new Set(["trigger", "end", "note", "group"]);
function isSpliceEligibleType(nodeType: string | undefined): boolean {
  return !!nodeType && !SPLICE_INELIGIBLE.has(nodeType);
}

function nodeSize(node: Node): { w: number; h: number } {
  return {
    w: node.measured?.width ?? node.width ?? DEFAULT_NODE_W,
    h: node.measured?.height ?? node.height ?? DEFAULT_NODE_H,
  };
}

/** Absolute (canvas) top-left of a node, accounting for a group parent's offset. */
function absolutePosition(node: Node, byId: Map<string, Node>): { x: number; y: number } {
  if (node.parentId) {
    const parent = byId.get(node.parentId);
    if (parent) {
      return { x: parent.position.x + node.position.x, y: parent.position.y + node.position.y };
    }
  }
  return { x: node.position.x, y: node.position.y };
}

/**
 * Live-refit a grouping frame around its members (Task 1). Recomputes the frame
 * bounding box from members' relative positions + dimensions (+ padding, min
 * size), then moves the frame and shifts every member by the inverse so their
 * ABSOLUTE positions never jump — the frame moves around the content, the
 * content stays put. Returns a new nodes array, or the same array if nothing
 * changed. No history side effects: callers fold this into an existing snapshot.
 */
function refitGroupNodes(nds: Node[], groupId: string): Node[] {
  const group = nds.find((n) => n.id === groupId);
  if (!group || (group.data as NodeData).nodeType !== "group") return nds;
  const children = nds.filter((n) => n.parentId === groupId);
  if (children.length === 0) return nds;

  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (const child of children) {
    const s = nodeSize(child);
    // Child positions are already relative to the group's top-left.
    minX = Math.min(minX, child.position.x);
    minY = Math.min(minY, child.position.y);
    maxX = Math.max(maxX, child.position.x + s.w);
    maxY = Math.max(maxY, child.position.y + s.h);
  }

  const padTop = GROUP_PAD + GROUP_LABEL_ROOM;
  // Shift so the content sits at (GROUP_PAD, padTop) inside the refitted frame.
  const dx = minX - GROUP_PAD;
  const dy = minY - padTop;
  const width = Math.max(maxX - minX + GROUP_PAD * 2, MIN_GROUP_W);
  const height = Math.max(maxY - minY + GROUP_PAD + padTop, MIN_GROUP_H);

  const curW = typeof group.style?.width === "number" ? group.style.width : undefined;
  const curH = typeof group.style?.height === "number" ? group.style.height : undefined;
  if (dx === 0 && dy === 0 && curW === width && curH === height) return nds;

  const newGroupX = group.position.x + dx;
  const newGroupY = group.position.y + dy;
  return nds.map((n) => {
    if (n.id === groupId) {
      return {
        ...n,
        position: { x: newGroupX, y: newGroupY },
        style: { ...(n.style ?? {}), width, height },
        data: { ...(n.data as NodeData), groupWidth: width, groupHeight: height },
      };
    }
    if (n.parentId === groupId) {
      return { ...n, position: { x: n.position.x - dx, y: n.position.y - dy } };
    }
    return n;
  });
}

/** Squared distance from point P to segment AB, clamped to the segment. */
function pointToSegmentDist(
  px: number,
  py: number,
  ax: number,
  ay: number,
  bx: number,
  by: number
): number {
  const dx = bx - ax;
  const dy = by - ay;
  const lenSq = dx * dx + dy * dy;
  let t = lenSq === 0 ? 0 : ((px - ax) * dx + (py - ay) * dy) / lenSq;
  t = Math.max(0, Math.min(1, t));
  const cx = ax + t * dx;
  const cy = ay + t * dy;
  return Math.hypot(px - cx, py - cy);
}

/**
 * Splice a node into an existing edge: A→B becomes A→N + N→B, with the original
 * edge removed. The upstream segment A→N inherits A→B's route/label/data (the
 * route belongs to the upstream branch); N→B is a fresh edge. Returns the new
 * edge array, or null when the target edge is missing or would self-loop.
 */
function spliceNodeIntoEdge(
  eds: Edge[],
  nodeId: string,
  edgeId: string,
  makeFreshEdge: (source: string, target: string) => Edge
): Edge[] | null {
  const edge = eds.find((e) => e.id === edgeId);
  if (!edge) return null;
  if (edge.source === nodeId || edge.target === nodeId) return null;
  const upstream: Edge = {
    ...edge,
    id: `e-${edge.source}-${nodeId}-${Date.now()}`,
    target: nodeId,
    targetHandle: null,
  };
  const downstream = makeFreshEdge(nodeId, edge.target);
  return [...eds.filter((e) => e.id !== edgeId), upstream, downstream];
}

function toGraph(nodes: Node[], edges: Edge[]): WorkflowGraph {
  return {
    nodes: nodes.map((node) => ({
      id: node.id,
      type: node.type,
      position: node.position,
      data: node.data as NodeData,
      // Grouping membership round-trips through the normal save (backend
      // tolerates it). Positions are already parent-relative when parentId is set.
      ...(node.parentId ? { parentId: node.parentId } : {}),
    })),
    edges: edges.map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      label: typeof edge.label === "string" ? edge.label : undefined,
      data: edge.data as { route?: string } | undefined,
    })),
  };
}

/**
 * Keys the canvas injects into `node.data` for rendering only — run state,
 * telemetry, diff rings and interaction callbacks (see `displayNodes` below and
 * `ExtendedNodeData` in nodes/BaseNode.tsx). They never belong to the persisted
 * graph, so the unsaved-changes comparison must not see them.
 */
const EPHEMERAL_NODE_DATA_KEYS = new Set([
  "isActive",
  "hasError",
  "errorMessage",
  "runtimeState",
  "startedAt",
  "category",
  "diffKind",
  "isRenaming",
  "peekAvailable",
  "telemetry",
  "showTelemetry",
  "pinned",
  "lintIssues",
  "onQuickAdd",
  "onDuplicate",
  "onDelete",
  "onRenameCommit",
  "onRenameCancel",
  "onPeekOutput",
  "onToggleCollapse",
  "memberCount",
  "aggregateStatus",
]);

/**
 * Stable, persisted-only projection of the graph, used as the "is this edited?"
 * signature. React Flow keeps plenty of state on its node/edge objects that is
 * not part of the workflow — `selected`, `dragging`, `measured`/`width`/
 * `height` — and the canvas layers display-only fields into `data`; comparing
 * raw React Flow state made a bare node click read as an unsaved edit and
 * raised the browser's "Leave site?" guard on a read-only visit. Keys are
 * emitted in sorted order so re-created objects can't differ by key order
 * alone, and functions/undefined are dropped.
 */
function persistedNodeData(data: NodeData): Record<string, unknown> {
  const source = (data ?? {}) as unknown as Record<string, unknown>;
  const out: Record<string, unknown> = {};
  for (const key of Object.keys(source).sort()) {
    if (EPHEMERAL_NODE_DATA_KEYS.has(key)) continue;
    const value = source[key];
    if (value === undefined || typeof value === "function") continue;
    out[key] = value;
  }
  return out;
}

function graphSignature(nodes: Node[], edges: Edge[]): string {
  return JSON.stringify({
    nodes: nodes.map((node) => ({
      id: node.id,
      type: node.type,
      parentId: node.parentId,
      position: { x: node.position.x, y: node.position.y },
      data: persistedNodeData(node.data as NodeData),
    })),
    edges: edges.map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      label: typeof edge.label === "string" ? edge.label : undefined,
      // `route` is the only persisted edge datum; displayEdges adds render-only
      // keys (active/failed/sourceNodeType…) that must not count as edits.
      route: (edge.data as { route?: string } | undefined)?.route,
    })),
  });
}

function graphToNodes(graph: WorkflowGraph): Node[] {
  return (graph.nodes || []).map((node) => {
    const data = node.data as NodeData;
    const built: Node = {
      id: node.id,
      type: flowNodeTypeForData(data),
      position: node.position,
      data,
    };
    if (node.parentId) built.parentId = node.parentId;
    // A grouping frame is sized via node.style (React Flow reads it for the
    // parent box); node.style is not serialized, so rebuild it from data.
    if (data.nodeType === "group") {
      built.style = { width: data.groupWidth ?? 320, height: data.groupHeight ?? 200 };
    }
    return built;
  });
}

function graphToEdges(graph: WorkflowGraph): Edge[] {
  return (graph.edges || []).map((edge) => ({
    id: edge.id,
    source: edge.source,
    target: edge.target,
    type: "smoothstep",
    // Error-branch edges (data.route === "error") originate from the node's
    // bottom "error" handle. sourceHandle isn't persisted, so rebuild it from
    // the route on load — otherwise the edge would snap back to the right handle.
    ...(edge.data?.route === "error" ? { sourceHandle: "error" } : {}),
    label: edge.label,
    data: edge.data,
    labelStyle: { fill: "var(--fg-muted)", fontSize: 11, fontWeight: 500 },
    labelBgStyle: { fill: "var(--surface-elevated)", fillOpacity: 0.95 },
    labelBgPadding: [6, 4] as [number, number],
    labelBgBorderRadius: 4,
  }));
}

interface WorkflowCanvasProps {
  workflowId: string;
  workflowName: string;
  initialGraph: WorkflowGraph;
  versionId?: string;
}

function WorkflowCanvasInner({
  workflowId,
  workflowName,
  initialGraph,
  versionId,
}: WorkflowCanvasProps) {
  const queryClient = useQueryClient();
  const reactFlowWrapper = useRef<HTMLDivElement>(null);
  const importInputRef = useRef<HTMLInputElement>(null);
  const reduceMotion = useReducedMotionStrict();
  // React Flow viewport animations honor prefers-reduced-motion.
  const viewportAnimMs = reduceMotion ? 0 : 300;
  const {
    screenToFlowPosition,
    flowToScreenPosition,
    fitView,
    deleteElements,
    getViewport,
    setViewport,
    setCenter,
  } = useReactFlow();

  const initialNodes = useMemo<Node[]>(() => graphToNodes(initialGraph), [initialGraph]);
  const initialEdges = useMemo<Edge[]>(() => graphToEdges(initialGraph), [initialGraph]);

  const [nodes, setNodes, onNodesChange] = useNodesState<Node>(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>(initialEdges);
  const [sidebarTab, setSidebarTab] = useState<CanvasRailTab>("nodes");
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [canvasMode, setCanvasMode] = useState<"compose" | "run">("compose");
  const isRunLens = canvasMode === "run";
  const [runLensNodeId, setRunLensNodeId] = useState<string | null>(null);
  const [rightTab, setRightTab] = useState<"configure" | "results">("configure");
  const [showResults, setShowResults] = useState(false);
  const [quickAdd, setQuickAdd] = useState<{
    screen: { x: number; y: number };
    flow: { x: number; y: number };
    sourceNodeId?: string;
    /** The source handle the drag started from — "error" threads an error-branch
     *  origin through to the created edge (Task 3); undefined is a normal edge. */
    sourceHandleId?: string;
  } | null>(null);
  const [selectedNodeIds, setSelectedNodeIds] = useState<string[]>([]);
  const [selectedEdgeIds, setSelectedEdgeIds] = useState<string[]>([]);
  const [contextMenu, setContextMenu] = useState<{
    kind: "node" | "edge" | "pane" | "selection";
    id?: string;
    screen: { x: number; y: number };
    flow: { x: number; y: number };
  } | null>(null);
  const [renamingNodeId, setRenamingNodeId] = useState<string | null>(null);
  // Feature: drag-to-splice — the edge currently highlighted as the drop target
  // under a dragged node. A ref mirror avoids redundant setState on every drag
  // frame (only re-render when the candidate actually changes).
  const [spliceEdgeId, setSpliceEdgeId] = useState<string | null>(null);
  const spliceEdgeIdRef = useRef<string | null>(null);
  // Feature: snippets — instance-local reusable selections (localStorage).
  const [snippets, setSnippets] = useState<Snippet[]>([]);
  // Feature: snippets — the serialized fragment awaiting a name in the dialog.
  const [snippetDraft, setSnippetDraft] = useState<{ nodes: Node[]; edges: Edge[] } | null>(null);
  const [nodeRunResults, setNodeRunResults] = useState<
    Record<
      string,
      { output: string | null; latencyMs: number | null; guardrailStatus: string | null; status: string }
    >
  >({});
  const [outputPeek, setOutputPeek] = useState<{ nodeId: string; screen: { x: number; y: number } } | null>(null);
  const [runStartedAt, setRunStartedAt] = useState<number | null>(null);
  const [displayName, setDisplayName] = useState(workflowName);
  const [currentVersionId, setCurrentVersionId] = useState(versionId);
  const [currentVersionNumber, setCurrentVersionNumber] = useState<number | null>(null);
  const [run, setRun] = useState<WorkflowRun | null>(null);
  const [liveEvents, setLiveEvents] = useState<Array<Record<string, unknown>>>([]);
  const [observedStartNodeIds, setObservedStartNodeIds] = useState<string[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [isRunStarting, setIsRunStarting] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [activeNodeId, setActiveNodeId] = useState<string | null>(null);
  // A run remains locked while a human decision is pending. `isRunning` tracks
  // active streaming only; this predicate protects the underlying graph for
  // the complete lifetime of a non-terminal run.
  const isRunLocked = isRunning || (!!run && !isTerminalRunStatus(run.status));
  const isCanvasReadOnly = isRunLens || isRunLocked;
  const [deleteConfirm, setDeleteConfirm] = useState<{ nodeIds: string[]; edgeIds: string[] } | null>(
    null
  );
  const [importConfirmOpen, setImportConfirmOpen] = useState(false);
  const [canvasAnnouncement, setCanvasAnnouncement] = useState("");
  const [diffHighlights, setDiffHighlights] = useState<Record<string, DiffKind> | null>(null);
  const lastSavedGraphRef = useRef(graphSignature(initialNodes, initialEdges));
  const savedVersionIdRef = useRef(versionId);
  const [historicalVersionNumber, setHistoricalVersionNumber] = useState<number | null>(null);
  // MVP2: per-node telemetry overlay, pin/run-from-here, Assist rail, run replay.
  const [showTelemetry, setShowTelemetry] = useState(false);
  const [pinnedOutputs, setPinnedOutputs] = useState<Record<string, string>>({});
  const [assistOpen, setAssistOpen] = useState(false);
  const [replayOpen, setReplayOpen] = useState(false);
  const replayInitRef = useRef(false);

  const lastPointerRef = useRef<{ x: number; y: number } | null>(null);
  // Feature 3: soft typed-port validation fires at most one toast per created
  // edge id in a session (never blocks — the runtime stringifies everything).
  const warnedKindEdgeIds = useRef<Set<string>>(new Set());
  // Task 4: dedupe the iteration-truncated notice to one toast per node per run.
  const truncatedNodesRef = useRef<Set<string>>(new Set());

  // Live refs so history/paste snapshots read fresh state synchronously.
  const nodesRef = useRef(nodes);
  nodesRef.current = nodes;
  const edgesRef = useRef(edges);
  edgesRef.current = edges;

  const history = useGraphHistory({ nodesRef, edgesRef, setNodes, setEdges });
  const record = history.record;
  const undo = history.undo;
  const redo = history.redo;

  const rightPanel = useResizablePanel({
    storageKey: "aegis:panel:right",
    defaultWidth: 360,
    min: 320,
    max: 520,
    side: "right",
  });

  // The run input is shared by the persistent desktop controls.
  const runInput = useRunInput(workflowId, nodes);

  // Single-selection views drive the inspectors; multi-selection drives bulk ops.
  const selectedNodeId =
    selectedNodeIds.length === 1 && selectedEdgeIds.length === 0 ? selectedNodeIds[0] : null;
  const selectedEdgeId =
    selectedEdgeIds.length === 1 && selectedNodeIds.length === 0 ? selectedEdgeIds[0] : null;
  const selectionCount = selectedNodeIds.length + selectedEdgeIds.length;

  const setSelectedNodeId = useCallback((id: string | null) => {
    setSelectedNodeIds(id ? [id] : []);
    if (id) setSelectedEdgeIds([]);
  }, []);
  const setSelectedEdgeId = useCallback((id: string | null) => {
    setSelectedEdgeIds(id ? [id] : []);
    if (id) setSelectedNodeIds([]);
  }, []);


  const isDirty = useMemo(
    () => graphSignature(nodes, edges) !== lastSavedGraphRef.current,
    [nodes, edges]
  );

  const validationIssues = useMemo(() => getWorkflowValidationIssues(nodes), [nodes]);

  // Feature 4: registry-driven config lint (soft, never blocks a run). Memoized
  // Map<nodeId, {field, message}[]>; feeds the node-card glyph, the inspector
  // hint list, and (deduped) the status-bar issues affordance.
  const lintByNodeId = useMemo(() => {
    const map = new Map<string, Array<{ field: string; message: string }>>();
    for (const node of nodes) {
      const issues = getNodeLintIssues(node.data as NodeData);
      if (issues.length) map.set(node.id, issues);
    }
    return map;
  }, [nodes]);

  // Structural (run-blocking) issues plus any lint issue not already covered by
  // a structural rule for the same node+field. Structural rows keep their exact
  // wording; lint only ADDS the broader registry-driven checks.
  const statusBarIssues = useMemo(() => {
    const structural = validationIssues.map((i) => ({ nodeId: i.nodeId, message: i.message }));
    const structuralKeys = new Set(validationIssues.map((i) => `${i.nodeId}:${i.field}`));
    const extra: Array<{ nodeId: string; message: string }> = [];
    lintByNodeId.forEach((issues, nodeId) => {
      for (const issue of issues) {
        if (structuralKeys.has(`${nodeId}:${issue.field}`)) continue;
        extra.push({ nodeId, message: issue.message });
      }
    });
    return [...structural, ...extra];
  }, [validationIssues, lintByNodeId]);

  // Grouping frames make the group-unaware auto-layout unsafe (see handleTidyLayout).
  const hasGroups = useMemo(
    () => nodes.some((n) => (n.data as NodeData).nodeType === "group"),
    [nodes]
  );

  const selectedNodeFieldErrors = useMemo(() => {
    if (!selectedNodeId) return {};
    const errors: Record<string, string> = {};
    for (const issue of validationIssues) {
      if (issue.nodeId === selectedNodeId) {
        errors[issue.field] = issue.message;
      }
    }
    return errors;
  }, [selectedNodeId, validationIssues]);
  const runSourceRef = useRef<{ close: () => void } | null>(null);
  const runRecoveryTimerRef = useRef<number | null>(null);
  const runStartPendingRef = useRef(false);
  const currentRunIdRef = useRef<string | null>(null);
  // Flipped false on unmount so awaited run steps can bail instead of starting
  // a stream (or touching state) after the component is gone.
  const mountedRef = useRef(true);
  const selectedNode = nodes.find((n) => n.id === selectedNodeId);
  const selectedData = selectedNode ? (selectedNode.data as NodeData) : null;
  const selectedEdge = edges.find((e) => e.id === selectedEdgeId) ?? null;

  const failedGuardrailIds = useMemo(() => {
    const ids = (run?.metrics_json?.failed_guardrails as string[] | undefined) || [];
    return new Set(ids);
  }, [run?.metrics_json]);

  const nodeErrorMessages = useMemo(() => {
    const map: Record<string, string> = {};
    const events =
      (run?.metrics_json?.guardrail_events as Array<{
        node_id: string;
        message?: string;
      }>) || [];
    for (const event of events) {
      if (event.message) map[event.node_id] = event.message;
    }
    failedGuardrailIds.forEach((id) => {
      if (!map[id]) map[id] = "Guardrail check failed";
    });
    for (const result of run?.node_results || []) {
      if (result.status === "failed" && result.output) {
        map[result.node_id] = result.output;
      }
    }
    return map;
  }, [run, failedGuardrailIds]);

  const activeEdgeIds = useMemo(() => {
    if (!isRunning || !activeNodeId) return new Set<string>();
    return new Set(
      edges
        .filter((edge) => edge.source === activeNodeId || edge.target === activeNodeId)
        .map((edge) => edge.id)
    );
  }, [edges, isRunning, activeNodeId]);

  const skipEdgeAnim = edges.length > 80;

  // Run replay: fetch the finished run's timeline (only while the transport is
  // open) and drive a pure scrubber controller. replayActive gates the memos.
  const replayRunId = run && !isRunLocked ? run.id : null;
  const timelineQuery = useQuery({
    queryKey: queryKeys.runTimeline(replayRunId ?? ""),
    queryFn: () => api.getRunTimeline(replayRunId as string),
    enabled: !!replayRunId && replayOpen,
    staleTime: 60_000,
  });
  const replay = useRunReplay({ timeline: timelineQuery.data });
  const replayActive = replayOpen && replay.steps.length > 0;

  // Per-node token/cost telemetry (for the on-canvas overlay), aggregated from
  // the run's LLM calls. Only fetched while the overlay is on.
  const telemetryRunId = run?.id ?? null;
  const llmCallsQuery = useQuery({
    queryKey: ["run-llm-calls", telemetryRunId] as const,
    queryFn: () => api.getRunLlmCalls(telemetryRunId as string),
    enabled: !!telemetryRunId && showTelemetry,
    staleTime: 60_000,
  });
  const llmCostByNode = useMemo(() => {
    const map: Record<string, { tokens: number; costUsd: number }> = {};
    for (const call of llmCallsQuery.data ?? []) {
      if (!call.node_id) continue;
      const prev = map[call.node_id] ?? { tokens: 0, costUsd: 0 };
      map[call.node_id] = {
        tokens: prev.tokens + (call.total_tokens ?? 0),
        costUsd: prev.costUsd + (call.cost_usd ?? 0),
      };
    }
    return map;
  }, [llmCallsQuery.data]);

  // Current graph, shared by the Assist rail and the inspector variable picker.
  const currentGraph = useMemo(() => toGraph(nodes, edges), [nodes, edges]);

  // Snippets are localStorage-backed — read after mount so SSR/first paint agree.
  const refreshSnippets = useCallback(() => setSnippets(getSnippets()), []);
  useEffect(() => {
    refreshSnippets();
  }, [refreshSnippets]);

  // Feature: find-on-canvas — publish this canvas's nodes to the module bridge so
  // the command palette can enumerate + focus them. Cleared on unmount.
  useEffect(() => {
    setCanvasNodeIndex(
      nodes.map((n) => {
        const d = n.data as NodeData;
        return { id: n.id, label: d.label || n.id, nodeType: d.nodeType };
      })
    );
    return () => clearCanvasNodeIndex();
  }, [nodes]);

  // The Run Lens deliberately changes the canvas height. Let the flex layout
  // settle for two frames, then reframe the existing graph so lower nodes never
  // disappear behind the execution deck.
  useEffect(() => {
    let nextFrame: number | null = null;
    const frame = window.requestAnimationFrame(() => {
      nextFrame = window.requestAnimationFrame(() => {
        void fitView({
          padding: canvasMode === "run" ? 0.14 : 0.2,
          maxZoom: 1.2,
          duration: viewportAnimMs,
        });
      });
    });

    return () => {
      window.cancelAnimationFrame(frame);
      if (nextFrame != null) window.cancelAnimationFrame(nextFrame);
    };
  }, [canvasMode, fitView, viewportAnimMs]);

  // On opening replay, park the scrubber at the end (matches the final canvas)
  // so nothing jumps; the user scrubs back to watch. Reset when it closes.
  useEffect(() => {
    if (!replayOpen) {
      replayInitRef.current = false;
      return;
    }
    if (replay.steps.length > 0 && !replayInitRef.current) {
      replayInitRef.current = true;
      replay.setIndex(replay.steps.length - 1);
    }
  }, [replayOpen, replay.steps.length, replay.setIndex, replay]);

  // O(1) node lookups by id — avoids the O(edges×nodes) scan displayEdges (and
  // other per-edge derivations) would otherwise do on every render (audit P2-47).
  const nodesById = useMemo(() => {
    const map = new Map<string, (typeof nodes)[number]>();
    for (const n of nodes) map.set(n.id, n);
    return map;
  }, [nodes]);

  const displayEdges = useMemo(
    () =>
      edges.map((edge) => {
        const src = nodesById.get(edge.source);
        const tgt = nodesById.get(edge.target);
        const srcData = src?.data as NodeData | undefined;
        const tgtData = tgt?.data as NodeData | undefined;
        const failed =
          failedGuardrailIds.has(edge.source) || failedGuardrailIds.has(edge.target);
        return {
          ...edge,
          type: "default",
          animated: false,
          data: {
            ...(edge.data as Record<string, unknown> | undefined),
            sourceNodeType: srcData?.nodeType,
            targetNodeType: tgtData?.nodeType,
            spliceCandidate: edge.id === spliceEdgeId,
            active: replayActive
              ? !skipEdgeAnim &&
                (edge.source === replay.derived.currentNodeId ||
                  edge.target === replay.derived.currentNodeId)
              : !skipEdgeAnim && activeEdgeIds.has(edge.id),
            failed,
            sourceCompleted: replayActive
              ? !skipEdgeAnim && replay.derived.isSourceCompleted(edge.source)
              : !skipEdgeAnim && nodeRunResults[edge.source]?.status === "completed",
          },
          labelStyle: { fill: "var(--fg-muted)", fontSize: 11, fontWeight: 500 },
          labelBgStyle: { fill: "var(--surface)", fillOpacity: 0.95 },
        };
      }),
    [
      edges,
      nodesById,
      activeEdgeIds,
      failedGuardrailIds,
      skipEdgeAnim,
      nodeRunResults,
      replayActive,
      replay.derived,
      spliceEdgeId,
    ]
  );

  const nodeTypes = useMemo(() => canvasNodeTypes, []);
  const memoizedEdgeTypes = useMemo(() => edgeTypes, []);

  // Pointer drags record via onNodeDragStart (dragging === true on their
  // position changes). Arrow-key nudges arrive as position changes with
  // dragging !== true and no drag session — record those once, coalescing
  // held-arrow repeats under a shared key.
  const handleNodesChange = useCallback(
    (changes: NodeChange[]) => {
      // Run Lens permits selection so the operator can inspect a stage, but it
      // never forwards position/removal/replace changes into the editable graph.
      if (isCanvasReadOnly) {
        onNodesChange(changes.filter((change) => change.type === "select"));
        return;
      }
      const keyMove = changes.some(
        (c) => c.type === "position" && c.dragging !== true
      );
      if (keyMove) record("keymove");
      onNodesChange(changes);
    },
    [isCanvasReadOnly, onNodesChange, record]
  );

  const addNodeAtPosition = useCallback(
    (data: NodeData, position: { x: number; y: number }) => {
      record();
      const newId = nextNodeId(nodesRef.current);
      setNodes((nds) => [
        ...nds.map((n) => (n.selected ? { ...n, selected: false } : n)),
        {
          id: newId,
          type: flowNodeTypeForData(data),
          position,
          data,
          selected: true,
        },
      ]);
      setSelectedNodeId(newId);
      setSelectedEdgeId(null);
    },
    [setNodes, record, setSelectedNodeId, setSelectedEdgeId]
  );

  const handleAddNode = useCallback(
    (data: NodeData) => {
      record();
      const newId = nextNodeId(nodesRef.current);
      const ordinal = Number.parseInt(newId.replace("node_", ""), 10);
      setNodes((nds) => [
        ...nds.map((n) => (n.selected ? { ...n, selected: false } : n)),
        {
          id: newId,
          type: flowNodeTypeForData(data),
          position: { x: 120 + ordinal * 48, y: 120 + ordinal * 32 },
          data,
          selected: true,
        },
      ]);
      setSelectedNodeId(newId);
      setSelectedEdgeId(null);
    },
    [setNodes, record, setSelectedNodeId, setSelectedEdgeId]
  );

  const makeEdge = useCallback(
    (sourceId: string, targetId: string): Edge => {
      const sourceNode = nodes.find((n) => n.id === sourceId);
      const sourceData = sourceNode?.data as NodeData | undefined;
      let route: string | undefined;

      const branchKeys =
        sourceData?.nodeType === "router"
          ? sourceData.routes
          : sourceData?.nodeType === "classifier"
            ? sourceData.categories
            : sourceData?.nodeType === "if"
              ? ["true", "false"]
              : sourceData?.nodeType === "switch"
                ? [
                    ...(sourceData.switchCases || []),
                    sourceData.switchDefault || "default",
                  ]
                : sourceData?.nodeType === "guardrail" &&
                    sourceData.rules?.fail_behavior === "route"
                  ? [
                      sourceData.rules.pass_route || "pass",
                      sourceData.rules.failure_route || "failed",
                    ]
                  : undefined;

      if (branchKeys?.length) {
        const used = edges
          .filter((e) => e.source === sourceId)
          .map((e) => (e.data as { route?: string })?.route)
          .filter(Boolean);
        route = branchKeys.find((r) => !used.includes(r)) ?? branchKeys[0];
      }

      return {
        source: sourceId,
        target: targetId,
        id: `e-${sourceId}-${targetId}-${Date.now()}`,
        type: "smoothstep",
        label: route,
        data: route ? { route } : undefined,
        labelStyle: { fill: "var(--fg-muted)", fontSize: 11 },
        labelBgStyle: { fill: "var(--surface-elevated)", fillOpacity: 0.9 },
      };
    },
    [nodes, edges]
  );

  /** Soft typed-port check (Feature 3): a single quiet toast when a list/JSON
   *  source feeds a text-only target. Never blocks — the runtime stringifies. */
  const maybeWarnKindMismatch = useCallback(
    (edgeId: string, sourceId: string, targetId: string) => {
      if (warnedKindEdgeIds.current.has(edgeId)) return;
      const sData = nodesRef.current.find((n) => n.id === sourceId)?.data as
        | NodeData
        | undefined;
      const tData = nodesRef.current.find((n) => n.id === targetId)?.data as
        | NodeData
        | undefined;
      if (!sData || !tData) return;
      const out = resolveNodeOutputKind(sData.nodeType, sData);
      const accepts = resolveNodeAcceptsKind(tData.nodeType, tData);
      const sLabel = sData.label || getNodeDefinition(sData.nodeType, sData)?.label || sData.nodeType;
      const tLabel = tData.label || getNodeDefinition(tData.nodeType, tData)?.label || tData.nodeType;
      const message = describeKindMismatch(sLabel, tLabel, out, accepts);
      if (message) {
        warnedKindEdgeIds.current.add(edgeId);
        toast.warning(message);
      }
    },
    []
  );

  const onConnect = useCallback(
    (connection: Connection) => {
      if (!connection.source || !connection.target) return;
      // A collapsed group grows display-only handles so re-pointed boundary edges
      // land somewhere; real connections to/from a frame make no graph sense —
      // refuse them quietly and tell the user how to proceed.
      const endpointIsGroup = (nodeId: string) =>
        (nodesRef.current.find((n) => n.id === nodeId)?.data as NodeData | undefined)?.nodeType ===
        "group";
      if (endpointIsGroup(connection.source) || endpointIsGroup(connection.target)) {
        toast.message("Expand the group to connect nodes");
        return;
      }
      const isError = connection.sourceHandle === "error";
      // addEdge dedupes an identical connection (same endpoints + handles);
      // don't record a phantom undo entry when it would be a no-op.
      const isDuplicate = edgesRef.current.some(
        (e) =>
          e.source === connection.source &&
          e.target === connection.target &&
          (e.sourceHandle ?? null) === (connection.sourceHandle ?? null) &&
          (e.targetHandle ?? null) === (connection.targetHandle ?? null)
      );
      if (isDuplicate) return;

      // Feature 2: at most one error route per source node (backend enforces it
      // too). Block a second and say why, rather than silently dropping it.
      if (isError) {
        const hasErrorEdge = edgesRef.current.some(
          (e) =>
            e.source === connection.source &&
            (e.data as { route?: string } | undefined)?.route === "error"
        );
        if (hasErrorEdge) {
          toast.error("One error route per node");
          return;
        }
      }

      const base = makeEdge(connection.source, connection.target);
      // An error connection overrides any branch route with the "error" sentinel
      // and keeps its bottom-handle origin so it renders (and reloads) downward.
      const edge: Edge = isError
        ? { ...base, sourceHandle: "error", label: undefined, data: { route: "error" } }
        : base;

      maybeWarnKindMismatch(edge.id, connection.source, connection.target);
      record();
      setEdges((eds) => addEdge(edge, eds));
    },
    [makeEdge, setEdges, record, maybeWarnKindMismatch]
  );

  /** n8n-style: dropping a half-made connection on empty canvas opens the node picker. */
  const onConnectEnd = useCallback(
    (event: MouseEvent | TouchEvent, connectionState: FinalConnectionState) => {
      if (connectionState.isValid) return;
      if (connectionState.fromHandle?.type !== "source") return;
      const sourceId = connectionState.fromNode?.id;
      if (!sourceId) return;
      // A collapsed frame's display handles must not spawn wiring (Task 2).
      const sourceType = (nodesRef.current.find((n) => n.id === sourceId)?.data as
        | NodeData
        | undefined)?.nodeType;
      if (sourceType === "group") {
        toast.message("Expand the group to connect nodes");
        return;
      }
      const client =
        "changedTouches" in event
          ? { x: event.changedTouches[0].clientX, y: event.changedTouches[0].clientY }
          : { x: event.clientX, y: event.clientY };
      setQuickAdd({
        screen: client,
        flow: screenToFlowPosition(client),
        sourceNodeId: sourceId,
        // Task 3: thread the origin handle so a drag from the bottom "error"
        // handle creates an error-branch edge (not a plain edge) on pick.
        sourceHandleId: connectionState.fromHandle?.id ?? undefined,
      });
    },
    [screenToFlowPosition]
  );

  /** Open the picker from a node's "+" button; new node lands one column right. */
  const openQuickAddFromNode = useCallback(
    (nodeId: string) => {
      const node = nodes.find((n) => n.id === nodeId);
      if (!node) return;
      // Group members store parent-relative positions — convert to absolute so
      // the menu and new node land next to the visible card, not near the origin.
      const byId = new Map(nodes.map((n) => [n.id, n]));
      const abs = absolutePosition(node, byId);
      const flow = { x: abs.x + 280, y: abs.y };
      const screen = flowToScreenPosition(flow);
      setQuickAdd({ screen, flow, sourceNodeId: nodeId });
    },
    [nodes, flowToScreenPosition]
  );

  const openQuickAddAtCenter = useCallback(() => {
    const rect = reactFlowWrapper.current?.getBoundingClientRect();
    const screen = rect
      ? { x: rect.x + rect.width / 2 - 144, y: rect.y + rect.height / 2 - 160 }
      : { x: window.innerWidth / 2, y: window.innerHeight / 2 };
    setQuickAdd({ screen, flow: screenToFlowPosition(screen) });
  }, [screenToFlowPosition]);

  /** Pan the viewport so a newly placed node is fully visible (the inspector
   *  column opens on selection and can otherwise hide it). */
  const ensureInView = useCallback(
    (flow: { x: number; y: number }) => {
      const rect = reactFlowWrapper.current?.getBoundingClientRect();
      if (!rect) return;
      const vp = getViewport();
      const screen = flowToScreenPosition(flow);
      const nodeW = 200 * vp.zoom;
      const nodeH = 96 * vp.zoom;
      // The inspector column occupies rightPanel.width on large screens once a
      // node is selected. Only reserve that space when it will actually show.
      const inspectorInset = rightPanel.width + 48;
      const rightLimit = rect.right - inspectorInset; // inspector width + margin
      const leftLimit = rect.left + 24;
      const topLimit = rect.top + 24;
      const bottomLimit = rect.bottom - 48;
      let dx = 0;
      let dy = 0;
      if (screen.x + nodeW > rightLimit) dx = rightLimit - (screen.x + nodeW);
      else if (screen.x < leftLimit) dx = leftLimit - screen.x;
      if (screen.y + nodeH > bottomLimit) dy = bottomLimit - (screen.y + nodeH);
      else if (screen.y < topLimit) dy = topLimit - screen.y;
      if (dx !== 0 || dy !== 0) {
        void setViewport({ x: vp.x + dx, y: vp.y + dy, zoom: vp.zoom }, { duration: reduceMotion ? 0 : 200 });
      }
    },
    [getViewport, setViewport, flowToScreenPosition, reduceMotion, rightPanel.width]
  );

  const handleQuickAddSelect = useCallback(
    (data: NodeData) => {
      if (!quickAdd) return;
      record();
      const newId = nextNodeId(nodesRef.current);
      setNodes((nds) => [
        ...nds.map((n) => (n.selected ? { ...n, selected: false } : n)),
        {
          id: newId,
          type: flowNodeTypeForData(data),
          position: quickAdd.flow,
          data,
          selected: true,
        },
      ]);
      if (quickAdd.sourceNodeId) {
        const sourceId = quickAdd.sourceNodeId;
        const sourceData = nodesRef.current.find((n) => n.id === sourceId)?.data as
          | NodeData
          | undefined;
        const sourceType = sourceData?.nodeType;
        // Trigger/note/group cannot receive edges (no target handle / annotation).
        // Keep the new node but skip wiring rather than persist an invisible edge.
        const targetAcceptsEdges = !["trigger", "note", "group"].includes(data.nodeType);
        // Task 3: an error-handle origin creates an error-branch edge, honoring
        // the one-error-route-per-node guard. The handle only exists on types
        // that support it, but assert cheaply anyway. On a guard conflict, keep
        // the new node but create NO edge (never a dangling normal edge).
        const wantsError =
          quickAdd.sourceHandleId === "error" && supportsErrorBranch(sourceType ?? "", sourceData);
        if (!targetAcceptsEdges) {
          toast.message("That node type cannot accept connections");
        } else if (wantsError) {
          const hasErrorEdge = edgesRef.current.some(
            (e) =>
              e.source === sourceId &&
              (e.data as { route?: string } | undefined)?.route === "error"
          );
          if (hasErrorEdge) {
            toast.error("One error route per node");
          } else {
            const base = makeEdge(sourceId, newId);
            const errorEdge: Edge = {
              ...base,
              sourceHandle: "error",
              label: undefined,
              data: { route: "error" },
            };
            maybeWarnKindMismatch(errorEdge.id, sourceId, newId);
            setEdges((eds) => addEdge(errorEdge, eds));
          }
        } else {
          const edge = makeEdge(sourceId, newId);
          maybeWarnKindMismatch(edge.id, sourceId, newId);
          setEdges((eds) => addEdge(edge, eds));
        }
      }
      setSelectedNodeId(newId);
      setSelectedEdgeId(null);
      setQuickAdd(null);
      ensureInView(quickAdd.flow);
    },
    [
      quickAdd,
      setNodes,
      setEdges,
      makeEdge,
      ensureInView,
      record,
      setSelectedNodeId,
      setSelectedEdgeId,
      maybeWarnKindMismatch,
    ]
  );

  /** Duplicate a set of nodes preserving intra-group connections. */
  const duplicateNodes = useCallback(
    (nodeIds: string[]) => {
      if (nodeIds.length === 0) return;
      const idSet = new Set(nodeIds);
      const fragment = duplicateFragment(
        nodesRef.current.filter((n) => idSet.has(n.id)),
        edgesRef.current,
        nodesRef.current
      );
      if (!fragment) return;
      record();
      setNodes((nds) => [
        ...nds.map((n) => (n.selected ? { ...n, selected: false } : n)),
        ...fragment.nodes,
      ]);
      if (fragment.edges.length > 0) {
        setEdges((eds) => [
          ...eds.map((e) => (e.selected ? { ...e, selected: false } : e)),
          ...fragment.edges,
        ]);
      }
    },
    [setNodes, setEdges, record]
  );

  const handleDuplicateNode = useCallback(
    (nodeId: string) => duplicateNodes([nodeId]),
    [duplicateNodes]
  );

  // ── Grouping frames ──────────────────────────────────────────────────────
  /** Wrap the current selection (≥2 flat nodes) in a group frame. */
  const handleGroupSelection = useCallback(() => {
    if (isCanvasReadOnly) return;
    const byId = new Map(nodesRef.current.map((n) => [n.id, n]));
    // v1 groups are flat: skip existing frames and already-grouped members.
    const members = selectedNodeIds
      .map((id) => byId.get(id))
      .filter((n): n is Node => {
        const t = (n?.data as NodeData | undefined)?.nodeType;
        return !!n && t !== "group" && !n.parentId;
      });
    if (members.length < 2) return;

    let minX = Infinity;
    let minY = Infinity;
    let maxX = -Infinity;
    let maxY = -Infinity;
    for (const m of members) {
      const p = absolutePosition(m, byId);
      const s = nodeSize(m);
      minX = Math.min(minX, p.x);
      minY = Math.min(minY, p.y);
      maxX = Math.max(maxX, p.x + s.w);
      maxY = Math.max(maxY, p.y + s.h);
    }
    const groupPos = { x: minX - GROUP_PAD, y: minY - GROUP_PAD - GROUP_LABEL_ROOM };
    const width = maxX - minX + GROUP_PAD * 2;
    const height = maxY - minY + GROUP_PAD * 2 + GROUP_LABEL_ROOM;
    const groupId = nextNodeId(nodesRef.current);
    const memberSet = new Set(members.map((m) => m.id));

    record();
    const groupNode: Node = {
      id: groupId,
      type: "group",
      position: groupPos,
      data: {
        label: "Group",
        nodeType: "group",
        groupWidth: width,
        groupHeight: height,
      } as NodeData,
      style: { width, height },
      selected: true,
    };
    setNodes((nds) => {
      const others = nds
        .filter((n) => !memberSet.has(n.id))
        .map((n) => (n.selected ? { ...n, selected: false } : n));
      const reparented = members.map((m) => {
        const p = absolutePosition(m, byId);
        return {
          ...m,
          parentId: groupId,
          // Positions become parent-relative once re-parented.
          position: { x: p.x - groupPos.x, y: p.y - groupPos.y },
          selected: false,
        };
      });
      // Frame first: React Flow requires a parent to precede its children, and
      // this also paints the frame behind every other node.
      return [groupNode, ...others, ...reparented];
    });
    setSelectedNodeId(groupId);
    setSelectedEdgeId(null);
  }, [
    isCanvasReadOnly,
    selectedNodeIds,
    record,
    setNodes,
    setSelectedNodeId,
    setSelectedEdgeId,
  ]);

  /** Dissolve a group frame, returning members to absolute positions. */
  const ungroupNode = useCallback(
    (groupId: string) => {
      if (isCanvasReadOnly) return;
      const group = nodesRef.current.find((n) => n.id === groupId);
      if (!group || (group.data as NodeData).nodeType !== "group") return;
      const gp = group.position;
      record();
      setNodes((nds) =>
        nds
          .filter((n) => n.id !== groupId)
          .map((n) =>
            n.parentId === groupId
              ? {
                  ...n,
                  parentId: undefined,
                  position: { x: n.position.x + gp.x, y: n.position.y + gp.y },
                }
              : n
          )
      );
      setSelectedNodeId(null);
      setSelectedEdgeId(null);
    },
    [isCanvasReadOnly, record, setNodes, setSelectedNodeId, setSelectedEdgeId]
  );

  /** Toggle a frame's presentational collapse (Task 2). Persisted + undoable. */
  const handleToggleCollapse = useCallback(
    (groupId: string) => {
      if (isCanvasReadOnly) return;
      record();
      setNodes((nds) =>
        nds.map((n) =>
          n.id === groupId
            ? { ...n, data: { ...(n.data as NodeData), collapsed: !(n.data as NodeData).collapsed } }
            : n
        )
      );
    },
    [isCanvasReadOnly, record, setNodes]
  );

  // ── Snippets (save selection → reusable insert) ──────────────────────────
  /** Serialize the current selection and open the name dialog. */
  const handleSaveSnippetRequest = useCallback(() => {
    const ids = new Set(selectedNodeIds);
    const selected = nodesRef.current.filter((n) => ids.has(n.id));
    if (selected.length === 0) return;
    setSnippetDraft(serializeSelection(selected, edgesRef.current));
  }, [selectedNodeIds]);

  const handleSnippetNameConfirm = useCallback(
    (name: string) => {
      setSnippetDraft((draft) => {
        if (draft) {
          saveSnippet(name, draft);
          refreshSnippets();
          toast.success("Snippet saved");
        }
        return null;
      });
    },
    [refreshSnippets]
  );

  const handleDeleteSnippet = useCallback(
    (id: string) => {
      deleteSnippet(id);
      refreshSnippets();
    },
    [refreshSnippets]
  );

  /** Paste a snippet's fragment at the quick-add position (fresh ids, undo). */
  const handleInsertSnippet = useCallback(
    (snippetId: string) => {
      const snippet = getSnippets().find((s) => s.id === snippetId);
      const anchor =
        quickAdd?.flow ??
        screenToFlowPosition(
          lastPointerRef.current ?? { x: window.innerWidth / 2, y: window.innerHeight / 2 }
        );
      if (!snippet) return;
      const fragment = materializeFragmentAt(
        snippet.payload.nodes,
        snippet.payload.edges,
        nodesRef.current,
        anchor
      );
      if (!fragment) return;
      record();
      setNodes((nds) => [
        ...nds.map((n) => (n.selected ? { ...n, selected: false } : n)),
        ...fragment.nodes,
      ]);
      if (fragment.edges.length > 0) {
        setEdges((eds) => [
          ...eds.map((e) => (e.selected ? { ...e, selected: false } : e)),
          ...fragment.edges,
        ]);
      }
      setQuickAdd(null);
    },
    [quickAdd, screenToFlowPosition, record, setNodes, setEdges]
  );


  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
  }, []);

  /**
   * Find the edge under a flow-space point that a node could splice into.
   * Straight source-handle→target-handle segment distance is used as a robust,
   * DOM-free proxy for the rendered bezier (good enough to signal "over this
   * edge"); the closest edge within threshold wins. Edges touching
   * `draggedNodeId` are ignored so a node never splices into its own wiring.
   */
  const findSpliceEdgeAt = useCallback(
    (point: { x: number; y: number }, draggedNodeId?: string): string | null => {
      const SPLICE_THRESHOLD = 44; // flow units
      const byId = new Map(nodesRef.current.map((n) => [n.id, n]));
      // Members of collapsed groups are hidden — their edges must not be splice
      // targets or a drop on empty canvas can wire into invisible geometry.
      const collapsedGroupIds = new Set<string>();
      for (const n of nodesRef.current) {
        const d = n.data as NodeData;
        if (d.nodeType === "group" && d.collapsed) collapsedGroupIds.add(n.id);
      }
      const isHiddenMember = (n: Node) => !!(n.parentId && collapsedGroupIds.has(n.parentId));
      let best: { id: string; dist: number } | null = null;
      for (const edge of edgesRef.current) {
        if (draggedNodeId && (edge.source === draggedNodeId || edge.target === draggedNodeId)) {
          continue;
        }
        const s = byId.get(edge.source);
        const t = byId.get(edge.target);
        if (!s || !t) continue;
        if (isHiddenMember(s) || isHiddenMember(t)) continue;
        const sp = absolutePosition(s, byId);
        const ss = nodeSize(s);
        const tp = absolutePosition(t, byId);
        const ts = nodeSize(t);
        const dist = pointToSegmentDist(
          point.x,
          point.y,
          sp.x + ss.w, // source handle: right-middle
          sp.y + ss.h / 2,
          tp.x, // target handle: left-middle
          tp.y + ts.h / 2
        );
        if (dist <= SPLICE_THRESHOLD && (!best || dist < best.dist)) {
          best = { id: edge.id, dist };
        }
      }
      return best?.id ?? null;
    },
    []
  );

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      const raw = event.dataTransfer.getData(DRAG_TYPE);
      if (!raw) return;
      try {
        const data = JSON.parse(raw) as NodeData;
        const position = screenToFlowPosition({ x: event.clientX, y: event.clientY });
        // Splice-on-drop: if the palette node lands over an edge and is
        // splice-eligible, insert it inline (A→N→B) instead of dropping loose.
        const center = { x: position.x + DEFAULT_NODE_W / 2, y: position.y + DEFAULT_NODE_H / 2 };
        const edgeId = isSpliceEligibleType(data.nodeType) ? findSpliceEdgeAt(center) : null;
        if (edgeId) {
          record();
          const newId = nextNodeId(nodesRef.current);
          setNodes((nds) => [
            ...nds.map((n) => (n.selected ? { ...n, selected: false } : n)),
            { id: newId, type: flowNodeTypeForData(data), position, data, selected: true },
          ]);
          const spliced = spliceNodeIntoEdge(edgesRef.current, newId, edgeId, makeEdge);
          if (spliced) {
            // Soft typed-port check for both new edges created by the splice.
            const added = spliced.filter((e) => !edgesRef.current.some((old) => old.id === e.id));
            for (const e of added) {
              maybeWarnKindMismatch(e.id, e.source, e.target);
            }
          }
          setEdges((eds) => spliceNodeIntoEdge(eds, newId, edgeId, makeEdge) ?? eds);
          setSelectedNodeId(newId);
          setSelectedEdgeId(null);
          return;
        }
        addNodeAtPosition(data, position);
      } catch {
        toast.error("Failed to add node");
      }
    },
    [
      screenToFlowPosition,
      addNodeAtPosition,
      findSpliceEdgeAt,
      record,
      setNodes,
      setEdges,
      makeEdge,
      setSelectedNodeId,
      setSelectedEdgeId,
      maybeWarnKindMismatch,
    ]
  );

  const setSpliceHighlight = useCallback((edgeId: string | null) => {
    if (spliceEdgeIdRef.current !== edgeId) {
      spliceEdgeIdRef.current = edgeId;
      setSpliceEdgeId(edgeId);
    }
  }, []);

  const handleNodeDragStart = useCallback(() => {
    record();
    setSpliceHighlight(null);
  }, [record, setSpliceHighlight]);

  const handleNodeDrag = useCallback(
    (_: MouseEvent | TouchEvent, node: Node) => {
      const data = node.data as NodeData;
      // Only a single, isolated, splice-eligible node participates: moving a
      // connected node (or a multi-selection) must never silently rewire.
      const selectedCount = nodesRef.current.filter((n) => n.selected).length;
      const connected = edgesRef.current.some(
        (e) => e.source === node.id || e.target === node.id
      );
      if (!isSpliceEligibleType(data.nodeType) || connected || selectedCount > 1) {
        setSpliceHighlight(null);
        return;
      }
      const byId = new Map(nodesRef.current.map((n) => [n.id, n]));
      const abs = node.parentId ? absolutePosition(node, byId) : node.position;
      const size = nodeSize(node);
      setSpliceHighlight(
        findSpliceEdgeAt({ x: abs.x + size.w / 2, y: abs.y + size.h / 2 }, node.id)
      );
    },
    [findSpliceEdgeAt, setSpliceHighlight]
  );

  const handleNodeDragStop = useCallback(
    (_: MouseEvent | TouchEvent, node: Node) => {
      const edgeId = spliceEdgeIdRef.current;
      setSpliceHighlight(null);
      // record() already fired on drag start — both the splice and the group
      // refit below fold into that undo step, so one ⌘Z reverts move + rewire +
      // refit together.
      if (edgeId) {
        const data = node.data as NodeData;
        const connected = edgesRef.current.some(
          (e) => e.source === node.id || e.target === node.id
        );
        if (isSpliceEligibleType(data.nodeType) && !connected) {
          const spliced = spliceNodeIntoEdge(edgesRef.current, node.id, edgeId, makeEdge);
          if (spliced) {
            const added = spliced.filter((e) => !edgesRef.current.some((old) => old.id === e.id));
            for (const e of added) {
              maybeWarnKindMismatch(e.id, e.source, e.target);
            }
          }
          setEdges((eds) => spliceNodeIntoEdge(eds, node.id, edgeId, makeEdge) ?? eds);
        }
      }
      // Task 1: a member drag grows/shrinks its frame to wrap the members while
      // their ABSOLUTE positions stay put (the frame moves, the content doesn't).
      if (node.parentId) {
        const parentId = node.parentId;
        setNodes((nds) => refitGroupNodes(nds, parentId));
      }
    },
    [setSpliceHighlight, setEdges, makeEdge, setNodes, maybeWarnKindMismatch]
  );

  const handleNodeDataChange = useCallback(
    (nodeId: string, data: NodeData) => {
      record(`data:${nodeId}`);
      setNodes((nds) => nds.map((node) => (node.id === nodeId ? { ...node, data } : node)));
    },
    [setNodes, record]
  );

  const handleEdgeChange = useCallback(
    (edgeId: string, updates: { route?: string; label?: string }) => {
      record(`edge:${edgeId}`);
      setEdges((eds) =>
        eds.map((edge) =>
          edge.id === edgeId
            ? {
                ...edge,
                label: updates.label ?? updates.route ?? edge.label,
                data: { ...(edge.data as object), route: updates.route },
              }
            : edge
        )
      );
    },
    [setEdges, record]
  );

  const handleDeleteEdge = useCallback(
    (edgeId: string) => {
      record();
      setEdges((eds) => eds.filter((e) => e.id !== edgeId));
      setSelectedEdgeId(null);
    },
    [setEdges, record, setSelectedEdgeId]
  );

  const handleVersionSelect = useCallback(
    (version: WorkflowVersion) => {
      if (isCanvasReadOnly) return;
      const graph = version.graph_json as WorkflowGraph;
      setNodes(graphToNodes(graph));
      setEdges(graphToEdges(graph));
      setCurrentVersionId(version.id);
      setCurrentVersionNumber(version.version_number);
      setHistoricalVersionNumber(
        version.id !== savedVersionIdRef.current ? version.version_number : null
      );
      setSelectedNodeId(null);
      setSelectedEdgeId(null);
      history.clear();
      toast.info(`Loaded version ${version.version_number}`);
      setTimeout(() => fitView({ padding: 0.2, maxZoom: 1.2, duration: viewportAnimMs }), 50);
    },
    [
      isCanvasReadOnly,
      setNodes,
      setEdges,
      fitView,
      viewportAnimMs,
      history,
      setSelectedNodeId,
      setSelectedEdgeId,
    ]
  );

  const handleExport = useCallback(() => {
    const graph = toGraph(nodes, edges);
    const payload = {
      format: "aegis-workflow-v1",
      workflow_id: workflowId,
      name: displayName,
      version_number: currentVersionNumber,
      graph_json: graph,
      exported_at: new Date().toISOString(),
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    const safeName = displayName.replace(/[^\w-]+/g, "-").replace(/^-|-$/g, "") || "workflow";
    anchor.href = url;
    anchor.download = `${safeName}-${workflowId.slice(0, 8)}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
    toast.success("Workflow exported");
  }, [nodes, edges, workflowId, displayName, currentVersionNumber]);

  const handleImportClick = useCallback(() => {
    if (isCanvasReadOnly) return;
    if (isDirty) {
      setImportConfirmOpen(true);
      return;
    }
    importInputRef.current?.click();
  }, [isCanvasReadOnly, isDirty]);

  const handleImportFile = useCallback(
    async (event: React.ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0];
      event.target.value = "";
      if (isCanvasReadOnly) return;
      if (!file) return;

      try {
        const payload = await readWorkflowExportFile(file);
        const graph = payload.graph_json;
        setNodes(graphToNodes(graph));
        setEdges(graphToEdges(graph));
        setSelectedNodeId(null);
        setSelectedEdgeId(null);
        setCurrentVersionId(undefined);
        setCurrentVersionNumber(null);
        setHistoricalVersionNumber(null);
        savedVersionIdRef.current = undefined;
        history.clear();
        lastSavedGraphRef.current = "";
        toast.success(
          payload.name
            ? `Imported "${payload.name}" — save to persist`
            : "Workflow imported — save to persist"
        );
        setTimeout(() => fitView({ padding: 0.2, maxZoom: 1.2, duration: viewportAnimMs }), 50);
      } catch (error) {
        const message =
          error instanceof WorkflowImportError
            ? error.message
            : error instanceof Error
              ? error.message
              : "Import failed";
        toast.error(message);
      }
    },
    [
      isCanvasReadOnly,
      setNodes,
      setEdges,
      fitView,
      viewportAnimMs,
      history,
      setSelectedNodeId,
      setSelectedEdgeId,
    ]
  );

  const clearSelection = useCallback(() => {
    setNodes((nds) => nds.map((n) => (n.selected ? { ...n, selected: false } : n)));
    setEdges((eds) => eds.map((e) => (e.selected ? { ...e, selected: false } : e)));
    setSelectedNodeId(null);
    setSelectedEdgeId(null);
    setShowResults(false);
    setRightTab("configure");
  }, [setNodes, setEdges, setSelectedNodeId, setSelectedEdgeId]);

  const handleSelectionChange = useCallback(
    ({ nodes: selNodes, edges: selEdges }: { nodes: Node[]; edges: Edge[] }) => {
      setSelectedNodeIds(selNodes.map((n) => n.id));
      setSelectedEdgeIds(selEdges.map((e) => e.id));
      if (canvasMode === "run" && selNodes[0]) setRunLensNodeId(selNodes[0].id);
      if ((selNodes[0] || selEdges[0]) && !isCanvasReadOnly) setRightTab("configure");
    },
    [canvasMode, isCanvasReadOnly]
  );

  /** Push a successful save into the workflow query cache so navigating away
   *  and back reseeds the canvas from the just-saved version, not a stale one. */
  const syncWorkflowCache = useCallback(
    (version: WorkflowVersion) => {
      queryClient.setQueryData<Workflow>(queryKeys.workflow(workflowId), (prev) => {
        if (!prev) {
          return {
            id: workflowId,
            name: displayName,
            created_at: version.created_at,
            updated_at: version.created_at,
            latest_version: version,
          };
        }
        return {
          ...prev,
          updated_at: version.created_at,
          latest_version: version,
        };
      });
      void queryClient.invalidateQueries({ queryKey: queryKeys.workflowVersions(workflowId) });
    },
    [queryClient, workflowId, displayName]
  );

  const handleSave = useCallback(
    async (saveAsNewVersion = false) => {
      // Cmd+S does not blur the active field — flush DraftTextarea drafts into
      // node data before serializing so set-fields / kb / regex edits aren't lost.
      flushSync(() => {
        flushDraftTextareas();
      });
      const nodesNow = nodesRef.current;
      const edgesNow = edgesRef.current;
      const issues = getWorkflowValidationIssues(nodesNow);
      if (issues.length > 0) {
        toast.error(formatValidationToast(issues));
        return;
      }
      setIsSaving(true);
      try {
        const graph = toGraph(nodesNow, edgesNow);
        const version = await api.saveVersion(workflowId, {
          graph_json: graph,
          save_as_new_version: saveAsNewVersion,
        });
        setCurrentVersionId(version.id);
        setCurrentVersionNumber(version.version_number);
        savedVersionIdRef.current = version.id;
        setHistoricalVersionNumber(null);
        lastSavedGraphRef.current = graphSignature(nodesNow, edgesNow);
        syncWorkflowCache(version);
        toast.success(saveAsNewVersion ? "Saved as new version" : "Workflow saved");
      } catch (error) {
        toast.error(error instanceof Error ? error.message : "Failed to save workflow");
      } finally {
        setIsSaving(false);
      }
    },
    [workflowId, syncWorkflowCache]
  );

  useEffect(() => {
    const onBeforeUnload = (e: BeforeUnloadEvent) => {
      if (!isDirty) return;
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => window.removeEventListener("beforeunload", onBeforeUnload);
  }, [isDirty]);

  useEffect(() => {
    // Set true in the effect body (not just at useRef init): React 18 StrictMode
    // double-invokes effects on mount as setup → cleanup → setup, and the cleanup
    // flips this to false. Without re-setting it here, mountedRef stays false while
    // the component is very much mounted, so every handleRun bails at the
    // `if (!mountedRef.current) return` guard and a run hangs on "Starting".
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      runSourceRef.current?.close();
      runSourceRef.current = null;
      if (runRecoveryTimerRef.current != null) {
        window.clearTimeout(runRecoveryTimerRef.current);
        runRecoveryTimerRef.current = null;
      }
    };
  }, []);

  const handleRun = useCallback(async (
    input: string,
    opts?: { startNodeId?: string; pinnedOutputs?: Record<string, string> }
  ) => {
    if (isRunLocked || runStartPendingRef.current) return;

    // Flush in-progress DraftTextarea drafts before validating / autosaving so
    // run-from-compose doesn't persist a graph missing uncommitted inspector edits.
    flushSync(() => {
      flushDraftTextareas();
    });
    const nodesNow = nodesRef.current;
    const edgesNow = edgesRef.current;

    // Validate + input checks BEFORE any autosave or UI reset so we don't
    // persist a broken graph or clear results only to bail immediately.
    const issues = getWorkflowValidationIssues(nodesNow);
    if (issues.length > 0) {
      toast.error(formatValidationToast(issues));
      return;
    }
    if (!input.trim()) {
      toast.error("Enter input text before running");
      return;
    }

    // Clear a previous terminal id before any await. Until createRun returns,
    // there is nothing safe to cancel, so the controls show a disabled
    // starting state rather than accidentally targeting the prior run.
    runStartPendingRef.current = true;
    currentRunIdRef.current = null;
    setIsRunStarting(true);

    // A run is its own working mode: preserve the editable graph while
    // shifting telemetry, output, and controls into the lower run lens. The
    // sidebar is hidden by the run-lens gate, so we leave sidebarOpen alone —
    // it restores to the user's choice when they return to compose.
    setCanvasMode("run");
    setAssistOpen(false);
    if (runRecoveryTimerRef.current != null) {
      window.clearTimeout(runRecoveryTimerRef.current);
      runRecoveryTimerRef.current = null;
    }
    setIsRunning(true);
    setLiveEvents([]);
    truncatedNodesRef.current = new Set();
    setObservedStartNodeIds([]);
    setQuickAdd(null);
    setContextMenu(null);
    setRenamingNodeId(null);
    setDeleteConfirm(null);
    setImportConfirmOpen(false);
    setRun(null);
    setReplayOpen(false);
    setActiveNodeId(null);
    setRunLensNodeId(null);
    setNodeRunResults({});
    setOutputPeek(null);
    setRunStartedAt(Date.now());
    setRightTab("results");
    setShowResults(false);

    try {
      const graph = toGraph(nodesNow, edgesNow);
      const graphKey = graphSignature(nodesNow, edgesNow);
      let versionId = currentVersionId;

      if (graphKey !== lastSavedGraphRef.current) {
        setIsSaving(true);
        try {
          const version = await api.saveVersion(workflowId, {
            graph_json: graph,
            save_as_new_version: false,
          });
          versionId = version.id;
          setCurrentVersionId(version.id);
          setCurrentVersionNumber(version.version_number);
          savedVersionIdRef.current = version.id;
          setHistoricalVersionNumber(null);
          lastSavedGraphRef.current = graphKey;
          syncWorkflowCache(version);
        } finally {
          setIsSaving(false);
        }
      }
      if (!mountedRef.current) return; // unmounted mid-save

      if (!versionId) {
        throw new Error("Save the workflow before running");
      }

      const createdRun = await api.createRun({
        workflow_id: workflowId,
        version_id: versionId,
        input_text: input.trim(),
        start_node_id: opts?.startNodeId,
        pinned_outputs: opts?.pinnedOutputs,
      });
      if (!mountedRef.current) {
        runStartPendingRef.current = false;
        return; // unmounted while createRun was in flight
      }
      setRun(createdRun);
      currentRunIdRef.current = createdRun.id;
      runStartPendingRef.current = false;
      setIsRunStarting(false);
      toast.info("Workflow started");

      runSourceRef.current?.close();
      runSourceRef.current = null;
      let streamClosed = false;
      // Track the last node that started so run_failed (which carries no
      // node_id) can attribute the failure to the node that was executing.
      let lastActiveNodeId: string | null = null;
      const streamedNodeResults: WorkflowRun["node_results"] = [];
      let recoveryNoticeShown = false;

      // The stream transport makes a few reconnect attempts itself. If that
      // budget is exhausted, reconcile the authoritative run record until it
      // reaches a terminal or approval state instead of stranding the canvas
      // in an unknowable pending state.
      const reconcileRunAfterStreamFailure = async (): Promise<void> => {
        if (!mountedRef.current || currentRunIdRef.current !== createdRun.id) return;

        try {
          const latestRun = await api.getRun(createdRun.id);
          if (!mountedRef.current || currentRunIdRef.current !== createdRun.id) return;

          setRun(latestRun);
          const recoveredNodeResults = latestRun.node_results ?? [];
          if (recoveredNodeResults.length) {
            setNodeRunResults((previous) => ({
              ...previous,
              ...Object.fromEntries(
                recoveredNodeResults.map((result) => [
                  result.node_id,
                  {
                    output: result.output ?? null,
                    latencyMs: result.latency_ms ?? null,
                    guardrailStatus: result.guardrail_status ?? null,
                    status: result.status,
                  },
                ])
              ),
            }));
          }

          if (isTerminalRunStatus(latestRun.status)) {
            setIsRunning(false);
            setActiveNodeId(null);
            currentRunIdRef.current = null;
            runRecoveryTimerRef.current = null;
            return;
          }
          if (latestRun.status === "awaiting_approval") {
            setIsRunning(false);
            setActiveNodeId(null);
            setRightTab("results");
            runRecoveryTimerRef.current = null;
            return;
          }

          // Keep the monitor live/locked while polling a still-active backend
          // run, even though its event transport is temporarily unavailable.
          setIsRunning(true);
        } catch {
          if (!recoveryNoticeShown) {
            recoveryNoticeShown = true;
            toast.warning("Live updates disconnected — checking run status…");
          }
        }

        if (!mountedRef.current || currentRunIdRef.current !== createdRun.id) return;
        runRecoveryTimerRef.current = window.setTimeout(() => {
          void reconcileRunAfterStreamFailure();
        }, 3_000);
      };

      const stream = api.streamRun(
        createdRun.id,
        (event) => {
        setLiveEvents((prev) => [
          ...prev.slice(-49),
          { ...event, received_at: new Date().toISOString() },
        ]);

        if (event.type === "node_started") {
          const startedNodeId = String(event.node_id);
          lastActiveNodeId = startedNodeId;
          setObservedStartNodeIds((previous) =>
            previous.includes(startedNodeId) ? previous : [...previous, startedNodeId]
          );
          setIsRunning(true);
          setActiveNodeId(startedNodeId);
          setRunLensNodeId(startedNodeId);
          setCanvasAnnouncement(
            `Node ${String(event.node_label || event.node_id)} started`
          );
        }
        if (event.type === "node_completed") {
          setActiveNodeId(null);
          // Backend contract: node_completed carries a status field
          // ("completed" | "failed"); default to "completed" for older streams.
          const nodeStatus = (event.status as string | undefined) ?? "completed";
          setCanvasAnnouncement(
            `Node ${String(event.node_label || event.node_id)} ${nodeStatus}`
          );
          setNodeRunResults((prev) => ({
            ...prev,
            [String(event.node_id)]: {
              output: (event.output as string | null | undefined) ?? null,
              latencyMs: (event.latency_ms as number | null) ?? null,
              guardrailStatus: (event.guardrail_status as string | null) ?? null,
              status: nodeStatus,
            },
          }));
          streamedNodeResults.push({
            id: String(event.node_id),
            node_id: String(event.node_id),
            node_type: "unknown",
            node_label: String(event.node_label || event.node_id),
            status: nodeStatus,
            output: (event.output as string | null | undefined) ?? null,
            evaluation_scores: (event.evaluation_scores as Record<string, unknown> | null) ?? null,
            guardrail_status: (event.guardrail_status as string | null) ?? null,
            latency_ms: (event.latency_ms as number | null) ?? null,
          });
        }
        if (event.type === "iteration_truncated") {
          // Task 4: one warning toast per node per run (max_items capped the
          // loop). liveEvents already carries the raw event to the trace log.
          const nodeId = String(event.node_id);
          if (!truncatedNodesRef.current.has(nodeId)) {
            truncatedNodesRef.current.add(nodeId);
            const label = String(
              (nodesRef.current.find((n) => n.id === nodeId)?.data as NodeData | undefined)?.label ||
                event.node_label ||
                nodeId
            );
            const processed = Number(event.processed ?? 0);
            const total = Number(event.total ?? 0);
            toast.warning(`Iteration truncated: processed ${processed} of ${total} items`, {
              description: label,
            });
          }
        }
        if (event.type === "run_completed") {
          setCanvasAnnouncement("Workflow run completed");
          toast.success("Workflow completed");
          setRun({
            ...createdRun,
            status: "completed",
            final_output: (event.final_output as string | null) ?? createdRun.final_output,
            metrics_json: (event.metrics as Record<string, unknown> | null) ?? createdRun.metrics_json,
            node_results:
              (event.node_results as WorkflowRun["node_results"]) ?? streamedNodeResults,
          });
        }
        if (event.type === "run_failed") {
          const errorMessage = String(event.error || "Workflow failed");
          setCanvasAnnouncement(`Workflow run failed: ${errorMessage}`);
          toast.error(errorMessage);
          // Backend emits failed_node_id / guardrail_node_id / eval_node_id /
          // approval_node_id depending on the failure path — accept all variants.
          const failedNodeId =
            (event.failed_node_id != null
              ? String(event.failed_node_id)
              : event.guardrail_node_id != null
                ? String(event.guardrail_node_id)
                : event.eval_node_id != null
                  ? String(event.eval_node_id)
                  : event.approval_node_id != null
                    ? String(event.approval_node_id)
                    : event.node_id != null
                      ? String(event.node_id)
                      : null) ?? lastActiveNodeId;
          if (failedNodeId) {
            setNodeRunResults((prev) => ({
              ...prev,
              [failedNodeId]: {
                output: prev[failedNodeId]?.output ?? errorMessage,
                latencyMs: prev[failedNodeId]?.latencyMs ?? null,
                guardrailStatus: prev[failedNodeId]?.guardrailStatus ?? null,
                status: "failed",
              },
            }));
          }
          setRun({
            ...createdRun,
            status: "failed",
            final_output: errorMessage,
            node_results: streamedNodeResults,
          });
        }
        if (event.type === "run_cancelled") {
          setCanvasAnnouncement("Workflow run cancelled");
          toast.warning("Workflow cancelled");
          setRun({ ...createdRun, status: "cancelled", node_results: streamedNodeResults });
        }
        if (event.type === "approval_required") {
          setCanvasAnnouncement("Human approval required");
          toast.message("Approval required — see Results panel");
          setRun((prev) => {
            const base = prev ?? createdRun;
            return {
              ...base,
              status: "awaiting_approval",
              metrics_json: {
                ...(base.metrics_json || {}),
                pending_approval: {
                  node_id: String(event.node_id || ""),
                  review: String(event.review || ""),
                },
              },
            };
          });
          setIsRunning(false);
          setActiveNodeId(null);
          setRightTab("results");
        }
        if (
          event.type === "run_completed" ||
          event.type === "run_failed" ||
          event.type === "run_cancelled"
        ) {
          setIsRunning(false);
          setActiveNodeId(null);
          currentRunIdRef.current = null;
          if (runRecoveryTimerRef.current != null) {
            window.clearTimeout(runRecoveryTimerRef.current);
            runRecoveryTimerRef.current = null;
          }
          streamClosed = true;
          stream.close();
          runSourceRef.current = null;
        }
        // `stream_end` normally follows a terminal event. If it arrives on
        // its own (for example after an upstream reconnect), reconcile the
        // durable run instead of treating the transport close as a finished
        // workflow and leaving the graph locked on stale local state.
        if (event.type === "stream_end") {
          streamClosed = true;
          stream.close();
          runSourceRef.current = null;
          void reconcileRunAfterStreamFailure();
        }
      },
        () => {
          streamClosed = true;
          runSourceRef.current?.close();
          runSourceRef.current = null;
          void reconcileRunAfterStreamFailure();
        }
      );
      // Only retain the stream handle if it hasn't already terminated
      // synchronously (a fast terminal event fires before this assignment).
      if (!streamClosed && mountedRef.current) {
        runSourceRef.current = stream;
      } else {
        stream.close();
      }
    } catch (error) {
      runStartPendingRef.current = false;
      setIsRunStarting(false);
      toast.error(error instanceof Error ? error.message : "Failed to start workflow");
      setIsRunning(false);
      runSourceRef.current?.close();
      runSourceRef.current = null;
      // If the run never got created (validation, save, or a 429 concurrency
      // rejection thrown by createRun), leave the run lens — an empty
      // "Starting" run must not linger on the canvas. A failure AFTER createRun
      // (e.g. stream setup) keeps run mode so the created run is still shown and
      // reconciled by the recovery path.
      if (!currentRunIdRef.current) {
        setRun(null);
        setActiveNodeId(null);
        setRunLensNodeId(null);
        setCanvasMode("compose");
      }
    }
  }, [workflowId, currentVersionId, isRunLocked, syncWorkflowCache]);

  const handleStop = useCallback(async () => {
    if (isRunStarting) {
      toast.info("The run is still starting — try again in a moment.");
      return;
    }
    const runId = currentRunIdRef.current;
    if (!runId) return;
    let stopped = false;
    try {
      await api.cancelRun(runId);
      toast.warning("Stopping workflow…");
      setRun((prev) => (prev ? { ...prev, status: "cancelled" } : prev));
      currentRunIdRef.current = null;
      stopped = true;
    } catch (error) {
      // A run may have finished between the click and cancellation request.
      // Reconcile it before abandoning the active stream or recovery poll.
      try {
        const latestRun = await api.getRun(runId);
        setRun(latestRun);
        if (isTerminalRunStatus(latestRun.status)) {
          toast.info(`Run already ${latestRun.status}`);
          currentRunIdRef.current = null;
          stopped = true;
        } else {
          toast.error(error instanceof Error ? error.message : "Failed to cancel run");
        }
      } catch {
        toast.error(error instanceof Error ? error.message : "Failed to cancel run");
      }
    }

    if (stopped) {
      if (runRecoveryTimerRef.current != null) {
        window.clearTimeout(runRecoveryTimerRef.current);
        runRecoveryTimerRef.current = null;
      }
      runSourceRef.current?.close();
      runSourceRef.current = null;
      setIsRunning(false);
      setActiveNodeId(null);
    }
  }, [isRunStarting]);

  const handleTidyLayout = useCallback(() => {
    if (nodes.length === 0) return;
    // Auto-layout is group-unaware (v1): it would scatter members out of their
    // frames. Disable it while any group exists rather than corrupt the layout.
    if (nodes.some((n) => (n.data as NodeData).nodeType === "group")) {
      toast.info("Tidy is unavailable while groups exist");
      return;
    }
    record();
    // Layer nodes left-to-right by graph depth (BFS from entry nodes).
    const adj = new Map<string, string[]>();
    const incoming = new Map<string, number>();
    for (const node of nodes) incoming.set(node.id, 0);
    for (const edge of edges) {
      adj.set(edge.source, [...(adj.get(edge.source) || []), edge.target]);
      incoming.set(edge.target, (incoming.get(edge.target) || 0) + 1);
    }
    const depth = new Map<string, number>();
    const queue = nodes.filter((n) => (incoming.get(n.id) || 0) === 0).map((n) => n.id);
    for (const id of queue) depth.set(id, 0);
    while (queue.length) {
      const id = queue.shift() as string;
      const d = (depth.get(id) || 0) + 1;
      if (d > nodes.length) continue; // cycle guard
      for (const next of adj.get(id) || []) {
        if ((depth.get(next) ?? -1) < d) {
          depth.set(next, d);
          queue.push(next);
        }
      }
    }
    const layers = new Map<number, string[]>();
    for (const node of nodes) {
      const d = depth.get(node.id) ?? 0;
      layers.set(d, [...(layers.get(d) || []), node.id]);
    }
    const maxRows = Math.max(...Array.from(layers.values()).map((ids) => ids.length));
    const positions = new Map<string, { x: number; y: number }>();
    layers.forEach((ids, d) => {
      const offset = ((maxRows - ids.length) * 140) / 2; // center shorter columns
      ids.forEach((id, i) => {
        positions.set(id, { x: 60 + d * 280, y: 60 + offset + i * 140 });
      });
    });
    setNodes((nds) =>
      nds.map((n) => {
        const pos = positions.get(n.id);
        return pos ? { ...n, position: pos } : n;
      })
    );
    setTimeout(() => fitView({ padding: 0.2, maxZoom: 1.2, duration: viewportAnimMs }), 50);
  }, [nodes, edges, setNodes, fitView, viewportAnimMs, record]);

  // MVP2 — pin output / run-from-here (authoring-only debugging).
  const handlePinOutput = useCallback((nodeId: string, output: string) => {
    setPinnedOutputs((prev) => {
      const next = { ...prev };
      if (nodeId in next) delete next[nodeId];
      else next[nodeId] = output;
      return next;
    });
  }, []);

  // Data loop — set/replace a node's pinned output (editable mock data). Unlike
  // handlePinOutput's toggle, this always writes so "Update pin" is idempotent.
  const handleUpdatePinnedOutput = useCallback((nodeId: string, output: string) => {
    setPinnedOutputs((prev) => ({ ...prev, [nodeId]: output }));
  }, []);

  const handleRunFromHere = useCallback(
    (nodeId: string) => {
      void handleRun(runInput.composed, { startNodeId: nodeId, pinnedOutputs });
    },
    [handleRun, runInput.composed, pinnedOutputs]
  );

  // MVP2 — Assist rail: apply a proposed graph (with undo) / preview diff rings.
  const handleAssistApply = useCallback(
    (proposed: WorkflowGraph) => {
      record();
      setNodes(graphToNodes(proposed));
      setEdges(graphToEdges(proposed));
      setDiffHighlights(null);
      setTimeout(() => fitView({ padding: 0.2, maxZoom: 1.2, duration: viewportAnimMs }), 50);
    },
    [record, setNodes, setEdges, fitView, viewportAnimMs]
  );

  const handleAssistPreview = useCallback((diff: GraphDiff | null) => {
    if (!diff) {
      setDiffHighlights(null);
      return;
    }
    const map: Record<string, DiffKind> = {};
    diff.added_node_ids.forEach((id) => (map[id] = "added"));
    diff.removed_node_ids.forEach((id) => (map[id] = "removed"));
    diff.changed_node_ids.forEach((id) => (map[id] = "changed"));
    setDiffHighlights(map);
  }, []);

  // MVP2 — command-palette "Add node" drops a node from its registry type.
  const handleAddNodeFromType = useCallback(
    (nodeType: string) => {
      const def = getNodeDefinition(nodeType);
      if (!def) return;
      handleAddNode(structuredClone(def.defaultData));
    },
    [handleAddNode]
  );

  // MVP2 — canvas actions dispatched by the command palette (window events).
  useEffect(() => {
    const onAddNode = (e: Event) => {
      if (isCanvasReadOnly) return;
      const nodeType = (e as CustomEvent<{ nodeType?: string }>).detail?.nodeType;
      if (nodeType) handleAddNodeFromType(nodeType);
    };
    const onRun = () => {
      if (!isRunLocked && nodes.length > 0) void handleRun(runInput.composed);
    };
    const onTidy = () => {
      if (!isCanvasReadOnly) handleTidyLayout();
    };
    const onFit = () =>
      fitView({ padding: isRunLens ? 0.14 : 0.2, maxZoom: 1.2, duration: viewportAnimMs });
    const onAssist = () => {
      if (!isCanvasReadOnly) setAssistOpen(true);
    };
    window.addEventListener(ADD_NODE_EVENT, onAddNode as EventListener);
    window.addEventListener(RUN_WORKFLOW_EVENT, onRun);
    window.addEventListener(TIDY_CANVAS_EVENT, onTidy);
    window.addEventListener(FIT_VIEW_EVENT, onFit);
    window.addEventListener(OPEN_ASSIST_EVENT, onAssist);
    return () => {
      window.removeEventListener(ADD_NODE_EVENT, onAddNode as EventListener);
      window.removeEventListener(RUN_WORKFLOW_EVENT, onRun);
      window.removeEventListener(TIDY_CANVAS_EVENT, onTidy);
      window.removeEventListener(FIT_VIEW_EVENT, onFit);
      window.removeEventListener(OPEN_ASSIST_EVENT, onAssist);
    };
  }, [
    handleAddNodeFromType,
    handleRun,
    handleTidyLayout,
    fitView,
    viewportAnimMs,
    isRunLocked,
    nodes.length,
    runInput.composed,
    isRunLens,
    isCanvasReadOnly,
  ]);

  const executeDelete = useCallback(
    (nodeIds: string[], edgeIds: string[]) => {
      if (isCanvasReadOnly) {
        setDeleteConfirm(null);
        return;
      }
      const groupIds = nodeIds.filter(
        (id) =>
          (nodesRef.current.find((n) => n.id === id)?.data as NodeData | undefined)
            ?.nodeType === "group"
      );
      if (groupIds.length === 0) {
        record();
        deleteElements({
          nodes: nodeIds.map((id) => ({ id })),
          edges: edgeIds.map((id) => ({ id })),
        });
        setSelectedNodeId(null);
        setSelectedEdgeId(null);
        return;
      }
      // Deleting a group frame UNGROUPS its members (they survive) rather than
      // letting React Flow's parent-cascade remove them. Do the whole mutation
      // locally so kept children lose their parent before anything is removed.
      record();
      const delNodeSet = new Set(nodeIds);
      const groupSet = new Set(groupIds);
      const posById = new Map(nodesRef.current.map((n) => [n.id, n.position]));
      setNodes((nds) =>
        nds
          .filter((n) => !delNodeSet.has(n.id))
          .map((n) => {
            if (n.parentId && groupSet.has(n.parentId)) {
              const gp = posById.get(n.parentId)!;
              return {
                ...n,
                parentId: undefined,
                position: { x: n.position.x + gp.x, y: n.position.y + gp.y },
              };
            }
            return n;
          })
      );
      const delEdgeSet = new Set(edgeIds);
      setEdges((eds) =>
        eds.filter(
          (e) =>
            !delEdgeSet.has(e.id) &&
            !delNodeSet.has(e.source) &&
            !delNodeSet.has(e.target)
        )
      );
      setSelectedNodeId(null);
      setSelectedEdgeId(null);
    },
    [
      isCanvasReadOnly,
      deleteElements,
      record,
      setNodes,
      setEdges,
      setSelectedNodeId,
      setSelectedEdgeId,
    ]
  );

  const handleDeleteSelection = useCallback(() => {
    if (isCanvasReadOnly) return;
    let nodeIds = nodes.filter((n) => n.selected).map((n) => n.id);
    let edgeIds = edges.filter((e) => e.selected).map((e) => e.id);

    if (nodeIds.length === 0 && edgeIds.length === 0) {
      if (selectedNodeIds.length > 0 || selectedEdgeIds.length > 0) {
        nodeIds = selectedNodeIds;
        edgeIds = selectedEdgeIds;
      } else return;
    }

    if (nodeIds.length >= 1 || edgeIds.length >= 2) {
      setDeleteConfirm({ nodeIds, edgeIds });
      return;
    }
    executeDelete(nodeIds, edgeIds);
  }, [isCanvasReadOnly, nodes, edges, selectedNodeIds, selectedEdgeIds, executeDelete]);

  /** Node-toolbar delete: confirm a single node by id. */
  const requestDeleteNode = useCallback(
    (nodeId: string) => {
      if (!isCanvasReadOnly) setDeleteConfirm({ nodeIds: [nodeId], edgeIds: [] });
    },
    [isCanvasReadOnly]
  );

  const handleCopy = useCallback(() => {
    const selected = nodesRef.current.filter((n) => n.selected || selectedNodeIds.includes(n.id));
    if (selected.length === 0) return;
    const count = copyToClipboard(selected, edgesRef.current);
    toast.success(`Copied ${count} node${count === 1 ? "" : "s"}`);
  }, [selectedNodeIds]);

  const handlePaste = useCallback(
    (anchorFlow?: { x: number; y: number }) => {
      if (!hasClipboard()) return;
      let anchor = anchorFlow;
      if (!anchor) {
        const rect = reactFlowWrapper.current?.getBoundingClientRect();
        const screen =
          lastPointerRef.current ??
          (rect
            ? { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 }
            : { x: window.innerWidth / 2, y: window.innerHeight / 2 });
        anchor = screenToFlowPosition(screen);
      }
      const fragment = materializeClipboard(nodesRef.current, anchor);
      if (!fragment) return;
      record();
      setNodes((nds) => [
        ...nds.map((n) => (n.selected ? { ...n, selected: false } : n)),
        ...fragment.nodes,
      ]);
      setEdges((eds) => [
        ...eds.map((e) => (e.selected ? { ...e, selected: false } : e)),
        ...fragment.edges,
      ]);
    },
    [screenToFlowPosition, record, setNodes, setEdges]
  );

  const handleSelectAll = useCallback(() => {
    setNodes((nds) => nds.map((n) => (n.selected ? n : { ...n, selected: true })));
  }, [setNodes]);

  /** Center a node and select it (validation-issue click-through). */
  const focusNode = useCallback(
    (nodeId: string) => {
      const node = nodesRef.current.find((n) => n.id === nodeId);
      if (!node) return;
      setNodes((nds) => nds.map((n) => ({ ...n, selected: n.id === nodeId })));
      setEdges((eds) => eds.map((e) => (e.selected ? { ...e, selected: false } : e)));
      const byId = new Map(nodesRef.current.map((n) => [n.id, n]));
      const abs = absolutePosition(node, byId);
      void setCenter(abs.x + 100, abs.y + 48, {
        zoom: 1,
        duration: viewportAnimMs,
      });
    },
    [setNodes, setEdges, setCenter, viewportAnimMs]
  );

  // Feature: find-on-canvas — the command palette dispatches a node id to focus.
  useEffect(() => {
    const onFocusNode = (e: Event) => {
      const nodeId = (e as CustomEvent<{ nodeId?: string }>).detail?.nodeId;
      if (nodeId) focusNode(nodeId);
    };
    window.addEventListener(FOCUS_NODE_EVENT, onFocusNode as EventListener);
    return () => window.removeEventListener(FOCUS_NODE_EVENT, onFocusNode as EventListener);
  }, [focusNode]);

  const openContextMenu = useCallback(
    (
      kind: "node" | "edge" | "pane" | "selection",
      event: React.MouseEvent | MouseEvent,
      id?: string
    ) => {
      event.preventDefault();
      const screen = { x: event.clientX, y: event.clientY };
      setContextMenu({ kind, id, screen, flow: screenToFlowPosition(screen) });
    },
    [screenToFlowPosition]
  );

  const onReconnect = useCallback(
    (oldEdge: Edge, connection: Connection) => {
      if (!connection.source || !connection.target) return;

      // Authoritative edge from live state — displayEdges may hand a re-pointed
      // clone when groups are collapsed; mutate by id against the real edge.
      const liveEdge = edgesRef.current.find((e) => e.id === oldEdge.id) ?? oldEdge;

      // Mirror onConnect: collapsed group frames expose display handles only.
      // Wiring a real edge endpoint to a frame id corrupts the graph on save.
      const endpointIsGroup = (nodeId: string) =>
        (nodesRef.current.find((n) => n.id === nodeId)?.data as NodeData | undefined)
          ?.nodeType === "group";
      if (endpointIsGroup(connection.source) || endpointIsGroup(connection.target)) {
        toast.message("Expand the group to connect nodes");
        return;
      }

      // Dropping the edge back on the same handles is a no-op — skip recording.
      if (
        connection.source === liveEdge.source &&
        connection.target === liveEdge.target &&
        (connection.sourceHandle ?? null) === (liveEdge.sourceHandle ?? null) &&
        (connection.targetHandle ?? null) === (liveEdge.targetHandle ?? null)
      ) {
        return;
      }
      record();
      // Feature 2: error-route-ness follows the source handle. Reconnecting an
      // error edge's start onto a normal handle drops "error" (recomputed as a
      // plain/branch edge); reconnecting any edge onto an error handle adopts it,
      // unless the node already owns an error route.
      const wasError = (liveEdge.data as { route?: string } | undefined)?.route === "error";
      let nowError = connection.sourceHandle === "error";
      if (nowError) {
        const conflict = edgesRef.current.some(
          (e) =>
            e.id !== liveEdge.id &&
            e.source === connection.source &&
            (e.data as { route?: string } | undefined)?.route === "error"
        );
        if (conflict) {
          toast.error("One error route per node");
          nowError = false;
        }
      }
      setEdges((eds) => {
        const next = reconnectEdge(liveEdge, connection, eds, { shouldReplaceId: false });
        if (nowError) {
          return next.map((e) =>
            e.id === liveEdge.id
              ? { ...e, sourceHandle: "error", label: undefined, data: { route: "error" } }
              : e
          );
        }
        // Normal edge: never keep an "error" handle/route. Recompute the branch
        // route when the source changed or the edge just shed its error route.
        const sourceChanged = connection.source !== liveEdge.source;
        const recompute = wasError || sourceChanged;
        let route: string | undefined;
        if (recompute) {
          const sourceData = nodesRef.current.find((n) => n.id === connection.source)
            ?.data as NodeData | undefined;
          const branchKeys =
            sourceData?.nodeType === "router"
              ? sourceData.routes
              : sourceData?.nodeType === "classifier"
                ? sourceData.categories
                : sourceData?.nodeType === "if"
                  ? ["true", "false"]
                  : sourceData?.nodeType === "switch"
                    ? [...(sourceData.switchCases || []), sourceData.switchDefault || "default"]
                    : sourceData?.nodeType === "guardrail" &&
                        sourceData.rules?.fail_behavior === "route"
                      ? [
                          sourceData.rules.pass_route || "pass",
                          sourceData.rules.failure_route || "failed",
                        ]
                      : undefined;
          const used = next
            .filter((e) => e.source === connection.source && e.id !== liveEdge.id)
            .map((e) => (e.data as { route?: string })?.route)
            .filter(Boolean);
          route = branchKeys?.length
            ? (branchKeys.find((r) => !used.includes(r)) ?? branchKeys[0])
            : undefined;
        }
        return next.map((e) => {
          if (e.id !== liveEdge.id) return e;
          const cleanedHandle = e.sourceHandle === "error" ? null : e.sourceHandle;
          // Only persist `route` — never write display-only edge data (active,
          // failed, sourceNodeType, …) into the saved graph.
          const persistedData = route ? { route } : undefined;
          if (!recompute) {
            const existingRoute = (e.data as { route?: string } | undefined)?.route;
            return {
              ...e,
              sourceHandle: cleanedHandle,
              data: existingRoute ? { route: existingRoute } : undefined,
            };
          }
          return {
            ...e,
            sourceHandle: cleanedHandle,
            label: route,
            data: persistedData,
          };
        });
      });
      // Soft typed-port warning for the reconnected endpoints.
      if (connection.source && connection.target) {
        maybeWarnKindMismatch(liveEdge.id, connection.source, connection.target);
      }
    },
    [record, setEdges, maybeWarnKindMismatch]
  );

  const handleRenameCommit = useCallback(
    (nodeId: string, label: string) => {
      const current = nodesRef.current.find((n) => n.id === nodeId);
      // Committing an unchanged label is a no-op — don't record a phantom entry.
      if (current && (current.data as NodeData).label === label) {
        setRenamingNodeId(null);
        return;
      }
      record();
      setNodes((nds) =>
        nds.map((n) =>
          n.id === nodeId ? { ...n, data: { ...(n.data as NodeData), label } } : n
        )
      );
      setRenamingNodeId(null);
    },
    [record, setNodes]
  );
  const handleRenameCancel = useCallback(() => setRenamingNodeId(null), []);

  const handlePeekOutput = useCallback(
    (nodeId: string) => {
      const node = nodesRef.current.find((n) => n.id === nodeId);
      if (!node) return;
      const byId = new Map(nodesRef.current.map((n) => [n.id, n]));
      const abs = absolutePosition(node, byId);
      const screen = flowToScreenPosition({
        x: abs.x + 210,
        y: abs.y,
      });
      setOutputPeek({ nodeId, screen });
    },
    [flowToScreenPosition]
  );

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      // Never let global shortcuts fire while focus rests inside a Radix
      // overlay (dialog/popover/menu) — the target is a button, not editable.
      if (isInOverlay(e.target)) return;
      // Always swallow ⌘S so the run lens never opens the browser save-page dialog.
      if ((e.metaKey || e.ctrlKey) && e.key === "s") {
        e.preventDefault();
        if (e.repeat || isCanvasReadOnly) return;
        handleSave(false);
        return;
      }
      // The runtime view is intentionally read-only. Selection remains useful,
      // but authoring shortcuts must not change the version being observed.
      if (isCanvasReadOnly) return;
      if ((e.key === "Delete" || e.key === "Backspace") && !isEditableTarget(e.target)) {
        e.preventDefault();
        handleDeleteSelection();
      }
      if ((e.metaKey || e.ctrlKey) && e.key === "d" && selectedNodeIds.length > 0 && !isEditableTarget(e.target)) {
        e.preventDefault();
        duplicateNodes(selectedNodeIds);
      }
      if ((e.metaKey || e.ctrlKey) && !isEditableTarget(e.target)) {
        const key = e.key.toLowerCase();
        if (key === "z" && !e.shiftKey) {
          e.preventDefault();
          undo();
        } else if ((key === "z" && e.shiftKey) || key === "y") {
          e.preventDefault();
          redo();
        } else if (key === "c") {
          if (selectedNodeIds.length > 0) {
            e.preventDefault();
            handleCopy();
          }
        } else if (key === "v") {
          if (hasClipboard()) {
            e.preventDefault();
            handlePaste();
          }
        }
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [
    handleSave,
    handleDeleteSelection,
    duplicateNodes,
    selectedNodeIds,
    undo,
    redo,
    handleCopy,
    handlePaste,
    isCanvasReadOnly,
  ]);

  // Reuse prior display-node `data` objects when only sibling nodes changed so
  // memo(BaseNode) can skip re-renders for unchanged runtime/auth fields.
  const displayNodesCacheRef = useRef<
    Map<string, { sig: string; node: Node; data: Record<string, unknown> }>
  >(new Map());

  const displayNodes = useMemo(() => {
    const nextCache = new Map<
      string,
      { sig: string; node: Node; data: Record<string, unknown> }
    >();
    const result = nodes.map((node) => {
      const runResult = nodeRunResults[node.id];
      const guardrailFailed = failedGuardrailIds.has(node.id);

      // Replay overrides live run state while the scrubber is active.
      const replayState = replayActive ? replay.derived.nodeStates[node.id] : undefined;
      const nodeFailed = replayActive
        ? replayState === "failed"
        : runResult?.status === "failed" || guardrailFailed;
      let runtimeState: "failed" | "completed" | undefined;
      if (replayActive) {
        runtimeState =
          replayState === "failed"
            ? "failed"
            : replayState === "completed"
              ? "completed"
              : undefined;
      } else {
        const completed =
          !!runResult &&
          node.id !== activeNodeId &&
          runResult.status === "completed" &&
          !guardrailFailed;
        runtimeState = nodeFailed ? "failed" : completed ? "completed" : undefined;
      }
      const isActive = replayActive
        ? replay.derived.currentNodeId === node.id
        : node.id === activeNodeId;

      // The run lens makes the graph the primary instrument, so inline
      // telemetry is always on there; in compose it stays the opt-in overlay.
      const telemetryOn = showTelemetry || isRunLens;

      // Per-node telemetry chips: replay uses its own snapshot; the live/final
      // view merges node latency with aggregated LLM token/cost.
      let telemetry: { tokens?: number; costUsd?: number; latencyMs?: number } | undefined;
      if (telemetryOn) {
        if (replayActive) {
          telemetry = replay.derived.nodeTelemetry[node.id];
        } else if (runResult) {
          const cost = llmCostByNode[node.id];
          telemetry = {
            latencyMs: runResult.latencyMs ?? undefined,
            tokens: cost?.tokens,
            costUsd: cost?.costUsd,
          };
        }
      }

      // Wavefront focus: while a run (live or scrubbed) has an active node,
      // the stages still ahead of it recede so attention tracks the front.
      // Completed/failed/active nodes stay at full weight.
      const inRunContext = isRunning || replayActive;
      const isPending = !runtimeState && !isActive;
      const dimmed = inRunContext && isPending;

      const errorMessage =
        nodeErrorMessages[node.id] ??
        (runResult?.status === "failed" ? runResult.output ?? undefined : undefined);
      const diffKind = diffHighlights?.[node.id] ?? undefined;
      const lintIssues = lintByNodeId.get(node.id)?.map((i) => i.message);
      const pinned = !isCanvasReadOnly && !!pinnedOutputs[node.id];
      const peekAvailable = !isCanvasReadOnly && !!runResult;
      const isRenaming = !isCanvasReadOnly && node.id === renamingNodeId;

      // Signature of everything injected into data (excluding stable callbacks).
      const sig = JSON.stringify({
        isActive,
        nodeFailed,
        errorMessage,
        diffKind,
        runtimeState,
        telemetry,
        telemetryOn,
        dimmed,
        lintIssues,
        pinned,
        peekAvailable,
        isRenaming,
        isCanvasReadOnly,
        // When the persisted node data/position/selection changes, rebuild.
        nodeData: node.data,
        selected: node.selected,
        position: node.position,
        parentId: node.parentId,
      });

      const prev = displayNodesCacheRef.current.get(node.id);
      if (prev && prev.sig === sig) {
        // Node shell may still need a new object for React Flow (selection),
        // but reuse data identity so memo(BaseNode) holds.
        const reused = { ...node, data: prev.data };
        nextCache.set(node.id, { sig, node: reused, data: prev.data });
        return reused;
      }

      const data = {
        ...(node.data as NodeData),
        isActive,
        hasError: nodeFailed,
        errorMessage,
        diffKind,
        runtimeState,
        telemetry,
        showTelemetry: telemetryOn,
        dimmed,
        lintIssues,
        pinned,
        peekAvailable,
        onPeekOutput: isCanvasReadOnly ? undefined : handlePeekOutput,
        isRenaming,
        onRenameCommit: isCanvasReadOnly ? undefined : handleRenameCommit,
        onRenameCancel: isCanvasReadOnly ? undefined : handleRenameCancel,
        onQuickAdd: isCanvasReadOnly ? undefined : openQuickAddFromNode,
        onDuplicate: isCanvasReadOnly ? undefined : handleDuplicateNode,
        onDelete: isCanvasReadOnly ? undefined : requestDeleteNode,
        onToggleCollapse: isCanvasReadOnly ? undefined : handleToggleCollapse,
      };
      const next = { ...node, data };
      nextCache.set(node.id, { sig, node: next, data: data as unknown as Record<string, unknown> });
      return next;
    });
    displayNodesCacheRef.current = nextCache;
    return result;
  }, [
    nodes,
    activeNodeId,
    failedGuardrailIds,
    nodeErrorMessages,
    diffHighlights,
    nodeRunResults,
    renamingNodeId,
    handlePeekOutput,
    handleRenameCommit,
    handleRenameCancel,
    openQuickAddFromNode,
    handleDuplicateNode,
    requestDeleteNode,
    handleToggleCollapse,
    replayActive,
    replay.derived,
    showTelemetry,
    isRunLens,
    isRunning,
    pinnedOutputs,
    llmCostByNode,
    isCanvasReadOnly,
    lintByNodeId,
  ]);

  // ── Group collapse: display transform (Task 2) ───────────────────────────
  // A collapsed frame hides its members and re-points boundary edges at the
  // frame FOR DISPLAY ONLY. toGraph()/save/export read the untransformed
  // `nodes`/`edges`, so the persisted graph is identical collapsed vs expanded.
  const groupCollapse = useMemo(() => {
    const collapsedIds = new Set<string>();
    for (const n of nodes) {
      const d = n.data as NodeData;
      if (d.nodeType === "group" && d.collapsed) collapsedIds.add(n.id);
    }
    const childToGroup = new Map<string, string>();
    const memberCount = new Map<string, number>();
    if (collapsedIds.size > 0) {
      for (const n of nodes) {
        if (n.parentId && collapsedIds.has(n.parentId)) {
          childToGroup.set(n.id, n.parentId);
          memberCount.set(n.parentId, (memberCount.get(n.parentId) ?? 0) + 1);
        }
      }
    }
    return { collapsedIds, childToGroup, memberCount };
  }, [nodes]);

  // Aggregate run state per collapsed frame so a hidden member's status still
  // surfaces on the frame (failed > running > completed wins).
  const collapsedGroupStatus = useMemo(() => {
    const status = new Map<string, "failed" | "running" | "completed">();
    if (groupCollapse.collapsedIds.size === 0) return status;
    const running = new Set<string>();
    const failed = new Set<string>();
    const completed = new Set<string>();
    groupCollapse.childToGroup.forEach((groupId, childId) => {
      const rr = nodeRunResults[childId];
      const isRunningChild = replayActive
        ? replay.derived.currentNodeId === childId
        : childId === activeNodeId;
      const isFailedChild = replayActive
        ? replay.derived.nodeStates[childId] === "failed"
        : rr?.status === "failed" || failedGuardrailIds.has(childId);
      const isCompletedChild = replayActive
        ? replay.derived.nodeStates[childId] === "completed"
        : rr?.status === "completed" && !failedGuardrailIds.has(childId);
      if (isRunningChild) running.add(groupId);
      if (isFailedChild) failed.add(groupId);
      if (isCompletedChild) completed.add(groupId);
    });
    groupCollapse.collapsedIds.forEach((groupId) => {
      if (failed.has(groupId)) status.set(groupId, "failed");
      else if (running.has(groupId)) status.set(groupId, "running");
      else if (completed.has(groupId)) status.set(groupId, "completed");
    });
    return status;
  }, [groupCollapse, nodeRunResults, activeNodeId, failedGuardrailIds, replayActive, replay.derived]);

  const renderNodes = useMemo(() => {
    if (groupCollapse.collapsedIds.size === 0) return displayNodes;
    return displayNodes.map((node) => {
      if (groupCollapse.collapsedIds.has(node.id)) {
        return {
          ...node,
          // Display-only size override; base groupWidth/Height stay expanded.
          style: { ...(node.style ?? {}), width: COLLAPSED_GROUP_W, height: COLLAPSED_GROUP_H },
          data: {
            ...(node.data as NodeData),
            collapsed: true,
            memberCount: groupCollapse.memberCount.get(node.id) ?? 0,
            aggregateStatus: collapsedGroupStatus.get(node.id),
          },
        };
      }
      if (groupCollapse.childToGroup.has(node.id)) {
        return { ...node, hidden: true };
      }
      return node;
    });
  }, [displayNodes, groupCollapse, collapsedGroupStatus]);

  const renderEdges = useMemo(() => {
    if (groupCollapse.collapsedIds.size === 0) return displayEdges;
    const { childToGroup } = groupCollapse;
    const seen = new Set<string>();
    const out: Edge[] = [];
    for (const edge of displayEdges) {
      const srcGroup = childToGroup.get(edge.source);
      const tgtGroup = childToGroup.get(edge.target);
      if (!srcGroup && !tgtGroup) {
        out.push(edge);
        continue;
      }
      const newSource = srcGroup ?? edge.source;
      const newTarget = tgtGroup ?? edge.target;
      // Intra-group edge (both endpoints inside the same collapsed frame): hidden.
      if (newSource === newTarget) continue;
      // Boundary edge → re-point at the frame's display handles; dedupe multiple
      // crossings between the same outside node and frame.
      const key = `${newSource}\u0001${newTarget}`;
      if (seen.has(key)) continue;
      seen.add(key);
      out.push({
        ...edge,
        source: newSource,
        target: newTarget,
        sourceHandle: srcGroup ? null : edge.sourceHandle,
        targetHandle: tgtGroup ? null : edge.targetHandle,
      });
    }
    return out;
  }, [displayEdges, groupCollapse]);

  const sourceNodeData = selectedEdge
    ? (nodes.find((n) => n.id === selectedEdge.source)?.data as NodeData | undefined)
    : undefined;
  const editorStatus = isRunLocked
    ? run?.status === "awaiting_approval"
      ? "Review"
      : "Running"
    : isDirty
      ? "Unsaved"
      : historicalVersionNumber != null
        ? `Viewing v${historicalVersionNumber}`
        : "Saved";
  const runDeckNodes = useMemo(
    () =>
      nodes
        .filter((node) => {
          const t = (node.data as NodeData).nodeType;
          return t !== "note" && t !== "group";
        })
        .map((node) => ({
          id: node.id,
          label: (node.data as NodeData).label || node.id,
        })),
    [nodes]
  );
  const openFullRunResults = useCallback(() => {
    // An actively streaming run stays in the deck. A paused approval can open
    // the inspector, but `isRunLocked` still keeps its graph read-only.
    if (isRunning) return;
    setCanvasMode("compose");
    setSidebarOpen(false);
    setRightTab("results");
    setShowResults(true);
  }, [isRunning]);

  const handleRunUpdate = useCallback((nextRun: WorkflowRun) => {
    setRun(nextRun);
    if (nextRun.status === "running") {
      // Approving a paused run resumes execution. Return to the Run Lens so the
      // canvas remains a read-only monitor. If the original SSE stream is dead,
      // poll the run to terminal so we never lock the canvas on "Live" forever.
      setIsRunning(true);
      setCanvasMode("run");
      setSidebarOpen(false);
      setAssistOpen(false);
      setShowResults(false);
      currentRunIdRef.current = nextRun.id;
      if (!runSourceRef.current) {
        if (runRecoveryTimerRef.current != null) {
          window.clearTimeout(runRecoveryTimerRef.current);
          runRecoveryTimerRef.current = null;
        }
        const poll = async () => {
          if (!mountedRef.current || currentRunIdRef.current !== nextRun.id) return;
          // Stream came back (e.g. another tab path) — stop polling.
          if (runSourceRef.current) return;
          try {
            const latest = await api.getRun(nextRun.id);
            if (!mountedRef.current || currentRunIdRef.current !== nextRun.id) return;
            setRun(latest);
            if (isTerminalRunStatus(latest.status)) {
              setIsRunning(false);
              setActiveNodeId(null);
              currentRunIdRef.current = null;
              runRecoveryTimerRef.current = null;
              return;
            }
            if (latest.status === "awaiting_approval") {
              setIsRunning(false);
              setActiveNodeId(null);
              setRightTab("results");
              runRecoveryTimerRef.current = null;
              return;
            }
            setIsRunning(true);
          } catch {
            // keep polling
          }
          if (!mountedRef.current || currentRunIdRef.current !== nextRun.id) return;
          runRecoveryTimerRef.current = window.setTimeout(() => {
            void poll();
          }, 3_000);
        };
        void poll();
      }
      return;
    }
    if (nextRun.status === "completed" || nextRun.status === "failed" || nextRun.status === "cancelled") {
      setIsRunning(false);
      setActiveNodeId(null);
      if (currentRunIdRef.current === nextRun.id) currentRunIdRef.current = null;
      if (runRecoveryTimerRef.current != null) {
        window.clearTimeout(runRecoveryTimerRef.current);
        runRecoveryTimerRef.current = null;
      }
    }
  }, []);

  const buildContextMenuItems = (menu: {
    kind: "node" | "edge" | "pane" | "selection";
    id?: string;
    flow: { x: number; y: number };
    screen: { x: number; y: number };
  }): ContextMenuItem[] => {
    if (menu.kind === "node" && menu.id) {
      const nodeId = menu.id;
      const nodeType = (nodesRef.current.find((n) => n.id === nodeId)?.data as NodeData | undefined)
        ?.nodeType;
      if (nodeType === "group") {
        return [
          { label: "Rename", icon: PenLine, onSelect: () => setRenamingNodeId(nodeId) },
          { label: "Ungroup", icon: Ungroup, onSelect: () => ungroupNode(nodeId) },
          "separator",
          {
            label: "Delete",
            icon: Trash2,
            shortcut: "⌫",
            danger: true,
            onSelect: () => requestDeleteNode(nodeId),
          },
        ];
      }
      return [
        { label: "Rename", icon: PenLine, onSelect: () => setRenamingNodeId(nodeId) },
        {
          label: "Duplicate",
          icon: Copy,
          shortcut: "⌘D",
          onSelect: () => duplicateNodes([nodeId]),
        },
        {
          label: "Copy",
          icon: ClipboardPaste,
          shortcut: "⌘C",
          onSelect: () => {
            const node = nodesRef.current.find((n) => n.id === nodeId);
            if (node) {
              copyToClipboard([node], edgesRef.current);
              toast.success("Copied 1 node");
            }
          },
        },
        { label: "Add next node", icon: Plus, onSelect: () => openQuickAddFromNode(nodeId) },
        ...buildNodeRunMenuItems({
          nodeId,
          output: nodeRunResults[nodeId]?.output ?? null,
          pinned: !!pinnedOutputs[nodeId],
          onPinOutput: handlePinOutput,
          onRunFromHere: handleRunFromHere,
        }),
        "separator",
        {
          label: "Delete",
          icon: Trash2,
          shortcut: "⌫",
          danger: true,
          onSelect: () => requestDeleteNode(nodeId),
        },
      ];
    }
    if (menu.kind === "edge" && menu.id) {
      const edgeId = menu.id;
      return [
        {
          label: "Edit label",
          icon: PenLine,
          onSelect: () => {
            setNodes((nds) => nds.map((n) => (n.selected ? { ...n, selected: false } : n)));
            setEdges((eds) => eds.map((e) => ({ ...e, selected: e.id === edgeId })));
          },
        },
        "separator",
        {
          label: "Delete connection",
          icon: Trash2,
          danger: true,
          onSelect: () => handleDeleteEdge(edgeId),
        },
      ];
    }
    if (menu.kind === "selection") {
      const count = selectionCount;
      // Only flat, ungrouped nodes can form a new frame (v1 groups don't nest).
      const groupableCount = selectedNodeIds.filter((id) => {
        const n = nodesRef.current.find((x) => x.id === id);
        const t = (n?.data as NodeData | undefined)?.nodeType;
        return n && t !== "group" && !n.parentId;
      }).length;
      const items: ContextMenuItem[] = [
        {
          label: `Duplicate ${count} item${count === 1 ? "" : "s"}`,
          icon: Copy,
          shortcut: "⌘D",
          onSelect: () => duplicateNodes(selectedNodeIds),
        },
        { label: "Copy", icon: ClipboardPaste, shortcut: "⌘C", onSelect: handleCopy },
      ];
      if (groupableCount >= 2) {
        items.push({ label: "Group selection", icon: Group, onSelect: handleGroupSelection });
      }
      if (selectedNodeIds.length >= 1) {
        items.push({
          label: "Save as snippet…",
          icon: Bookmark,
          onSelect: handleSaveSnippetRequest,
        });
      }
      items.push("separator", {
        label: `Delete ${count} item${count === 1 ? "" : "s"}`,
        icon: Trash2,
        shortcut: "⌫",
        danger: true,
        onSelect: handleDeleteSelection,
      });
      return items;
    }
    return [
      {
        label: "Add node here",
        icon: Plus,
        onSelect: () => setQuickAdd({ screen: menu.screen, flow: menu.flow }),
      },
      {
        label: "Paste here",
        icon: ClipboardPaste,
        shortcut: "⌘V",
        disabled: !hasClipboard(),
        onSelect: () => handlePaste(menu.flow),
      },
      { label: "Select all", icon: MousePointer2, onSelect: handleSelectAll },
      "separator",
      { label: "Tidy layout", icon: Wand2, onSelect: handleTidyLayout },
      {
        label: "Fit view",
        icon: Maximize2,
        onSelect: () => fitView({ padding: 0.2, maxZoom: 1.2, duration: viewportAnimMs }),
      },
    ];
  };

  return (
    <div className="flex h-screen flex-col bg-background">
      <p className="sr-only" aria-live="polite" aria-atomic="true">
        {canvasAnnouncement}
      </p>
      <header className="relative z-30 flex h-16 shrink-0 items-center gap-4 border-b border-border bg-surface-elevated/95 px-4 shadow-[0_1px_0_var(--surface-highlight)] backdrop-blur-sm">
        <div className="flex min-w-0 items-center gap-3">
          <Link
            href="/"
            className="focus-ring flex h-8 shrink-0 items-center gap-2 rounded-md px-1.5 text-foreground transition-colors hover:bg-surface-hover"
            title="Back to workflows"
          >
            <ArrowLeft className="h-4 w-4 text-muted" />
            <span className="text-base font-semibold tracking-tight">Aegis</span>
          </Link>
          <span className="h-5 w-px bg-border" aria-hidden />
          <div className="flex min-w-0 items-center gap-2">
            <WorkflowNameEditor
              workflowId={workflowId}
              name={displayName}
              onRenamed={setDisplayName}
              disabled={isCanvasReadOnly}
            />
            <span
              className={cn(
                "hidden shrink-0 items-center gap-1.5 font-mono text-2xs uppercase tracking-[0.08em] sm:inline-flex",
                isRunLocked ? "text-active" : isDirty ? "text-warning" : "text-success"
              )}
            >
              <span className={cn("h-1.5 w-1.5 rounded-full bg-current", isRunning && "animate-pulse")} />
              {isRunLocked ? (run?.status === "awaiting_approval" ? "Review" : "Live") : editorStatus}
            </span>
          </div>
        </div>

        <div
          className="absolute left-1/2 hidden -translate-x-1/2 items-center rounded-md border border-border bg-background/35 p-0.5 sm:flex"
          role="group"
          aria-label="Canvas mode"
        >
          <button
            type="button"
            onClick={() => setCanvasMode("compose")}
            disabled={isRunLocked}
            aria-pressed={!isRunLens}
            className={cn(
              "focus-ring rounded-[3px] px-4 py-1.5 text-sm transition-colors disabled:cursor-not-allowed disabled:opacity-50",
              !isRunLens ? "bg-surface-hover text-foreground" : "text-muted hover:text-foreground"
            )}
          >
            Compose
          </button>
          <button
            type="button"
            onClick={() => {
              setCanvasMode("run");
              setSidebarOpen(false);
              setAssistOpen(false);
            }}
            aria-pressed={isRunLens}
            className={cn(
              "focus-ring inline-flex items-center gap-2 rounded-[3px] px-4 py-1.5 text-sm transition-colors",
              isRunLens ? "bg-surface-hover text-foreground" : "text-muted hover:text-foreground"
            )}
          >
            Run
            {isRunning && <span className="h-1.5 w-1.5 rounded-full bg-active" />}
          </button>
        </div>

        <div className="ml-auto flex shrink-0 items-center gap-2">
          <RunControl
            isRunning={isRunLocked}
            isStarting={isRunStarting}
            disabled={nodes.length === 0}
            onRun={handleRun}
            onStop={handleStop}
            runInput={runInput}
          />
          {!isCanvasReadOnly && (
            <HeaderActions
              workflowId={workflowId}
              versionId={currentVersionId}
              onSave={() => handleSave(false)}
              onSaveAsNew={() => handleSave(true)}
              onImport={handleImportClick}
              onExport={handleExport}
              isSaving={isSaving}
            />
          )}
        </div>
      </header>
        <input
          ref={importInputRef}
          type="file"
          accept="application/json,.json"
          className="hidden"
          onChange={handleImportFile}
        />

      <div className="relative flex min-h-0 flex-1 overflow-hidden">
        {!isRunLens && sidebarOpen && (
          <CanvasSidebar
            activeTab={sidebarTab}
            onTabChange={setSidebarTab}
            onCollapse={() => setSidebarOpen(false)}
            onAddNode={handleAddNode}
            workflowId={workflowId}
            currentVersionId={currentVersionId}
            onSelectVersion={handleVersionSelect}
            onDiffHighlight={setDiffHighlights}
          />
        )}
        <div className="flex min-w-0 flex-1 flex-col">
          <div className="relative flex min-h-0 flex-1 overflow-hidden">
            {!isRunLens && !sidebarOpen && (
              <button
                type="button"
                onClick={() => setSidebarOpen(true)}
                aria-label="Show workflow tools"
                title="Show workflow tools"
                className="focus-ring absolute left-3 top-3 z-30 flex h-9 w-9 items-center justify-center rounded-md border border-border bg-surface-elevated text-muted shadow-elev-1 transition-colors duration-1 hover:bg-surface-hover hover:text-foreground"
              >
                <PanelLeft className="h-[17px] w-[17px]" strokeWidth={1.65} aria-hidden />
              </button>
            )}

            <div
              ref={reactFlowWrapper}
              className="canvas-bg relative min-w-0 flex-1"
          onPointerMove={(e) => {
            lastPointerRef.current = { x: e.clientX, y: e.clientY };
          }}
        >
          {historicalVersionNumber != null && (
            <div className="absolute inset-x-0 top-0 z-20 flex flex-col">
              <div className="border-b border-warning/30 bg-warning/10 px-4 py-2 text-center text-sm text-foreground">
                You&apos;re viewing version {historicalVersionNumber}. Save to make this the
                current version.
              </div>
            </div>
          )}
          <ReactFlow
            nodes={renderNodes}
            edges={renderEdges}
            onNodesChange={handleNodesChange}
            onEdgesChange={isCanvasReadOnly ? undefined : onEdgesChange}
            onConnect={isCanvasReadOnly ? undefined : onConnect}
            onConnectEnd={isCanvasReadOnly ? undefined : onConnectEnd}
            onDragOver={isCanvasReadOnly ? undefined : onDragOver}
            onDrop={isCanvasReadOnly ? undefined : onDrop}
            nodeTypes={nodeTypes}
            edgeTypes={memoizedEdgeTypes}
            nodesDraggable={!isCanvasReadOnly}
            nodesConnectable={!isCanvasReadOnly}
            snapToGrid
            snapGrid={[20, 20]}
            deleteKeyCode={null}
            panOnScroll
            selectionOnDrag
            selectionMode={SelectionMode.Partial}
            panOnDrag={[1]}
            zoomOnDoubleClick={false}
            edgesReconnectable={!isCanvasReadOnly}
            onReconnect={isCanvasReadOnly ? undefined : onReconnect}
            onNodeDragStart={isCanvasReadOnly ? undefined : handleNodeDragStart}
            onNodeDrag={isCanvasReadOnly ? undefined : handleNodeDrag}
            onNodeDragStop={isCanvasReadOnly ? undefined : handleNodeDragStop}
            onSelectionDragStart={isCanvasReadOnly ? undefined : () => record()}
            onMove={() => {
              // Peek position is computed once at open; panning/zooming detaches
              // it, so close it on any viewport move.
              if (outputPeek) setOutputPeek(null);
            }}
            onNodeDoubleClick={isCanvasReadOnly ? undefined : (_, node) => setRenamingNodeId(node.id)}
            onNodeContextMenu={isCanvasReadOnly ? undefined : (e, node) => openContextMenu("node", e, node.id)}
            onEdgeContextMenu={isCanvasReadOnly ? undefined : (e, edge) => openContextMenu("edge", e, edge.id)}
            onPaneContextMenu={isCanvasReadOnly ? undefined : (e) => openContextMenu("pane", e as React.MouseEvent)}
            onSelectionContextMenu={isCanvasReadOnly ? undefined : (e) => openContextMenu("selection", e)}
            connectionRadius={36}
            defaultEdgeOptions={{ type: "default" }}
            connectionLineComponent={ConnectionLine}
            onSelectionChange={handleSelectionChange}
            fitView
            fitViewOptions={{ padding: 0.08, maxZoom: 1.35 }}
            className="canvas-flow bg-background"
            proOptions={{ hideAttribution: true }}
          >
            {/* Two stacked layers (unique id per layer) for a quiet blueprint feel:
                a fine dot grid, plus a coarse line grid every ~110px underneath. */}
            <Background
              id="canvas-grid-coarse"
              variant={BackgroundVariant.Lines}
              gap={110}
              lineWidth={0.5}
              color="var(--canvas-grid)"
              className="opacity-40"
            />
            <Background
              id="canvas-grid-fine"
              variant={BackgroundVariant.Dots}
              gap={22}
              size={1.25}
              color="var(--canvas-grid)"
            />
            {!isRunLens && (
              <MiniMap
                nodeColor={minimapNodeColor}
                nodeStrokeWidth={0}
                nodeBorderRadius={3}
                /* Theme-aware mask — dark hardcode looked like a white “screen” in light mode */
                maskColor="color-mix(in srgb, var(--bg) 78%, transparent)"
                pannable
                zoomable
                className="!overflow-hidden !rounded-lg !border !border-border !bg-surface-elevated !shadow-elev-1"
              />
            )}

            {!isCanvasReadOnly && nodes.length === 0 && (
              <Panel position="top-center" className="mt-32">
                <button
                  type="button"
                  onClick={openQuickAddAtCenter}
                  className="flex flex-col items-center gap-3 rounded-xl border-2 border-dashed border-border px-12 py-10 text-muted transition-colors hover:border-border-strong hover:text-foreground"
                >
                  <span className="flex h-10 w-10 items-center justify-center rounded-lg border border-border bg-surface-elevated">
                    <Plus className="h-5 w-5" />
                  </span>
                  <span className="text-sm font-medium">Add first step…</span>
                  <span className="text-xs">Pick a trigger to start the workflow</span>
                  <span className="mt-1 flex items-center gap-1.5 text-2xs text-subtle">
                    <span>or press</span>
                    <kbd className="rounded border border-border bg-surface px-1.5 py-0.5 font-mono text-2xs">
                      ⌘K
                    </kbd>
                  </span>
                </button>
              </Panel>
            )}

            {!isCanvasReadOnly && (
              <Panel position="bottom-left" className="!m-4">
                <CanvasToolbar
                  onTidy={handleTidyLayout}
                  onDelete={handleDeleteSelection}
                  deleteDisabled={selectionCount === 0}
                  tidyDisabled={nodes.length === 0 || hasGroups}
                  tidyTitle={hasGroups ? "Tidy is unavailable while groups exist" : undefined}
                  animMs={viewportAnimMs}
                  showTelemetry={showTelemetry}
                  onToggleTelemetry={setShowTelemetry}
                />
              </Panel>
            )}
          </ReactFlow>
          {!isCanvasReadOnly && quickAdd && (
            <QuickAddMenu
              position={quickAdd.screen}
              preferTriggers={nodes.length === 0}
              onSelect={handleQuickAddSelect}
              onClose={() => setQuickAdd(null)}
              workflowId={workflowId}
              sourceNodeId={quickAdd.sourceNodeId}
              snippets={snippets}
              onInsertSnippet={handleInsertSnippet}
              onDeleteSnippet={handleDeleteSnippet}
              graphContext={{
                nodes: nodes.map((n) => {
                  const d = n.data as NodeData;
                  return { id: n.id, nodeType: d.nodeType, label: d.label };
                }),
                edges: edges.map((e) => ({
                  source: e.source,
                  target: e.target,
                  route: (e.data as { route?: string } | undefined)?.route,
                })),
              }}
            />
          )}
          {!isCanvasReadOnly && contextMenu && (
            <CanvasContextMenu
              position={contextMenu.screen}
              items={buildContextMenuItems(contextMenu)}
              onClose={() => setContextMenu(null)}
            />
          )}
          {!isCanvasReadOnly && outputPeek && nodeRunResults[outputPeek.nodeId] && (
            <NodeOutputPeek
              position={outputPeek.screen}
              nodeLabel={
                ((nodes.find((n) => n.id === outputPeek.nodeId)?.data as NodeData | undefined)
                  ?.label ?? outputPeek.nodeId)
              }
              output={nodeRunResults[outputPeek.nodeId].output ?? ""}
              latencyMs={nodeRunResults[outputPeek.nodeId].latencyMs}
              guardrailStatus={nodeRunResults[outputPeek.nodeId].guardrailStatus}
              runId={run?.id ?? null}
              nodeId={outputPeek.nodeId}
              pinned={!!pinnedOutputs[outputPeek.nodeId]}
              onPinOutput={handlePinOutput}
              onRunFromHere={handleRunFromHere}
              onClose={() => setOutputPeek(null)}
            />
          )}
          {/* Keep AssistRail mounted across run-lens transitions so the thread
              and any pending proposal survive starting a run. Hide + force
              closed while the canvas is read-only. */}
          <div
            className={cn(
              "absolute inset-y-0 right-0 z-20 flex",
              isCanvasReadOnly && "pointer-events-none invisible"
            )}
            aria-hidden={isCanvasReadOnly}
          >
            <AssistRail
              open={assistOpen && !isCanvasReadOnly}
              onOpenChange={(next) => {
                if (!isCanvasReadOnly) setAssistOpen(next);
              }}
              workflowId={workflowId}
              graph={currentGraph}
              onApply={handleAssistApply}
              onPreviewDiff={handleAssistPreview}
            />
          </div>
        </div>

        <div
          style={{ width: rightPanel.width }}
          className={cn(
            // animate-panel-in replays whenever the panel flips from
            // display:none to visible — an enter-only slide with no
            // AnimatePresence wrapper around the resizable flex column.
            "animate-panel-in relative shrink-0 flex-col border-l border-border bg-surface-elevated",
            !isRunLens && ((!isCanvasReadOnly && selectionCount > 0) || showResults) ? "flex" : "hidden"
          )}
        >
          <div
            {...rightPanel.handleProps}
            className="focus-ring absolute inset-y-0 -left-px z-10 block w-[3px] cursor-col-resize transition-colors hover:bg-primary/30 focus-visible:bg-primary/30 active:bg-primary/30"
          />
          <div className="flex border-b border-border bg-background/25">
            <div className="flex flex-1" role="tablist" aria-label="Canvas panels">
            <button
              type="button"
              role="tab"
              id="canvas-right-tab-configure"
              aria-selected={rightTab === "configure"}
              aria-controls="canvas-right-panel-configure"
              onClick={() => setRightTab("configure")}
              disabled={isCanvasReadOnly}
              className={cn(
                "tab-trigger disabled:cursor-not-allowed disabled:opacity-45",
                rightTab === "configure" && "tab-trigger-active"
              )}
            >
              <Settings2 className="h-4 w-4" />
              Configure
            </button>
            <button
              type="button"
              role="tab"
              id="canvas-right-tab-results"
              aria-selected={rightTab === "results"}
              aria-controls="canvas-right-panel-results"
              onClick={() => setRightTab("results")}
              className={cn("tab-trigger", rightTab === "results" && "tab-trigger-active")}
            >
              <Play className="h-4 w-4" />
              Results
              {isRunning && (
                <span className="h-2 w-2 animate-pulse rounded-full bg-active" />
              )}
            </button>
            </div>
            <button
              type="button"
              onClick={clearSelection}
              aria-label="Close panel"
              className="focus-ring px-3 text-muted transition-colors hover:text-foreground"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto">
            {rightTab === "configure" && !isCanvasReadOnly ? (
              <div
                role="tabpanel"
                id="canvas-right-panel-configure"
                aria-labelledby="canvas-right-tab-configure"
              >
                {/* No padding here: NodeInspector's header is a full-bleed
                    docking bar (sticky, with a category rule hugging the panel
                    edge) and pads its own body. The other two branches carry
                    their own gutter instead. */}
                {selectionCount > 1 ? (
                  <div className="p-4">
                    <div className="space-y-3 rounded-lg border border-dashed border-border p-4 text-center">
                      <MousePointer2 className="mx-auto h-5 w-5 text-muted" aria-hidden />
                      <p className="text-sm font-medium text-foreground">{selectionCount} items selected</p>
                      <p className="text-xs text-muted">
                        Drag to move together, ⌘D duplicates, ⌘C copies, ⌫ deletes.
                      </p>
                    </div>
                  </div>
                ) : selectedEdge ? (
                  <div className="p-4">
                    <EdgeInspector
                      edge={selectedEdge}
                      sourceLabel={(nodes.find((n) => n.id === selectedEdge.source)?.data as NodeData)?.label}
                      targetLabel={(nodes.find((n) => n.id === selectedEdge.target)?.data as NodeData)?.label}
                      routerRoutes={
                        sourceNodeData?.nodeType === "router"
                          ? sourceNodeData.routes
                          : sourceNodeData?.nodeType === "classifier"
                            ? sourceNodeData.categories
                            : sourceNodeData?.nodeType === "if"
                              ? ["true", "false"]
                              : sourceNodeData?.nodeType === "switch"
                                ? [
                                    ...(sourceNodeData.switchCases || []),
                                    sourceNodeData.switchDefault || "default",
                                  ]
                                : sourceNodeData?.nodeType === "guardrail" &&
                                    sourceNodeData.rules?.fail_behavior === "route"
                                  ? [
                                      sourceNodeData.rules.pass_route || "pass",
                                      sourceNodeData.rules.failure_route || "failed",
                                    ]
                                  : undefined
                      }
                      onChange={handleEdgeChange}
                      onDelete={handleDeleteEdge}
                    />
                  </div>
                ) : (
                  <NodeInspector
                    nodeId={selectedNodeId}
                    data={selectedData}
                    workflowId={workflowId}
                    fieldErrors={selectedNodeFieldErrors}
                    graphDirty={isDirty}
                    onChange={handleNodeDataChange}
                    graph={currentGraph}
                    lastRunResults={run?.node_results}
                    liveResults={nodeRunResults}
                    runId={run?.id ?? null}
                    pinnedOutput={selectedNodeId ? pinnedOutputs[selectedNodeId] ?? null : null}
                    onPinOutput={handlePinOutput}
                    onUpdatePinnedOutput={handleUpdatePinnedOutput}
                  />
                )}
              </div>
            ) : (
              <div
                role="tabpanel"
                id="canvas-right-panel-results"
                aria-labelledby="canvas-right-tab-results"
              >
                <RunResultsPanel
                  embedded
                  run={run}
                  liveEvents={liveEvents}
                  isRunning={isRunning}
                  onRunUpdate={handleRunUpdate}
                />
              </div>
            )}
          </div>
        </div>
        </div>
          {isRunLens && (
            <RunDeck
              nodes={runDeckNodes}
              run={run}
              liveEvents={liveEvents}
              observedStartNodeIds={observedStartNodeIds}
              isRunning={isRunning}
              isStarting={isRunStarting}
              activeNodeId={activeNodeId}
              selectedNodeId={runLensNodeId}
              nodeRunResults={nodeRunResults}
              startedAt={runStartedAt}
              onStop={handleStop}
              onOpenTrace={openFullRunResults}
              className="h-[42%] min-h-[320px] lg:min-h-[360px]"
              replaySlot={
                // Replay is a run-review activity, so its transport lives in the
                // rail (not a floating compose-mode panel). Only a finished run
                // is replayable — a live run has no timeline to scrub yet.
                !isRunning && replayRunId ? (
                  replayOpen ? (
                    timelineQuery.isLoading || replay.steps.length === 0 ? (
                      <span className="rounded-full glass-panel px-3 py-1 font-mono text-2xs text-muted shadow-elev-1">
                        Loading replay…
                      </span>
                    ) : (
                      <PostRunTransport replay={replay} onClose={() => setReplayOpen(false)} />
                    )
                  ) : (
                    <button
                      type="button"
                      onClick={() => setReplayOpen(true)}
                      className="focus-ring inline-flex h-7 items-center gap-1.5 rounded-md border border-border px-2 text-2xs font-medium text-muted transition-colors duration-1 hover:border-border-strong hover:bg-surface-hover hover:text-foreground"
                    >
                      <Play className="h-3.5 w-3.5" />
                      Replay
                    </button>
                  )
                ) : undefined
              }
              approvalSlot={
                run?.status === "awaiting_approval" ? (
                  <button
                    type="button"
                    onClick={openFullRunResults}
                    className="focus-ring inline-flex h-7 items-center rounded-md border border-active/40 bg-active/10 px-2 text-2xs font-medium text-active transition-colors duration-1 hover:bg-active/15"
                  >
                    Review approval
                  </button>
                ) : undefined
              }
            />
          )}
        </div>
      </div>

      {isRunLens ? (
        <span data-tour="status-bar" className="sr-only">
          Run status is shown in the execution deck.
        </span>
      ) : (
        <CanvasStatusBar
          editorStatus={editorStatus}
          statusTone={isRunning ? "active" : isDirty ? "warning" : "success"}
          hint="⌘S save · ⌫ delete · ⌘Z undo · right-click for actions"
          nodeCount={nodes.length}
          edgeCount={edges.length}
          selectionCount={selectionCount}
          issues={statusBarIssues}
          onIssueClick={focusNode}
        />
      )}

      <ConfirmDialog
        open={deleteConfirm !== null}
        onOpenChange={(open) => {
          if (!open) setDeleteConfirm(null);
        }}
        title="Delete selection?"
        description={
          deleteConfirm
            ? `This will remove ${deleteConfirm.nodeIds.length} node${deleteConfirm.nodeIds.length === 1 ? "" : "s"}${deleteConfirm.edgeIds.length > 0 ? ` and ${deleteConfirm.edgeIds.length} connection${deleteConfirm.edgeIds.length === 1 ? "" : "s"}` : ""}. You can undo this with ⌘Z.`
            : ""
        }
        confirmLabel={
          deleteConfirm
            ? `Delete ${deleteConfirm.nodeIds.length + deleteConfirm.edgeIds.length} item${deleteConfirm.nodeIds.length + deleteConfirm.edgeIds.length === 1 ? "" : "s"}`
            : "Delete"
        }
        loadingLabel="Deleting…"
        variant="destructive"
        onConfirm={async () => {
          if (deleteConfirm) executeDelete(deleteConfirm.nodeIds, deleteConfirm.edgeIds);
          setDeleteConfirm(null);
        }}
      />

      <ConfirmDialog
        open={importConfirmOpen}
        onOpenChange={setImportConfirmOpen}
        title="Import workflow?"
        description="Importing replaces the current workflow. Unsaved changes will be lost."
        confirmLabel="Import and replace"
        loadingLabel="Importing…"
        variant="destructive"
        onConfirm={async () => {
          setImportConfirmOpen(false);
          importInputRef.current?.click();
        }}
      />

      <SnippetNameDialog
        open={snippetDraft !== null}
        onOpenChange={(open) => {
          if (!open) setSnippetDraft(null);
        }}
        nodeCount={snippetDraft?.nodes.length ?? 0}
        onConfirm={handleSnippetNameConfirm}
      />
    </div>
  );
}

export function WorkflowCanvas(props: WorkflowCanvasProps) {
  return (
    <ReactFlowProvider>
      <WorkflowCanvasInner {...props} />
    </ReactFlowProvider>
  );
}
