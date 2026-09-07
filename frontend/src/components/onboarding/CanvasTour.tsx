"use client";

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { dismissOnboarding, isOnboardingDismissed } from "@/lib/onboarding";
import { CANVAS_TOUR_STEPS, type TourStep } from "@/components/onboarding/tour-steps";

const START_EVENT = "aegis:start-canvas-tour";
const CARD_W = 288; // w-72
const CARD_H = 200; // generous estimate for clamping
const GAP = 12;
const PAD = 8; // viewport padding, matches QuickAddMenu clamp

/** Dispatch to (re)start the canvas tour from anywhere (mirrors openCommandPalette). */
export function startCanvasTour() {
  window.dispatchEvent(new Event(START_EVENT));
}

/** First visible element matching the selector, or null. */
function findVisibleAnchor(selector: string): HTMLElement | null {
  const matches = Array.from(document.querySelectorAll<HTMLElement>(selector));
  return matches.find((el) => el.getClientRects().length > 0) ?? null;
}

function warnDev(message: string) {
  if (process.env.NODE_ENV !== "production") {
    // eslint-disable-next-line no-console
    console.warn(`[CanvasTour] ${message}`);
  }
}

/**
 * Given a starting index and direction, return the index of the next step whose
 * anchor is currently visible, or null when none remain.
 */
function resolveStepIndex(from: number, dir: 1 | -1): number | null {
  let i = from;
  while (i >= 0 && i < CANVAS_TOUR_STEPS.length) {
    const step = CANVAS_TOUR_STEPS[i];
    if (findVisibleAnchor(step.selector)) return i;
    warnDev(`skipping step "${step.id}" — anchor not visible: ${step.selector}`);
    i += dir;
  }
  return null;
}

interface Position {
  top: number;
  left: number;
}

function computePosition(rect: DOMRect, placement: TourStep["placement"]): Position {
  let top = 0;
  let left = 0;
  switch (placement) {
    case "right":
      top = rect.top + rect.height / 2 - CARD_H / 2;
      left = rect.right + GAP;
      break;
    case "left":
      top = rect.top + rect.height / 2 - CARD_H / 2;
      left = rect.left - CARD_W - GAP;
      break;
    case "bottom":
      top = rect.bottom + GAP;
      left = rect.left + rect.width / 2 - CARD_W / 2;
      break;
    case "top":
    default:
      top = rect.top - CARD_H - GAP;
      left = rect.left + rect.width / 2 - CARD_W / 2;
      break;
  }
  // Clamp into the viewport — same formula shape as QuickAddMenu.
  left = Math.max(PAD, Math.min(left, window.innerWidth - CARD_W - PAD));
  top = Math.max(PAD, Math.min(top, window.innerHeight - CARD_H - PAD));
  return { top, left };
}

export function CanvasTour() {
  const [stepIndex, setStepIndex] = useState<number | null>(null);
  const [rect, setRect] = useState<DOMRect | null>(null);
  const [position, setPosition] = useState<Position | null>(null);
  const cardRef = useRef<HTMLDivElement>(null);

  const step = stepIndex === null ? null : CANVAS_TOUR_STEPS[stepIndex];

  const finish = useCallback(() => {
    dismissOnboarding("canvas-tour");
    setStepIndex(null);
    setRect(null);
    setPosition(null);
  }, []);

  const goTo = useCallback((target: number, dir: 1 | -1) => {
    const resolved = resolveStepIndex(target, dir);
    if (resolved === null) {
      dismissOnboarding("canvas-tour");
      setStepIndex(null);
      setRect(null);
      setPosition(null);
      return;
    }
    setStepIndex(resolved);
  }, []);

  const next = useCallback(() => {
    if (stepIndex === null) return;
    goTo(stepIndex + 1, 1);
  }, [stepIndex, goTo]);

  const back = useCallback(() => {
    if (stepIndex === null) return;
    goTo(stepIndex - 1, -1);
  }, [stepIndex, goTo]);

  // Auto-start on mount: poll for step 1's anchor (canvas is ssr:false, so
  // anchors appear late). Give up silently after ~4s.
  useEffect(() => {
    if (isOnboardingDismissed("canvas-tour")) return;
    let cancelled = false;
    let elapsed = 0;
    const interval = window.setInterval(() => {
      if (cancelled) return;
      elapsed += 200;
      const resolved = resolveStepIndex(0, 1);
      if (resolved !== null) {
        window.clearInterval(interval);
        setStepIndex(resolved);
      } else if (elapsed >= 4000) {
        window.clearInterval(interval);
      }
    }, 200);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, []);

  // Explicit restart via window event — starts at step 0 regardless of dismissal.
  useEffect(() => {
    const handler = () => {
      const resolved = resolveStepIndex(0, 1);
      if (resolved === null) {
        warnDev("start requested but no visible anchors found");
        return;
      }
      setStepIndex(resolved);
    };
    window.addEventListener(START_EVENT, handler);
    return () => window.removeEventListener(START_EVENT, handler);
  }, []);

  // Recompute anchor rect + card position on step change and on resize.
  useLayoutEffect(() => {
    if (!step) return;
    const recompute = () => {
      const anchor = findVisibleAnchor(step.selector);
      if (!anchor) {
        // Anchor vanished — skip forward.
        goTo((stepIndex ?? 0) + 1, 1);
        return;
      }
      const r = anchor.getBoundingClientRect();
      setRect(r);
      setPosition(computePosition(r, step.placement));
    };
    recompute();
    window.addEventListener("resize", recompute);
    return () => window.removeEventListener("resize", recompute);
  }, [step, stepIndex, goTo]);

  // Move focus to the card per step; Esc skips the tour.
  useEffect(() => {
    if (!step) return;
    cardRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        finish();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [step, finish]);

  if (!step || !rect || !position) return null;

  const isLast = stepIndex === CANVAS_TOUR_STEPS.length - 1;

  return (
    <>
      {/* Spotlight ring — no dimming overlay. */}
      <div
        aria-hidden
        className="pointer-events-none fixed z-40 rounded-lg ring-2 ring-primary/70"
        style={{
          top: rect.top - 4,
          left: rect.left - 4,
          width: rect.width + 8,
          height: rect.height + 8,
        }}
      />

      <div
        ref={cardRef}
        role="dialog"
        aria-label={step.title}
        aria-modal="false"
        tabIndex={-1}
        className="glass-panel fixed z-50 w-72 rounded-lg border border-border p-4 shadow-elev-3 outline-none"
        style={{ top: position.top, left: position.left }}
      >
        <h3 className="text-sm font-semibold text-foreground">{step.title}</h3>
        <p className="mt-1.5 text-xs leading-5 text-muted">{step.body}</p>

        <div className="mt-4 flex items-center justify-between gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={back}
            disabled={stepIndex === 0}
          >
            Back
          </Button>

          <div className="flex items-center gap-1.5" aria-hidden>
            {CANVAS_TOUR_STEPS.map((s, i) => (
              <span
                key={s.id}
                className={cn(
                  "h-1.5 w-1.5 rounded-full transition-colors",
                  i === stepIndex ? "bg-primary" : "bg-border-strong"
                )}
              />
            ))}
          </div>

          <Button size="sm" onClick={next}>
            {isLast ? "Done" : "Next"}
          </Button>
        </div>

        <button
          type="button"
          onClick={finish}
          className="focus-ring mt-2 w-full rounded-md py-1 text-2xs text-subtle transition-colors hover:text-foreground"
        >
          Skip tour
        </button>
      </div>
    </>
  );
}
