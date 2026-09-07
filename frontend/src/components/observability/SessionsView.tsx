"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ChevronRight, MessagesSquare, RefreshCw } from "lucide-react";
import { SectionCard } from "@/components/ui/section-card";
import { EmptyState } from "@/components/ui/empty-state";
import { LoadingState } from "@/components/ui/loading-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatRelativeTime } from "@/lib/format-date";
import { runStatusLabel, runStatusTextClass, runStatusVariant } from "@/lib/run-status";
import { queryKeys } from "@/lib/query-keys";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import type { RunSession } from "@/types/workflow";

/** Runs of one session, loaded lazily when the session is expanded. */
function SessionRuns({ sessionId }: { sessionId: string }) {
  const { data: runs = [], isLoading, isError, refetch } = useQuery({
    queryKey: queryKeys.sessionRuns(sessionId),
    queryFn: () => api.listRuns({ session_id: sessionId }),
  });

  if (isLoading) return <LoadingState variant="list" label="Loading runs…" />;
  // A failed fetch must never read as "this session has no runs" — the row above
  // is displaying a non-zero run_count for the very session we couldn't load.
  if (isError) {
    return (
      <div className="flex flex-wrap items-center gap-3 border-t border-border px-3 py-2">
        <p className="text-xs text-destructive">Couldn&apos;t load runs for this session.</p>
        <Button variant="outline" size="xs" onClick={() => void refetch()}>
          <RefreshCw aria-hidden />
          Retry
        </Button>
      </div>
    );
  }
  if (runs.length === 0) return <p className="px-3 py-2 text-xs text-subtle">No runs.</p>;

  return (
    <ul className="divide-y divide-border border-t border-border">
      {runs.map((run) => (
        <li key={run.id} className="flex items-center justify-between gap-3 px-3 py-2">
          <div className="min-w-0">
            <p className="truncate text-xs text-foreground">{run.input_text || "—"}</p>
            <p className="mt-0.5 font-mono text-2xs text-subtle">
              {run.created_at ? formatRelativeTime(run.created_at) : ""}
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <Badge variant={runStatusVariant(run.status)}>{runStatusLabel(run.status)}</Badge>
            <Link
              href={`/runs/${run.id}`}
              className="focus-ring text-xs font-medium text-foreground underline-offset-4 hover:underline"
            >
              Open
            </Link>
          </div>
        </li>
      ))}
    </ul>
  );
}

/** Compact status breakdown for a session, e.g. "2 completed · 1 failed". */
function StatusMix({ counts }: { counts: Record<string, number> }) {
  const entries = Object.entries(counts);
  return (
    <span className="flex flex-wrap items-center gap-2 font-mono text-2xs tabular-nums">
      {entries.map(([status, count]) => (
        <span key={status} className={runStatusTextClass(status)}>
          {count} {runStatusLabel(status)}
        </span>
      ))}
    </span>
  );
}

/**
 * Sessions view: multi-turn runs grouped by session_id. Each session expands to
 * its runs in order. Sessions are formed when a caller threads runs with a
 * shared session_id (e.g. the invoke API's session field for a conversation).
 */
export function SessionsView() {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: queryKeys.runSessions,
    queryFn: api.getRunSessions,
    refetchInterval: 60_000,
  });
  const sessions: RunSession[] = data?.sessions ?? [];
  const [expanded, setExpanded] = useState<string | null>(null);

  return (
    <SectionCard
      title="Sessions"
      description="Multi-turn runs grouped by session — thread runs with a shared session_id to form a conversation."
      flush
      actions={
        <span className="font-mono text-2xs tabular-nums text-muted">
          {isError ? "—" : sessions.length}
        </span>
      }
    >
      {isLoading ? (
        <div className="p-4">
          <LoadingState variant="list" label="Loading sessions…" />
        </div>
      ) : isError ? (
        <div className="flex flex-wrap items-center gap-3 p-4">
          <p className="text-sm text-destructive">Couldn&apos;t load sessions.</p>
          <Button variant="outline" size="sm" onClick={() => void refetch()}>
            <RefreshCw aria-hidden />
            Retry
          </Button>
        </div>
      ) : sessions.length === 0 ? (
        <EmptyState
          compact
          icon={MessagesSquare}
          title="No sessions yet"
          description="Pass a session_id when creating runs (e.g. via the invoke API) to group a conversation's turns here."
        />
      ) : (
        <ul className="divide-y divide-border">
          {sessions.map((session) => {
            const open = expanded === session.session_id;
            return (
              <li key={session.session_id}>
                <button
                  type="button"
                  onClick={() => setExpanded(open ? null : session.session_id)}
                  aria-expanded={open}
                  className="focus-ring flex w-full items-center justify-between gap-3 px-4 py-3 text-left transition-colors hover:bg-surface-hover"
                >
                  <div className="flex min-w-0 items-center gap-2">
                    <ChevronRight
                      className={cn(
                        "h-3.5 w-3.5 shrink-0 text-subtle transition-transform",
                        open && "rotate-90"
                      )}
                      aria-hidden
                    />
                    <div className="min-w-0">
                      <p className="truncate font-mono text-xs text-foreground">
                        {session.session_id}
                      </p>
                      <p className="mt-0.5 truncate text-2xs text-muted">
                        {session.workflows.join(", ") || "—"}
                        {session.last_run_at
                          ? ` · ${formatRelativeTime(session.last_run_at)}`
                          : ""}
                      </p>
                    </div>
                  </div>
                  <div className="flex shrink-0 items-center gap-3">
                    <StatusMix counts={session.status_counts} />
                    <span className="font-mono text-2xs tabular-nums text-subtle">
                      {session.run_count} run{session.run_count === 1 ? "" : "s"}
                    </span>
                  </div>
                </button>
                {open && <SessionRuns sessionId={session.session_id} />}
              </li>
            );
          })}
        </ul>
      )}
    </SectionCard>
  );
}
