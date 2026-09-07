import { cn } from "@/lib/utils";

/** House sidebar-panel section: uppercase micro heading with optional count
 *  badge and a right-aligned action slot. Mirrors NodeInspector's internal
 *  InspectorSection so all canvas panels share one recipe. */
export function PanelSection({
  title,
  count,
  action,
  children,
  className,
}: {
  title: string;
  count?: number;
  action?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("space-y-3", className)}>
      <div className="flex items-center justify-between gap-2">
        <p className="text-micro text-subtle">
          {title}
          {typeof count === "number" && (
            <span className="ml-1.5 rounded border border-border px-1 py-px font-mono text-2xs text-muted">
              {count}
            </span>
          )}
        </p>
        {action}
      </div>
      {children}
    </div>
  );
}

const STAT_TONES = {
  default: "text-foreground",
  success: "text-success",
  warning: "text-warning",
  destructive: "text-destructive",
} as const;

/** Mini stat cell used across canvas panels (docs count, guardrail trio…). */
export function PanelStat({
  label,
  value,
  tone = "default",
}: {
  label: string;
  value: React.ReactNode;
  tone?: keyof typeof STAT_TONES;
}) {
  return (
    <div className="rounded-lg border border-border bg-background px-2.5 py-2">
      <p className="text-2xs uppercase tracking-wider text-subtle">{label}</p>
      <p className={cn("mt-0.5 text-lg font-semibold leading-6", STAT_TONES[tone])}>
        {value}
      </p>
    </div>
  );
}

export function PanelStatGrid({ children }: { children: React.ReactNode }) {
  return <div className="grid grid-cols-3 gap-2">{children}</div>;
}
