import { cn } from "@/lib/utils";

/**
 * Dense metadata chip for trace/run rows — mono + tabular by construction so
 * durations, token counts and scores line up column-wise. Tone strings mirror
 * badgeVariants; use Badge for the larger status pill, Chip for row metadata.
 */
export type ChipTone = "outline" | "success" | "warning" | "destructive" | "accent";

const CHIP_TONES: Record<ChipTone, string> = {
  outline: "border-border bg-surface-input text-muted",
  success: "border-success/25 bg-success/12 text-success",
  warning: "border-warning/25 bg-warning/12 text-warning",
  destructive: "border-destructive/25 bg-destructive/12 text-destructive",
  accent: "border-accent/25 bg-accent-muted text-accent",
};

interface ChipProps {
  tone?: ChipTone;
  title?: string;
  className?: string;
  children: React.ReactNode;
}

export function Chip({ tone = "outline", title, className, children }: ChipProps) {
  return (
    <span
      title={title}
      className={cn(
        "inline-flex items-center gap-1 rounded border px-1.5 py-0.5 font-mono text-2xs tabular-nums",
        CHIP_TONES[tone],
        className
      )}
    >
      {children}
    </span>
  );
}
