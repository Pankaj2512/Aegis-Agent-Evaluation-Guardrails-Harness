/**
 * Parse API timestamps. SQLite/FastAPI often emit naive UTC without an offset
 * (`2026-08-06T20:48:47`); ECMA-262 treats those as local time, shifting every
 * "x ago" by the viewer's zone. Append Z when no offset is present.
 */
export function parseTimestamp(iso: string): Date {
  if (!iso) return new Date(NaN);
  const s = String(iso).trim();
  // Already has Z or ±HH:MM / ±HHMM offset
  if (/[zZ]$/.test(s) || /[+-]\d{2}:?\d{2}$/.test(s)) {
    return new Date(s);
  }
  // Date-only: keep as UTC midnight
  if (/^\d{4}-\d{2}-\d{2}$/.test(s)) {
    return new Date(`${s}T00:00:00Z`);
  }
  // Naive datetime → treat as UTC
  if (/^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}/.test(s)) {
    const normalized = s.includes("T") ? s : s.replace(" ", "T");
    return new Date(`${normalized}Z`);
  }
  return new Date(s);
}

export function formatRelativeTime(iso: string, now = Date.now()): string {
  const then = parseTimestamp(iso).getTime();
  if (Number.isNaN(then)) return iso;

  const diffSec = Math.max(0, Math.round((now - then) / 1000));
  if (diffSec < 45) return "just now";

  const diffMin = Math.round(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;

  const diffHr = Math.round(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;

  const diffDay = Math.round(diffHr / 24);
  if (diffDay < 7) return `${diffDay}d ago`;

  return parseTimestamp(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function formatFullTimestamp(iso: string): string {
  return parseTimestamp(iso).toLocaleString();
}

/**
 * Renders the instant in UTC with the zone spelled out. Schedules (cron
 * windows, "next runs") are stored and evaluated in UTC, so showing them in the
 * viewer's local zone under a "UTC" heading is an off-by-hours lie — this is
 * the formatter for anything labelled UTC.
 */
export function formatUtcTimestamp(iso: string): string {
  const d = parseTimestamp(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, { timeZone: "UTC", timeZoneName: "short" });
}