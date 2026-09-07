"use client";

import { MotionConfig } from "framer-motion";

/** Honors prefers-reduced-motion for all framer-motion animations app-wide. */
export function MotionProvider({ children }: { children: React.ReactNode }) {
  return <MotionConfig reducedMotion="user">{children}</MotionConfig>;
}
