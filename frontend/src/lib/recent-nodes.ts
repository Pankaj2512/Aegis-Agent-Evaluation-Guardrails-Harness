const STORAGE_KEY = "aegis:recent-nodes";
const MAX_RECENT = 5;

/**
 * Recently added node types, most-recent first. Mirrors lib/recent-workflows.ts
 * — localStorage-backed, best-effort, and safe on the server (returns [] when
 * window is undefined). Consumers must guard first-paint reads for hydration.
 */
export interface RecentNode {
  /** Registry node type, e.g. "agent". */
  type: string;
  /** Label at time of pick — kept for display without a registry lookup. */
  label: string;
  at: number;
}

export function getRecentNodes(): RecentNode[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as RecentNode[];
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(
      (item) => item && typeof item.type === "string" && typeof item.label === "string"
    );
  } catch {
    return [];
  }
}

export function recordNodePick(type: string, label: string) {
  if (typeof window === "undefined") return;
  try {
    const existing = getRecentNodes().filter((item) => item.type !== type);
    const next = [{ type, label, at: Date.now() }, ...existing].slice(0, MAX_RECENT);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {
    // ignore write failures (private mode, quota, etc.)
  }
}
