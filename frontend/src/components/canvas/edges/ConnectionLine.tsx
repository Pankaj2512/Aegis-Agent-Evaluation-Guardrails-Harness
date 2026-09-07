"use client";

import { type ConnectionLineComponentProps } from "@xyflow/react";

export function ConnectionLine({ fromX, fromY, toX, toY }: ConnectionLineComponentProps) {
  return (
    <g>
      <path
        d={`M ${fromX} ${fromY} C ${fromX + 50} ${fromY}, ${toX - 50} ${toY}, ${toX} ${toY}`}
        stroke="var(--canvas-connection)"
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeDasharray="6 4"
        fill="none"
      />
      <circle cx={toX} cy={toY} r={3} fill="var(--canvas-connection)" />
    </g>
  );
}