"use client";
import { motion } from "framer-motion";
import { ReactNode } from "react";
import { useReducedMotionStrict } from "./use-reduced-motion-strict";

type Props = {
  children: ReactNode;
  className?: string;
  delay?: number;
};

export function PageEnter({ children, className, delay = 0 }: Props) {
  const reduce = useReducedMotionStrict();
  if (reduce) {
    return <div className={className}>{children}</div>;
  }
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.32, ease: [0.16, 1, 0.3, 1], delay }}
    >
      {children}
    </motion.div>
  );
}