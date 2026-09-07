const STORAGE_KEY = "aegis:recent-workflows";
const MAX_RECENT = 5;

export interface RecentWorkflow {
  id: string;
  name: string;
  at: number;
}

export function getRecentWorkflows(): RecentWorkflow[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as RecentWorkflow[];
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(
      (item) => item && typeof item.id === "string" && typeof item.name === "string"
    );
  } catch {
    return [];
  }
}

export function recordWorkflowVisit(id: string, name: string) {
  if (typeof window === "undefined") return;
  try {
    const existing = getRecentWorkflows().filter((item) => item.id !== id);
    const next = [{ id, name, at: Date.now() }, ...existing].slice(0, MAX_RECENT);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {
    // ignore write failures (private mode, quota, etc.)
  }
}
