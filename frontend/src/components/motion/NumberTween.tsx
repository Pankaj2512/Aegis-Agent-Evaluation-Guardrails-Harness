"use client";
import { useEffect, useRef, useState } from "react";
import { useReducedMotionStrict } from "./use-reduced-motion-strict";

type Props = {
  value: number;
  /** Decimal places to display. Defaults to 0. */
  precision?: number;
  /** Append a suffix like "%" or "ms". */
  suffix?: string;
  /** Duration in ms. Defaults to 320. */
  duration?: number;
  className?: string;
};

export function NumberTween({ value, precision = 0, suffix = "", duration = 320, className }: Props) {
  const reduce = useReducedMotionStrict();
  const [display, setDisplay] = useState(value);
  const fromRef = useRef(value);
  const startTimeRef = useRef<number | null>(null);

  useEffect(() => {
    if (reduce) {
      setDisplay(value);
      return;
    }
    const from = fromRef.current;
    const to = value;
    if (from === to) return;
    startTimeRef.current = null;
    let raf = 0;
    const tick = (t: number) => {
      if (startTimeRef.current === null) startTimeRef.current = t;
      const elapsed = t - startTimeRef.current;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplay(from + (to - from) * eased);
      if (progress < 1) {
        raf = requestAnimationFrame(tick);
      } else {
        fromRef.current = to;
      }
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value, duration, reduce]);

  return (
    <span className={className}>
      {display.toLocaleString(undefined, {
        minimumFractionDigits: precision,
        maximumFractionDigits: precision,
      })}
      {suffix}
    </span>
  );
}