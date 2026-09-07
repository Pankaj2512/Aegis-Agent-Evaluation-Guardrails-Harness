import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { AlertTriangle, Compass, RefreshCcw, ShieldAlert } from "lucide-react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { GlassCard } from "@/components/ui/glass-card";

type RecoveryTone = "error" | "not-found" | "warning";

interface RecoveryStateProps {
  icon?: LucideIcon;
  tone?: RecoveryTone;
  title: string;
  description: string;
  primaryAction?: ReactNode;
  secondaryAction?: ReactNode;
  tertiaryAction?: ReactNode;
  diagnostic?: string;
  className?: string;
}

const toneStyles: Record<
  RecoveryTone,
  {
    badge: "destructive" | "accent" | "warning";
    icon: string;
    label: string;
    defaultIcon: LucideIcon;
  }
> = {
  error: {
    badge: "destructive",
    icon: "border-destructive/25 bg-destructive/10 text-destructive",
    label: "Recovery mode",
    defaultIcon: ShieldAlert,
  },
  "not-found": {
    badge: "accent",
    icon: "border-border bg-surface-input text-muted",
    label: "Route not found",
    defaultIcon: Compass,
  },
  warning: {
    badge: "warning",
    icon: "border-warning/25 bg-warning/10 text-warning",
    label: "Attention needed",
    defaultIcon: AlertTriangle,
  },
};

export function RecoveryState({
  icon,
  tone = "error",
  title,
  description,
  primaryAction,
  secondaryAction,
  tertiaryAction,
  diagnostic,
  className,
}: RecoveryStateProps) {
  const style = toneStyles[tone];
  const Icon = icon ?? style.defaultIcon;

  return (
    <GlassCard className={cn("w-full max-w-3xl overflow-hidden p-0", className)}>
      <div className="grid gap-0 md:grid-cols-[minmax(0,1fr)_220px]">
        <div className="space-y-6 p-6 sm:p-8">
          <div className="flex items-start gap-4">
            <span
              className={cn(
                "flex h-11 w-11 shrink-0 items-center justify-center rounded-lg border",
                style.icon
              )}
            >
              <Icon className="h-5 w-5" aria-hidden="true" />
            </span>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant={style.badge}>{style.label}</Badge>
                {diagnostic && <Badge variant="outline">Ref {diagnostic}</Badge>}
              </div>
              <h1 className="mt-3 text-2xl font-semibold tracking-tight text-foreground sm:text-[28px]">
                {title}
              </h1>
              <p className="mt-2 max-w-xl text-sm leading-6 text-muted">{description}</p>
            </div>
          </div>

          {(primaryAction || secondaryAction || tertiaryAction) && (
            <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
              {primaryAction}
              {secondaryAction}
              {tertiaryAction}
            </div>
          )}
        </div>

        <div className="border-t border-border bg-surface-input p-5 md:border-l md:border-t-0">
          <div className="flex h-full flex-col justify-between gap-5">
            <div className="space-y-2">
              {[
                "Preserve the current workspace",
                "Retry the failed route",
                "Return to a stable surface",
              ].map((item) => (
                <div
                  key={item}
                  className="flex items-center gap-2 rounded-md border border-border bg-background px-3 py-2 text-xs text-muted"
                >
                  <RefreshCcw className="h-3.5 w-3.5 shrink-0 text-muted" aria-hidden="true" />
                  <span>{item}</span>
                </div>
              ))}
            </div>
            <p className="text-xs leading-5 text-subtle">
              Recovery is isolated from workflow data — retrying will not mutate saved graphs.
            </p>
          </div>
        </div>
      </div>
    </GlassCard>
  );
}
