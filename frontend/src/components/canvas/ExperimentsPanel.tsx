"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronRight, FlaskConical, Plus } from "lucide-react";
import { EmptyState } from "@/components/ui/empty-state";
import { LoadingState } from "@/components/ui/loading-state";
import { PanelSection } from "@/components/canvas/panel/PanelSection";
import { formatFullTimestamp, formatRelativeTime } from "@/lib/format-date";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { api } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import { formatCostUsd } from "@/lib/format";
import type { Experiment } from "@/types/workflow";

interface ExperimentsPanelProps {
  workflowId: string;
  currentVersionId?: string;
}

function verdictBadge(exp: Experiment) {
  if (exp.status !== "completed") {
    return <Badge variant={exp.status === "failed" ? "destructive" : "outline"}>{exp.status}</Badge>;
  }
  const verdict = exp.summary?.verdict;
  if (!verdict) {
    return <Badge variant="outline">batch</Badge>;
  }
  return (
    <Badge variant={verdict.passed ? "success" : "destructive"}>
      {verdict.passed ? "no regression" : "regression"}
    </Badge>
  );
}

/** Compact inline failure row: a side panel is too dense for a full error state,
 *  but a silent empty list would read as "you have none of these". */
function InlineQueryError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="flex items-center justify-between gap-2 rounded-md border border-destructive/25 bg-destructive/10 px-2.5 py-1.5">
      <p className="text-xs text-destructive">{message}</p>
      <Button variant="ghost" size="xs" onClick={onRetry}>
        Retry
      </Button>
    </div>
  );
}

/** Golden datasets + batch/regression experiments for one workflow. */
export function ExperimentsPanel({ workflowId, currentVersionId }: ExperimentsPanelProps) {
  const queryClient = useQueryClient();
  const [newDatasetName, setNewDatasetName] = useState("");
  const [newItemInput, setNewItemInput] = useState("");
  const [selectedDataset, setSelectedDataset] = useState<string>("");
  const [baselineVersion, setBaselineVersion] = useState<string>("");
  const [captureFilter, setCaptureFilter] = useState<"recent" | "failed" | "low_eval">("failed");
  /** One pending action at a time keeps every mutation double-click-safe. */
  const [pending, setPending] = useState<
    "dataset" | "item" | "batch" | "regression" | "capture" | null
  >(null);

  const {
    data: datasets = [],
    isError: datasetsError,
    refetch: refetchDatasets,
  } = useQuery({
    queryKey: ["datasets", workflowId],
    queryFn: () => api.listDatasets(workflowId),
  });
  const {
    data: experiments = [],
    isLoading: experimentsLoading,
    isError: experimentsError,
    refetch: refetchExperiments,
  } = useQuery({
    queryKey: ["experiments", workflowId],
    queryFn: () => api.listExperiments(workflowId),
    refetchInterval: (query) =>
      (query.state.data || []).some((e) => ["pending", "running"].includes(e.status))
        ? 4000
        : false,
  });
  const {
    data: versions = [],
    isError: versionsError,
    refetch: refetchVersions,
  } = useQuery({
    queryKey: queryKeys.workflowVersions(workflowId),
    queryFn: () => api.listVersions(workflowId),
  });

  const activeDataset = selectedDataset || datasets[0]?.id || "";

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["datasets", workflowId] });
    void queryClient.invalidateQueries({ queryKey: ["experiments", workflowId] });
  };

  const createDataset = async () => {
    if (!newDatasetName.trim() || pending) return;
    setPending("dataset");
    try {
      await api.createDataset(workflowId, newDatasetName.trim());
      setNewDatasetName("");
      refresh();
      toast.success("Dataset created");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to create dataset");
    } finally {
      setPending(null);
    }
  };

  const addItem = async () => {
    if (!activeDataset || !newItemInput.trim() || pending) return;
    setPending("item");
    try {
      await api.addDatasetItem(activeDataset, { input_text: newItemInput.trim() });
      setNewItemInput("");
      refresh();
      toast.success("Item added");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to add item");
    } finally {
      setPending(null);
    }
  };

  const captureRuns = async () => {
    if (!activeDataset || pending) return;
    setPending("capture");
    try {
      const result = await api.captureRunsToDataset(activeDataset, {
        filter: captureFilter,
        limit: 20,
      });
      refresh();
      toast.success(
        result.added > 0
          ? `Captured ${result.added} run${result.added === 1 ? "" : "s"}` +
              (result.skipped ? ` (${result.skipped} already in set)` : "")
          : "No new runs to capture"
      );
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to capture runs");
    } finally {
      setPending(null);
    }
  };

  const launch = async (kind: "batch" | "regression") => {
    if (pending) return;
    if (!activeDataset || !currentVersionId) {
      toast.error("Save the workflow and pick a dataset first");
      return;
    }
    if (kind === "regression" && !baselineVersion) {
      toast.error("Pick a baseline version");
      return;
    }
    setPending(kind);
    try {
      await api.createExperiment({
        workflow_id: workflowId,
        dataset_id: activeDataset,
        version_id: currentVersionId,
        kind,
        baseline_version_id: kind === "regression" ? baselineVersion : undefined,
      });
      refresh();
      toast.success(kind === "regression" ? "Regression check started" : "Batch run started");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to start experiment");
    } finally {
      setPending(null);
    }
  };

  return (
    <div className="space-y-4">
      <PanelSection title="Datasets">
        <div className="space-y-2 rounded-md border border-border bg-surface-input p-3">
        {datasetsError && (
          <InlineQueryError
            message="Couldn't load datasets"
            onRetry={() => void refetchDatasets()}
          />
        )}
        {datasets.length > 0 && (
          <Select value={activeDataset} onValueChange={setSelectedDataset}>
            <SelectTrigger className="w-full" aria-label="Dataset">
              <SelectValue placeholder="Select dataset" />
            </SelectTrigger>
            <SelectContent>
              {datasets.map((d) => (
                <SelectItem key={d.id} value={d.id}>
                  {d.name} ({d.item_count})
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
        <div className="flex gap-2">
          <Input
            value={newDatasetName}
            onChange={(e) => setNewDatasetName(e.target.value)}
            placeholder="New dataset name…"
            aria-label="New dataset name"
            size="sm"
          />
          <Button
            variant="outline"
            size="sm"
            onClick={createDataset}
            disabled={pending === "dataset" || !newDatasetName.trim()}
            aria-label="Create dataset"
          >
            <Plus className="h-3.5 w-3.5" />
          </Button>
        </div>
        {activeDataset && (
          <div className="flex gap-2">
            <Input
              value={newItemInput}
              onChange={(e) => setNewItemInput(e.target.value)}
              placeholder="Add test input…"
              aria-label="Add test input"
              size="sm"
              onKeyDown={(e) => {
                if (e.key === "Enter") void addItem();
              }}
            />
            <Button
              variant="outline"
              size="sm"
              onClick={addItem}
              disabled={pending === "item" || !newItemInput.trim()}
            >
              {pending === "item" ? "Adding…" : "Add"}
            </Button>
          </div>
        )}
        {activeDataset && (
          <div className="flex gap-2 border-t border-border pt-2">
            <Select
              value={captureFilter}
              onValueChange={(v) => setCaptureFilter(v as "recent" | "failed" | "low_eval")}
            >
              <SelectTrigger size="sm" className="flex-1" aria-label="Capture filter">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="failed">Failed runs</SelectItem>
                <SelectItem value="low_eval">Low-eval runs</SelectItem>
                <SelectItem value="recent">Recent runs</SelectItem>
              </SelectContent>
            </Select>
            <Button
              variant="outline"
              size="sm"
              onClick={captureRuns}
              disabled={pending === "capture"}
              aria-label="Capture runs into dataset"
            >
              {pending === "capture" ? "Capturing…" : "Capture"}
            </Button>
          </div>
        )}
        </div>
      </PanelSection>

      <PanelSection title="Run experiment">
        <div className="space-y-2 rounded-md border border-border bg-surface-input p-3">
        <p className="text-caption">
          Batch scores the current version on the dataset. Regression compares it against a
          baseline version and renders a pass/fail verdict.
        </p>
        <div className="flex flex-col gap-2">
          <Button
            variant="outline"
            size="sm"
            className="w-full justify-center"
            onClick={() => void launch("batch")}
            disabled={pending !== null}
          >
            <FlaskConical className="h-3.5 w-3.5" />
            {pending === "batch" ? "Starting…" : "Batch"}
          </Button>
          {versionsError && (
            <InlineQueryError
              message="Couldn't load versions"
              onRetry={() => void refetchVersions()}
            />
          )}
          <Select value={baselineVersion} onValueChange={setBaselineVersion}>
            <SelectTrigger size="sm" className="w-full min-w-0" aria-label="Baseline version">
              <SelectValue placeholder="Baseline version…" />
            </SelectTrigger>
            <SelectContent>
              {versions.map((v) => (
                <SelectItem key={v.id} value={v.id}>
                  v{v.version_number}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button
            variant="outline"
            size="sm"
            className="w-full justify-center"
            onClick={() => void launch("regression")}
            disabled={pending !== null}
          >
            {pending === "regression" ? "Starting…" : "Regression"}
          </Button>
        </div>
        </div>
      </PanelSection>

      <PanelSection title="History" count={experiments.length}>
        {experimentsLoading ? (
          <LoadingState variant="list" label="Loading experiments…" />
        ) : experimentsError ? (
          <EmptyState
            compact
            icon={FlaskConical}
            title="Couldn't load experiments"
            description="The experiments request failed. Check the API and try again."
            action={
              <Button variant="outline" size="sm" onClick={() => void refetchExperiments()}>
                Retry
              </Button>
            }
          />
        ) : experiments.length === 0 ? (
          <EmptyState
            compact
            icon={FlaskConical}
            title="No experiments yet"
            description="Create a dataset, then run a batch or regression check."
          />
        ) : null}
        <div className="space-y-2">
        {experiments.map((exp) => {
          const candidate = exp.summary?.candidate;
          const verdict = exp.summary?.verdict;
          const isRegression =
            exp.status === "failed" || (verdict != null && !verdict.passed);
          return (
            <details
              key={exp.id}
              className="group rounded-md border border-border bg-surface-input"
              open={isRegression}
            >
              <summary className="focus-ring flex cursor-pointer list-none items-center justify-between gap-2 rounded-md px-3 py-2 transition-colors hover:bg-surface-hover [&::-webkit-details-marker]:hidden">
                <span className="flex min-w-0 items-center gap-2">
                  <ChevronRight
                    className="h-3.5 w-3.5 shrink-0 text-muted transition-transform group-open:rotate-90"
                    aria-hidden
                  />
                  <span className="truncate font-mono text-xs text-muted">
                    {exp.kind}
                    {exp.created_at && (
                      <>
                        {" · "}
                        <time dateTime={exp.created_at} title={formatFullTimestamp(exp.created_at)}>
                          {formatRelativeTime(exp.created_at)}
                        </time>
                      </>
                    )}
                  </span>
                </span>
                {verdictBadge(exp)}
              </summary>
              <div className="space-y-1 border-t border-border px-3 py-2">
                {candidate ? (
                  <p className="font-mono text-xs text-muted">
                    eval {candidate.avg_eval ?? "—"} · {candidate.failures}/{candidate.items} failed
                    {typeof candidate.total_cost_usd === "number"
                      ? ` · ${formatCostUsd(candidate.total_cost_usd)}`
                      : ""}
                  </p>
                ) : (
                  <p className="font-mono text-xs text-subtle">No candidate metrics yet.</p>
                )}
                {verdict && !verdict.passed && (
                  <p className="text-xs text-destructive">{verdict.reasons.join("; ")}</p>
                )}
              </div>
            </details>
          );
        })}
        </div>
      </PanelSection>
    </div>
  );
}
