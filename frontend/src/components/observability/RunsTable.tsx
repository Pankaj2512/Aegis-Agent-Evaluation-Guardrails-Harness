"use client";

import { Activity, Search } from "lucide-react";
import { SectionCard } from "@/components/ui/section-card";
import { EmptyState } from "@/components/ui/empty-state";
import { VirtualList } from "@/components/ui/virtual-list";
import { Input } from "@/components/ui/input";
import { TableSkeleton } from "@/components/ui/loading-state";
import { RunColumnHeader, StreamRunRow, type RecentRun } from "./run-row";

const ROW_HEIGHT = 48;

interface RunsTableProps {
  runs: RecentRun[];
  search: string;
  onSearchChange: (value: string) => void;
  /** True when `runs` are search results rather than the recent window. */
  isSearchResults: boolean;
  totalRunCount: number;
  recentCount: number;
  /** Render a content-matched skeleton instead of rows while fetching. */
  loading?: boolean;
}

/** "All runs" — the full recent window (or search results) as a virtual table. */
export function RunsTable({
  runs,
  search,
  onSearchChange,
  isSearchResults,
  totalRunCount,
  recentCount,
  loading = false,
}: RunsTableProps) {
  const countLabel = isSearchResults
    ? `${runs.length} matching`
    : recentCount < totalRunCount
      ? `${recentCount} of ${totalRunCount}`
      : `${recentCount}`;

  return (
    <SectionCard
      title="All runs"
      flush
      actions={
        <div className="flex flex-wrap items-center justify-end gap-2">
          <span className="font-mono text-2xs text-muted tabular-nums">{countLabel}</span>
          <div className="relative w-full sm:w-56">
            <Search
              className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted"
              aria-hidden
            />
            <Input
              size="sm"
              value={search}
              onChange={(e) => onSearchChange(e.target.value)}
              placeholder="Search inputs…"
              aria-label="Search all runs"
              className="pl-8"
            />
          </div>
        </div>
      }
    >
      <RunColumnHeader runs={loading ? undefined : runs} />
      {loading ? (
        <TableSkeleton rows={8} rowHeight={ROW_HEIGHT} label="Loading runs…" />
      ) : (
        <VirtualList
          items={runs}
          itemHeight={ROW_HEIGHT}
          maxHeight={480}
          getItemKey={(run) => run.run_id}
          emptyState={
            <EmptyState
              compact
              icon={Activity}
              title={isSearchResults ? "No matching runs" : "No runs yet"}
              description={
                isSearchResults
                  ? "Try a different search term."
                  : "Run a workflow to populate this list."
              }
            />
          }
          renderItem={(run) => <StreamRunRow run={run} />}
        />
      )}
    </SectionCard>
  );
}
