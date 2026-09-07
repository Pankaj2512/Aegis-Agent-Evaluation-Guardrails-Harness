"use client";

import { useCallback, useRef } from "react";
import type { Edge, Node } from "@xyflow/react";

export interface GraphSnapshot {
  nodes: Node[];
  edges: Edge[];
}

interface UseGraphHistoryOptions {
  nodesRef: React.MutableRefObject<Node[]>;
  edgesRef: React.MutableRefObject<Edge[]>;
  setNodes: (nodes: Node[]) => void;
  setEdges: (edges: Edge[]) => void;
  capacity?: number;
}

interface UseGraphHistoryReturn {
  record: (coalesceKey?: string) => void;
  undo: () => void;
  redo: () => void;
  canUndo: boolean;
  canRedo: boolean;
  clear: () => void;
}

const DEFAULT_CAPACITY = 100;
const COALESCE_WINDOW_MS = 800;

/**
 * Push-before-mutate undo/redo for the workflow graph.
 *
 * The integrator calls `record()` explicitly BEFORE each graph mutation — this
 * hook never records automatically via effects. Snapshots are deep-cloned from
 * the passed refs (state arrays are pure JSON-safe persisted data; display
 * callbacks are injected in separate memos downstream, so no stripping needed).
 *
 * Stacks live in refs so record/undo/redo stay useCallback-stable. We do NOT
 * bump a version counter per mutation: that forced a whole-canvas re-render on
 * every edit and re-subscribed the keydown listener. canUndo/canRedo are read
 * lazily from the refs (kept for API surface; the canvas doesn't render them).
 */
export function useGraphHistory({
  nodesRef,
  edgesRef,
  setNodes,
  setEdges,
  capacity = DEFAULT_CAPACITY,
}: UseGraphHistoryOptions): UseGraphHistoryReturn {
  const pastRef = useRef<GraphSnapshot[]>([]);
  const futureRef = useRef<GraphSnapshot[]>([]);
  const lastKeyRef = useRef<string | null>(null);
  const lastTimeRef = useRef<number>(0);

  const snapshot = useCallback(
    (): GraphSnapshot => ({
      nodes: structuredClone(nodesRef.current),
      edges: structuredClone(edgesRef.current),
    }),
    [nodesRef, edgesRef]
  );

  const record = useCallback(
    (coalesceKey?: string) => {
      const now = Date.now();
      // Coalesce only when the SAME key was recorded within the window, anchored
      // to the FIRST record of the group — we do NOT refresh lastTimeRef on a
      // skip, otherwise a long typing session collapses into a single snapshot.
      if (
        coalesceKey !== undefined &&
        coalesceKey === lastKeyRef.current &&
        now - lastTimeRef.current < COALESCE_WINDOW_MS
      ) {
        return;
      }
      lastKeyRef.current = coalesceKey ?? null;
      lastTimeRef.current = now;

      pastRef.current.push(snapshot());
      if (pastRef.current.length > capacity) {
        pastRef.current.shift(); // drop oldest
      }
      futureRef.current = [];
    },
    [snapshot, capacity]
  );

  const undo = useCallback(() => {
    if (pastRef.current.length === 0) return;
    futureRef.current.push(snapshot());
    const prev = pastRef.current.pop() as GraphSnapshot;
    // Any explicit record after this restore should start a fresh coalesce group.
    lastKeyRef.current = null;
    setNodes(prev.nodes);
    setEdges(prev.edges);
  }, [snapshot, setNodes, setEdges]);

  const redo = useCallback(() => {
    if (futureRef.current.length === 0) return;
    pastRef.current.push(snapshot());
    const next = futureRef.current.pop() as GraphSnapshot;
    lastKeyRef.current = null;
    setNodes(next.nodes);
    setEdges(next.edges);
  }, [snapshot, setNodes, setEdges]);

  const clear = useCallback(() => {
    pastRef.current = [];
    futureRef.current = [];
    lastKeyRef.current = null;
    lastTimeRef.current = 0;
  }, []);

  return {
    record,
    undo,
    redo,
    canUndo: pastRef.current.length > 0,
    canRedo: futureRef.current.length > 0,
    clear,
  };
}
