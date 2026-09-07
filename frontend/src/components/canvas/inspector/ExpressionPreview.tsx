"use client";

import { useRef, useState } from "react";
import { Eye, EyeOff, Loader2 } from "lucide-react";
import { api, type ExpressionPreviewResult } from "@/lib/api";
import { formatOutput } from "@/lib/pretty-output";
import { cn } from "@/lib/utils";

const MAX_CHARS = 800;

/** True when the resolving run had no context at all to bind against. */
function hasBoundContext(ctx: ExpressionPreviewResult["context_available"]): boolean {
  return Boolean(ctx && (ctx.input || ctx.last_output || (ctx.steps?.length ?? 0) > 0));
}

/**
 * Feature 3 — live expression preview. Extends the expression affordance next
 * to a {{ }} field: an eye button (revealed on the field's hover/focus group)
 * that resolves the current template against the workflow's latest run and
 * renders the result inline beneath the field. Fires only on explicit click,
 * caches per-expression, and never toasts — errors read quietly in place.
 */
export function ExpressionPreview({
  workflowId,
  expression,
}: {
  workflowId?: string;
  expression: string;
}) {
  const [pending, setPending] = useState(false);
  const [result, setResult] = useState<ExpressionPreviewResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Which exact expression the open panel is showing — so editing the field
  // after a preview quietly retires the stale result instead of misleading.
  const [shownFor, setShownFor] = useState<string | null>(null);
  // Short-lived cache keyed by expression + run_id so a newer run does not
  // keep serving a superseded resolution. Entries expire after CACHE_TTL_MS.
  const cacheRef = useRef<Map<string, { at: number; res: ExpressionPreviewResult }>>(new Map());
  const CACHE_TTL_MS = 15_000;

  // Only expression-bearing values are previewable, and only when we know the
  // workflow to resolve against.
  if (!workflowId || !expression.includes("{{")) return null;

  const open = shownFor === expression && (result != null || error != null);

  const handlePreview = async () => {
    // A second click on the same expression collapses the panel.
    if (open) {
      setShownFor(null);
      return;
    }
    // Reuse a fresh cache hit for this exact expression; expired entries force
    // a re-fetch so a newer run is not hidden behind a superseded resolution.
    const now = Date.now();
    const entries = Array.from(cacheRef.current.entries());
    for (const [key, entry] of entries) {
      if (now - entry.at > CACHE_TTL_MS) cacheRef.current.delete(key);
    }
    const cached = entries.find(
      ([key, entry]) => key.startsWith(`${expression}::`) && now - entry.at <= CACHE_TTL_MS
    );
    if (cached) {
      setResult(cached[1].res);
      setError(null);
      setShownFor(expression);
      return;
    }
    setPending(true);
    setError(null);
    try {
      const res = await api.previewExpression(workflowId, {
        expression,
        run_id: null,
        sample_input: null,
      });
      const cacheKey = `${expression}::${res.run_id ?? "none"}`;
      Array.from(cacheRef.current.keys()).forEach((key) => {
        if (key.startsWith(`${expression}::`) && key !== cacheKey) {
          cacheRef.current.delete(key);
        }
      });
      cacheRef.current.set(cacheKey, { at: Date.now(), res });
      setResult(res);
      setShownFor(expression);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Preview failed");
      setResult(null);
      setShownFor(expression);
    } finally {
      setPending(false);
    }
  };

  const shown = open && shownFor === expression ? result : null;
  const shownError = open && shownFor === expression ? error : null;
  const bound = shown ? hasBoundContext(shown.context_available) : false;
  const shortId = shown?.run_id ? shown.run_id.slice(0, 8) : null;
  const rendered = shown?.rendered ?? null;
  const caption =
    bound && shortId ? `resolved against run ${shortId}` : "no run data — showing raw";
  const body = rendered ?? expression;
  const formatted = formatOutput(body).text;
  const clamped =
    formatted.length > MAX_CHARS ? `${formatted.slice(0, MAX_CHARS)}…` : formatted;

  return (
    <div className="mt-1">
      <button
        type="button"
        onClick={handlePreview}
        aria-expanded={open}
        aria-label={open ? "Hide expression preview" : "Preview resolved expression"}
        title="Preview resolved value"
        className={cn(
          "focus-ring inline-flex h-6 items-center gap-1 rounded-md px-1.5 text-2xs text-muted transition-[color,opacity,background-color] duration-1 hover:bg-surface-hover hover:text-foreground",
          // Reveal on the field's hover/focus group; stay put once engaged.
          "opacity-0 group-hover:opacity-100 group-focus-within:opacity-100",
          (open || pending) && "opacity-100"
        )}
      >
        {pending ? (
          <Loader2 className="h-3 w-3 animate-spin" aria-hidden />
        ) : open ? (
          <EyeOff className="h-3 w-3" aria-hidden />
        ) : (
          <Eye className="h-3 w-3" aria-hidden />
        )}
        Preview
      </button>

      {shownError ? (
        <p className="mt-1 whitespace-pre-wrap break-words font-mono text-2xs leading-5 text-destructive/80">
          {shownError}
        </p>
      ) : shown ? (
        <div className="mt-1 rounded-md border border-border bg-surface-input/60 px-2 py-1.5">
          <p className="font-mono text-2xs text-subtle">{caption}</p>
          {shown.error ? (
            <p className="mt-1 whitespace-pre-wrap break-words font-mono text-2xs leading-5 text-destructive/80">
              {shown.error}
            </p>
          ) : (
            <pre className="mt-1 max-h-24 overflow-y-auto whitespace-pre-wrap break-words font-mono text-2xs leading-5 text-muted">
              {clamped.trim() ? clamped : "—"}
            </pre>
          )}
        </div>
      ) : null}
    </div>
  );
}
