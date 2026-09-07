const STORAGE_KEY = "aegis:pinned-workflows";
const MAX_PINNED = 24;

/**
 * Pinned workflow ids for the home desk. localStorage-backed, best-effort,
 * and safe on the server (returns [] when window is undefined). Consumers must
 * guard first-paint reads for hydration.
 */
export function getPinnedWorkflowIds(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter((id): id is string => typeof id === "string" && id.length > 0)
      .slice(0, MAX_PINNED);
  } catch {
    return [];
  }
}

export function setPinnedWorkflowIds(ids: string[]): string[] {
  if (typeof window === "undefined") return [];
  const next = Array.from(
    new Set(ids.filter((id) => typeof id === "string" && id.length > 0))
  ).slice(0, MAX_PINNED);
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {
    // ignore write failures (private mode, quota, etc.)
  }
  return next;
}

export function isWorkflowPinned(id: string): boolean {
  return getPinnedWorkflowIds().includes(id);
}

/** Toggle pin; returns the next id list. */
export function togglePinnedWorkflow(id: string): string[] {
  const current = getPinnedWorkflowIds();
  if (current.includes(id)) {
    return setPinnedWorkflowIds(current.filter((x) => x !== id));
  }
  return setPinnedWorkflowIds([id, ...current]);
}
