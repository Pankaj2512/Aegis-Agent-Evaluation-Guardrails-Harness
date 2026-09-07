import { cn } from "@/lib/utils";

interface SeverityBarProps {
  passed: number;
  warned: number;
  failed: number;
  className?: string;
}

/**
 * Proportional pass/warn/fail rail — the one place chroma is allowed on a bar,
 * because the bar *is* the data. Renders nothing but the track when empty.
 */
export function SeverityBar({ passed, warned, failed, className }: SeverityBarProps) {
  const total = passed + warned + failed;
  const pct = (n: number) => (total > 0 ? (n / total) * 100 : 0);

  return (
    <div className={cn("flex h-1.5 overflow-hidden rounded-full bg-surface-input", className)}>
      <div className="bg-success/70" style={{ width: `${pct(passed)}%` }} />
      <div className="bg-warning/70" style={{ width: `${pct(warned)}%` }} />
      <div className="bg-destructive/70" style={{ width: `${pct(failed)}%` }} />
    </div>
  );
}
