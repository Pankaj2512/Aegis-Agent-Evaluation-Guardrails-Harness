import type { LucideIcon } from "lucide-react";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

type AlertVariant = "warning" | "destructive" | "success" | "info";

const variantStyles: Record<AlertVariant, { box: string; icon: string; mark: string }> = {
  warning: {
    box: "border-warning/25 bg-warning/10",
    icon: "text-warning",
    mark: "bg-warning",
  },
  destructive: {
    box: "border-destructive/25 bg-destructive/10",
    icon: "text-destructive",
    mark: "bg-destructive",
  },
  success: {
    box: "border-success/25 bg-success/10",
    icon: "text-success",
    mark: "bg-success",
  },
  info: {
    box: "border-primary/25 bg-primary-muted",
    icon: "text-primary",
    mark: "bg-primary",
  },
};

interface AlertProps {
  variant?: AlertVariant;
  icon?: LucideIcon;
  title: string;
  description?: React.ReactNode;
  actions?: React.ReactNode;
  onDismiss?: () => void;
  className?: string;
}

export function Alert({
  variant = "warning",
  icon: Icon,
  title,
  description,
  actions,
  onDismiss,
  className,
}: AlertProps) {
  const styles = variantStyles[variant];

  return (
    <div
      className={cn(
        "relative flex w-full items-start gap-3 overflow-hidden rounded-lg border p-4 shadow-[inset_0_1px_0_var(--surface-highlight)] backdrop-blur-md",
        styles.box,
        className
      )}
      role="alert"
    >
      <span className={cn("absolute inset-y-0 left-0 w-1", styles.mark)} aria-hidden="true" />
      {Icon && (
        <span className={cn("mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-current/20 bg-background/30", styles.icon)}>
          <Icon className="h-4 w-4" aria-hidden="true" />
        </span>
      )}
      <div className="min-w-0 flex-1 space-y-1">
        <p className="text-sm font-semibold text-foreground">{title}</p>
        {description && <div className="text-sm leading-6 text-muted">{description}</div>}
        {actions && <div className="flex flex-wrap gap-2 pt-2 text-xs">{actions}</div>}
      </div>
      {onDismiss && (
        <button
          type="button"
          aria-label="Dismiss alert"
          onClick={onDismiss}
          className="shrink-0 rounded-md p-1.5 text-muted transition hover:bg-surface-hover hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/20"
        >
          <X className="h-4 w-4" />
        </button>
      )}
    </div>
  );
}
