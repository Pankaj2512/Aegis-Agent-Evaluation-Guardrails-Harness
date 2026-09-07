import type { Edge, Node } from "@xyflow/react";

/**
 * Module-level in-memory clipboard for canvas copy/paste.
 *
 * Deliberate tradeoff vs the system clipboard: we keep the fragment in a plain
 * module variable rather than navigator.clipboard. This avoids permission
 * prompts and clipboard-read gating, and keeps rich Node/Edge objects intact
 * without JSON round-tripping through text/plain. The cost is that the buffer
 * is per-tab and does not survive a reload — acceptable for canvas paste.
 */

interface ClipboardStore {
  nodes: Node[];
  edges: Edge[];
}

let store: ClipboardStore | null = null;

const GRID = 20;

/**
 * Strip node-anchored comments (`data.comments`) from a node. Comments are
 * per-instance annotations, not reusable structure — copy/paste, duplicate and
 * saved snippets all mint FRESH nodes, so they start with a clean comment slate
 * rather than inheriting the source node's commentary. Applied at every
 * serialization boundary (serializeSelection, duplicateFragment).
 */
function withoutComments<T extends Node>(node: T): T {
  const data = node.data as Record<string, unknown> | undefined;
  if (!data || !("comments" in data)) return node;
  const rest = { ...data };
  delete rest.comments;
  return { ...node, data: rest };
}

function snapToGrid(value: number): number {
  return Math.round(value / GRID) * GRID;
}

/**
 * Serialize a selection into a self-contained fragment: deep-cloned nodes
 * (stripped of `selected`) plus only the edges whose BOTH endpoints are in the
 * selection. Shared by the module clipboard and the snippet store so both use
 * the same intra-selection edge rule and the same id-remap on materialize.
 */
export function serializeSelection(
  selectedNodes: Node[],
  allEdges: Edge[]
): { nodes: Node[]; edges: Edge[] } {
  const ids = new Set(selectedNodes.map((n) => n.id));
  const nodes = selectedNodes.map((n) => {
    const clone = structuredClone(n);
    delete clone.selected;
    // A serialized fragment (clipboard buffer or saved snippet) is a reusable
    // asset: drop per-instance comments so pasted/inserted nodes start clean.
    return withoutComments(clone);
  });
  const edges = allEdges
    .filter((e) => ids.has(e.source) && ids.has(e.target))
    .map((e) => structuredClone(e));
  return { nodes, edges };
}

/**
 * Copy the selected nodes (and internal edges) into the module clipboard.
 * Returns the number of nodes stored.
 */
export function copyToClipboard(selectedNodes: Node[], allEdges: Edge[]): number {
  store = serializeSelection(selectedNodes, allEdges);
  return store.nodes.length;
}

export function hasClipboard(): boolean {
  return store !== null && store.nodes.length > 0;
}

/** Matches WorkflowCanvas `nextNodeId`: scan `node_<n>` ids, return max+1 suffix. */
function nextNodeIndex(existingNodes: Node[]): number {
  let max = 0;
  for (const node of existingNodes) {
    const match = /^node_(\d+)$/.exec(node.id);
    if (match) {
      max = Math.max(max, Number.parseInt(match[1], 10));
    }
  }
  return max + 1;
}

/**
 * Shared materializer for both paste and bulk-duplicate.
 *
 * Deep-clones the fragment, computes its bounding-box top-left from node
 * positions, offsets every node so that top-left lands on `targetTopLeft`
 * (preserving relative layout), allocates fresh non-colliding `node_<n>` ids,
 * remaps edge source/target, and mints new `e-<src>-<tgt>-<n>` edge ids
 * following WorkflowCanvas `makeEdge`. Returned nodes are selected, edges are not.
 */
function materialize(
  fragmentNodes: Node[],
  fragmentEdges: Edge[],
  existingNodes: Node[],
  targetTopLeft: (bbox: { x: number; y: number }) => { x: number; y: number }
): { nodes: Node[]; edges: Edge[] } | null {
  if (fragmentNodes.length === 0) return null;

  // Grouping frames re-parent members: a member's `position` is RELATIVE to its
  // frame, so only top-level nodes (no parent inside the fragment) participate
  // in the bounding box and receive the paste offset — members ride along with
  // their frame's move and keep their relative position.
  const fragmentIds = new Set(fragmentNodes.map((n) => n.id));
  const isTopLevel = (n: Node) => !n.parentId || !fragmentIds.has(n.parentId);
  const topLevel = fragmentNodes.filter(isTopLevel);

  // Bounding-box top-left of the source fragment (top-level nodes only).
  const minX = Math.min(...topLevel.map((n) => n.position.x));
  const minY = Math.min(...topLevel.map((n) => n.position.y));

  const anchor = targetTopLeft({ x: minX, y: minY });
  const dx = anchor.x - minX;
  const dy = anchor.y - minY;

  // Allocate new ids in a single deterministic pass; each is guaranteed unique
  // against existing nodes AND the others we mint here (the counter only grows).
  let counter = nextNodeIndex(existingNodes);
  const idMap = new Map<string, string>();

  const nodes: Node[] = fragmentNodes.map((n) => {
    const clone = structuredClone(n);
    const newId = `node_${counter}`;
    counter += 1;
    idMap.set(n.id, newId);
    clone.id = newId;
    if (isTopLevel(n)) {
      clone.position = { x: clone.position.x + dx, y: clone.position.y + dy };
    }
    // Re-map group membership within the fragment; drop a dangling parent link
    // when the frame itself was not part of the selection (member copied flat).
    // A member's position is parent-relative — convert to absolute using the
    // live parent's position so the copy does not teleport near the origin.
    if (clone.parentId) {
      const remapped = fragmentIds.has(clone.parentId)
        ? idMap.get(clone.parentId)
        : undefined;
      if (remapped) {
        clone.parentId = remapped;
      } else {
        const parent = existingNodes.find((p) => p.id === clone.parentId);
        if (parent) {
          clone.position = {
            x: parent.position.x + clone.position.x + (isTopLevel(n) ? 0 : dx),
            y: parent.position.y + clone.position.y + (isTopLevel(n) ? 0 : dy),
          };
        } else if (!isTopLevel(n)) {
          // No live parent and not offset above — still apply the paste delta
          // so the copy lands near the selection rather than at relative (0,0).
          clone.position = {
            x: clone.position.x + dx,
            y: clone.position.y + dy,
          };
        }
        delete clone.parentId;
      }
    }
    clone.selected = true;
    return clone;
  });

  const edges: Edge[] = fragmentEdges.map((e, i) => {
    const clone = structuredClone(e);
    const source = idMap.get(e.source) ?? e.source;
    const target = idMap.get(e.target) ?? e.target;
    clone.source = source;
    clone.target = target;
    // Follow makeEdge's `e-<src>-<tgt>-<uniq>` scheme; `${Date.now()}-${i}`
    // keeps ids unique within this batch (Date.now alone collides in a loop).
    clone.id = `e-${source}-${target}-${Date.now()}-${i}`;
    clone.selected = false;
    return clone;
  });

  return { nodes, edges };
}

/**
 * Materialize the stored clipboard at `anchor` (snapped to the 20px grid),
 * WITHOUT consuming the clipboard. Returns null if the clipboard is empty.
 */
export function materializeClipboard(
  existingNodes: Node[],
  anchor: { x: number; y: number }
): { nodes: Node[]; edges: Edge[] } | null {
  if (!store || store.nodes.length === 0) return null;
  return materialize(store.nodes, store.edges, existingNodes, () => ({
    x: snapToGrid(anchor.x),
    y: snapToGrid(anchor.y),
  }));
}

/**
 * Materialize an explicit fragment (e.g. a saved snippet) at `anchor` (snapped
 * to the grid), allocating fresh ids and offsetting to the anchor. Same id/edge/
 * group-membership remap as clipboard paste; does not touch the clipboard.
 */
export function materializeFragmentAt(
  fragmentNodes: Node[],
  fragmentEdges: Edge[],
  existingNodes: Node[],
  anchor: { x: number; y: number }
): { nodes: Node[]; edges: Edge[] } | null {
  return materialize(fragmentNodes, fragmentEdges, existingNodes, () => ({
    x: snapToGrid(anchor.x),
    y: snapToGrid(anchor.y),
  }));
}

/**
 * Duplicate a given selection in place, offset by the WorkflowCanvas duplicate
 * delta (+40, +48) from the fragment's top-left. Does not touch the clipboard.
 */
export function duplicateFragment(
  nodes: Node[],
  edges: Edge[],
  existingNodes: Node[]
): { nodes: Node[]; edges: Edge[] } | null {
  const ids = new Set(nodes.map((n) => n.id));
  const internalEdges = edges.filter((e) => ids.has(e.source) && ids.has(e.target));
  // Duplicate bypasses serializeSelection (it clones live nodes), so strip
  // per-instance comments here too — a duplicated node gets a clean slate.
  return materialize(nodes.map(withoutComments), internalEdges, existingNodes, (bbox) => ({
    x: bbox.x + 40,
    y: bbox.y + 48,
  }));
}
