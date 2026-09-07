"use client";

import type { EvalScores } from "@/types/workflow";
import { cn } from "@/lib/utils";

// Bar grammar (shared with Sparkline): neutral fill, hue only as a single
// dot next to the label — never a full colored fill. `dot` is a text-* token
// so the swatch reads as a legend key, not decoration.
const SCORE_KEYS = [
  { key: "faithfulness", label: "Faithfulness", dot: "text-primary" },
  { key: "helpfulness", label: "Helpfulness", dot: "text-accent" },
  { key: "relevance", label: "Relevance", dot: "text-success" },
  { key: "toxicity", label: "Toxicity", dot: "text-destructive", invert: true },
] as const;

interface EvalScoresChartProps {
  scores: EvalScores;
  delta?: Record<string, number | null>;
  compact?: boolean;
}

function scoreValue(scores: EvalScores, key: string): number | null {
  const val = scores[key as keyof EvalScores];
  return typeof val === "number" ? val : null;
}

function formatDelta(value: number | null | undefined) {
  if (value == null) return null;
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}`;
}

function radarPoints(scores: EvalScores): string {
  const cx = 60;
  const cy = 60;
  const maxR = 45;
  const angles = SCORE_KEYS.map((_, i) => (Math.PI * 2 * i) / SCORE_KEYS.length - Math.PI / 2);

  return angles
    .map((angle, i) => {
      const key = SCORE_KEYS[i];
      let val = scoreValue(scores, key.key) ?? 0;
      if ("invert" in key && key.invert) val = 6 - val;
      const r = (val / 5) * maxR;
      const x = cx + r * Math.cos(angle);
      const y = cy + r * Math.sin(angle);
      return `${x},${y}`;
    })
    .join(" ");
}

export function EvalScoresChart({ scores, delta, compact }: EvalScoresChartProps) {
  const aggregate = scoreValue(scores, "aggregate_score");

  return (
    <div className={cn("space-y-4", compact && "space-y-3")}>
      {aggregate != null && (
        <div
          className={cn(
            "flex rounded-lg border border-border bg-surface-input px-3 py-2",
            compact ? "flex-col items-start gap-1" : "items-baseline justify-between"
          )}
        >
          <span className="text-micro">Aggregate</span>
          <div className="flex items-baseline gap-2">
            <span
              className={cn(
                "font-mono font-bold tabular-nums text-foreground",
                compact ? "text-xl" : "text-2xl"
              )}
            >
              {aggregate.toFixed(2)}
            </span>
            <span className="text-xs text-muted">/ 5</span>
            {delta?.aggregate_score != null && (
              <span
                className={cn(
                  "font-mono text-xs font-medium tabular-nums",
                  delta.aggregate_score > 0 ? "text-success" : "text-destructive"
                )}
              >
                {formatDelta(delta.aggregate_score)}
              </span>
            )}
          </div>
        </div>
      )}

      {!compact && (
        <div className="flex justify-center">
          <svg viewBox="0 0 120 120" className="h-28 w-28">
            {[1, 2, 3, 4, 5].map((ring) => (
              <circle
                key={ring}
                cx="60"
                cy="60"
                r={(ring / 5) * 45}
                fill="none"
                stroke="var(--border-strong)"
                strokeWidth="0.5"
              />
            ))}
            {SCORE_KEYS.map((_, i) => {
              const angle = (Math.PI * 2 * i) / SCORE_KEYS.length - Math.PI / 2;
              const x = 60 + 45 * Math.cos(angle);
              const y = 60 + 45 * Math.sin(angle);
              return (
                <line
                  key={i}
                  x1="60"
                  y1="60"
                  x2={x}
                  y2={y}
                  stroke="var(--border-strong)"
                  strokeWidth="0.5"
                />
              );
            })}
            <polygon
              points={radarPoints(scores)}
              fill="color-mix(in srgb, var(--foreground) 12%, transparent)"
              stroke="var(--foreground)"
              strokeWidth="1.5"
            />
          </svg>
        </div>
      )}

      <div className="space-y-2">
        {SCORE_KEYS.map((item) => {
          const { key, label, dot } = item;
          const invert = "invert" in item && item.invert;
          const raw = scoreValue(scores, key);
          const display = raw == null ? null : invert ? 6 - raw : raw;
          const pct = display != null ? (display / 5) * 100 : 0;
          const keyDelta = delta?.[key];

          return (
            <div key={key} className="space-y-1">
              <div className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-2 text-xs">
                <span className="flex items-center gap-1.5 text-muted">
                  {/* Single hue dot = the only category color; the bar stays neutral. */}
                  <span
                    className={cn("h-1.5 w-1.5 shrink-0 rounded-full bg-current", dot)}
                    aria-hidden
                  />
                  {label}
                </span>
                <div className="flex min-w-0 items-center justify-end gap-2">
                  <span className="font-mono font-medium tabular-nums text-foreground">
                    {raw ?? "—"}
                    {invert && raw != null && (
                      <span className="ml-1 font-sans text-muted">(lower is better)</span>
                    )}
                  </span>
                  {keyDelta != null && (
                    <span
                      className={cn(
                        "font-mono font-medium tabular-nums",
                        invert
                          ? keyDelta < 0
                            ? "text-success"
                            : "text-destructive"
                          : keyDelta > 0
                            ? "text-success"
                            : "text-destructive"
                      )}
                    >
                      {formatDelta(keyDelta)}
                    </span>
                  )}
                </div>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-surface-hover">
                {/* Neutral fill — matches Sparkline grammar (no full color wash). */}
                <div
                  className="h-full rounded-full bg-foreground/45 transition-all"
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>

      {scores.reasoning && (
        <p className="text-xs italic text-muted">{scores.reasoning}</p>
      )}
    </div>
  );
}
