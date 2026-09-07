"use client";
import { motion, type HTMLMotionProps } from "framer-motion";
import { ReactNode } from "react";

type Props = HTMLMotionProps<"div"> & { children: ReactNode };

/**
 * Hover-lift wrapper. Always active (hover transitions are <120ms — exempt from reduced-motion).
 * Lifts 1px and intensifies shadow on hover.
 */
export function HoverLift({ children, className, ...rest }: Props) {
  return (
    <motion.div
      className={className}
      whileHover={{ y: -1, transition: { duration: 0.12, ease: [0.16, 1, 0.3, 1] } }}
      {...rest}
    >
      {children}
    </motion.div>
  );
}