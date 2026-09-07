"use client";
import { useState } from "react";
import { useStoreApi } from "@xyflow/react";
import { useReducedMotionStrict } from "@/components/motion";

type StaggerRecord = { epoch: number; count: number };

// Per-canvas-instance stagger bookkeeping, keyed on the React Flow store object
// (a fresh store => a remounted canvas => a fresh stagger burst). A WeakMap lets
// old canvas instances be garbage-collected with their records.
const registry = new WeakMap<object, StaggerRecord>();

// Nodes mounting within this window of the first node's mount are treated as the
// initial hydration burst and staggered; anything later (quick-add, paste)
// mounts with zero delay.
const BURST_WINDOW_MS = 400;
const MAX_STAGGERED = 12;
const STEP_SEC = 0.035;

/**
 * Returns a per-node mount animation delay (seconds). Computed exactly once per
 * mount via lazy useState so it survives BaseNode's data-identity churn during
 * runs. Returns 0 under strict reduced motion.
 */
export function useEntryStagger(): number {
  const storeApi = useStoreApi();
  const reduce = useReducedMotionStrict();

  const [delay] = useState(() => {
    let record = registry.get(storeApi);
    if (!record) {
      record = { epoch: performance.now(), count: 0 };
      registry.set(storeApi, record);
    }
    if (performance.now() - record.epoch < BURST_WINDOW_MS) {
      return Math.min(record.count++, MAX_STAGGERED) * STEP_SEC;
    }
    return 0;
  });

  return reduce ? 0 : delay;
}
