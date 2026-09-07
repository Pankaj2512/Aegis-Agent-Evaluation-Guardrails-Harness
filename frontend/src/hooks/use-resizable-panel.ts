"use client";

import { useCallback, useEffect, useRef, useState } from "react";

interface UseResizablePanelOptions {
  storageKey: string;
  defaultWidth: number;
  min: number;
  max: number;
  side: "left" | "right";
}

interface UseResizablePanelResult {
  width: number;
  handleProps: React.HTMLAttributes<HTMLDivElement>;
  reset: () => void;
}

const KEYBOARD_STEP = 16;

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function readStoredWidth(
  storageKey: string,
  defaultWidth: number,
  min: number,
  max: number
): number {
  if (typeof window === "undefined") return defaultWidth;
  try {
    const raw = window.localStorage.getItem(storageKey);
    if (raw == null) return defaultWidth;
    const parsed = Number.parseFloat(raw);
    if (!Number.isFinite(parsed)) return defaultWidth;
    return clamp(parsed, min, max);
  } catch {
    return defaultWidth;
  }
}

/**
 * Pointer-based resizable panel with localStorage persistence, keyboard
 * support and rAF-throttled width updates. Spread `handleProps` onto the
 * drag-handle element.
 */
export function useResizablePanel({
  storageKey,
  defaultWidth,
  min,
  max,
  side,
}: UseResizablePanelOptions): UseResizablePanelResult {
  const [width, setWidth] = useState<number>(() =>
    readStoredWidth(storageKey, defaultWidth, min, max)
  );

  // Drag bookkeeping — refs avoid re-creating handlers each render.
  const dragStartXRef = useRef(0);
  const dragStartWidthRef = useRef(width);
  const rafRef = useRef<number | null>(null);
  const pendingWidthRef = useRef(width);
  const latestWidthRef = useRef(width);

  latestWidthRef.current = width;

  const persist = useCallback(
    (value: number) => {
      if (typeof window === "undefined") return;
      try {
        window.localStorage.setItem(storageKey, String(Math.round(value)));
      } catch {
        // ignore write failures (private mode, quota, etc.)
      }
    },
    [storageKey]
  );

  const flushWidth = useCallback(() => {
    rafRef.current = null;
    setWidth(pendingWidthRef.current);
  }, []);

  const scheduleWidth = useCallback(
    (next: number) => {
      pendingWidthRef.current = clamp(next, min, max);
      if (rafRef.current != null) return;
      if (typeof window === "undefined") {
        setWidth(pendingWidthRef.current);
        return;
      }
      rafRef.current = window.requestAnimationFrame(flushWidth);
    },
    [flushWidth, min, max]
  );

  const setBodyDragging = useCallback((active: boolean) => {
    if (typeof document === "undefined") return;
    // Inline body styles keep the col-resize cursor steady during a drag so it
    // doesn't flicker back to the default over other elements.
    document.body.style.cursor = active ? "col-resize" : "";
    document.body.style.userSelect = active ? "none" : "";
  }, []);

  useEffect(() => {
    return () => {
      if (rafRef.current != null && typeof window !== "undefined") {
        window.cancelAnimationFrame(rafRef.current);
      }
      setBodyDragging(false);
    };
  }, [setBodyDragging]);

  const reset = useCallback(() => {
    setWidth(defaultWidth);
    persist(defaultWidth);
  }, [defaultWidth, persist]);

  const onPointerMove = useCallback(
    (event: React.PointerEvent<HTMLDivElement>) => {
      // Only track while dragging (pointer captured).
      if (!event.currentTarget.hasPointerCapture(event.pointerId)) return;
      const delta = event.clientX - dragStartXRef.current;
      // Left panel grows as pointer moves right; right panel grows as it moves left.
      const next =
        side === "left"
          ? dragStartWidthRef.current + delta
          : dragStartWidthRef.current - delta;
      scheduleWidth(next);
    },
    [side, scheduleWidth]
  );

  const endDrag = useCallback(
    (event: React.PointerEvent<HTMLDivElement>) => {
      if (!event.currentTarget.hasPointerCapture(event.pointerId)) return;
      event.currentTarget.releasePointerCapture(event.pointerId);
      setBodyDragging(false);
      // Persist the last requested (pending) width — latestWidthRef only holds
      // the last width flushed to state, which lags the final pointer position
      // by up to one animation frame.
      persist(pendingWidthRef.current);
    },
    [persist, setBodyDragging]
  );

  const onPointerDown = useCallback(
    (event: React.PointerEvent<HTMLDivElement>) => {
      if (event.button !== 0) return;
      // Don't preventDefault (it would suppress focus on the tabbable handle);
      // focus it explicitly so keyboard resize works right after a click.
      dragStartXRef.current = event.clientX;
      dragStartWidthRef.current = latestWidthRef.current;
      pendingWidthRef.current = latestWidthRef.current;
      event.currentTarget.setPointerCapture(event.pointerId);
      event.currentTarget.focus();
      setBodyDragging(true);
    },
    [setBodyDragging]
  );

  const onDoubleClick = useCallback(() => {
    reset();
  }, [reset]);

  const onKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLDivElement>) => {
      let next: number | null = null;
      if (event.key === "ArrowLeft") {
        next = latestWidthRef.current + (side === "left" ? -KEYBOARD_STEP : KEYBOARD_STEP);
      } else if (event.key === "ArrowRight") {
        next = latestWidthRef.current + (side === "left" ? KEYBOARD_STEP : -KEYBOARD_STEP);
      }
      if (next == null) return;
      event.preventDefault();
      const clamped = clamp(next, min, max);
      setWidth(clamped);
      persist(clamped);
    },
    [side, min, max, persist]
  );

  const handleProps: React.HTMLAttributes<HTMLDivElement> = {
    role: "separator",
    "aria-orientation": "vertical",
    "aria-label": "Resize panel",
    "aria-valuenow": Math.round(width),
    "aria-valuemin": min,
    "aria-valuemax": max,
    tabIndex: 0,
    onPointerDown,
    onPointerMove,
    onPointerUp: endDrag,
    onPointerCancel: endDrag,
    onDoubleClick,
    onKeyDown,
    style: { cursor: "col-resize", touchAction: "none" },
  };

  return { width, handleProps, reset };
}
