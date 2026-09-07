import { ShieldAlert, ShieldCheck } from "lucide-react";
import { cn } from "@/lib/utils";
import { Chip } from "@/components/ui/chip";
import { GUARDRAIL_TYPE_LABELS } from "@/lib/guardrail-labels";
import type { GuardrailMode, GuardrailType } from "@/types/workflow";

export interface GuardrailVerdict {
  passed: boolean;
  message: string;
  severity: string;
  would_block: boolean;
}

interface VerdictPanelProps {
  result: GuardrailVerdict | null;
  guardrailType: GuardrailType;
  mode: GuardrailMode;
  /** Client-measured round-trip in ms (performance.now around the fetch). */
  roundTripMs: number | null;
}

/** Full-width verdict band replacing the quiet result box. */
export function VerdictPanel({ result, guardrailType, mode, roundTripMs }: VerdictPanelProps) {
  return (
    <div
      aria-live="polite"
      className={cn(
        "rounded-lg border p-4 transition-colors",
        !result
          ? "border-border bg-surface-input"
          : result.passed
            ? "border-success/40 bg-success/10"
            : "border-destructive/40 bg-destructive/10"
      )}
    >
      {!result ? (
        <>
          <p className="text-2xs font-medium uppercase tracking-wider text-muted">Result</p>
          <p className="mt-2 text-sm text-subtle">Run a test to see pass / fail.</p>
        </>
      ) : (
        <div className="space-y-3">
          <div className="flex items-center gap-3">
            {result.passed ? (
              <ShieldCheck className="h-6 w-6 shrink-0 text-success" aria-hidden />
            ) : (
              <ShieldAlert className="h-6 w-6 shrink-0 text-destructive" aria-hidden />
            )}
            <span
              className={cn(
                "font-mono text-2xl font-semibold tracking-tight",
                result.passed ? "text-success" : "text-destructive"
              )}
            >
              {result.passed ? "PASS" : "FAIL"}
            </span>
          </div>
          <p className="text-sm leading-6 text-foreground">{result.message}</p>
          <div className="flex flex-wrap gap-1.5">
            <Chip>severity: {result.severity}</Chip>
            <Chip>{result.would_block ? "would block" : "log only"}</Chip>
            <Chip>{mode}</Chip>
            <Chip>{GUARDRAIL_TYPE_LABELS[guardrailType]}</Chip>
            {roundTripMs !== null && <Chip>~{Math.round(roundTripMs)} ms round-trip</Chip>}
          </div>
        </div>
      )}
    </div>
  );
}
