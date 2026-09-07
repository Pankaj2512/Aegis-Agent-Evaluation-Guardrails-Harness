import { cn } from "@/lib/utils";

interface StatCardProps {
  label: string;
  value: React.ReactNode;
  icon?: React.ElementType;
  trend?: string;
  /** Optional mini-visual (e.g. a Sparkline) rendered under the value. */
  chart?: React.ReactNode;
  className?: string;
}

export function StatCard({ label, value, icon: Icon, trend, chart, className }: StatCardProps) {
  return (
    <div
      className={cn(
        "surface-card min-h-24 rounded-lg border border-border bg-surface-elevated p-4 shadow-elev-1 transition-colors duration-fast hover:border-border-strong",
        className
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <p className="text-micro">{label}</p>
        {Icon && (
          <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-border bg-surface-input text-primary shadow-[inset_0_1px_0_var(--surface-highlight)]">
            <Icon className="h-4 w-4 text-primary" strokeWidth={2} />
          </div>
        )}
      </div>
      <div className="mt-5 flex items-end justify-between gap-3">
        <p className="font-mono text-[30px] font-semibold leading-none tabular-nums text-foreground">
          {value}
        </p>
        {chart && <div className="min-w-0 overflow-hidden">{chart}</div>}
      </div>
      {trend && <p className="mt-1 font-mono text-2xs tabular-nums text-muted">{trend}</p>}
    </div>
  );
}
