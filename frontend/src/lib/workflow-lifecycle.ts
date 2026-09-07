import type { WorkflowListItem } from "@/types/workflow";

/** Publish-lifecycle stage for the home board (concept 18). */
export type WorkflowLifecycleStage = "draft" | "in_review" | "published";

export const LIFECYCLE_STAGES: Array<{
  id: WorkflowLifecycleStage;
  label: string;
  description: string;
}> = [
  {
    id: "draft",
    label: "Drafts",
    description: "No saved version yet",
  },
  {
    id: "in_review",
    label: "In review",
    description: "Saved, not published",
  },
  {
    id: "published",
    label: "Published",
    description: "Invoke API serves a version",
  },
];

/**
 * Derive stage from list fields only (no separate review flag in the API).
 *
 * - published → published column
 * - has ≥1 saved version, not published → in review (ready to publish)
 * - no versions → draft
 */
export function workflowLifecycleStage(w: WorkflowListItem): WorkflowLifecycleStage {
  if (w.published) return "published";
  const hasVersion =
    (w.version_count != null && w.version_count > 0) || w.latest_version_number != null;
  if (hasVersion) return "in_review";
  return "draft";
}

export function partitionByLifecycle(
  workflows: WorkflowListItem[]
): Record<WorkflowLifecycleStage, WorkflowListItem[]> {
  const buckets: Record<WorkflowLifecycleStage, WorkflowListItem[]> = {
    draft: [],
    in_review: [],
    published: [],
  };
  for (const w of workflows) {
    buckets[workflowLifecycleStage(w)].push(w);
  }
  // List API is already updated_at desc; keep stable order within columns.
  return buckets;
}
