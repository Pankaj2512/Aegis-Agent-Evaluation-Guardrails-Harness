"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import {
  Check,
  ChevronRight,
  CircleDashed,
  Loader2,
  Pin,
  PinOff,
  XCircle,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CopyButton } from "@/components/ui/copy-button";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { formatOutput } from "@/lib/pretty-output";
import { formatDurationMs } from "@/lib/format";
import {
  guardrailStatusTone,
  runStatusLabel,
  runStatusTextClass,
  runStatusTone,
} from "@/lib/run-status";
import { cn } from "@/lib/utils";
import type { NodeResult, WorkflowGraph } from "@/types/workflow";

/** Streamed per-node state the canvas owns, mirrored structurally so this file
 *  needn't import React Flow or WorkflowCanvas internals. */
export interface NodeLiveResult {
  output: string | null;
  latencyMs: number | null;
  guardrailStatus: string | null;
  status: string;
}

interface NodeEvidence {
  status: string | null;
  output: string | null;
  latencyMs: number | null;
  guardrailStatus: string | null;
}

const OUTPUT_MAX_CHARS = 2000;

/** Merge streamed + persisted evidence for one node: streamed wins field-by-
 *  field, falling back to the persisted run result (mirrors RunDeck). */
function resolveEvidence(
  nodeId: string,
  lastRunResults: NodeResult[] | undefined,
  liveResults: Readonly<Record<string, NodeLiveResult>> | undefined
): NodeEvidence | null {
  const persisted = lastRunResults?.find((r) => r.node_id === nodeId);
  const live = liveResults?.[nodeId];
  if (!persisted && !live) return null;
  return {
    status: live?.status ?? persisted?.status ?? null,
    output: live?.output ?? persisted?.output ?? null,
    latencyMs: live?.latencyMs ?? persisted?.latency_ms ?? null,
    guardrailStatus: live?.guardrailStatus ?? persisted?.guardrail_status ?? null,
  };
}

/** Direct predecessors of a node — its effective input evidence. */
function directPredecessors(graph: WorkflowGraph | undefined, targetId: string): string[] {
  if (!graph) return [];
  const seen = new Set<string>();
  const ids: string[] = [];
  for (const edge of graph.edges) {
    if (edge.target === targetId && !seen.has(edge.source)) {
      seen.add(edge.source);
      ids.push(edge.source);
    }
  }
  return ids;
}

/** All transitive upstream node ids — used to build the {{steps.*}} context. */
function allUpstream(graph: WorkflowGraph | undefined, targetId: string): string[] {
  if (!graph) return [];
  const incoming = new Map<string, string[]>();
  for (const edge of graph.edges) {
    const list = incoming.get(edge.target) ?? [];
    list.push(edge.source);
    incoming.set(edge.target, list);
  }
  const seen = new Set<string>();
  const queue = [...(incoming.get(targetId) ?? [])];
  while (queue.length) {
    const id = queue.shift()!;
    if (seen.has(id)) continue;
    seen.add(id);
    for (const src of incoming.get(id) ?? []) if (!seen.has(src)) queue.push(src);
  }
  return Array.from(seen);
}

function oneLine(text: string): string {
  return text.replace(/\s+/g, " ").trim();
}

function StatusGlyph({ status, className }: { status: string; className?: string }) {
  const tone = runStatusTone(status);
  const classes = cn("h-3.5 w-3.5 shrink-0", runStatusTextClass(status), className);
  if (tone === "success") return <Check className={classes} aria-hidden />;
  if (tone === "destructive") return <XCircle className={classes} aria-hidden />;
  if (tone === "warning") return <Loader2 className={cn(classes, "animate-spin")} aria-hidden />;
  return <CircleDashed className={cn("h-3.5 w-3.5 shrink-0 text-subtle", className)} aria-hidden />;
}

/** House micro-heading matching InspectorSection's idiom. */
function SubHeading({ children }: { children: React.ReactNode }) {
  return <p className="text-micro text-subtle">{children}</p>;
}

function OutputBlock({ output }: { output: string }) {
  const { text, isJson } = formatOutput(output);
  const clamped = text.length > OUTPUT_MAX_CHARS ? `${text.slice(0, OUTPUT_MAX_CHARS)}…` : text;
  return (
    <div className="rounded-md border border-border bg-surface-input/60">
      <div className="flex items-center justify-between gap-2 border-b border-border px-2 py-1">
        <span className="text-2xs text-subtle">output</span>
        <div className="flex items-center gap-1">
          {isJson && (
            <Badge variant="outline" className="min-h-0 py-0.5 text-2xs">
              json
            </Badge>
          )}
          <CopyButton text={output} label="Copy output" />
        </div>
      </div>
      <pre className="max-h-48 overflow-y-auto whitespace-pre-wrap break-words px-2 py-1.5 font-mono text-xs leading-5 text-foreground">
        {clamped.trim() ? clamped : "—"}
      </pre>
    </div>
  );
}

export interface NodeDataSectionProps {
  workflowId?: string;
  nodeId: string;
  graph?: WorkflowGraph;
  /**
   * When true the canvas has unsaved edits. Backend node-test resolves config
   * from the last-saved version, so we warn rather than pretending the test
   * exercises the on-screen draft.
   */
  graphDirty?: boolean;
  /** Persisted run.node_results (fallback evidence source). */
  lastRunResults?: NodeResult[];
  /** Streamed per-node results (wins over persisted). */
  liveResults?: Readonly<Record<string, NodeLiveResult>>;
  runId?: string | null;
  /** This node's pinned mock output (owned by WorkflowCanvas), or null. */
  pinnedOutput?: string | null;
  /** Toggle pin on this node's output (existing canvas semantics). */
  onPinOutput?: (nodeId: string, output: string) => void;
  /** Set/replace this node's pinned output (n8n-style editable mock data). */
  onUpdatePinnedOutput?: (nodeId: string, output: string) => void;
}

/**
 * Features 1/2/4 — the per-node "Data" loop. A collapsible section under the
 * node's identity header that shows this node's latest-run evidence, its
 * upstream input evidence, a single-node step-run ("Test node"), and an
 * editable pinned output. Keyed by nodeId in the inspector so its local drafts
 * and open state re-seed per selection.
 */
export function NodeDataSection({
  workflowId,
  nodeId,
  graph,
  graphDirty = false,
  lastRunResults,
  liveResults,
  runId,
  pinnedOutput,
  onPinOutput,
  onUpdatePinnedOutput,
}: NodeDataSectionProps) {
  const evidence = useMemo(
    () => resolveEvidence(nodeId, lastRunResults, liveResults),
    [nodeId, lastRunResults, liveResults]
  );

  const predecessors = useMemo(() => directPredecessors(graph, nodeId), [graph, nodeId]);
  const labelById = useMemo(
    () => new Map((graph?.nodes ?? []).map((n) => [n.id, n.data.label] as const)),
    [graph]
  );

  // Upstream input evidence: each direct predecessor + its latest output.
  const upstream = useMemo(
    () =>
      predecessors.map((id) => ({
        id,
        label: labelById.get(id) || id,
        evidence: resolveEvidence(id, lastRunResults, liveResults),
      })),
    [predecessors, labelById, lastRunResults, liveResults]
  );

  // {{steps.*}} context for the step-run: every transitive upstream output.
  const stepsContext = useMemo(() => {
    const steps: Record<string, string> = {};
    for (const id of allUpstream(graph, nodeId)) {
      const ev = resolveEvidence(id, lastRunResults, liveResults);
      if (ev?.output != null && ev.output.length > 0) steps[id] = ev.output;
    }
    return steps;
  }, [graph, nodeId, lastRunResults, liveResults]);
  const stepsCount = Object.keys(stepsContext).length;

  const primaryUpstreamOutput = upstream[0]?.evidence?.output ?? "";

  const hasEvidence = evidence != null && (evidence.output != null || evidence.status != null);
  const hasPin = pinnedOutput != null;

  const [open, setOpen] = useState<boolean>(hasEvidence || hasPin);

  // Test node state (seeded once per node; the section is keyed by nodeId).
  const [testInput, setTestInput] = useState<string>(primaryUpstreamOutput);
  // The node's current on-canvas data — sent so the step-run tests unsaved
  // inspector edits (and works for a node not yet in the saved graph).
  const liveNodeData = useMemo(
    () => (graph?.nodes ?? []).find((n) => n.id === nodeId)?.data ?? null,
    [graph, nodeId]
  );
  const testMutation = useMutation({
    mutationFn: (vars: { input: string; steps: Record<string, string> }) =>
      api.testNode(workflowId as string, {
        node_id: nodeId,
        input_text: vars.input,
        extra_context: Object.keys(vars.steps).length ? { steps: vars.steps } : null,
        node_data: (liveNodeData as Record<string, unknown> | null) ?? undefined,
      }),
  });
  const testResult = testMutation.data ?? null;

  // Pinned-output editor draft; re-seed if the pin changes underneath us.
  const [pinDraft, setPinDraft] = useState<string>(pinnedOutput ?? "");
  useEffect(() => {
    setPinDraft(pinnedOutput ?? "");
  }, [pinnedOutput]);

  const runTest = () => {
    if (!workflowId) return;
    testMutation.mutate({ input: testInput, steps: stepsContext });
  };

  return (
    <details
      className="group rounded-lg border border-border bg-surface"
      open={open}
      onToggle={(e) => setOpen(e.currentTarget.open)}
    >
      <summary className="text-micro focus-ring flex cursor-pointer list-none items-center gap-1.5 px-3 py-2 transition-colors hover:text-foreground [&::-webkit-details-marker]:hidden">
        <ChevronRight
          className="h-3 w-3 shrink-0 transition-transform group-open:rotate-90"
          aria-hidden
        />
        Data
        {hasPin && <Pin className="h-3 w-3 shrink-0 text-accent" aria-hidden />}
      </summary>

      <div className="space-y-4 border-t border-border px-3 py-3">
        {/* --- Feature 1: this node's latest-run evidence --- */}
        <div className="space-y-2">
          <SubHeading>Latest output</SubHeading>
          {hasEvidence ? (
            <>
              <div className="flex flex-wrap items-center gap-2">
                {evidence?.status && (
                  <span className="inline-flex items-center gap-1.5">
                    <StatusGlyph status={evidence.status} />
                    <span
                      className={cn(
                        "text-xs font-medium",
                        runStatusTextClass(evidence.status)
                      )}
                    >
                      {runStatusLabel(evidence.status)}
                    </span>
                  </span>
                )}
                {evidence?.latencyMs != null && (
                  <span className="rounded-md border border-border bg-surface px-1.5 py-0.5 font-mono text-2xs tabular-nums text-muted">
                    {formatDurationMs(evidence.latencyMs)}
                  </span>
                )}
                {evidence?.guardrailStatus && (
                  <Badge
                    variant={guardrailStatusTone(evidence.guardrailStatus)}
                    className="min-h-0 py-0.5 text-2xs"
                  >
                    {evidence.guardrailStatus}
                  </Badge>
                )}
              </div>
              {evidence?.output != null && evidence.output.length > 0 && (
                <OutputBlock output={evidence.output} />
              )}
            </>
          ) : (
            <p className="text-xs text-muted">
              No run data yet — run the workflow or test this node.
            </p>
          )}
        </div>

        {/* --- Feature 1: upstream input evidence --- */}
        {upstream.length > 0 && (
          <div className="space-y-1.5">
            <SubHeading>Upstream ({upstream.length})</SubHeading>
            <ul className="space-y-1">
              {upstream.map((u) => {
                const out = u.evidence?.output ?? null;
                return (
                  <li
                    key={u.id}
                    className="flex items-baseline gap-2 rounded-md border border-border bg-surface-input/50 px-2 py-1"
                  >
                    <span className="shrink-0 truncate text-2xs font-medium text-foreground max-w-[40%]">
                      {u.label}
                    </span>
                    <span className="min-w-0 flex-1 truncate font-mono text-2xs text-muted">
                      {out && out.trim() ? oneLine(out) : "—"}
                    </span>
                  </li>
                );
              })}
            </ul>
          </div>
        )}

        {/* --- Feature 4: editable pinned output --- */}
        {hasPin && (
          <div className="space-y-2">
            <div className="flex items-center gap-1.5">
              <Pin className="h-3 w-3 shrink-0 text-accent" aria-hidden />
              <SubHeading>Pinned output</SubHeading>
            </div>
            <Textarea
              rows={4}
              className="font-mono text-xs"
              value={pinDraft}
              onChange={(e) => setPinDraft(e.target.value)}
              aria-label="Pinned output"
            />
            <p className="form-hint">
              Used as this node&apos;s mock output when running from here.
            </p>
            <div className="flex items-center gap-2">
              <Button
                type="button"
                size="sm"
                onClick={() => onUpdatePinnedOutput?.(nodeId, pinDraft)}
                disabled={!onUpdatePinnedOutput || pinDraft === (pinnedOutput ?? "")}
              >
                Update pin
              </Button>
              <Button
                type="button"
                size="sm"
                variant="ghost"
                onClick={() => onPinOutput?.(nodeId, pinnedOutput ?? "")}
                disabled={!onPinOutput}
              >
                <PinOff className="h-3.5 w-3.5" />
                Unpin
              </Button>
            </div>
          </div>
        )}

        {/* --- Feature 2: single-node step-run --- */}
        <div className="space-y-2 border-t border-border pt-3">
          <div className="flex items-center justify-between gap-2">
            <SubHeading>Test node</SubHeading>
            {stepsCount > 0 && (
              <span className="rounded-md border border-border bg-surface px-1.5 py-0.5 font-mono text-2xs tabular-nums text-subtle">
                {stepsCount} upstream {stepsCount === 1 ? "output" : "outputs"} included
              </span>
            )}
          </div>
          <Textarea
            rows={3}
            value={testInput}
            onChange={(e) => setTestInput(e.target.value)}
            placeholder="Test input for this node…"
            aria-label="Test input"
          />
          <div className="flex items-center gap-2">
            <Button
              type="button"
              size="sm"
              onClick={runTest}
              disabled={!workflowId || testMutation.isPending}
            >
              {testMutation.isPending ? "Testing…" : "Run test"}
            </Button>
            {!workflowId && (
              <span className="text-2xs text-subtle">Save the workflow to test nodes.</span>
            )}
          </div>
          {graphDirty && workflowId && (
            <p className="text-2xs text-subtle">
              Testing your current edits (unsaved) — save to persist them
            </p>
          )}

          {testMutation.isError && !testResult && (
            <p className="whitespace-pre-wrap break-words font-mono text-2xs leading-5 text-destructive/80">
              {testMutation.error instanceof Error
                ? testMutation.error.message
                : "Test failed"}
            </p>
          )}

          {testResult && (
            <div className="space-y-2 rounded-md border border-border bg-surface-input/50 p-2">
              {testResult.status === "unsupported" ? (
                <p className="text-xs text-muted">
                  {testResult.error || "This node type can't be tested in isolation."}
                </p>
              ) : (
                <>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="inline-flex items-center gap-1.5">
                      <StatusGlyph status={testResult.status} />
                      <span
                        className={cn(
                          "text-xs font-medium",
                          runStatusTextClass(testResult.status)
                        )}
                      >
                        {runStatusLabel(testResult.status)}
                      </span>
                    </span>
                    <span className="rounded-md border border-border bg-surface px-1.5 py-0.5 font-mono text-2xs tabular-nums text-muted">
                      {formatDurationMs(testResult.latency_ms)}
                    </span>
                  </div>
                  {testResult.status === "failed" ? (
                    <p className="whitespace-pre-wrap break-words font-mono text-2xs leading-5 text-destructive/80">
                      {testResult.error || "Node execution failed."}
                    </p>
                  ) : (
                    testResult.output != null && <OutputBlock output={testResult.output} />
                  )}
                  {testResult.status === "completed" && testResult.output != null && (
                    <button
                      type="button"
                      onClick={() => onPinOutput?.(nodeId, testResult.output as string)}
                      aria-pressed={hasPin}
                      disabled={!onPinOutput}
                      className={cn(
                        "focus-ring inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium transition-colors",
                        hasPin
                          ? "text-accent hover:bg-surface-hover"
                          : "text-muted hover:bg-surface-hover hover:text-foreground"
                      )}
                    >
                      {hasPin ? (
                        <PinOff className="h-3.5 w-3.5" />
                      ) : (
                        <Pin className="h-3.5 w-3.5" />
                      )}
                      {hasPin ? "Unpin output" : "Pin as output"}
                    </button>
                  )}
                </>
              )}
            </div>
          )}
        </div>

        {runId && (
          <p className="font-mono text-2xs text-subtle">
            run {runId.slice(0, 8)}
          </p>
        )}
      </div>
    </details>
  );
}
