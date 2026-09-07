import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex min-h-6 items-center gap-1 rounded-md border px-2.5 py-1 text-xs font-semibold leading-none shadow-[inset_0_1px_0_var(--surface-highlight)]",
  {
    variants: {
      variant: {
        default: "border-border bg-surface text-foreground",
        primary: "border-primary/25 bg-primary-muted text-primary-300",
        success: "border-success/25 bg-success/12 text-success",
        warning: "border-warning/25 bg-warning/12 text-warning",
        destructive: "border-destructive/25 bg-destructive/12 text-destructive",
        accent: "border-accent/25 bg-accent-muted text-accent",
        outline: "border-border bg-surface-input text-muted",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

export function Badge({
  className,
  variant,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & VariantProps<typeof badgeVariants>) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />;
}
