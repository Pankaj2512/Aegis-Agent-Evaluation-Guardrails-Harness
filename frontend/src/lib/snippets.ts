import type { Edge, Node } from "@xyflow/react";

/**
 * Instance-local snippet store (localStorage) — no backend. A snippet is a saved
 * canvas selection (nodes + intra-selection edges) that can be re-inserted from
 * the QuickAdd menu. Kept deliberately per-browser: snippets are a personal
 * scratchpad, not shared workflow content.
 */
export interface Snippet {
  id: string;
  name: string;
  createdAt: number;
  payload: { nodes: Node[]; edges: Edge[] };
}

const STORAGE_KEY = "aegis:snippets";
const MAX_SNIPPETS = 20;

/** Read all snippets, newest first. Never throws — returns [] on any parse error. */
export function getSnippets(): Snippet[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(
      (s): s is Snippet =>
        !!s &&
        typeof (s as Snippet).id === "string" &&
        typeof (s as Snippet).name === "string" &&
        !!(s as Snippet).payload &&
        Array.isArray((s as Snippet).payload.nodes)
    );
  } catch {
    return [];
  }
}

function write(snippets: Snippet[]): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(snippets));
  } catch {
    // Storage full / disabled — snippets are best-effort, swallow.
  }
}

/**
 * Persist a new snippet at the front. Caps at MAX_SNIPPETS with FIFO eviction of
 * the oldest entries. Returns the created snippet.
 */
export function saveSnippet(
  name: string,
  payload: { nodes: Node[]; edges: Edge[] }
): Snippet {
  const snippet: Snippet = {
    id: `snip_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
    name: name.trim() || "Untitled snippet",
    createdAt: Date.now(),
    payload,
  };
  const next = [snippet, ...getSnippets()].slice(0, MAX_SNIPPETS);
  write(next);
  return snippet;
}

/** Remove a snippet by id. */
export function deleteSnippet(id: string): void {
  write(getSnippets().filter((s) => s.id !== id));
}
