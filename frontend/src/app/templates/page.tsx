"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { LayoutTemplate, Loader2, Search, Upload, UserCheck } from "lucide-react";
import { ApiConnectionState } from "@/components/ui/connection-state";
import { EmptyState } from "@/components/ui/empty-state";
import { FilterChip } from "@/components/ui/filter-chip";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { GlassCard } from "@/components/ui/glass-card";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { categorize, CATEGORY_COLOR_VAR } from "@/components/canvas/nodes/category";
import { HoverLift } from "@/components/motion";
import { api } from "@/lib/api";
import { pluralize } from "@/lib/format";
import { queryKeys } from "@/lib/query-keys";
import type { WorkflowGraph, WorkflowTemplate } from "@/types/workflow";

type TemplateFilter = "all" | "eval" | "guardrail" | "approval";

const FILTER_OPTIONS: Array<{ id: TemplateFilter; label: string }> = [
  { id: "all", label: "All" },
  { id: "eval", label: "Evaluation" },
  { id: "guardrail", label: "Guardrails" },
  { id: "approval", label: "Human approval" },
];

const FILTER_IDS = new Set<TemplateFilter>(["all", "eval", "guardrail", "approval"]);

/** How many of the first templates render in the larger "Recommended" row. */
const FEATURED_COUNT = 3;

function templateFlags(template: WorkflowTemplate) {
  const nodes = template.graph_json.nodes;
  return {
    hasEval: nodes.some((n) => n.data.nodeType === "evaluation"),
    hasGuardrail: nodes.some((n) => n.data.nodeType === "guardrail"),
    hasApproval: nodes.some((n) => n.data.nodeType === "human_approval"),
  };
}

/** Coarse complexity hint from node count — a quiet mono caption, not a badge. */
function complexityLabel(nodeCount: number): string {
  if (nodeCount <= 4) return "Starter";
  if (nodeCount <= 8) return "Standard";
  return "Advanced";
}

function previewLayout(graph: WorkflowGraph) {
  const nodes = graph.nodes.slice(0, 7);
  const xs = nodes.map((node) => node.position.x);
  const ys = nodes.map((node) => node.position.y);
  const minX = Math.min(...xs, 0);
  const maxX = Math.max(...xs, 1);
  const minY = Math.min(...ys, 0);
  const maxY = Math.max(...ys, 1);
  const xRange = Math.max(maxX - minX, 1);
  const yRange = Math.max(maxY - minY, 1);

  return nodes.map((node, index) => {
    const fallbackX = nodes.length <= 1 ? 50 : 14 + (index / (nodes.length - 1)) * 72;
    const x = xRange > 1 ? 12 + ((node.position.x - minX) / xRange) * 76 : fallbackX;
    const y = yRange > 1 ? 18 + ((node.position.y - minY) / yRange) * 58 : 24 + (index % 3) * 22;
    return {
      ...node,
      x: Math.min(82, Math.max(8, x)),
      y: Math.min(74, Math.max(12, y)),
    };
  });
}

function TemplatePreview({ template, tall }: { template: WorkflowTemplate; tall?: boolean }) {
  const nodes = previewLayout(template.graph_json);
  const edgeCount = template.graph_json.edges.length;
  const visibleNodeIds = new Set(nodes.map((node) => node.id));
  const visibleEdges = template.graph_json.edges
    .filter((edge) => visibleNodeIds.has(edge.source) && visibleNodeIds.has(edge.target))
    .slice(0, 8);
  const nodeById = new Map(nodes.map((node) => [node.id, node]));

  return (
    <div className="border-b border-border-mid bg-surface-input p-3">
      <div
        className={`relative overflow-hidden rounded-lg border border-border bg-bg ${
          tall ? "h-44" : "h-36"
        }`}
      >
        <div
          className="absolute inset-0 opacity-70"
          style={{
            backgroundImage:
              "radial-gradient(var(--canvas-grid) 1px, transparent 1px)",
            backgroundSize: "14px 14px",
          }}
        />
        <svg className="absolute inset-0 h-full w-full" aria-hidden="true">
          {visibleEdges.map((edge) => {
            const source = nodeById.get(edge.source);
            const target = nodeById.get(edge.target);
            if (!source || !target) return null;
            return (
              <line
                key={edge.id}
                x1={`${source.x}%`}
                y1={`${source.y}%`}
                x2={`${target.x}%`}
                y2={`${target.y}%`}
                stroke="var(--canvas-edge)"
                strokeWidth="1.4"
                strokeLinecap="round"
                strokeDasharray={edge.label ? "3 4" : undefined}
              />
            );
          })}
        </svg>
        <div className="absolute inset-0">
          {nodes.map((node, index) => (
            <span
              key={node.id}
              title={node.data.label || node.data.nodeType}
              className="absolute h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-[3px] border border-border shadow-elev-1"
              style={{
                left: `${node.x}%`,
                top: `${node.y}%`,
                zIndex: 10 + index,
                background: CATEGORY_COLOR_VAR[categorize(node.data.nodeType)],
              }}
            />
          ))}
        </div>
      </div>
      <div className="mt-2.5 flex items-center gap-3 font-mono text-2xs tabular-nums text-subtle">
        <span>{pluralize(template.graph_json.nodes.length, "node")}</span>
        <span aria-hidden className="h-2.5 w-px bg-border-mid" />
        <span>{pluralize(edgeCount, "edge")}</span>
      </div>
    </div>
  );
}

/** Quiet mono capability captions + provenance shown on every card. */
function TemplateMeta({ template }: { template: WorkflowTemplate }) {
  const flags = templateFlags(template);
  const nodeCount = template.graph_json.nodes.length;
  const caps = [
    complexityLabel(nodeCount),
    flags.hasEval && "eval",
    flags.hasGuardrail && "guardrails",
    flags.hasApproval && "approval",
  ].filter((v): v is string => Boolean(v));

  const isBuiltin = template.builtin ?? !template.author;
  const usage = template.usage_count ?? 0;

  return (
    <div className="space-y-2 border-t border-border-mid pt-3">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 font-mono text-2xs text-subtle">
        {caps.map((cap, index) => (
          <span key={cap} className="flex items-center gap-2">
            {index > 0 && <span aria-hidden className="h-2.5 w-px bg-border-mid" />}
            <span>{cap}</span>
          </span>
        ))}
      </div>
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 font-mono text-2xs text-subtle tabular-nums">
        <span>{isBuiltin ? "Built-in" : `by ${template.author}`}</span>
        {usage > 0 && (
          <>
            <span aria-hidden className="h-2.5 w-px bg-border-mid" />
            <span>{pluralize(usage, "use")}</span>
          </>
        )}
      </div>
    </div>
  );
}

function CapabilityBadges({ template }: { template: WorkflowTemplate }) {
  const flags = templateFlags(template);
  if (!flags.hasEval && !flags.hasGuardrail && !flags.hasApproval) return null;
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {flags.hasEval && (
        <Badge variant="outline">
          <span className="mr-1.5 h-1.5 w-1.5 rounded-full bg-cat-quality" aria-hidden />
          Eval
        </Badge>
      )}
      {flags.hasGuardrail && (
        <Badge variant="outline">
          <span className="mr-1.5 h-1.5 w-1.5 rounded-full bg-cat-quality" aria-hidden />
          Guardrails
        </Badge>
      )}
      {flags.hasApproval && (
        <Badge variant="outline">
          <UserCheck className="mr-1 h-3 w-3" />
          Approval
        </Badge>
      )}
    </div>
  );
}

interface TemplateCardProps {
  template: WorkflowTemplate;
  featured?: boolean;
  creatingId: string | null;
  onUse: (template: WorkflowTemplate) => void;
}

function TemplateCard({ template, featured, creatingId, onUse }: TemplateCardProps) {
  return (
    <HoverLift className="h-full">
      <GlassCard
        role="button"
        tabIndex={0}
        aria-label={`Use template ${template.name}`}
        aria-disabled={creatingId !== null}
        className="focus-ring flex h-full cursor-pointer flex-col overflow-hidden transition-colors duration-1 hover:border-border-strong hover:bg-surface-hover"
        onClick={() => onUse(template)}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            onUse(template);
          }
        }}
      >
        <TemplatePreview template={template} tall={featured} />
        <div className="flex flex-1 flex-col gap-3 p-4">
          <div className="min-w-0 space-y-1.5">
            <div className="flex items-start justify-between gap-2">
              <h2 className="text-sm font-semibold leading-5 text-foreground">{template.name}</h2>
              <CapabilityBadges template={template} />
            </div>
            <p
              className={`text-xs leading-5 text-muted ${
                featured ? "line-clamp-3" : "line-clamp-2"
              }`}
            >
              {template.description}
            </p>
          </div>
          <TemplateMeta template={template} />
          <Button
            className="mt-auto w-full"
            onClick={(event) => {
              event.stopPropagation();
              onUse(template);
            }}
            disabled={creatingId === template.id}
          >
            {creatingId === template.id ? "Creating…" : "Use template"}
          </Button>
        </div>
      </GlassCard>
    </HoverLift>
  );
}

function PublishTemplateDialog() {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [workflowId, setWorkflowId] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [publishing, setPublishing] = useState(false);

  const {
    data: workflows = [],
    isLoading,
    isError,
  } = useQuery({
    queryKey: queryKeys.workflows,
    queryFn: api.listWorkflows,
    enabled: open,
  });

  // Prefill the template name from the chosen workflow when name is untouched.
  const selected = workflows.find((w) => w.id === workflowId);

  const reset = () => {
    setWorkflowId("");
    setName("");
    setDescription("");
  };

  const handlePublish = async () => {
    if (!workflowId) {
      toast.error("Choose a workflow to publish");
      return;
    }
    if (!name.trim()) {
      toast.error("Template name is required");
      return;
    }
    setPublishing(true);
    try {
      const created = await api.createTemplate({
        name: name.trim(),
        description: description.trim() || undefined,
        workflow_id: workflowId,
      });
      await queryClient.invalidateQueries({ queryKey: queryKeys.templates });
      toast.success(`Published "${created.name}" as a template`);
      setOpen(false);
      reset();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to publish template");
    } finally {
      setPublishing(false);
    }
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) reset();
      }}
    >
      <Button size="sm" className="gap-1.5" onClick={() => setOpen(true)}>
        <Upload className="h-3.5 w-3.5" />
        Publish as template
      </Button>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Publish a workflow as a template</DialogTitle>
          <DialogDescription>
            Share a starting graph. Others can create their own workflow from it — usage is
            tracked so the most-used templates rise to the top.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-1.5">
            <label
              htmlFor="publish-workflow"
              className="text-2xs font-medium uppercase tracking-wider text-muted"
            >
              Workflow
            </label>
            {isLoading ? (
              <div className="skeleton h-9 w-full rounded-md" />
            ) : isError ? (
              <p className="text-xs text-destructive">Could not load workflows.</p>
            ) : workflows.length === 0 ? (
              <p className="text-xs text-muted">No workflows yet — build one first.</p>
            ) : (
              <select
                id="publish-workflow"
                value={workflowId}
                onChange={(event) => {
                  const id = event.target.value;
                  setWorkflowId(id);
                  const wf = workflows.find((w) => w.id === id);
                  if (wf && !name.trim()) setName(wf.name);
                }}
                className="focus-ring h-9 w-full rounded-md border border-border bg-surface-input px-3 text-sm text-foreground"
              >
                <option value="">Select a workflow…</option>
                {workflows.map((wf) => (
                  <option key={wf.id} value={wf.id}>
                    {wf.name}
                  </option>
                ))}
              </select>
            )}
          </div>

          <div className="space-y-1.5">
            <label
              htmlFor="publish-name"
              className="text-2xs font-medium uppercase tracking-wider text-muted"
            >
              Template name
            </label>
            <Input
              id="publish-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder={selected?.name ?? "Support triage starter"}
            />
          </div>

          <div className="space-y-1.5">
            <label
              htmlFor="publish-description"
              className="text-2xs font-medium uppercase tracking-wider text-muted"
            >
              Description
            </label>
            <Input
              id="publish-description"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="What this template is for (optional)"
            />
          </div>
        </div>

        <DialogFooter>
          <DialogClose asChild>
            <Button variant="outline" size="sm">
              Cancel
            </Button>
          </DialogClose>
          <Button
            size="sm"
            className="gap-1.5"
            onClick={handlePublish}
            disabled={publishing || !workflowId || !name.trim()}
          >
            {publishing ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                Publishing…
              </>
            ) : (
              "Publish template"
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default function TemplatesPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [creatingId, setCreatingId] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<TemplateFilter>("all");

  // Honour an inbound ?filter= from cross-page CTAs (e.g. the guardrails banner).
  // Read from window after mount (not useSearchParams) so the route stays
  // statically renderable and there's no hydration mismatch.
  useEffect(() => {
    const incoming = new URLSearchParams(window.location.search).get("filter");
    if (incoming && FILTER_IDS.has(incoming as TemplateFilter)) {
      setFilter(incoming as TemplateFilter);
    }
  }, []);

  const {
    data: templates = [],
    isLoading: loading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: queryKeys.templates,
    queryFn: api.listTemplates,
  });

  const filteredTemplates = useMemo(() => {
    const query = search.trim().toLowerCase();
    return templates.filter((template) => {
      const flags = templateFlags(template);
      if (filter === "eval" && !flags.hasEval) return false;
      if (filter === "guardrail" && !flags.hasGuardrail) return false;
      if (filter === "approval" && !flags.hasApproval) return false;
      if (!query) return true;
      return (
        template.name.toLowerCase().includes(query) ||
        template.description.toLowerCase().includes(query) ||
        template.id.toLowerCase().includes(query)
      );
    });
  }, [templates, search, filter]);

  const templateStats = useMemo(() => {
    return templates.reduce(
      (acc, template) => {
        const flags = templateFlags(template);
        acc.nodes += template.graph_json.nodes.length;
        if (flags.hasEval) acc.eval += 1;
        if (flags.hasGuardrail) acc.guardrail += 1;
        if (flags.hasApproval) acc.approval += 1;
        return acc;
      },
      { nodes: 0, eval: 0, guardrail: 0, approval: 0 }
    );
  }, [templates]);

  // The recommended row is only meaningful in the default (unfiltered) view.
  const isDefaultView = filter === "all" && search.trim() === "";
  const featured = isDefaultView ? filteredTemplates.slice(0, FEATURED_COUNT) : [];
  const rest = isDefaultView ? filteredTemplates.slice(FEATURED_COUNT) : filteredTemplates;

  const handleUseTemplate = async (template: WorkflowTemplate) => {
    if (creatingId) return;
    setCreatingId(template.id);
    try {
      // useTemplate increments usage_count and returns the canonical graph.
      const used = await api.useTemplate(template.id);
      const workflow = await api.createWorkflow({
        name: template.name,
        description: template.description,
        graph_json: used.graph_json,
      });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.workflows }),
        queryClient.invalidateQueries({ queryKey: queryKeys.observabilitySummary }),
        queryClient.invalidateQueries({ queryKey: queryKeys.templates }),
      ]);
      toast.success(`Created workflow from "${template.name}"`);
      router.push(`/workflows/${workflow.id}`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to create workflow");
    } finally {
      setCreatingId(null);
    }
  };

  if (loading) {
    return (
      <div className="page-container space-y-6">
        <div className="space-y-3">
          <div className="skeleton h-7 w-40" />
          <div className="skeleton h-4 w-96 max-w-full" />
        </div>
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, index) => (
            <div key={index} className="panel space-y-4 p-5">
              <div className="flex items-start gap-3">
                <div className="skeleton h-10 w-10 rounded-lg" />
                <div className="flex-1 space-y-2">
                  <div className="skeleton h-5 w-3/4" />
                  <div className="skeleton h-4 w-full" />
                  <div className="skeleton h-4 w-5/6" />
                </div>
              </div>
              <div className="flex gap-2">
                <div className="skeleton h-5 w-16 rounded-full" />
                <div className="skeleton h-5 w-20 rounded-full" />
              </div>
              <div className="skeleton h-9 w-full rounded-lg" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="page-container">
        <ApiConnectionState
          description="Templates could not be loaded from the backend. Check the API target, then retry."
          error={error}
          onRetry={() => {
            void refetch();
          }}
        />
      </div>
    );
  }

  return (
    <div className="page-container space-y-6">
      <PageHeader
        title="Templates"
        description="Starter graphs for evaluation, guardrails, approval, and integrations."
        actions={<PublishTemplateDialog />}
      />

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="relative w-full max-w-md">
          <Search
            className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted"
            aria-hidden="true"
          />
          <Input
            id="template-search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search templates…"
            aria-label="Search templates"
            className="pl-9"
          />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filter templates">
            {FILTER_OPTIONS.map((option) => {
              const count =
                option.id === "all"
                  ? templates.length
                  : option.id === "eval"
                    ? templateStats.eval
                    : option.id === "guardrail"
                      ? templateStats.guardrail
                      : templateStats.approval;
              return (
                <FilterChip
                  key={option.id}
                  label={`${option.label} ${count}`}
                  active={filter === option.id}
                  onClick={() => setFilter(option.id)}
                />
              );
            })}
          </div>
          <p className="font-mono text-xs text-muted tabular-nums">
            {filteredTemplates.length}/{templates.length}
          </p>
        </div>
      </div>

      {filteredTemplates.length === 0 ? (
        <EmptyState
          icon={LayoutTemplate}
          title="No templates found"
          description="Try a different search term or filter."
          action={
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setSearch("");
                setFilter("all");
              }}
            >
              Clear filters
            </Button>
          }
        />
      ) : (
        <div className="space-y-6">
          {featured.length > 0 && (
            <section className="space-y-3">
              <p className="font-mono text-2xs uppercase tracking-wider text-subtle">
                Recommended
              </p>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {featured.map((template) => (
                  <TemplateCard
                    key={template.id}
                    template={template}
                    featured
                    creatingId={creatingId}
                    onUse={handleUseTemplate}
                  />
                ))}
              </div>
            </section>
          )}

          {rest.length > 0 && (
            <section className="space-y-3">
              {featured.length > 0 && (
                <p className="font-mono text-2xs uppercase tracking-wider text-subtle">
                  All templates
                </p>
              )}
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {rest.map((template) => (
                  <TemplateCard
                    key={template.id}
                    template={template}
                    creatingId={creatingId}
                    onUse={handleUseTemplate}
                  />
                ))}
              </div>
            </section>
          )}
        </div>
      )}
    </div>
  );
}
