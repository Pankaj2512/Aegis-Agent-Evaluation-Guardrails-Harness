import type { LucideIcon } from "lucide-react";
import { AlertTriangle, Inbox, Info } from "lucide-react";
import { cn } from "@/lib/utils";

interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  description?: string;
  action?: React.ReactNode;
  secondaryAction?: React.ReactNode;
  className?: string;
  compact?: boolean;
  variant?: "default" | "error" | "info";
}

const variantStyles: Record<
  NonNullable<EmptyStateProps["variant"]>,
  { icon: string }
> = {
  default: {
    icon: "border-border bg-surface-input text-muted",
  },
  error: {
    icon: "border-destructive/25 bg-destructive/10 text-destructive",
  },
  info: {
    icon: "border-border bg-surface-input text-muted",
  },
};

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  secondaryAction,
  className,
  compact = false,
  variant = "default",
}: EmptyStateProps) {
  const ResolvedIcon =
    Icon ?? (variant === "error" ? AlertTriangle : variant === "info" ? Info : Inbox);
  const styles = variantStyles[variant];

  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center rounded-lg border border-border bg-surface text-center shadow-elev-1",
        compact ? "gap-3 px-4 py-5" : "gap-4 p-8 sm:p-10",
        className
      )}
    >
      {ResolvedIcon && (
        <div
          className={cn(
            "flex items-center justify-center rounded-lg border",
            styles.icon,
            compact ? "h-10 w-10" : "h-11 w-11"
          )}
        >
          <ResolvedIcon className={cn(compact ? "h-5 w-5" : "h-5 w-5")} aria-hidden="true" />
        </div>
      )}
      <div className={cn("max-w-sm", compact ? "space-y-1" : "space-y-1.5")}>
        <p className={cn("font-semibold text-foreground", compact ? "text-sm" : "text-base")}>
          {title}
        </p>
        {description && (
          <p className={cn("text-muted", compact ? "text-xs leading-5" : "text-sm leading-6")}>
            {description}
          </p>
        )}
      </div>
      {(action || secondaryAction) && (
        <div className="flex w-full flex-col items-center justify-center gap-2 sm:w-auto sm:flex-row sm:flex-wrap">
          {action}
          {secondaryAction}
        </div>
      )}
    </div>
  );
}
