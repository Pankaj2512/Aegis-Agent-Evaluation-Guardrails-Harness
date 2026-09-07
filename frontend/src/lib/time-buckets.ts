import { parseTimestamp } from "@/lib/format-date";

interface Stamped {
  created_at?: string | null;
}

/**
 * Bucket timestamped items into `bucketCount` equal windows between the
 * oldest and newest timestamps. Tolerates unsorted and duplicated input —
 * live-stream patches mutate cached lists in place.
 *
 * Returns counts per bucket (oldest → newest), or averages of `value(item)`
 * when a selector is given (empty buckets carry the previous average so
 * sparklines don't spike to zero on sparse windows).
 */
export function timeBuckets<T extends Stamped>(
  items: T[],
  bucketCount: number,
  value?: (item: T) => number | null | undefined
): number[] {
  const stamps = items
    .map((item) => ({
      item,
      // parseTimestamp treats naive SQLite UTC as UTC (not local), matching the
      // rest of the app's timestamp handling.
      t: item.created_at ? parseTimestamp(item.created_at).getTime() : NaN,
    }))
    .filter((entry) => Number.isFinite(entry.t));
  if (stamps.length === 0 || bucketCount < 1) return [];

  let min = Infinity;
  let max = -Infinity;
  for (const { t } of stamps) {
    if (t < min) min = t;
    if (t > max) max = t;
  }
  const rawSpan = max - min;

  // A single item, or many items sharing one timestamp, has no real time
  // spread — bucketing them all into slot 0 fabricates a cliff. Return a flat
  // series at the true value/count instead.
  if (rawSpan === 0) {
    if (value) {
      let sum = 0;
      let count = 0;
      for (const { item } of stamps) {
        const v = value(item);
        if (typeof v === "number" && Number.isFinite(v)) {
          sum += v;
          count += 1;
        }
      }
      const avg = count > 0 ? sum / count : 0;
      return new Array<number>(bucketCount).fill(avg);
    }
    // Count mode: spread the total evenly so the line reads flat, not spiky.
    return new Array<number>(bucketCount).fill(stamps.length / bucketCount);
  }

  const span = rawSpan;

  const sums = new Array<number>(bucketCount).fill(0);
  const counts = new Array<number>(bucketCount).fill(0);
  for (const { item, t } of stamps) {
    const idx = Math.min(bucketCount - 1, Math.floor(((t - min) / span) * bucketCount));
    if (value) {
      const v = value(item);
      if (typeof v !== "number" || !Number.isFinite(v)) continue;
      sums[idx] += v;
      counts[idx] += 1;
    } else {
      counts[idx] += 1;
    }
  }

  if (!value) return counts;

  const out: number[] = [];
  let carry = 0;
  for (let i = 0; i < bucketCount; i++) {
    if (counts[i] > 0) carry = sums[i] / counts[i];
    out.push(carry);
  }
  return out;
}
