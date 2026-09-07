import { cn } from "@/lib/utils";

interface PageHeaderProps {
  title: string;
  description?: React.ReactNode;
  eyebrow?: string;
  actions?: React.ReactNode;
  back?: React.ReactNode;
  className?: string;
  as?: "h1" | "h2" | "h3";
}

/** Quiet page title row — no elevated card, no gradient rail. */
export function PageHeader({
  title,
  description,
  eyebrow,
  actions,
  back,
  className,
  as: Component = "h1",
}: PageHeaderProps) {
  return (
    <section
      className={cn(
        "flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between",
        className
      )}
    >
      <div className="min-w-0 space-y-1">
        {back}
        {eyebrow && (
          <p className="text-micro text-muted">{eyebrow}</p>
        )}
        <Component className="text-[28px] font-semibold leading-9 tracking-tight text-foreground sm:text-[32px] sm:leading-10">
          {title}
        </Component>
        {description && (
          <div className="max-w-xl text-sm leading-6 text-muted sm:max-w-2xl">
            {description}
          </div>
        )}
      </div>
      {actions && (
        <div className="flex min-w-0 flex-wrap items-center justify-end gap-2 sm:gap-3">
          {actions}
        </div>
      )}
    </section>
  );
}
