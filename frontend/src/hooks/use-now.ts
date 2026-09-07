"use client";

import { useEffect, useState } from "react";

/**
 * Ticks on an interval so relative timestamps ("2m ago") refresh without a
 * data refetch. Returns a millisecond timestamp that changes every
 * `intervalMs` (default 30s). Pass the value into `formatRelativeTime(iso, now)`
 * to keep rendered ages current.
 */
export function useNow(intervalMs = 30_000): number {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);

  return now;
}
