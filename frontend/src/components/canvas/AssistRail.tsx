"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { Sparkles, X, ArrowRight, Check, RotateCcw, Eraser } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { EmptyState } from "@/components/ui/empty-state";
import { PanelSlide } from "@/components/motion/PanelSlide";
import { cn } from "@/lib/utils";
import {
  api,
  type AssistHistoryTurn,
  type EditGraphResponse,
  type GraphDiff,
} from "@/lib/api";
import type { WorkflowGraph } from "@/types/workflow";

export interface AssistRailProps {
  /** Persisted workflow id, if the graph has been saved. Optional — the
   *  backend accepts a bare graph for unsaved drafts. */
  workflowId?: string;
  /** Current canvas graph, mirrored from WorkflowCanvas each render. */
  graph: WorkflowGraph;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Called on Accept. The rail NEVER mutates the canvas itself — the caller
   *  swaps the graph and pushes undo history. */
  onApply: (graph: WorkflowGraph, diff: GraphDiff) => void;
  /** Optional: while a proposal is pending, the canvas can ring affected
   *  nodes via BaseNode's diffKind. Called with the diff when a proposal is
   *  live and with null when it is accepted / discarded. */
  onPreviewDiff?: (diff: GraphDiff | null) => void;
}

/** Displayed-thread cap (oldest pruned) and the server-side history cap. */
const MAX_TURNS = 12;
const MAX_HISTORY = 8;

type TurnStatus = "loading" | "proposal" | "error";
type TurnOutcome = "applied" | "dismissed";

/** One exchange in the thread: the user's instruction and, once it lands, the
 *  assistant's proposal (or an error). Outcome records what the user did. */
interface AssistTurn {
  id: string;
  instruction: string;
  status: TurnStatus;
  proposal: EditGraphResponse | null;
  error: string | null;
  outcome: TurnOutcome | null;
}

/** Compact assistant-side summary for the history payload, including outcome so
 *  the model knows what actually happened to a prior proposal. */
function assistantHistoryContent(turn: AssistTurn): string | null {
  if (turn.status === "error") {
    return "(the previous request did not produce a usable edit)";
  }
  if (turn.status !== "proposal" || !turn.proposal) return null;
  const summary = turn.proposal.summary?.trim() || "Proposed a graph edit.";
  const outcome =
    turn.outcome === "applied"
      ? " — the user applied this change"
      : turn.outcome === "dismissed"
        ? " — the user dismissed this proposal"
        : " — proposed, awaiting the user's decision";
  return `Proposed: ${summary}${outcome}`;
}

/** Flatten prior turns into a role/content history, capped to the last N. */
function buildHistory(turns: AssistTurn[]): AssistHistoryTurn[] {
  const history: AssistHistoryTurn[] = [];
  for (const turn of turns) {
    history.push({ role: "user", content: turn.instruction });
    const content = assistantHistoryContent(turn);
    if (content) history.push({ role: "assistant", content });
  }
  return history.slice(-MAX_HISTORY);
}

/** Cheap fingerprint of a graph for stale-proposal detection. */
function graphFingerprint(graph: WorkflowGraph): string {
  return JSON.stringify({
    nodes: graph.nodes.map((n) => ({
      id: n.id,
      type: n.data?.nodeType,
      label: n.data?.label,
      // Position + a shallow data hash — enough to detect authoring after propose.
      x: Math.round(n.position?.x ?? 0),
      y: Math.round(n.position?.y ?? 0),
      data: n.data,
    })),
    edges: graph.edges.map((e) => ({
      id: e.id,
      s: e.source,
      t: e.target,
      r: e.data?.route,
    })),
  });
}

/** Label lookup for a proposal's diff: current graph (covers removed nodes)
 *  overlaid with the proposed graph (covers added nodes). */
function buildLabelMap(
  graph: WorkflowGraph,
  proposal: EditGraphResponse | null,
): Map<string, string> {
  const map = new Map<string, string>();
  for (const node of graph.nodes) map.set(node.id, node.data?.label ?? node.id);
  if (proposal) {
    for (const node of proposal.proposed_graph.nodes) {
      map.set(node.id, node.data?.label ?? node.id);
    }
  }
  return map;
}

/** A single diff group (added / removed / changed) with affected labels. */
function DiffGroup({
  label,
  ids,
  labels,
  tone,
}: {
  label: string;
  ids: string[];
  labels: Map<string, string>;
  tone: "added" | "removed" | "changed";
}) {
  if (ids.length === 0) return null;
  const dot =
    tone === "added"
      ? "bg-success"
      : tone === "removed"
        ? "bg-destructive"
        : "bg-warning";
  return (
    <div className="space-y-1">
      <div className="flex items-center gap-1.5">
        <span className={cn("h-1.5 w-1.5 rounded-full", dot)} aria-hidden />
        <span className="text-micro text-subtle">{label}</span>
        <span className="font-mono tabular-nums text-2xs text-muted">{ids.length}</span>
      </div>
      <ul className="ml-3 space-y-0.5">
        {ids.map((id) => (
          <li key={id} className="truncate font-mono text-xs text-muted" title={labels.get(id) ?? id}>
            {labels.get(id) ?? id}
          </li>
        ))}
      </ul>
    </div>
  );
}

/** The user's instruction — a quiet right-aligned block, not a chat bubble. */
function UserTurn({ text }: { text: string }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[88%] rounded-md border border-border bg-background px-2.5 py-1.5 text-sm leading-5 text-foreground">
        {text}
      </div>
    </div>
  );
}

/** The assistant result for one turn: proposal review card, loading, or error. */
function AssistantTurn({
  turn,
  graph,
  onAccept,
  onDismiss,
}: {
  turn: AssistTurn;
  graph: WorkflowGraph;
  onAccept: () => void;
  onDismiss: () => void;
}) {
  const labelById = useMemo(
    () => buildLabelMap(graph, turn.proposal),
    [graph, turn.proposal],
  );

  if (turn.status === "loading") {
    return <p className="font-mono text-xs text-muted">Drafting a graph edit…</p>;
  }

  if (turn.status === "error") {
    return (
      <p className="text-xs leading-5 text-destructive">
        {turn.error ?? "Couldn't propose an edit."}
      </p>
    );
  }

  const proposal = turn.proposal;
  if (!proposal) return null;

  const diff = proposal.diff;
  const changeCount =
    diff.added_node_ids.length +
    diff.removed_node_ids.length +
    diff.changed_node_ids.length;
  const edgeDelta = diff.added_edges.length + diff.removed_edges.length;
  const resolved = turn.outcome !== null;

  return (
    <div className="space-y-2.5 rounded-md border border-border bg-surface-overlay px-3 py-2.5">
      {/* Summary + metadata as mono caption, no bubbles */}
      <div className="space-y-1.5">
        <div className="flex items-center gap-1.5">
          <Sparkles className="h-3 w-3 text-muted" aria-hidden />
          <span className="text-micro text-subtle">Proposed edit</span>
        </div>
        <p className="text-sm leading-6 text-foreground">{proposal.summary}</p>
        <p className="font-mono tabular-nums text-2xs text-muted">
          {changeCount} node{changeCount === 1 ? "" : "s"}
          {edgeDelta > 0 ? ` · ${edgeDelta} edge${edgeDelta === 1 ? "" : "s"}` : ""}
        </p>
      </div>

      {/* Diff readout — counts + affected node labels */}
      {changeCount > 0 && (
        <div className="space-y-2 rounded-md border border-border bg-background px-3 py-2.5">
          <DiffGroup label="Added" ids={diff.added_node_ids} labels={labelById} tone="added" />
          <DiffGroup label="Removed" ids={diff.removed_node_ids} labels={labelById} tone="removed" />
          <DiffGroup label="Changed" ids={diff.changed_node_ids} labels={labelById} tone="changed" />
        </div>
      )}

      {changeCount === 0 && edgeDelta === 0 && (
        <p className="font-mono text-xs text-subtle">
          No structural change — edges and node configs are unchanged.
        </p>
      )}

      {/* Notes */}
      {proposal.notes.length > 0 && (
        <div className="space-y-1">
          <p className="text-micro text-subtle">Notes</p>
          <ul className="space-y-1">
            {proposal.notes.map((note, i) => (
              <li key={i} className="text-xs leading-5 text-muted">
                {note}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Accept / Discard, or the recorded outcome */}
      {resolved ? (
        <div className="flex items-center gap-1.5 pt-0.5">
          {turn.outcome === "applied" ? (
            <Check className="h-3 w-3 text-muted" aria-hidden />
          ) : (
            <RotateCcw className="h-3 w-3 text-muted" aria-hidden />
          )}
          <span className="font-mono text-2xs uppercase tracking-wide text-muted">
            {turn.outcome}
          </span>
        </div>
      ) : (
        <div className="flex items-center gap-2 pt-0.5">
          <Button variant="outline" size="sm" className="flex-1 justify-center" onClick={onDismiss}>
            <RotateCcw className="h-3.5 w-3.5" />
            Dismiss
          </Button>
          <Button size="sm" className="flex-1 justify-center" onClick={onAccept}>
            <Check className="h-3.5 w-3.5" />
            Apply
          </Button>
        </div>
      )}
    </div>
  );
}

/**
 * Right-docked Assist rail: a session-scoped copilot thread. Each turn shows the
 * user instruction (quiet block) and the assistant's reviewable graph proposal
 * (diff + Apply/Dismiss). Proposals are NEVER auto-applied — Apply hands the
 * proposed graph + diff to the caller. Instrument chrome — a thin bone-white
 * left border, mono metadata, no chat bubbles or avatars. Thread state is
 * component-local (lost on unmount); "New thread" clears it. onPreviewDiff
 * mirrors the live pending diff so the canvas can ring affected nodes.
 */
export function AssistRail({
  workflowId,
  graph,
  open,
  onOpenChange,
  onApply,
  onPreviewDiff,
}: AssistRailProps) {
  const [instruction, setInstruction] = useState("");
  const [turns, setTurns] = useState<AssistTurn[]>([]);
  const [liveAnnouncement, setLiveAnnouncement] = useState("");
  const nextId = useRef(0);
  const scrollRef = useRef<HTMLDivElement>(null);
  const composerRef = useRef<HTMLTextAreaElement | null>(null);
  // Fingerprint of the graph each proposal was drafted against — Apply refuses
  // when the canvas has moved on (stale whole-graph replace).
  const proposalGraphFp = useRef<Map<string, string>>(new Map());

  const loading = turns.some((t) => t.status === "loading");

  // Keep the newest turn in view as the thread grows / resolves.
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [turns]);

  // Announce status changes to screen readers.
  useEffect(() => {
    const latest = turns[turns.length - 1];
    if (!latest) return;
    if (latest.status === "loading") setLiveAnnouncement("Proposing edit…");
    else if (latest.status === "proposal") setLiveAnnouncement("Proposal ready for review");
    else if (latest.status === "error") setLiveAnnouncement(latest.error || "Proposal failed");
    else if (latest.outcome === "applied") setLiveAnnouncement("Edit applied");
    else if (latest.outcome === "dismissed") setLiveAnnouncement("Proposal dismissed");
  }, [turns]);

  const propose = async () => {
    const trimmed = instruction.trim();
    if (!trimmed || loading) return;

    // History is built from turns *before* this one is added.
    const history = buildHistory(turns);
    const id = String(nextId.current++);
    const fp = graphFingerprint(graph);

    // Drop any prior pending proposal's ring before the new request lands.
    onPreviewDiff?.(null);
    setInstruction("");
    setTurns((prev) => {
      const next: AssistTurn[] = [
        ...prev,
        { id, instruction: trimmed, status: "loading", proposal: null, error: null, outcome: null },
      ];
      return next.length > MAX_TURNS ? next.slice(next.length - MAX_TURNS) : next;
    });

    try {
      const result = await api.editGraph({
        workflow_id: workflowId,
        graph,
        instruction: trimmed,
        history,
      });
      proposalGraphFp.current.set(id, fp);
      setTurns((prev) =>
        prev.map((t) => (t.id === id ? { ...t, status: "proposal", proposal: result } : t)),
      );
      onPreviewDiff?.(result.diff);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Couldn't propose an edit";
      setTurns((prev) =>
        prev.map((t) => (t.id === id ? { ...t, status: "error", error: message } : t)),
      );
      onPreviewDiff?.(null);
      toast.error(message);
    }
  };

  const accept = (turn: AssistTurn) => {
    if (!turn.proposal || turn.outcome) return;
    const expected = proposalGraphFp.current.get(turn.id);
    if (expected && expected !== graphFingerprint(graph)) {
      toast.error("Graph changed since this proposal — dismiss and propose again");
      return;
    }
    onApply(turn.proposal.proposed_graph, turn.proposal.diff);
    onPreviewDiff?.(null);
    setTurns((prev) => prev.map((t) => (t.id === turn.id ? { ...t, outcome: "applied" } : t)));
    toast.success("Applied AI edit");
    // Restore focus to the composer after Apply so keyboard users aren't dropped.
    requestAnimationFrame(() => composerRef.current?.focus());
  };

  const dismiss = (turn: AssistTurn) => {
    if (turn.outcome) return;
    onPreviewDiff?.(null);
    setTurns((prev) => prev.map((t) => (t.id === turn.id ? { ...t, outcome: "dismissed" } : t)));
    requestAnimationFrame(() => composerRef.current?.focus());
  };

  const newThread = () => {
    onPreviewDiff?.(null);
    proposalGraphFp.current.clear();
    setTurns([]);
    setInstruction("");
    setLiveAnnouncement("Thread cleared");
  };

  return (
    <PanelSlide
      side="right"
      open={open}
      className="pointer-events-auto flex h-full w-[340px] flex-col border-l border-primary/70 bg-surface-overlay"
    >
      {/* Header — monochrome chrome */}
      <div className="flex items-center justify-between gap-2 border-b border-border px-3.5 py-2.5">
        <div className="flex items-center gap-2">
          <Sparkles className="h-3.5 w-3.5 text-muted" aria-hidden />
          <span className="text-micro text-subtle">AI Assist</span>
        </div>
        <div className="flex items-center gap-0.5">
          {turns.length > 0 && (
            <Button
              variant="ghost"
              size="icon-xs"
              onClick={newThread}
              aria-label="New thread"
              title="New thread"
            >
              <Eraser className="h-3.5 w-3.5" />
            </Button>
          )}
          <Button
            variant="ghost"
            size="icon-xs"
            onClick={() => onOpenChange(false)}
            aria-label="Close AI assist"
          >
            <X className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>

      {/* Live region for assist status (proposals, apply, errors). */}
      <div className="sr-only" role="status" aria-live="polite" aria-atomic="true">
        {liveAnnouncement}
      </div>

      {/* Thread */}
      <div ref={scrollRef} className="min-h-0 flex-1 space-y-3 overflow-y-auto px-3.5 py-3">
        {turns.length === 0 ? (
          <EmptyState
            compact
            icon={Sparkles}
            title="Start a thread"
            description="Describe a change and Aegis drafts a reviewable graph edit — follow up to refine it. Nothing touches the canvas until you apply."
          />
        ) : (
          turns.map((turn) => (
            <div key={turn.id} className="space-y-2">
              <UserTurn text={turn.instruction} />
              <AssistantTurn
                turn={turn}
                graph={graph}
                onAccept={() => accept(turn)}
                onDismiss={() => dismiss(turn)}
              />
            </div>
          ))
        )}
      </div>

      {/* Composer — pinned to the bottom */}
      <div className="space-y-2 border-t border-border px-3.5 py-3">
        <Textarea
          ref={composerRef}
          value={instruction}
          onChange={(e) => setInstruction(e.target.value)}
          placeholder={
            turns.length === 0
              ? "Describe an edit — e.g. add a guardrail before the LLM, make this branch retry twice…"
              : "Follow up — e.g. make the second branch stricter, undo that last change…"
          }
          aria-label="Describe an edit"
          className="min-h-[76px] text-sm"
          onKeyDown={(e) => {
            if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
              e.preventDefault();
              void propose();
            }
          }}
        />
        <div className="flex items-center justify-between gap-2">
          <span className="font-mono text-2xs text-subtle">
            {graph.nodes.length} node{graph.nodes.length === 1 ? "" : "s"}
          </span>
          <Button size="sm" onClick={() => void propose()} disabled={loading || !instruction.trim()}>
            {loading ? "Proposing…" : "Propose edit"}
            {!loading && <ArrowRight className="h-3.5 w-3.5" />}
          </Button>
        </div>
      </div>
    </PanelSlide>
  );
}
