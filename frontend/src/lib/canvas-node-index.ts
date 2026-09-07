/**
 * Tiny module-level bridge that lets the command palette enumerate the CURRENT
 * canvas's nodes without prop-drilling through AppShell. WorkflowCanvas publishes
 * its live node list here (including unsaved edits); the palette reads the
 * snapshot when it opens on a canvas route, and dispatches FOCUS_NODE_EVENT to
 * focus a chosen node. Deliberately a plain module singleton (like clipboard.ts):
 * one canvas is mounted at a time, and the buffer is cleared on unmount.
 */

export interface CanvasNodeEntry {
  id: string;
  label: string;
  nodeType: string;
}

let entries: CanvasNodeEntry[] = [];

export function setCanvasNodeIndex(next: CanvasNodeEntry[]): void {
  entries = next;
}

export function clearCanvasNodeIndex(): void {
  entries = [];
}

export function getCanvasNodeIndex(): CanvasNodeEntry[] {
  return entries;
}
