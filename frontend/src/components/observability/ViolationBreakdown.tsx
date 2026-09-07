"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";
import { SectionCard } from "@/components/ui/section-card";
import { LoadingState } from "@/components/ui/loading-state";
import { SeverityBar } from "@/components/ui/severity-bar";
import { Button } from "@/components/ui/button";
import { queryKeys } from "@/lib/query-keys";
import { formatRelativeTime } from "@/lib/format-date";
import { guardrailTypeLabel } from "@/lib/guardrail-labels";
import { guardrailStatusTone, type GuardrailStatusTone } from "@/lib/run-status";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";

/** Text spelling of the shared guardrail tone for these dense mono rows. */
const TONE_TEXT: Record<GuardrailStatusTone, string> = {
  success: "text-success",
  warning: "text-warning",
  destructive: "text-destructive",
  outline: "text-muted",
};

/**
 * Guardrail violation drill-down: events grouped by rail type (not just
 * severity totals) plus a recent violation log. Extends the Trust dashboard's
 * Safety story from "how many" to "which rail, and where". Chroma is data-only
 * (severity); chrome stays monochrome.
 */
export function ViolationBreakdown() {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: queryKeys.guardrailViolations(""),
    queryFn: api.getGuardrailViolations,
    refetchInterval: 60_000,
  });

  if (isLoading) {
    return (
      <SectionCard title="Guardrail violations" description="By rail type across recent runs">
        <LoadingState variant="list" label="Loading violations…" />
      </SectionCard>
    );
  }

  // A failed safety drill-down must announce itself; a silent skeleton reads as
  // "still loading" forever and a blank card reads as "nothing to see".
  if (isError || !data) {
    return (
      <SectionCard title="Guardrail violations" description="By rail type across recent runs">
        <div className="flex flex-wrap items-center gap-3">
          <p className="text-sm text-destructive">Couldn&apos;t load guardrail violations.</p>
          <Button variant="outline" size="sm" onClick={() => void refetch()}>
            <RefreshCw aria-hidden />
            Retry
          </Button>
        </div>
      </SectionCard>
    );
  }

  const windowLabel = `last ${data.runs_scanned.toLocaleString()} runs`;

  return (
    <SectionCard
      title="Guardrail violations"
      description={`By rail type · ${windowLabel}`}
      actions={
        <span className="font-mono text-2xs tabular-nums text-subtle">
          {data.total_violations.toLocaleString()} of {data.total_events.toLocaleString()} events
        </span>
      }
    >
      {data.total_events === 0 ? (
        <p className="text-sm text-subtle">No guardrail events in this window.</p>
      ) : (
        <div className="space-y-5">
          {/* By-type breakdown */}
          <ul className="space-y-2">
            {data.by_type.map((row) => (
              <li key={row.type} className="space-y-1">
                <div className="flex items-center justify-between gap-3">
                  <span className="font-mono text-2xs text-foreground">
                    {guardrailTypeLabel(row.type)}
                  </span>
                  <span className="flex shrink-0 items-center gap-2.5 font-mono text-2xs tabular-nums">
                    {row.warned > 0 && <span className="text-warning">{row.warned} warned</span>}
                    {row.failed > 0 && (
                      <span className="text-destructive">{row.failed} failed</span>
                    )}
                    <span className="text-subtle">{row.total} total</span>
                  </span>
                </div>
                <SeverityBar passed={row.passed} warned={row.warned} failed={row.failed} />
              </li>
            ))}
          </ul>

          {/* Recent violation log */}
          {data.recent.length > 0 && (
            <div>
              <p className="text-micro mb-2">Recent violations</p>
              <ul className="divide-y divide-border overflow-hidden rounded-md border border-border">
                {data.recent.map((v, i) => (
                  <li
                    key={`${v.run_id}-${i}`}
                    className="flex items-center justify-between gap-3 px-3 py-2 transition-colors hover:bg-surface-hover"
                  >
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span
                          className={cn(
                            "font-mono text-2xs uppercase",
                            TONE_TEXT[guardrailStatusTone(v.status)]
                          )}
                        >
                          {v.status}
                        </span>
                        <span className="font-mono text-2xs text-muted">
                          {guardrailTypeLabel(v.type)}
                        </span>
                        <span className="truncate text-sm text-foreground">
                          {v.workflow || "Workflow"}
                          {v.node_label ? ` · ${v.node_label}` : ""}
                        </span>
                      </div>
                      {v.message && (
                        <p className="mt-0.5 truncate text-xs text-subtle">{v.message}</p>
                      )}
                    </div>
                    <div className="flex shrink-0 items-center gap-3">
                      {v.created_at && (
                        <span className="font-mono text-2xs tabular-nums text-subtle">
                          {formatRelativeTime(v.created_at)}
                        </span>
                      )}
                      <Link
                        href={`/runs/${v.run_id}`}
                        className="focus-ring text-xs font-medium text-foreground underline-offset-4 hover:underline"
                      >
                        View run
                      </Link>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </SectionCard>
  );
}
