export const pluralize = (n: number, singular: string, plural = `${singular}s`) =>
  `${n} ${n === 1 ? singular : plural}`;

/** Canonical money formatting: 4 decimals covers per-run costs; sub-cent
 * dust shows a floor instead of misleading zeros. */
export function formatCostUsd(usd: number | null | undefined): string {
  if (typeof usd !== "number" || usd <= 0) return "—";
  if (usd < 0.0001) return "<$0.0001";
  return `$${usd.toFixed(4)}`;
}

/** "1.0" reads as false precision on a tweened metric; drop the dead decimal. */
const stripTrailingZero = (s: string) => s.replace(/\.0$/, "");

/**
 * Canonical duration/latency formatting — the single implementation for every
 * ms value in the app (trace rows, timeline ticks, percentile tiles, run deck).
 * No space before the unit: "940ms", "1.2s", "2s", "12s", "1,204s".
 */
export function formatDurationMs(ms: number | null | undefined): string {
  if (typeof ms !== "number" || !Number.isFinite(ms)) return "—";
  if (ms < 1000) return `${Math.round(ms)}ms`;
  if (ms < 10000) return `${stripTrailingZero((ms / 1000).toFixed(1))}s`;
  return `${Math.round(ms / 1000).toLocaleString()}s`;
}

/**
 * Canonical token-count formatting: exact with thousands grouping while the
 * number stays readable, abbreviated above 10k so it fits a chip ("12.3k",
 * "1.2M"). Grouping matters — bare "12345" loses scannability in a mono column.
 */
export function formatTokens(n: number | null | undefined): string {
  if (typeof n !== "number" || !Number.isFinite(n)) return "—";
  if (n < 10000) return n.toLocaleString();
  if (n < 1000000) return `${stripTrailingZero((n / 1000).toFixed(1))}k`;
  return `${stripTrailingZero((n / 1000000).toFixed(1))}M`;
}
