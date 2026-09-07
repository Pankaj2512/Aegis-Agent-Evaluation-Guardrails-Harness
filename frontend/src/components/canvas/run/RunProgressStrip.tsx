"use client";

import { useEffect, useState } from "react";
import { Pause, Play, Square, StepBack, StepForward, X } from "lucide-react";
import type { UseRunReplay } from "./useRunReplay";

interface RunProgressStripProps {
  completed: number;
  total: number;
  activeLabel?: string | null;
  startedAt: number;
  onStop: () => void;
}

function useElapsedSeconds(startedAt: number): number {
  const [elapsed, setElapsed] = useState(() =>
    Math.max(0, Math.floor((Date.now() - startedAt) / 1000))
  );
  useEffect(() => {
    setElapsed(Math.max(0, Math.floor((Date.now() - startedAt) / 1000)));
    const id = setInterval(() => {
      setElapsed(Math.max(0, Math.floor((Date.now() - startedAt) / 1000)));
    }, 1000);
    return () => clearInterval(id);
  }, [startedAt]);
  return elapsed;
}

/**
 * Slim run-progress pill. Rendered by the integrator inside a React Flow
 * <Panel position="top-center">.
 */
export function RunProgressStrip({
  completed,
  total,
  activeLabel,
  startedAt,
  onStop,
}: RunProgressStripProps) {
  const elapsed = useElapsedSeconds(startedAt);
  const pct = total > 0 ? Math.min(100, Math.round((completed / total) * 100)) : 0;

  return (
    <div className="relative flex items-center gap-3 overflow-hidden rounded-full glass-panel px-4 py-1.5 shadow-elev-2">
      <span
        className="h-2 w-2 shrink-0 animate-pulse rounded-full bg-active"
        aria-hidden="true"
      />
      <span className="shrink-0 font-mono text-xs text-foreground">
        {completed}/{total} nodes
      </span>
      {activeLabel && (
        <span className="min-w-0 max-w-[16rem] truncate text-xs text-muted">
          {activeLabel}
        </span>
      )}
      <span className="shrink-0 font-mono text-xs text-muted tabular-nums">
        {elapsed}s
      </span>
      <button
        type="button"
        onClick={onStop}
        aria-label="Stop run"
        className="focus-ring flex h-6 w-6 shrink-0 items-center justify-center rounded-md text-muted transition-colors hover:bg-surface-hover hover:text-foreground"
      >
        <Square className="h-3 w-3" />
      </button>
      <span
        className="absolute inset-x-0 bottom-0 h-0.5 bg-active transition-[width] duration-3"
        style={{ width: `${pct}%` }}
        aria-hidden="true"
      />
    </div>
  );
}

interface PostRunTransportProps {
  /** Replay controller from useRunReplay(). */
  replay: Pick<
    UseRunReplay,
    "steps" | "index" | "setIndex" | "playing" | "play" | "pause" | "step" | "atStart" | "atEnd" | "current" | "reducedMotion"
  >;
  /** Dismiss the transport (integrator clears replay state + restores canvas). */
  onClose: () => void;
}

/**
 * Post-run replay transport: a draggable scrubber + play/pause/step + the
 * current node label. Drives a useRunReplay() controller; the integrator wires
 * onApply so scrubbing re-drives canvas node/edge state. Reduced-motion is a
 * concern of the integrator's onApply (it should snap instead of tween) — the
 * transport UI itself has no animated advance, so it is already RM-safe.
 */
export function PostRunTransport({ replay, onClose }: PostRunTransportProps) {
  const { steps, index, setIndex, playing, play, pause, step, atStart, atEnd, current } = replay;
  const total = steps.length;
  // Slider spans [0, total]; slot 0 = clean slate (index -1), slot k = step k-1.
  const sliderValue = index + 1;
  const currentLabel = current?.label ?? current?.node_type ?? null;
  const stepNumberLabel = index < 0 ? `0/${total}` : `${index + 1}/${total}`;

  if (total === 0) return null;

  return (
    <div
      className="flex items-center gap-2.5 rounded-full glass-panel px-3 py-1.5 shadow-elev-2"
      role="group"
      aria-label="Run replay transport"
    >
      <TransportButton
        label={playing ? "Pause replay" : "Play replay"}
        onClick={playing ? pause : play}
        primary
      >
        {playing ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}
      </TransportButton>

      <TransportButton label="Step back" onClick={() => step(-1)} disabled={atStart}>
        <StepBack className="h-3.5 w-3.5" />
      </TransportButton>
      <TransportButton label="Step forward" onClick={() => step(1)} disabled={atEnd}>
        <StepForward className="h-3.5 w-3.5" />
      </TransportButton>

      <input
        type="range"
        min={0}
        max={total}
        step={1}
        value={sliderValue}
        onChange={(e) => setIndex(Number(e.target.value) - 1)}
        aria-label="Scrub replay position"
        aria-valuetext={
          current ? `Step ${index + 1}: ${currentLabel}` : "Start (before first step)"
        }
        className="replay-scrubber h-1 w-40 cursor-pointer appearance-none rounded-full bg-border accent-primary"
      />

      <span className="shrink-0 font-mono text-2xs tabular-nums text-subtle">
        {stepNumberLabel}
      </span>

      <span className="min-w-0 max-w-[12rem] truncate text-xs text-muted">
        {currentLabel ?? "Start"}
      </span>

      <button
        type="button"
        onClick={onClose}
        aria-label="Exit replay"
        className="focus-ring flex h-6 w-6 shrink-0 items-center justify-center rounded-md text-muted transition-colors hover:bg-surface-hover hover:text-foreground"
      >
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}

function TransportButton({
  label,
  onClick,
  disabled,
  primary,
  children,
}: {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  primary?: boolean;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      title={label}
      className={
        "focus-ring flex h-6 w-6 shrink-0 items-center justify-center rounded-md transition-colors disabled:pointer-events-none disabled:opacity-40 " +
        (primary
          ? "text-foreground hover:bg-surface-hover"
          : "text-muted hover:bg-surface-hover hover:text-foreground")
      }
    >
      {children}
    </button>
  );
}
