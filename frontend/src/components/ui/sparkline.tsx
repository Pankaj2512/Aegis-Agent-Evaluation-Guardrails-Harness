import { cn } from "@/lib/utils";

interface SparklineProps {
  data: number[];
  /** Accessible description, e.g. "Latency trend over the last 100 runs". */
  label: string;
  width?: number;
  height?: number;
  strokeWidth?: number;
  /** Soft area fill under the line. */
  fill?: boolean;
  /** Emphasize the most recent point. */
  showLastDot?: boolean;
  /** Color via text-* token classes; the SVG draws with currentColor. */
  className?: string;
}

/** Hand-rolled SVG sparkline — no chart library, color from currentColor. */
export function Sparkline({
  data,
  label,
  width = 96,
  height = 28,
  strokeWidth = 1.5,
  fill = false,
  showLastDot = false,
  className,
}: SparklineProps) {
  const pad = 2;
  const points =
    data.length >= 2
      ? data
      : data.length === 1
        ? // Single real value: render it as a flat line, not a fake zero.
          [data[0], data[0]]
        : // Nothing to plot yet.
          [0, 0];
  const min = Math.min(...points);
  const max = Math.max(...points);
  const span = max - min || 1;
  const stepX = (width - pad * 2) / (points.length - 1);
  const coords = points.map((v, i) => ({
    x: pad + i * stepX,
    y: pad + (height - pad * 2) * (1 - (v - min) / span),
  }));
  const polyline = coords.map((c) => `${c.x.toFixed(2)},${c.y.toFixed(2)}`).join(" ");
  const last = coords[coords.length - 1];

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      width={width}
      height={height}
      role="img"
      aria-label={label}
      className={cn("shrink-0 overflow-visible", className)}
    >
      {fill && (
        <path
          d={[
            `M ${coords[0].x.toFixed(2)} ${height - pad}`,
            ...coords.map((c) => `L ${c.x.toFixed(2)} ${c.y.toFixed(2)}`),
            `L ${last.x.toFixed(2)} ${height - pad}`,
            "Z",
          ].join(" ")}
          fill="currentColor"
          opacity={0.1}
          stroke="none"
        />
      )}
      <polyline
        points={polyline}
        fill="none"
        stroke="currentColor"
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {showLastDot && (
        <circle cx={last.x} cy={last.y} r={strokeWidth + 0.5} fill="currentColor" stroke="none" />
      )}
    </svg>
  );
}
