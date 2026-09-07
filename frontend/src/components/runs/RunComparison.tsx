"use client";

import { useEffect, useId, useMemo, useState } from "react";
import { Activity, ArrowRight, GitCompare } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { CopyButton } from "@/components/ui/copy-button";
import { EmptyState } from "@/components/ui/empty-state";

import { formatRelativeTime } from "@/lib/format-date";
import { EvalScoresChart } from "@/components/results/EvalScoresChart";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { PanelSection, PanelStat, PanelStatGrid } from "@/components/canvas/panel/PanelSection";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { api } from "@/lib/api";
import type { EvalHistoryEntry, RunCompareResponse } from "@/types/workflow";

interface RunComparisonProps {
  workflowId: string;
  embedded?: boolean;
}

export function RunComparison({ workflowId, embedded = false }: RunComparisonProps) {
  const runAId = useId();
  const runBId = useId();
  const [history, setHistory] = useState<EvalHistoryEntry[]>([]);
  const [runA, setRunA] = useState("");
  const [runB, setRunB] = useState("");
  const [comparison, setComparison] = useState<RunCompareResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getEvalHistory(workflowId)
      .then(setHistory)
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Failed to load eval history");
        setHistory([]);
      });
  }, [workflowId]);

  useEffect(() => {
    if (history.length >= 2 && !runA && !runB) {
      setRunA(history[1].run_id);
      setRunB(history[0].run_id);
    }
  }, [history, runA, runB]);

  const selectedA = useMemo(
    () => history.find((entry) => entry.run_id === runA),
    [history, runA]
  );
  const selectedB = useMemo(
    () => history.find((entry) => entry.run_id === runB),
    [history, runB]
  );
  const deltaScore =
    selectedA?.scores.aggregate_score != null && selectedB?.scores.aggregate_score != null
      ? selectedB.scores.aggregate_score - selectedA.scores.aggregate_score
      : null;

  const handleCompare = async () => {
    if (!runA || !runB || runA === runB) return;
    setLoading(true);
    setError(null);
    try {
      const result = await api.compareRuns(workflowId, runA, runB);
      setComparison(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Comparison failed");
      setComparison(null);
    } finally {
      setLoading(false);
    }
  };

  if (error && history.length < 2) {
    return (
      <EmptyState
        compact
        variant="error"
        icon={GitCompare}
        title="Couldn't load eval history"
        description={error}
        className={embedded ? "py-6" : undefined}
      />
    );
  }

  if (history.length < 2) {
    return (
      <EmptyState
        compact
        icon={GitCompare}
        title="Not enough eval runs"
        description="Run the workflow at least twice with an evaluation node to compare scores."
        className={embedded ? "py-6" : undefined}
      />
    );
  }

  return (
    <div className={embedded ? "flex flex-col gap-3" : "panel flex w-full flex-col gap-3 p-4 sm:w-96"}>
      {!embedded && (
        <div className="flex items-start gap-2">
          <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary-muted text-primary">
            <GitCompare className="h-4 w-4" />
          </div>
          <div className="min-w-0">
            <p className="text-sm font-semibold text-foreground">Compare runs</p>
            <p className="text-xs leading-relaxed text-muted">
              Review score movement and output drift between two evaluated runs.
            </p>
          </div>
        </div>
      )}

      <PanelSection title="Select runs">
      <div className="grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-end gap-2 rounded-xl border border-border bg-surface p-3">
        <div className="min-w-0 space-y-2">
          <Label htmlFor={runAId}>Baseline</Label>
          <Select value={runA || undefined} onValueChange={setRunA}>
            <SelectTrigger id={runAId} className="text-xs">
              <SelectValue placeholder="Select run…" />
            </SelectTrigger>
            <SelectContent>
              {history.map((entry) => (
                <SelectItem key={entry.run_id} value={entry.run_id}>
                  {formatRelativeTime(entry.created_at)} ·{" "}
                  {entry.scores.aggregate_score?.toFixed(2) ?? "—"}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="mb-1 flex h-8 w-8 items-center justify-center rounded-lg border border-border bg-background text-muted">
          <ArrowRight className="h-3.5 w-3.5" />
        </div>

        <div className="min-w-0 space-y-2">
          <Label htmlFor={runBId}>Compare</Label>
          <Select value={runB || undefined} onValueChange={setRunB}>
            <SelectTrigger id={runBId} className="text-xs">
              <SelectValue placeholder="Select run…" />
            </SelectTrigger>
            <SelectContent>
              {history.map((entry) => (
                <SelectItem key={entry.run_id} value={entry.run_id}>
                  {formatRelativeTime(entry.created_at)} ·{" "}
                  {entry.scores.aggregate_score?.toFixed(2) ?? "—"}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <PanelStatGrid>
        <PanelStat label="Runs" value={history.length} />
        <PanelStat label="Baseline" value={selectedA?.scores.aggregate_score?.toFixed(2) ?? "—"} />
        <PanelStat
          label="Delta"
          tone={deltaScore == null ? "default" : deltaScore >= 0 ? "success" : "destructive"}
          value={deltaScore == null ? "—" : `${deltaScore >= 0 ? "+" : ""}${deltaScore.toFixed(2)}`}
        />
      </PanelStatGrid>
      </PanelSection>

      <Button size="sm" className="w-full justify-center" onClick={handleCompare} disabled={loading || !runA || !runB || runA === runB}>
        <Activity className="h-3.5 w-3.5" />
        {loading ? "Comparing…" : "Compare"}
      </Button>

      {error && <p className="text-xs text-destructive">{error}</p>}

      {comparison && (
        <PanelSection title="Result">
          <div className={embedded ? "grid grid-cols-1 gap-2 text-xs" : "grid grid-cols-2 gap-2 text-xs"}>
            <div className="rounded-lg border border-border bg-background p-2">
              <div className="mb-2 flex items-center justify-between gap-2">
                <p className="font-medium text-foreground">Baseline</p>
                <Badge variant="outline" className="px-1.5 py-0 text-2xs">
                  v{comparison.run_a_version}
                </Badge>
              </div>
              {comparison.run_a_scores && <EvalScoresChart scores={comparison.run_a_scores} compact />}
            </div>
            <div className="rounded-lg border border-border bg-background p-2">
              <div className="mb-2 flex items-center justify-between gap-2">
                <p className="font-medium text-foreground">Compare</p>
                <Badge variant="primary" className="px-1.5 py-0 text-2xs">
                  v{comparison.run_b_version}
                </Badge>
              </div>
              {comparison.run_b_scores && (
                <EvalScoresChart scores={comparison.run_b_scores} delta={comparison.delta} compact />
              )}
            </div>
          </div>

          {(comparison.run_a_output || comparison.run_b_output) && (
            <div className="space-y-2 text-xs">
              <div>
                <div className="flex items-center justify-between gap-2">
                  <p className="font-medium text-muted">Output A</p>
                  {comparison.run_a_output && (
                    <CopyButton text={comparison.run_a_output} label="Copy output A" />
                  )}
                </div>
                <p className="line-clamp-3 text-foreground">{comparison.run_a_output}</p>
              </div>
              <div>
                <div className="flex items-center justify-between gap-2">
                  <p className="font-medium text-muted">Output B</p>
                  {comparison.run_b_output && (
                    <CopyButton text={comparison.run_b_output} label="Copy output B" />
                  )}
                </div>
                <p className="line-clamp-3 text-foreground">{comparison.run_b_output}</p>
              </div>
            </div>
          )}
        </PanelSection>
      )}
    </div>
  );
}
