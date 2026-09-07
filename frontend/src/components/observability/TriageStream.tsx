"use client";

import { useMemo } from "react";
import { Activity } from "lucide-react";
import { SectionCard } from "@/components/ui/section-card";
import { FilterChip } from "@/components/ui/filter-chip";
import { EmptyState } from "@/components/ui/empty-state";
import { VirtualList } from "@/components/ui/virtual-list";
import { RunColumnHeader, StreamRunRow, type RecentRun } from "./run-row";

export type StreamFilter = "all" | "failed" | "running";

interface TriageStreamProps {
  runs: RecentRun[];
  filter: StreamFilter;
  onFilterChange: (filter: StreamFilter) => void;
}

/** Live triage stream — filtered view of recent runs, patched by the page. */
export function TriageStream({ runs, filter, onFilterChange }: TriageStreamProps) {
  const items = useMemo(() => {
    if (filter === "all") return runs;
    if (filter === "running") {
      return runs.filter((r) =>
        ["running", "pending", "queued", "awaiting_approval"].includes(r.status)
      );
    }
    // failed: hard failures + blocked + eval fail
    return runs.filter(
      (r) =>
        r.status === "failed" ||
        r.status === "cancelled" ||
        r.guardrail_blocked ||
        r.eval_passed === false
    );
  }, [runs, filter]);

  const emptyTitle =
    filter === "failed"
      ? "No failed runs"
      : filter === "running"
        ? "No running runs"
        : "No runs yet";
  const emptyDescription =
    filter === "failed"
      ? "See All runs below for the full history."
      : filter === "running"
        ? "No runs in progress right now."
        : "Run a workflow to populate this stream.";

  return (
    <SectionCard
      title="Triage stream"
      flush
      actions={
        <div className="flex items-center gap-1.5" role="group" aria-label="Filter runs">
          <FilterChip label="All" active={filter === "all"} onClick={() => onFilterChange("all")} />
          <FilterChip
            label="Failed"
            active={filter === "failed"}
            onClick={() => onFilterChange("failed")}
          />
          <FilterChip
            label="Running"
            active={filter === "running"}
            onClick={() => onFilterChange("running")}
          />
        </div>
      }
    >
      <RunColumnHeader />
      <VirtualList
        items={items}
        itemHeight={48}
        maxHeight={320}
        getItemKey={(run) => run.run_id}
        emptyState={
          <EmptyState compact icon={Activity} title={emptyTitle} description={emptyDescription} />
        }
        renderItem={(run) => <StreamRunRow run={run} />}
      />
    </SectionCard>
  );
}
