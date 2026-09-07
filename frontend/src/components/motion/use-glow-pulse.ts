"use client";
import { useReducedMotionStrict } from "./use-reduced-motion-strict";

type Variant = "primary" | "warning";

/**
 * Returns the className for an animated glow pulse, or empty string when
 * reduced motion is on. Use on canvas active nodes, live status dots, etc.
 */
export function useGlowPulse(variant: Variant = "primary"): string {
  const reduce = useReducedMotionStrict();
  if (reduce) return "";
  return variant === "warning" ? "animate-glow-pulse-warning" : "animate-glow-pulse";
}