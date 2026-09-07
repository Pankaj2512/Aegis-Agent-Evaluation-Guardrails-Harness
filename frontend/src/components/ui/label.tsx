import { cn } from "@/lib/utils";

interface LabelProps extends React.LabelHTMLAttributes<HTMLLabelElement> {
  required?: boolean;
}

export function Label({ className, required, children, ...props }: LabelProps) {
  return (
    <label
      className={cn(
        "inline-flex items-center gap-1.5 text-xs font-semibold leading-5 text-foreground transition-colors peer-disabled:cursor-not-allowed peer-disabled:text-subtle",
        className
      )}
      {...props}
    >
      {children}
      {required && (
        <span className="text-destructive" aria-hidden="true">
          *
        </span>
      )}
    </label>
  );
}
