"use client";

import { formatFullTimestamp } from "@/lib/format-date";
import { cn } from "@/lib/utils";

interface EvalTrendPoint {
  run_id: string;
  workflow_name?: string | null;
  created_at: string;
  aggregate: number;
  passed?: boolean | null;
}

interface EvalTrendChartProps {
  points: EvalTrendPoint[];
  className?: string;
}

export function EvalTrendChart({ points, className }: EvalTrendChartProps) {
  if (points.length === 0) {
    return <p className="text-caption">No eval runs yet — runs with an Evaluation node chart their scores here</p>;
  }

  const maxScore = 5;

  return (
    <div className={cn("space-y-3", className)}>
      <div className="flex h-32 items-end gap-1.5">
        {points.map((point) => {
          const height = Math.max(8, (point.aggregate / maxScore) * 100);
          const color =
            point.passed === false
              ? "bg-destructive/80"
              : point.passed === true
                ? "bg-success/80"
                : "bg-accent/80";

          return (
            <div
              key={point.run_id}
              className="group relative flex flex-1 flex-col items-center justify-end"
              title={`${point.aggregate.toFixed(2)} / 5 — ${formatFullTimestamp(point.created_at)}`}
            >
              <div
                className={cn("w-full rounded-t transition-all", color)}
                style={{ height: `${height}%` }}
              />
            </div>
          );
        })}
      </div>
      <div className="flex justify-between text-2xs text-muted">
        <span>Older</span>
        <span>Recent eval runs (aggregate / 5)</span>
        <span>Newer</span>
      </div>
    </div>
  );
}