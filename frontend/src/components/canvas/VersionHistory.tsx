"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { GitCompare, History } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import {
  buildDiffHighlightMap,
  VersionDiffView,
  type DiffKind,
} from "@/components/canvas/VersionDiffView";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { LoadingState } from "@/components/ui/loading-state";
import { api } from "@/lib/api";
import { formatFullTimestamp, formatRelativeTime } from "@/lib/format-date";
import { queryKeys } from "@/lib/query-keys";
import type { WorkflowVersion, WorkflowVersionListItem } from "@/types/workflow";
import { cn } from "@/lib/utils";
import { PanelSection } from "@/components/canvas/panel/PanelSection";

interface VersionHistoryProps {
  workflowId: string;
  currentVersionId?: string;
  onSelectVersion: (version: WorkflowVersion) => void;
  onDiffHighlight?: (highlights: Record<string, DiffKind> | null) => void;
  embedded?: boolean;
}

export function VersionHistory({
  workflowId,
  currentVersionId,
  onSelectVersion,
  onDiffHighlight,
  embedded = false,
}: VersionHistoryProps) {
  const [loadingVersionId, setLoadingVersionId] = useState<string | null>(null);
  const [diffVersionId, setDiffVersionId] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const { data: published } = useQuery({
    queryKey: queryKeys.published(workflowId),
    queryFn: () => api.getPublished(workflowId),
  });
  const publishedId = published?.published_version_id ?? null;

  const [publishingId, setPublishingId] = useState<string | null>(null);

  const handlePublish = async (versionId: string, versionNumber: number) => {
    if (publishingId) return;
    setPublishingId(versionId);
    try {
      await api.publishVersion(workflowId, versionId);
      void queryClient.invalidateQueries({ queryKey: queryKeys.published(workflowId) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.deployDescriptor(workflowId) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.workflow(workflowId) });
      toast.success(`v${versionNumber} published — the invoke API now serves it`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Publish failed");
    } finally {
      setPublishingId(null);
    }
  };

  const { data: versions = [], isLoading: loading } = useQuery({
    queryKey: queryKeys.workflowVersions(workflowId),
    queryFn: () => api.listVersions(workflowId),
  });

  const { data: diffPair, isLoading: diffLoading } = useQuery({
    queryKey: ["version-diff", workflowId, currentVersionId, diffVersionId],
    queryFn: async () => {
      if (!currentVersionId || !diffVersionId || currentVersionId === diffVersionId) {
        return null;
      }
      const [current, selected] = await Promise.all([
        api.getVersion(workflowId, currentVersionId),
        api.getVersion(workflowId, diffVersionId),
      ]);
      return { current, selected };
    },
    enabled: Boolean(currentVersionId && diffVersionId && currentVersionId !== diffVersionId),
  });

  const handleSelect = async (version: WorkflowVersionListItem) => {
    if (loadingVersionId) return;
    setLoadingVersionId(version.id);
    try {
      const fullVersion = await api.getVersion(workflowId, version.id);
      onSelectVersion(fullVersion);
      if (version.id !== currentVersionId) {
        setDiffVersionId(version.id);
      } else {
        setDiffVersionId(null);
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to load version");
    } finally {
      setLoadingVersionId(null);
    }
  };

  const handleDiffToggle = (versionId: string, event: React.MouseEvent) => {
    event.stopPropagation();
    if (!currentVersionId || versionId === currentVersionId) return;
    setDiffVersionId((current) => (current === versionId ? null : versionId));
  };

  useEffect(() => {
    if (!onDiffHighlight) return;
    if (diffPair) {
      onDiffHighlight(buildDiffHighlightMap(diffPair.selected, diffPair.current));
    } else {
      onDiffHighlight(null);
    }
  }, [diffPair, onDiffHighlight]);

  return (
    <div className={cn("flex flex-col", !embedded && "panel w-64")}>
      {!embedded && (
        <div className="border-b border-border px-3 py-3">
          <div className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary-muted text-primary">
              <History className="h-3.5 w-3.5" />
            </div>
            <div className="min-w-0">
              <p className="text-sm font-semibold text-foreground">Version history</p>
              <p className="text-xs text-muted">{versions.length} saved snapshots</p>
            </div>
          </div>
        </div>
      )}

      {embedded && (
        <div className="mb-3">
          <PanelSection title="Snapshots" count={versions.length}>
            {null}
          </PanelSection>
        </div>
      )}

      <div className={cn("overflow-y-auto", embedded ? "space-y-1" : "max-h-72 p-2")}>
        {loading && <LoadingState variant="inline" label="Loading versions…" className="px-2 py-3" />}
        {!loading && versions.length === 0 && (
          <EmptyState
            compact
            icon={History}
            title="No versions yet"
            description="Saved snapshots will appear here after workflow changes are versioned."
            className="border-dashed bg-background py-6"
          />
        )}
        {versions.map((version) => {
          const isActive = version.id === currentVersionId;
          const isDiffTarget = version.id === diffVersionId;
          const isLoading = loadingVersionId === version.id;
          const canDiff = Boolean(currentVersionId && version.id !== currentVersionId);

          return (
            <div key={version.id} className="mb-1.5 flex items-stretch gap-1.5">
              <button
                type="button"
                disabled={Boolean(loadingVersionId)}
                onClick={() => handleSelect(version)}
                className={cn(
                  "min-w-0 flex-1 rounded-lg border px-3 py-2 text-left transition",
                  isActive
                    ? "border-primary/25 bg-primary-muted text-foreground shadow-elev-1"
                    : "border-transparent text-muted hover:border-border hover:bg-surface-hover hover:text-foreground",
                  isDiffTarget && !isActive && "border-warning/40 bg-warning/10 text-foreground",
                  isLoading && "opacity-60"
                )}
              >
                <div className="flex items-center gap-2">
                  <p className="text-sm font-semibold">v{version.version_number}</p>
                  {publishedId === version.id && (
                    <Badge variant="success" className="ml-auto px-1.5 py-0 text-2xs">
                      published
                    </Badge>
                  )}
                  {isActive && (
                    <Badge variant="primary" className={publishedId === version.id ? "px-1.5 py-0 text-2xs" : "ml-auto px-1.5 py-0 text-2xs"}>
                      current
                    </Badge>
                  )}
                  {isDiffTarget && !isActive && (
                    <Badge variant="warning" className="ml-auto px-1.5 py-0 text-2xs">
                      compare
                    </Badge>
                  )}
                </div>
                <p className="text-xs text-muted">
                  {version.node_count} nodes ·{" "}
                  <time dateTime={version.created_at} title={formatFullTimestamp(version.created_at)}>
                    {formatRelativeTime(version.created_at)}
                  </time>
                </p>
              </button>
              {publishedId !== version.id && (
                <button
                  type="button"
                  title={`Publish v${version.version_number} — the invoke API serves the published version`}
                  onClick={() => void handlePublish(version.id, version.version_number)}
                  disabled={publishingId !== null}
                  className="focus-ring flex shrink-0 items-center justify-center rounded-lg border border-border px-2 font-mono text-2xs text-muted transition-colors hover:border-border-strong hover:bg-surface-hover hover:text-foreground disabled:opacity-50"
                >
                  {publishingId === version.id ? "Publishing…" : "Publish"}
                </button>
              )}
              {canDiff && (
                <button
                  type="button"
                  title="Compare with current version"
                  onClick={(event) => handleDiffToggle(version.id, event)}
                  className={cn(
                    "flex shrink-0 items-center justify-center rounded-lg border border-border px-2 transition",
                    isDiffTarget
                      ? "border-warning/50 bg-warning/10 text-warning"
                      : "text-muted hover:bg-surface-hover hover:text-foreground"
                  )}
                >
                  <GitCompare className="h-3.5 w-3.5" />
                </button>
              )}
            </div>
          );
        })}
      </div>

      {diffVersionId && currentVersionId && diffVersionId !== currentVersionId && (
        <div className="mt-3 pt-3">
          <PanelSection title="Version diff">
            {diffLoading && <p className="text-xs text-muted">Loading comparison…</p>}
            {diffPair && (
              <VersionDiffView left={diffPair.selected} right={diffPair.current} />
            )}
          </PanelSection>
        </div>
      )}
    </div>
  );
}
