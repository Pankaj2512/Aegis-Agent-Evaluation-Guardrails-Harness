"use client";
import { AnimatePresence, motion } from "framer-motion";
import { ReactNode } from "react";
import { useReducedMotionStrict } from "./use-reduced-motion-strict";

type Props = {
  side: "left" | "right";
  open: boolean;
  children: ReactNode;
  className?: string;
};

/**
 * Slides a panel in/out from an edge using transform+opacity only (never
 * width/height, which would reflow the layout). Enter 220ms, exit 160ms.
 * Under strict reduced motion, renders a plain conditional div.
 */
export function PanelSlide({ side, open, children, className }: Props) {
  const reduce = useReducedMotionStrict();
  const offset = side === "right" ? 24 : -24;

  if (reduce) {
    return open ? <div className={className}>{children}</div> : null;
  }

  return (
    <AnimatePresence initial={false}>
      {open && (
        <motion.div
          className={className}
          initial={{ x: offset, opacity: 0 }}
          animate={{
            x: 0,
            opacity: 1,
            transition: { duration: 0.22, ease: [0.16, 1, 0.3, 1] },
          }}
          exit={{
            x: offset,
            opacity: 0,
            transition: { duration: 0.16, ease: [0.16, 1, 0.3, 1] },
          }}
        >
          {children}
        </motion.div>
      )}
    </AnimatePresence>
  );
}
