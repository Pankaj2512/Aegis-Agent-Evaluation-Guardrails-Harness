"use client";
import { motion } from "framer-motion";
import { Children, ReactNode } from "react";
import { useReducedMotionStrict } from "./use-reduced-motion-strict";

type Props = {
  children: ReactNode;
  className?: string;
  itemClassName?: string;
  /** Max items to stagger; remaining items snap in instantly. Defaults to 8. */
  max?: number;
};

export function StaggerList({ children, className, itemClassName, max = 8 }: Props) {
  const reduce = useReducedMotionStrict();
  const items = Children.toArray(children);
  if (reduce) {
    return (
      <div className={className}>
        {items.map((c, i) => (
          <div key={i} className={itemClassName}>
            {c}
          </div>
        ))}
      </div>
    );
  }
  return (
    <div className={className}>
      {items.map((child, i) => {
        const delay = Math.min(i, max) * 0.04;
        return (
          <motion.div
            key={i}
            className={itemClassName}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1], delay }}
          >
            {child}
          </motion.div>
        );
      })}
    </div>
  );
}