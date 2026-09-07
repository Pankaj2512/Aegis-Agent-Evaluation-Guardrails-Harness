"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { BarChart3 } from "lucide-react";
import { StatCard } from "@/components/ui/stat-card";
import { SectionCard } from "@/components/ui/section-card";
import { EmptyState } from "@/components/ui/empty-state";
import { Button } from "@/components/ui/button";
import { FilterChip } from "@/components/ui/filter-chip";
import { LoadingState } from "@/components/ui/loading-state";
import { ApiConnectionState } from "@/components/ui/connection-state";
import { api, type ObservabilityDashboardFilters } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import { formatCostUsd, formatDurationMs, formatTokens } from "@/lib/format";
import { categorize, CATEGORY_COLOR_VAR } from "@/components/canvas/nodes/category";
import { CostBreakdownTable } from "@/components/observability/CostBreakdownTable";

/** The breakdown dimension the operator is slicing spend by. */
export type CostDimension = "workflow" | "node_type" | "model";

const DIMENSION_LABEL: Record<CostDimension, string> = {
  workflow: "By workflow",
  node_type: "By node type",
  model: "By model",
};

const DIMENSIONS: CostDimension[] = ["workflow", "node_type", "model"];

export interface CostDashboardProps {
  /**
   * Active filters. Held in component state by default so the section works
   * standalone, but the parent (page / eventual URL sync) can hoist them.
   */
  filters?: ObservabilityDashboardFilters;
  onFiltersChange?: (next: ObservabilityDashboardFilters) => void;
  /** Where the empty-state / onboarding CTA should route (build a workflow). */
  primaryCtaHref?: string;
  primaryCtaLabel?: string;
}

/** Stable, order-independent hash of the active filters for the query key. */
function hashFilters(filters: ObservabilityDashboardFilters): string {
  const parts = [
    `status=${filters.status ?? ""}`,
    `workflow=${filters.workflow_id ?? ""}`,
    `start=${filters.start_date ?? ""}`,
    `end=${filters.end_date ?? ""}`,
  ];
  return parts.join("&");
}

/**
 * Cost & usage command-center. Renders total spend / tokens / latency
 * percentiles plus workflow / node-type / model breakdowns behind a dimension
 * selector. All chrome is monochrome; the only chroma is a <=2px category rule
 * on node-type rows and status hue on the "failed" aggregate.
 */
export function CostDashboard({
  filters: controlledFilters,
  onFiltersChange,
  primaryCtaHref = "/workflows/new",
  primaryCtaLabel = "Build a workflow",
}: CostDashboardProps) {
  const [uncontrolledFilters, setUncontrolledFilters] =
    useState<ObservabilityDashboardFilters>({});
  const filters = controlledFilters ?? uncontrolledFilters;
  const setFilters = onFiltersChange ?? setUncontrolledFilters;

  const [dimension, setDimension] = useState<CostDimension>("workflow");

  const filtersHash = useMemo(() => hashFilters(filters), [filters]);

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: queryKeys.observabilityDashboards(filtersHash),
    queryFn: () => api.getObservabilityDashboards(filters),
    staleTime: 30_000,
  });

  const hasActiveFilter = Boolean(
    filters.status || filters.workflow_id || filters.start_date || filters.end_date
  );

  if (isLoading) {
    return <LoadingState label="Loading cost & usage…" />;
  }

  if (isError) {
    return (
      <ApiConnectionState
        description="Cost & usage dashboards could not be loaded. Check the API target, then retry."
        error={error}
        onRetry={() => {
          void refetch();
        }}
      />
    );
  }

  const noData = !data || data.run_count === 0;

  if (noData) {
    return (
      <EmptyState
        icon={BarChart3}
        title="Trace every dollar your agents spend"
        description={
          hasActiveFilter
            ? "No runs match the active filters yet. Clear the filters or run a workflow to start collecting cost and usage."
            : "Run a workflow to start collecting spend, token, and latency telemetry across every model and node."
        }
        action={
          <Button asChild>
            <Link href={primaryCtaHref}>{primaryCtaLabel}</Link>
          </Button>
        }
        secondaryAction={
          hasActiveFilter ? (
            <Button variant="outline" onClick={() => setFilters({})}>
              Clear filters
            </Button>
          ) : undefined
        }
      />
    );
  }

  const { total_cost_usd, total_tokens, latency_ms, run_count } = data;

  const activeFilterChips = (
    <>
      {filters.status && (
        <FilterChip
          label={`status: ${filters.status} ×`}
          active
          onClick={() => setFilters({ ...filters, status: undefined })}
        />
      )}
      {filters.workflow_id && (
        <FilterChip
          label="workflow ×"
          active
          onClick={() => setFilters({ ...filters, workflow_id: undefined })}
        />
      )}
      {(filters.start_date || filters.end_date) && (
        <FilterChip
          label="date range ×"
          active
          onClick={() =>
            setFilters({ ...filters, start_date: undefined, end_date: undefined })
          }
        />
      )}
    </>
  );

  return (
    <div className="space-y-4">
      {hasActiveFilter && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-mono text-2xs uppercase tracking-wide text-subtle">
            Filters
          </span>
          {activeFilterChips}
        </div>
      )}

      {/* Headline aggregates — the window these tiles cover is stated out loud
          so they can be reconciled against the Trust / Triage tabs. */}
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-micro">Cost &amp; usage</p>
        <p className="font-mono text-2xs tabular-nums text-subtle">
          Window: {run_count.toLocaleString()} runs ·{" "}
          {latency_ms.sample_size.toLocaleString()} latency samples
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        <StatCard
          label="Total spend"
          value={formatCostUsd(total_cost_usd)}
          trend={`${run_count.toLocaleString()} runs`}
        />
        <StatCard label="Total tokens" value={formatTokens(total_tokens)} trend="in + out" />
        <StatCard
          label="Latency p50"
          value={formatDurationMs(latency_ms.p50)}
          trend={`${latency_ms.sample_size.toLocaleString()} samples`}
        />
        <StatCard
          label="Latency p95"
          value={formatDurationMs(latency_ms.p95)}
          trend={`${latency_ms.sample_size.toLocaleString()} samples`}
        />
        <StatCard
          className="col-span-2 sm:col-span-1"
          label="Latency p99"
          value={formatDurationMs(latency_ms.p99)}
          trend={`${latency_ms.sample_size.toLocaleString()} samples`}
        />
      </div>

      {/* Dimension selector + breakdown */}
      <SectionCard
        title="Cost breakdown"
        description="Slice spend and usage across workflows, node types, and models."
        flush
        actions={
          <div className="flex items-center gap-1.5">
            {DIMENSIONS.map((dim) => (
              <FilterChip
                key={dim}
                label={DIMENSION_LABEL[dim]}
                active={dimension === dim}
                onClick={() => setDimension(dim)}
              />
            ))}
          </div>
        }
      >
        {dimension === "workflow" && (
          <CostBreakdownTable
            aria-label="Cost by workflow"
            columns={[
              { key: "name", header: "Workflow", align: "left" },
              { key: "runs", header: "Runs", align: "right", aggregate: "sum" },
              { key: "failed", header: "Failed", align: "right", aggregate: "sum", status: true },
              { key: "tokens", header: "Tokens", align: "right", aggregate: "sum" },
              { key: "cost", header: "Cost", align: "right", aggregate: "sumCost" },
            ]}
            rows={data.by_workflow.map((row) => ({
              id: row.workflow_id,
              cells: {
                name: row.workflow_name || row.workflow_id,
                runs: row.run_count,
                failed: row.failed_count,
                tokens: row.total_tokens,
                cost: row.cost_usd,
              },
            }))}
          />
        )}

        {dimension === "node_type" && (
          <CostBreakdownTable
            aria-label="Usage by node type"
            columns={[
              { key: "name", header: "Node type", align: "left" },
              { key: "runs", header: "Executions", align: "right", aggregate: "sum" },
              { key: "failed", header: "Failed", align: "right", aggregate: "sum", status: true },
              { key: "latency", header: "Avg latency", align: "right" },
            ]}
            rows={data.by_node_type.map((row) => ({
              id: row.node_type,
              accentVar: CATEGORY_COLOR_VAR[categorize(row.node_type)],
              cells: {
                name: row.node_type,
                runs: row.count,
                failed: row.failed_count,
                latency: formatDurationMs(row.avg_latency_ms),
              },
            }))}
          />
        )}

        {dimension === "model" && (
          <CostBreakdownTable
            aria-label="Cost by model"
            columns={[
              { key: "name", header: "Model", align: "left" },
              { key: "calls", header: "Calls", align: "right", aggregate: "sum" },
              { key: "tokens", header: "Tokens", align: "right", aggregate: "sum" },
              { key: "latency", header: "Avg latency", align: "right" },
              { key: "cost", header: "Cost", align: "right", aggregate: "sumCost" },
            ]}
            rows={data.by_model.map((row) => ({
              id: row.model,
              cells: {
                name: row.model,
                calls: row.call_count,
                tokens: row.total_tokens,
                latency: formatDurationMs(row.avg_latency_ms),
                cost: row.cost_usd,
              },
            }))}
          />
        )}
      </SectionCard>
    </div>
  );
}
