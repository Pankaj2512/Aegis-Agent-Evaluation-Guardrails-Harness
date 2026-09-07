import { cn } from "@/lib/utils";

interface FilterChipProps {
  label: string;
  active?: boolean;
  onClick?: () => void;
  className?: string;
}

export function FilterChip({ label, active, onClick, className }: FilterChipProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={Boolean(active)}
      className={cn(
        "rounded-md border px-3 py-1.5 text-xs font-semibold leading-none shadow-[inset_0_1px_0_var(--surface-highlight)] transition-colors",
        active
          ? "border-border-strong bg-surface-hover text-foreground"
          : "border-border bg-surface-input text-muted hover:border-border-strong hover:bg-surface-hover hover:text-foreground",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/25 focus-visible:ring-offset-2 focus-visible:ring-offset-bg",
        className
      )}
    >
      {label}
    </button>
  );
}
