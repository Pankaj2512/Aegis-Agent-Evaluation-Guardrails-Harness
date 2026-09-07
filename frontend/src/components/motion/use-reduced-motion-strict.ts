"use client";
import { useReducedMotion } from "framer-motion";

/**
 * Strict reduced-motion: returns true if the user has prefers-reduced-motion: reduce.
 * Components should disable looping or large motion when this is true.
 * Sub-120ms transitions (hover, button press) may still run — those don't trigger this gate.
 */
export function useReducedMotionStrict(): boolean {
  const prefers = useReducedMotion();
  return prefers === true;
}