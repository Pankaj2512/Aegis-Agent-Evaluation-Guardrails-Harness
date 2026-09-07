"use client";

import { useCallback, useEffect, useState } from "react";
import {
  getPinnedWorkflowIds,
  togglePinnedWorkflow,
} from "@/lib/pinned-workflows";

/** Hydration-safe pinned workflow ids for the home desk. */
export function usePinnedWorkflows() {
  const [pinnedIds, setPinnedIds] = useState<string[]>([]);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setPinnedIds(getPinnedWorkflowIds());
    setReady(true);
  }, []);

  const toggle = useCallback((id: string) => {
    setPinnedIds(togglePinnedWorkflow(id));
  }, []);

  const isPinned = useCallback(
    (id: string) => pinnedIds.includes(id),
    [pinnedIds]
  );

  return { pinnedIds, ready, toggle, isPinned };
}
