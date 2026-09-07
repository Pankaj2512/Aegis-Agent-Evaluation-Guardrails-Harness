"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { RunTimeline, RunTimelineNode } from "@/lib/api";
import { useReducedMotionStrict } from "@/components/motion/use-reduced-motion-strict";

/** Per-node telemetry surfaced to the canvas overlay during replay. */
export interface ReplayNodeTelemetry {
  tokens?: number;
  costUsd?: number;
  latencyMs?: number;
}

/** Runtime state a node should render at a given scrub position. */
export type ReplayNodeState = "completed" | "failed" | "running" | "pending";

/**
 * Derived canvas state for scrub position `i`. Pure data — the hook never
 * touches the canvas. The integrator (WorkflowCanvas / M3) applies this to
 * nodes+edges however it likes (or reads it from `onApply`).
 */
export interface ReplayDerivedState {
  /** Scrub index this snapshot corresponds to (-1 = before the first step). */
  index: number;
  /** node_id -> the runtime state it should show at this position. */
  nodeStates: Record<string, ReplayNodeState>;
  /** node_id -> telemetry (present for nodes already reached at this position). */
  nodeTelemetry: Record<string, ReplayNodeTelemetry>;
  /** node_ids that have completed (status completed/success) up to & incl. i. */
  completedNodeIds: string[];
  /** node_ids that have failed up to & incl. i. */
  failedNodeIds: string[];
  /** node_ids not yet reached at this position. */
  pendingNodeIds: string[];
  /**
   * Edge predicate helper: an edge is "source-completed" when its source node
   * has completed at this position — the integrator uses this to animate/flow
   * only the edges that had already fired. Pass the source node_id.
   */
  isSourceCompleted: (sourceNodeId: string) => boolean;
  /** The node the scrubber is currently parked on (null before the first step). */
  currentNodeId: string | null;
}

export interface UseRunReplayOptions {
  /** Timeline to replay (from api.getRunTimeline). Null disables the hook. */
  timeline: RunTimeline | null | undefined;
  /**
   * Called whenever the derived state changes (scrub, play tick, step). The
   * integrator applies it to the canvas. Kept out of the hook so replay stays
   * pure and testable.
   */
  onApply?: (state: ReplayDerivedState) => void;
  /** ms between auto-advance ticks while playing. Default 900ms. */
  playIntervalMs?: number;
}

export interface UseRunReplay {
  /** Ordered nodes being replayed (note nodes already excluded upstream). */
  steps: RunTimelineNode[];
  /** Current scrub index. -1 means "before the first step" (clean slate). */
  index: number;
  /** Jump to an absolute index (clamped to [-1, steps.length-1]). */
  setIndex: (i: number) => void;
  playing: boolean;
  play: () => void;
  pause: () => void;
  /** Advance by ±1 step (pauses playback). */
  step: (dir: 1 | -1) => void;
  atStart: boolean;
  atEnd: boolean;
  /** The node the scrubber is parked on (null before first step). */
  current: RunTimelineNode | null;
  /** Fully derived canvas state for the current index. */
  derived: ReplayDerivedState;
  /** True when reduced motion is preferred (play advances via instant snap). */
  reducedMotion: boolean;
}

function isCompletedStatus(status: string): boolean {
  const s = status.toLowerCase();
  return s === "completed" || s === "success" || s === "succeeded" || s === "passed" || s === "ok";
}

function isFailedStatus(status: string): boolean {
  const s = status.toLowerCase();
  return s === "failed" || s === "error" || s === "errored" || s === "blocked";
}

function telemetryFor(node: RunTimelineNode): ReplayNodeTelemetry {
  const t: ReplayNodeTelemetry = {};
  if (typeof node.latency_ms === "number") t.latencyMs = node.latency_ms;
  else if (typeof node.duration_ms === "number") t.latencyMs = node.duration_ms;
  return t;
}

/** Build the pure derived snapshot for a given scrub index. */
function deriveState(steps: RunTimelineNode[], index: number): ReplayDerivedState {
  const nodeStates: Record<string, ReplayNodeState> = {};
  const nodeTelemetry: Record<string, ReplayNodeTelemetry> = {};
  const completedNodeIds: string[] = [];
  const failedNodeIds: string[] = [];
  const pendingNodeIds: string[] = [];

  steps.forEach((node, i) => {
    if (i < index) {
      // Fully-past nodes settle to their terminal state.
      if (isFailedStatus(node.status)) {
        nodeStates[node.node_id] = "failed";
        failedNodeIds.push(node.node_id);
      } else {
        nodeStates[node.node_id] = "completed";
        completedNodeIds.push(node.node_id);
      }
      nodeTelemetry[node.node_id] = telemetryFor(node);
    } else if (i === index) {
      // The node the scrubber is parked on: show its terminal state (we are
      // scrubbing a finished run, so "the current node has just resolved").
      if (isFailedStatus(node.status)) {
        nodeStates[node.node_id] = "failed";
        failedNodeIds.push(node.node_id);
      } else if (isCompletedStatus(node.status)) {
        nodeStates[node.node_id] = "completed";
        completedNodeIds.push(node.node_id);
      } else {
        nodeStates[node.node_id] = "running";
      }
      nodeTelemetry[node.node_id] = telemetryFor(node);
    } else {
      nodeStates[node.node_id] = "pending";
      pendingNodeIds.push(node.node_id);
    }
  });

  const completedSet = new Set(completedNodeIds);
  const currentNodeId = index >= 0 && index < steps.length ? steps[index].node_id : null;

  return {
    index,
    nodeStates,
    nodeTelemetry,
    completedNodeIds,
    failedNodeIds,
    pendingNodeIds,
    isSourceCompleted: (sourceNodeId: string) => completedSet.has(sourceNodeId),
    currentNodeId,
  };
}

/**
 * Replay-scrubber controller for a finished run's timeline.
 *
 * Pure: it computes the derived canvas state for a scrub position and hands it
 * to `onApply`. It NEVER mutates the canvas. Reduced-motion collapses playback
 * to instant snaps (no per-tick animation semantics change here — the integrator
 * should skip node transitions when `reducedMotion` is true).
 */
export function useRunReplay({
  timeline,
  onApply,
  playIntervalMs = 900,
}: UseRunReplayOptions): UseRunReplay {
  const reducedMotion = useReducedMotionStrict();

  // Only real executed nodes participate; ordered by start offset for a stable
  // left-to-right scrub even if the backend returns them unordered.
  const steps = useMemo<RunTimelineNode[]>(() => {
    if (!timeline?.nodes?.length) return [];
    return [...timeline.nodes].sort((a, b) => a.start_offset_ms - b.start_offset_ms);
  }, [timeline]);

  const [index, setIndexRaw] = useState(-1);
  const [playing, setPlaying] = useState(false);

  const lastKey = useRef<string | null>(null);
  const stepCount = steps.length;

  // Reset scrub to a clean slate whenever the underlying run changes.
  useEffect(() => {
    setIndexRaw(-1);
    setPlaying(false);
  }, [timeline?.run_id]);

  const clamp = useCallback(
    (i: number) => Math.max(-1, Math.min(i, stepCount - 1)),
    [stepCount]
  );

  const setIndex = useCallback(
    (i: number) => setIndexRaw((prev) => (prev === clamp(i) ? prev : clamp(i))),
    [clamp]
  );

  const atStart = index <= -1;
  const atEnd = stepCount === 0 || index >= stepCount - 1;

  const play = useCallback(() => {
    if (stepCount === 0) return;
    // Restart from the top if parked at the end.
    setIndexRaw((prev) => (prev >= stepCount - 1 ? -1 : prev));
    setPlaying(true);
  }, [stepCount]);

  const pause = useCallback(() => setPlaying(false), []);

  const step = useCallback(
    (dir: 1 | -1) => {
      setPlaying(false);
      setIndexRaw((prev) => clamp(prev + dir));
    },
    [clamp]
  );

  // Auto-advance while playing. Reduced-motion keeps the same cadence but the
  // integrator applies each snapshot instantly (no node transition tweens).
  useEffect(() => {
    if (!playing || stepCount === 0) return;
    const id = window.setInterval(() => {
      setIndexRaw((prev) => {
        if (prev >= stepCount - 1) {
          setPlaying(false);
          return prev;
        }
        return prev + 1;
      });
    }, playIntervalMs);
    return () => window.clearInterval(id);
  }, [playing, stepCount, playIntervalMs]);

  const derived = useMemo(() => deriveState(steps, index), [steps, index]);

  // Push derived state to the integrator only when it meaningfully changes.
  useEffect(() => {
    const key = `${timeline?.run_id ?? ""}:${derived.index}`;
    if (key === lastKey.current) return;
    lastKey.current = key;
    onApply?.(derived);
  }, [derived, onApply, timeline?.run_id]);

  const current = index >= 0 && index < stepCount ? steps[index] : null;

  return {
    steps,
    index,
    setIndex,
    playing,
    play,
    pause,
    step,
    atStart,
    atEnd,
    current,
    derived,
    reducedMotion,
  };
}
