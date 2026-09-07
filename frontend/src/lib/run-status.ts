export type RunStatusVariant = "success" | "warning" | "destructive" | "accent" | "outline";

/** Semantic tone for a run/node status. `muted` is the neutral fallback —
 *  each projection below spells it with its own surface-appropriate token. */
export type RunStatusTone = "success" | "warning" | "destructive" | "accent" | "muted";

/**
 * The one status→tone decision in the app. Chroma is reserved for data
 * semantics, so a live run must read the same on the canvas run deck, the
 * observability tables, and the trace: live work is `warning` (amber), a run
 * parked on a human is `accent`. Synonyms emitted by the executor
 * (success/passed, error, in_progress/starting) fold into the same buckets so
 * no surface has to re-normalize.
 */
export function runStatusTone(status: string): RunStatusTone {
  const s = status.toLowerCase();
  if (s === "completed" || s === "success" || s === "passed") return "success";
  if (s === "failed" || s === "error" || s === "cancelled") return "destructive";
  if (s === "awaiting_approval" || s === "awaiting") return "accent";
  if (
    s === "running" ||
    s === "pending" ||
    s === "queued" ||
    s === "waiting" ||
    s === "starting" ||
    s === "in_progress" ||
    s === "warned"
  ) {
    return "warning";
  }
  return "muted";
}

export function runStatusVariant(status: string): RunStatusVariant {
  const tone = runStatusTone(status);
  return tone === "muted" ? "outline" : tone;
}

/** Status → text color token (headers, inline status words, attention lists). */
export function runStatusTextClass(status: string): string {
  const tone = runStatusTone(status);
  if (tone === "success") return "text-success";
  if (tone === "warning") return "text-warning";
  if (tone === "destructive") return "text-destructive";
  if (tone === "accent") return "text-accent";
  return "text-muted";
}

/** Status → dot/pip fill (run tables, session mixes). */
export function runStatusDotClass(status: string): string {
  const tone = runStatusTone(status);
  if (tone === "success") return "bg-success";
  if (tone === "warning") return "bg-warning";
  if (tone === "destructive") return "bg-destructive";
  if (tone === "accent") return "bg-accent";
  return "bg-muted";
}

/** Status → ring token for glyphs. Callers own the ring width/opacity
 *  (e.g. `cn("ring-2", runStatusRingClass(s))`); neutral stays on the hairline
 *  border token so an unremarkable node doesn't gain a visible halo. */
export function runStatusRingClass(status: string): string {
  const tone = runStatusTone(status);
  if (tone === "success") return "ring-success";
  if (tone === "warning") return "ring-warning";
  if (tone === "destructive") return "ring-destructive";
  if (tone === "accent") return "ring-accent";
  return "ring-border";
}

/** Status → border token for result cards. Neutral keeps the card's own
 *  border treatment rather than tinting it muted. */
export function runStatusBorderClass(status: string): string {
  const tone = runStatusTone(status);
  if (tone === "success") return "border-success";
  if (tone === "warning") return "border-warning";
  if (tone === "destructive") return "border-destructive";
  if (tone === "accent") return "border-accent";
  return "border-border";
}

/** Guardrail severity tone. Distinct from run status: a guardrail that
 *  `blocked` is a destructive outcome, and anything unrecognized renders as a
 *  neutral outlined chip rather than borrowing a severity hue. */
export type GuardrailStatusTone = "success" | "warning" | "destructive" | "outline";

export function guardrailStatusTone(status: string): GuardrailStatusTone {
  const s = status.toLowerCase();
  if (s === "passed" || s === "ok" || s === "completed") return "success";
  if (s === "warned" || s === "warn") return "warning";
  if (s === "blocked" || s === "failed" || s === "error") return "destructive";
  return "outline";
}

export function runStatusLabel(status: string): string {
  if (status === "awaiting_approval") return "awaiting approval";
  return status.replace(/_/g, " ");
}
