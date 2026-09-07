"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, ListChecks, Shield, ShieldCheck, Sparkles } from "lucide-react";
import { Alert } from "@/components/ui/alert";
import { EmptyState } from "@/components/ui/empty-state";
import { LoadingState } from "@/components/ui/loading-state";
import { EvalScoresChart } from "@/components/results/EvalScoresChart";
import { EvalTrendChart } from "@/components/results/EvalTrendChart";
import { GuardrailEventsPanel } from "@/components/results/GuardrailEventsPanel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { GlassCard } from "@/components/ui/glass-card";
import { ExperimentsPanel } from "@/components/canvas/ExperimentsPanel";
import { PanelSection, PanelStat, PanelStatGrid } from "@/components/canvas/panel/PanelSection";
import { api } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";

interface WorkflowQualityPanelProps {
  workflowId: string;
  currentVersionId?: string;
}

export function WorkflowQualityPanel({ workflowId, currentVersionId }: WorkflowQualityPanelProps) {
  const {
    data: quality,
    isLoading: loading,
    error,
    refetch,
  } = useQuery({
    queryKey: queryKeys.workflowQuality(workflowId),
    queryFn: () => api.getWorkflowQuality(workflowId),
  });

  if (loading) {
    return <LoadingState variant="card" label="Loading quality metrics…" />;
  }

  if (error) {
    return (
      <div className="space-y-2">
        <p className="text-sm text-destructive">
          {error instanceof Error ? error.message : "Failed to load quality metrics"}
        </p>
        <Button variant="outline" size="sm" onClick={() => void refetch()}>
          Retry
        </Button>
      </div>
    );
  }

  if (!quality) return null;

  const avgDimensionScores = quality.avg_dimension_scores || {};
  const evalTrend = quality.eval_trend || [];
  const graphConfig = quality.graph_config || {
    eval_node_count: 0,
    guardrail_node_count: 0,
    has_quality_nodes: false,
    eval_nodes: [],
    guardrail_nodes: [],
  };
  const guardrailStats = quality.guardrail_stats || {
    passed: 0,
    warned: 0,
    failed: 0,
    blocked_runs: 0,
    total_events: 0,
  };
  const recentGuardrailEvents = quality.recent_guardrail_events || [];

  const dimensionScores = {
    faithfulness: avgDimensionScores.faithfulness,
    helpfulness: avgDimensionScores.helpfulness,
    relevance: avgDimensionScores.relevance,
    toxicity: avgDimensionScores.toxicity,
    aggregate_score:
      evalTrend.length > 0
        ? evalTrend[evalTrend.length - 1]?.aggregate
        : undefined,
  };

  return (
    <div className="space-y-4">
      <PanelSection
        title="Quality"
        action={
          <Button variant="ghost" size="sm" onClick={() => void refetch()}>
            Refresh
          </Button>
        }
      >
        {!graphConfig.has_quality_nodes && (
          <p className="rounded-lg border border-dashed border-border px-3 py-2 text-xs text-muted">
            Add Evaluation or Guardrail nodes to track quality on this workflow.
          </p>
        )}

        {graphConfig.has_quality_nodes && (
          <div className="flex flex-wrap gap-2">
            {graphConfig.eval_node_count > 0 && (
              <Badge variant="accent">
                <Sparkles className="mr-1 h-3 w-3" />
                {graphConfig.eval_node_count} eval
              </Badge>
            )}
            {graphConfig.guardrail_node_count > 0 && (
              <Badge variant="outline">
                <Shield className="mr-1 h-3 w-3" />
                {graphConfig.guardrail_node_count} guardrails
              </Badge>
            )}
          </div>
        )}
      </PanelSection>

      {quality.eval_regression?.detected && (
        <Alert
          variant="warning"
          icon={AlertTriangle}
          title="Eval regression detected"
          description={quality.eval_regression.message}
          actions={
            quality.eval_regression.latest_run_id ? (
              <Link
                href={`/runs/${quality.eval_regression.latest_run_id}`}
                className="text-primary hover:underline"
              >
                View latest run
              </Link>
            ) : undefined
          }
        />
      )}

      {quality.eval_run_count > 0 ? (
        <GlassCard className="overflow-hidden p-0">
          <CardHeader className="bg-surface-input/80 shadow-[inset_0_1px_0_var(--surface-highlight)]">
            <div className="flex items-center gap-2">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg border border-warning/25 bg-warning/10 text-warning">
                <ListChecks className="h-4 w-4" />
              </span>
              <CardTitle>Evaluation</CardTitle>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex flex-wrap gap-2 text-xs">
              <Badge variant="outline">{quality.eval_run_count} eval runs</Badge>
              {quality.eval_pass_rate != null && (
                <Badge variant="success">{Math.round(quality.eval_pass_rate * 100)}% pass rate</Badge>
              )}
              {quality.eval_fail_count > 0 && (
                <Badge variant="destructive">{quality.eval_fail_count} below threshold</Badge>
              )}
            </div>
            <EvalTrendChart points={evalTrend} />
            {dimensionScores.aggregate_score != null && (
              <EvalScoresChart scores={dimensionScores} compact />
            )}
          </CardContent>
        </GlassCard>
      ) : (
        <EmptyState
          compact
          icon={Sparkles}
          title="No evaluation scores yet"
          description="Run the workflow with an Evaluation node to populate this chart."
        />
      )}

      {guardrailStats.total_events > 0 && (
        <GlassCard className="overflow-hidden p-0">
          <CardHeader className="bg-surface-input/80 shadow-[inset_0_1px_0_var(--surface-highlight)]">
            <div className="flex items-center gap-2">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg border border-success/25 bg-success/10 text-success">
                <ShieldCheck className="h-4 w-4" />
              </span>
              <CardTitle>Guardrail activity</CardTitle>
            </div>
          </CardHeader>
          <CardContent className="space-y-2">
            <PanelStatGrid>
              <PanelStat label="Passed" value={guardrailStats.passed} tone="success" />
              <PanelStat label="Warned" value={guardrailStats.warned} tone="warning" />
              <PanelStat label="Failed" value={guardrailStats.failed} tone="destructive" />
            </PanelStatGrid>
            {recentGuardrailEvents.length > 0 && (
              <GuardrailEventsPanel events={recentGuardrailEvents} compact />
            )}
          </CardContent>
        </GlassCard>
      )}

      {graphConfig.eval_nodes.length > 0 && (
        <PanelSection title="Eval nodes">
          <div className="space-y-1">
            {graphConfig.eval_nodes.map((node) => (
              <div key={node.node_id} className="text-xs text-foreground">
                {node.label}
                {node.threshold != null && (
                  <span className="text-muted"> · threshold {node.threshold}</span>
                )}
              </div>
            ))}
          </div>
        </PanelSection>
      )}

      <PanelSection title="Experiments">
        <ExperimentsPanel workflowId={workflowId} currentVersionId={currentVersionId} />
      </PanelSection>

      <Button asChild variant="outline" size="sm" className="w-full">
        <Link href="/observability">
          Full observability
        </Link>
      </Button>
    </div>
  );
}
