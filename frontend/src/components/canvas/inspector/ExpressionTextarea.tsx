"use client";

import {
  forwardRef,
  useCallback,
  useLayoutEffect,
  useMemo,
  useRef,
  type UIEvent,
} from "react";
import { cn } from "@/lib/utils";

/* ============================================================================
 * ExpressionTextarea — a drop-in <textarea> that highlights {{ }} expression
 * references inline (Tier-4 rich-editor parity).
 *
 * TECHNIQUE — textarea-over-backdrop overlay:
 *   • A backdrop <div> (aria-hidden, pointer-events-none) paints the text with
 *     {{...}} spans tinted.
 *   • A real <textarea> sits ON TOP with transparent text (so it never
 *     double-paints the glyphs) but a VISIBLE caret + selection, and owns all
 *     input/focus/keyboard handling.
 *
 * ── PAIRED-STYLES INVARIANT (read before touching styles) ───────────────────
 *   For the tinted columns in the backdrop to line up EXACTLY under the caret,
 *   the backdrop and the textarea MUST share byte-identical box + glyph metrics:
 *     font-family, font-size, line-height, letter-spacing, tab-size,
 *     padding, border-width, box-sizing, white-space (pre-wrap), overflow-wrap.
 *   Those shared metrics live in the single `FIELD_METRICS` const below and in
 *   the caller-supplied `className` — BOTH are applied verbatim to BOTH layers.
 *   Rules that keep the columns from drifting:
 *     1. Never add a metric-affecting utility (padding / margin / border-width /
 *        tracking / font-size / line-height) to only one layer.
 *     2. Highlight <span>s may ONLY set background, color and border-radius —
 *        all layout-neutral. NEVER give a span padding/margin/border, or the
 *        glyph advance shifts and every following column drifts.
 *     3. Scroll is mirrored (backdrop.scrollTop/Left ← textarea) on every
 *        scroll + value change so long content stays aligned.
 *     4. A trailing zero-width space guards the backdrop's height so a value
 *        ending in "\n" keeps its final (empty) line box.
 *   The paint/escape is done with React elements (never dangerouslySetInnerHTML),
 *   so arbitrary user input is HTML-escaped for free.
 * ==========================================================================*/

// The ONLY styles that must stay identical on both layers. Mirrors the box +
// glyph metrics of src/components/ui/textarea.tsx so an ExpressionTextarea is
// visually indistinguishable from a plain <Textarea>. Caller `className`
// (e.g. "font-mono text-xs") is layered on top of this on BOTH elements.
const FIELD_METRICS =
  "box-border w-full min-h-[88px] rounded-lg border px-3 py-2.5 " +
  // scrollbar-gutter:stable keeps both layers the same content width once a
  // classic scrollbar appears — without it the backdrop (overflow-hidden) is
  // wider than the textarea and columns drift as you scroll.
  "text-sm leading-6 whitespace-pre-wrap break-words " +
  "overflow-x-hidden overflow-y-auto [scrollbar-gutter:stable]";

// Quiet-accent treatment. `accent` in this system is a warm NEUTRAL (collapsed
// into the mono ramp — "no second hue in the chrome"), so tinting refs with it
// respects the "chroma = data semantics only" invariant: refs read as a token,
// not candy. bg-accent-muted is the purpose-built <=10% accent wash.
const REF_CLASS = "rounded-[3px] bg-accent-muted text-accent";
// An unclosed "{{" tail is an incomplete reference — a muted warning tint (the
// one place chroma is warranted here: it flags an invalid/partial expression).
const OPEN_CLASS = "rounded-[3px] bg-warning/10 text-warning";

type Segment = { kind: "text" | "ref" | "open"; value: string };

// Closed reference, matching the brief's rule /{{[^}]*}}/g.
const CLOSED_REF = /\{\{[^}]*\}\}/g;

/** Split raw text into plain / closed-ref / unclosed-tail segments. */
function tokenize(text: string): Segment[] {
  const segments: Segment[] = [];
  let last = 0;
  let match: RegExpExecArray | null;
  CLOSED_REF.lastIndex = 0;
  while ((match = CLOSED_REF.exec(text)) !== null) {
    if (match.index > last) {
      segments.push({ kind: "text", value: text.slice(last, match.index) });
    }
    segments.push({ kind: "ref", value: match[0] });
    last = match.index + match[0].length;
  }
  // Whatever trails the last closed ref may still open an unterminated "{{".
  const rest = text.slice(last);
  const openAt = rest.indexOf("{{");
  if (openAt === -1) {
    if (rest) segments.push({ kind: "text", value: rest });
  } else {
    if (openAt > 0) segments.push({ kind: "text", value: rest.slice(0, openAt) });
    segments.push({ kind: "open", value: rest.slice(openAt) });
  }
  return segments;
}

export type ExpressionTextareaProps = React.ComponentPropsWithoutRef<"textarea">;

/**
 * Drop-in replacement for a <textarea>: identical prop surface (value, onChange,
 * placeholder, rows, className, id, aria-*, disabled, onFocus/onBlur, …) and the
 * ref is forwarded to the inner textarea, so cursor/selection/insert logic that
 * relies on the element keeps working unchanged.
 */
export const ExpressionTextarea = forwardRef<HTMLTextAreaElement, ExpressionTextareaProps>(
  function ExpressionTextarea({ className, value, disabled, onScroll, ...rest }, ref) {
    const text = typeof value === "string" ? value : value == null ? "" : String(value);
    const segments = useMemo(() => tokenize(text), [text]);

    const innerRef = useRef<HTMLTextAreaElement | null>(null);
    const backdropRef = useRef<HTMLDivElement | null>(null);

    // Merge the forwarded ref with our own so we can drive scroll sync while the
    // caller still gets the raw textarea node.
    const setRefs = useCallback(
      (node: HTMLTextAreaElement | null) => {
        innerRef.current = node;
        if (typeof ref === "function") ref(node);
        else if (ref) (ref as React.MutableRefObject<HTMLTextAreaElement | null>).current = node;
      },
      [ref]
    );

    const syncScroll = useCallback(() => {
      const ta = innerRef.current;
      const bd = backdropRef.current;
      if (!ta || !bd) return;
      bd.scrollTop = ta.scrollTop;
      bd.scrollLeft = ta.scrollLeft;
    }, []);

    // Re-mirror after every value change (typing can auto-scroll the caret into
    // view) and on mount. useLayoutEffect keeps it flicker-free.
    useLayoutEffect(() => {
      syncScroll();
    }, [text, syncScroll]);

    const handleScroll = (e: UIEvent<HTMLTextAreaElement>) => {
      syncScroll();
      onScroll?.(e);
    };

    return (
      <div className="relative w-full">
        {/* Textarea first in DOM so the backdrop can react to its state via
            `peer-*`; z-index (not DOM order) keeps the backdrop painted behind. */}
        <textarea
          ref={setRefs}
          value={value}
          disabled={disabled}
          onScroll={handleScroll}
          className={cn(
            FIELD_METRICS,
            className,
            // Interactive chrome (border, focus ring, caret) lives here; the fill
            // is transparent so the backdrop's tinted text shows through.
            "peer relative z-[1] resize-y appearance-none bg-transparent text-transparent",
            "caret-foreground outline-none transition-[border-color,box-shadow]",
            "placeholder:text-muted hover:border-border-strong",
            "focus-visible:border-primary/55 focus-visible:ring-2 focus-visible:ring-primary/20 focus-visible:ring-offset-2 focus-visible:ring-offset-bg",
            "disabled:cursor-not-allowed",
            "aria-invalid:border-destructive aria-invalid:ring-2 aria-invalid:ring-destructive/20 aria-invalid:focus-visible:border-destructive aria-invalid:focus-visible:ring-destructive/20"
          )}
          {...rest}
        />
        <div
          ref={backdropRef}
          aria-hidden
          className={cn(
            FIELD_METRICS,
            className,
            // Metric-identical to the textarea, minus interactivity. The fill +
            // text colour live here. `!border-transparent` neutralises any border
            // colour arriving via `className` (e.g. border-destructive) so only
            // the textarea's border is ever visible.
            // overflow-y-auto + stable gutter matches the textarea; hide the
            // backdrop scrollbar so only one rail is visible while scrollTop stays synced.
            "pointer-events-none absolute inset-0 z-0 select-none !border-transparent",
            "[scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden",
            "bg-surface-input text-foreground",
            "peer-hover:bg-surface-hover/50 peer-focus-visible:bg-background",
            "peer-disabled:bg-surface peer-disabled:text-subtle peer-disabled:opacity-70"
          )}
        >
          {segments.map((seg, i) =>
            seg.kind === "ref" ? (
              <span key={i} className={REF_CLASS}>
                {seg.value}
              </span>
            ) : seg.kind === "open" ? (
              <span key={i} className={OPEN_CLASS}>
                {seg.value}
              </span>
            ) : (
              <span key={i}>{seg.value}</span>
            )
          )}
          {/* Trailing-newline guard — keeps a final empty line box so the
              backdrop height matches the textarea when `value` ends with "\n". */}
          {"​"}
        </div>
      </div>
    );
  }
);
