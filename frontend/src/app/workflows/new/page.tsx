"use client";

import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  Bot,
  CheckCircle2,
  FileJson,
  Route,
  ShieldCheck,
  Sparkles,
  Upload,
} from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { categorize, CATEGORY_COLOR_VAR } from "@/components/canvas/nodes/category";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import { cn } from "@/lib/utils";
import { readWorkflowExportFile, WorkflowImportError } from "@/lib/workflow-import";
import type { WorkflowGraph } from "@/types/workflow";
import {
  DescribeWorkflowCard,
  GeneratedNotes,
  type GeneratedWorkflow,
} from "./DescribeWorkflowCard";

const starterGraphs = [
  {
    id: "agent",
    name: "Agent draft",
    description: "A clean input-to-agent flow for fast prototyping.",
    icon: Bot,
    graph: {
      nodes: [
        {
          id: "trigger",
          type: "baseNode",
          position: { x: 40, y: 120 },
          data: { label: "Trigger", nodeType: "trigger", triggerType: "manual" },
        },
        {
          id: "input_schema",
          type: "baseNode",
          position: { x: 320, y: 120 },
          data: {
            label: "Input Schema",
            nodeType: "input_schema",
            inputFields: [
              { key: "message", type: "string", required: true },
              { key: "priority", type: "string", default: "normal" },
            ],
          },
        },
        {
          id: "agent",
          type: "baseNode",
          position: { x: 600, y: 120 },
          data: {
            label: "LLM Agent",
            nodeType: "agent",
            instruction: "Use {{input.message}} and return a concise, grounded response.",
          },
        },
        {
          id: "end",
          type: "baseNode",
          position: { x: 880, y: 120 },
          data: { label: "End", nodeType: "end" },
        },
      ],
      edges: [
        { id: "e-trigger-input", source: "trigger", target: "input_schema" },
        { id: "e-input-agent", source: "input_schema", target: "agent" },
        { id: "e-agent-end", source: "agent", target: "end" },
      ],
    } satisfies WorkflowGraph,
  },
  {
    id: "triage",
    name: "Support triage",
    description: "Route customer messages before drafting a response.",
    icon: Route,
    graph: {
      nodes: [
        {
          id: "trigger",
          type: "baseNode",
          position: { x: 40, y: 160 },
          data: { label: "Intake", nodeType: "trigger", triggerType: "manual" },
        },
        {
          id: "classifier",
          type: "baseNode",
          position: { x: 320, y: 160 },
          data: {
            label: "Classify request",
            nodeType: "classifier",
            categories: ["billing", "technical", "refund"],
          },
        },
        {
          id: "agent",
          type: "baseNode",
          position: { x: 600, y: 160 },
          data: {
            label: "Draft reply",
            nodeType: "agent",
            instruction: "Respond according to the classified support category.",
          },
        },
        {
          id: "end",
          type: "baseNode",
          position: { x: 880, y: 160 },
          data: { label: "End", nodeType: "end" },
        },
      ],
      edges: [
        { id: "e-trigger-classifier", source: "trigger", target: "classifier" },
        { id: "e-classifier-agent", source: "classifier", target: "agent" },
        { id: "e-agent-end", source: "agent", target: "end" },
      ],
    } satisfies WorkflowGraph,
  },
  {
    id: "quality",
    name: "Quality gated",
    description: "Ship with eval scoring and a guardrail checkpoint from day one.",
    icon: ShieldCheck,
    graph: {
      nodes: [
        {
          id: "trigger",
          type: "baseNode",
          position: { x: 40, y: 140 },
          data: { label: "Trigger", nodeType: "trigger", triggerType: "manual" },
        },
        {
          id: "agent",
          type: "baseNode",
          position: { x: 320, y: 140 },
          data: {
            label: "Agent",
            nodeType: "agent",
            instruction: "Produce a policy-grounded answer with concise reasoning.",
          },
        },
        {
          id: "guardrail",
          type: "baseNode",
          position: { x: 600, y: 60 },
          data: {
            label: "Safety check",
            nodeType: "guardrail",
            rules: { guardrail_type: "rules", blocked_keywords: ["secret"], fail_behavior: "block" },
          },
        },
        {
          id: "eval",
          type: "baseNode",
          position: { x: 600, y: 220 },
          data: {
            label: "Evaluate quality",
            nodeType: "evaluation",
            evalType: "llm",
            evalThreshold: 0.8,
            criteria: "Accurate, helpful, and grounded.",
          },
        },
        {
          id: "end",
          type: "baseNode",
          position: { x: 880, y: 140 },
          data: { label: "End", nodeType: "end" },
        },
      ],
      edges: [
        { id: "e-trigger-agent", source: "trigger", target: "agent" },
        { id: "e-agent-guardrail", source: "agent", target: "guardrail" },
        { id: "e-guardrail-eval", source: "guardrail", target: "eval" },
        { id: "e-eval-end", source: "eval", target: "end" },
      ],
    } satisfies WorkflowGraph,
  },
] as const;

type StarterId = (typeof starterGraphs)[number]["id"] | "describe";

const describeShape = {
  id: "describe" as const,
  name: "Describe it",
  description: "Tell Aegis what you want in plain language and generate a graph.",
  icon: Sparkles,
};

function pointForNode(graph: WorkflowGraph, nodeId: string) {
  const node = graph.nodes.find((item) => item.id === nodeId);
  if (!node) return null;
  const xs = graph.nodes.map((item) => item.position.x);
  const ys = graph.nodes.map((item) => item.position.y);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const spanX = Math.max(maxX - minX, 1);
  const spanY = Math.max(maxY - minY, 1);
  return {
    x: 10 + ((node.position.x - minX) / spanX) * 80,
    y: graph.nodes.length <= 4 && spanY === 1
      ? 50
      : 24 + ((node.position.y - minY) / spanY) * 52,
  };
}

function StarterGraphPreview({ graph }: { graph: WorkflowGraph }) {
  return (
    <div className="relative min-h-[220px] overflow-hidden rounded-lg border border-border bg-bg p-4 sm:min-h-[260px] sm:p-5">
      <div
        className="absolute inset-0 opacity-80"
        style={{
          backgroundImage:
            "radial-gradient(var(--canvas-grid) 1.1px, transparent 1.1px)",
          backgroundSize: "16px 16px",
        }}
      />
      <svg className="pointer-events-none absolute inset-0 h-full w-full" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden>
        {graph.edges.map((edge) => {
          const source = pointForNode(graph, edge.source);
          const target = pointForNode(graph, edge.target);
          if (!source || !target) return null;
          const mid = Math.max(8, Math.abs(target.x - source.x) * 0.35);
          return (
            <path
              key={edge.id}
              d={`M ${source.x} ${source.y} C ${source.x + mid} ${source.y}, ${target.x - mid} ${target.y}, ${target.x} ${target.y}`}
              fill="none"
              stroke="var(--canvas-edge)"
              strokeLinecap="round"
              strokeWidth="1.5"
              vectorEffect="non-scaling-stroke"
            />
          );
        })}
      </svg>
      <div className="relative h-[188px] sm:h-[220px]">
        {graph.nodes.map((node) => {
          const point = pointForNode(graph, node.id);
          const catColor = CATEGORY_COLOR_VAR[categorize(node.data.nodeType)];
          return (
            <div
              key={node.id}
              className="absolute w-[104px] -translate-x-1/2 -translate-y-1/2 overflow-hidden rounded-lg border border-border bg-surface px-2 py-2 shadow-elev-1 sm:w-[124px] sm:px-3"
              style={{
                left: `${point?.x ?? 50}%`,
                top: `${point?.y ?? 50}%`,
              }}
            >
              <span className="absolute inset-y-0 left-0 w-0.5" style={{ background: catColor }} aria-hidden />
              <div className="min-w-0">
                <p className="truncate text-xs font-medium text-foreground">{node.data.label}</p>
                <p className="truncate font-mono text-2xs lowercase text-subtle">
                  {node.data.nodeType}
                </p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function NewWorkflowPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const importInputRef = useRef<HTMLInputElement>(null);
  const [name, setName] = useState("My Agent Workflow");
  const [description, setDescription] = useState("");
  const [starterId, setStarterId] = useState<StarterId>("agent");
  const [generated, setGenerated] = useState<GeneratedWorkflow | null>(null);
  const [loading, setLoading] = useState(false);
  const [importing, setImporting] = useState(false);
  const describing = starterId === "describe";
  const selectedStarter = starterGraphs.find((starter) => starter.id === starterId) ?? starterGraphs[0];
  // When describing, the graph comes from the generator; otherwise the starter.
  const activeGraph = describing ? generated?.graph ?? null : selectedStarter.graph;

  const handleCreate = async () => {
    if (!activeGraph) return;
    setLoading(true);
    try {
      const workflow = await api.createWorkflow({
        name,
        description,
        graph_json: activeGraph,
      });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.workflows }),
        queryClient.invalidateQueries({ queryKey: queryKeys.observabilitySummary }),
      ]);
      router.push(`/workflows/${workflow.id}`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to create workflow");
    } finally {
      setLoading(false);
    }
  };

  const handleImportClick = () => {
    importInputRef.current?.click();
  };

  const handleImportFile = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;

    setImporting(true);
    try {
      const payload = await readWorkflowExportFile(file);
      const workflow = await api.importWorkflow({
        format: payload.format,
        name: payload.name ?? name,
        description: payload.description ?? description,
        graph_json: payload.graph_json,
      });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.workflows }),
        queryClient.invalidateQueries({ queryKey: queryKeys.observabilitySummary }),
      ]);
      toast.success(`Imported "${workflow.name}"`);
      router.push(`/workflows/${workflow.id}`);
    } catch (error) {
      const message =
        error instanceof WorkflowImportError
          ? error.message
          : error instanceof Error
            ? error.message
            : "Import failed";
      toast.error(message);
    } finally {
      setImporting(false);
    }
  };

  return (
    <div className="page-container space-y-6">
      <PageHeader
        title="Create workflow"
        description="Start from a blank graph or a starter shape, then tune it on the canvas."
      />

      <div className="grid gap-4 xl:grid-cols-[minmax(0,0.9fr)_minmax(460px,1.1fr)]">
        <section className="surface-card overflow-hidden rounded-lg border border-border bg-surface shadow-elev-1">
          <div className="border-b border-border-mid bg-surface-input px-4 py-3">
            <h2 className="text-sm font-semibold tracking-tight text-foreground">Details</h2>
            <p className="mt-0.5 text-xs text-muted">
              Name the workflow and choose a starting graph shape.
            </p>
          </div>

          <div className="space-y-4 p-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="name">Name</Label>
                <Input id="name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Workflow name" />
              </div>

            </div>

            {!describing && (
              <div className="space-y-2">
                <Label htmlFor="description">Description</Label>
                <Textarea
                  id="description"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="What does this workflow do? (optional)"
                  className="min-h-20"
                />
              </div>
            )}

            <div className="grid gap-2 border-t border-border-mid pt-4">
              <div className="flex items-center justify-between gap-3">
                <Label>Choose a launch shape</Label>
                <Badge variant="outline">
                  {activeGraph ? `${activeGraph.nodes.length} nodes` : "Describe"}
                </Badge>
              </div>
              {[...starterGraphs, describeShape].map((starter) => {
                const Icon = starter.icon;
                const selected = starter.id === starterId;
                return (
                  <button
                    key={starter.id}
                    type="button"
                    onClick={() => setStarterId(starter.id)}
                    aria-pressed={selected}
                    aria-label={`Use ${starter.name} starter`}
                    className={cn(
                      "focus-ring group relative flex items-center gap-3 overflow-hidden rounded-lg border px-3 py-2.5 text-left transition-colors duration-1",
                      selected
                        ? "border-primary/40 bg-primary-muted text-foreground shadow-elev-1"
                        : "border-border bg-surface-input text-muted hover:border-border-strong hover:bg-surface-hover hover:text-foreground"
                    )}
                  >
                    <span
                      className={cn(
                        "absolute inset-y-0 left-0 w-0.5 opacity-0 transition-opacity duration-1",
                        selected && "opacity-100"
                      )}
                      style={{ background: selected ? "var(--primary)" : undefined }}
                      aria-hidden
                    />
                    <span
                      className={cn(
                        "flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-border shadow-[inset_0_1px_0_var(--surface-highlight)]",
                        selected ? "bg-primary text-primary-foreground" : "bg-surface text-muted group-hover:text-foreground"
                      )}
                    >
                      <Icon className="h-4 w-4" />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="text-sm font-semibold">{starter.name}</span>
                      <span className="mt-0.5 block text-xs leading-5 text-muted">{starter.description}</span>
                    </span>
                    {selected && <CheckCircle2 className="h-4 w-4 shrink-0 text-primary" />}
                  </button>
                );
              })}
            </div>

            {describing && (
              <DescribeWorkflowCard
                description={description}
                onDescriptionChange={setDescription}
                result={generated}
                onResult={setGenerated}
                busy={loading || importing}
                onError={(message) => toast.error(message)}
              />
            )}

            <div className="rounded-lg border border-border-mid bg-surface-input/80 p-3 shadow-[inset_0_1px_0_var(--surface-highlight)]">
              <div className="flex items-start gap-3">
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-border bg-surface text-muted shadow-[inset_0_1px_0_var(--surface-highlight)]">
                  <FileJson className="h-4 w-4" />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-foreground">Import instead</p>
                  <p className="mt-1 text-xs leading-5 text-muted">
                    Use an <code className="rounded bg-surface px-1 font-mono text-2xs">aegis-workflow-v1</code> JSON export to restore a backup or shared graph.
                  </p>
                </div>
                <input
                  ref={importInputRef}
                  type="file"
                  accept="application/json,.json"
                  className="hidden"
                  onChange={handleImportFile}
                />
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={handleImportClick}
                  disabled={loading || importing}
                >
                  <Upload className="h-3.5 w-3.5" />
                  {importing ? "Importing…" : "Import"}
                </Button>
              </div>
            </div>

            <div className="flex flex-col gap-3 border-t border-border-mid pt-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="text-xs leading-5 text-muted">
                Creates a versioned workflow and opens the canvas immediately.
              </div>
              <Button
                onClick={handleCreate}
                disabled={loading || importing || !name.trim() || !activeGraph}
                className="w-full sm:w-auto"
              >
                <Sparkles className="h-4 w-4" />
                {loading ? "Creating…" : "Create & open canvas"}
              </Button>
            </div>
          </div>
        </section>

        <section className="surface-card overflow-hidden rounded-lg border border-border bg-surface shadow-elev-1">
          <div className="flex flex-col gap-2 border-b border-border-mid bg-surface-input px-4 py-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h2 className="text-sm font-semibold tracking-tight text-foreground">
                {describing ? "Generated graph" : "Starter graph"}
              </h2>
              <p className="mt-0.5 text-xs text-muted">Created when you open the canvas.</p>
            </div>
            {activeGraph && (
              <p className="shrink-0 font-mono text-2xs tabular-nums text-subtle">
                {activeGraph.nodes.length}n · {activeGraph.edges.length}e
              </p>
            )}
          </div>
          <div className="p-4">
            {activeGraph ? (
              <>
                <StarterGraphPreview graph={activeGraph} />
                {describing && generated && <GeneratedNotes notes={generated.notes} />}
              </>
            ) : (
              <div className="flex min-h-[220px] flex-col items-center justify-center rounded-lg border border-dashed border-border bg-bg p-6 text-center sm:min-h-[260px]">
                <Sparkles className="h-5 w-5 text-muted" />
                <p className="mt-3 text-sm font-medium text-foreground">Describe your workflow</p>
                <p className="mt-1 max-w-xs text-xs leading-5 text-muted">
                  Generate a graph from your description and it will appear here.
                </p>
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
