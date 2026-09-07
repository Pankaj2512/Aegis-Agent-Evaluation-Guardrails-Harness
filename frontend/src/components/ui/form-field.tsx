import { cloneElement, isValidElement, type ReactElement, type ReactNode } from "react";
import { AlertCircle, Info } from "lucide-react";
import { cn } from "@/lib/utils";
import { Label } from "./label";

interface FormFieldProps {
  id: string;
  label: string;
  hint?: string;
  error?: string;
  required?: boolean;
  children: ReactNode;
  className?: string;
}

export function FormField({
  id,
  label,
  hint,
  error,
  required,
  children,
  className,
}: FormFieldProps) {
  const hintId = hint ? `${id}-hint` : undefined;
  const errorId = error ? `${id}-error` : undefined;
  const describedBy = [hintId, errorId].filter(Boolean).join(" ") || undefined;
  const control = isValidElement<Record<string, unknown>>(children)
    ? cloneElement(children as ReactElement<Record<string, unknown>>, {
        "aria-describedby": [children.props["aria-describedby"], describedBy].filter(Boolean).join(" ") || undefined,
        "aria-invalid": error ? true : children.props["aria-invalid"],
      })
    : children;

  return (
    <div className={cn("group/form-field space-y-2.5", className)} data-invalid={error ? true : undefined}>
      <Label htmlFor={id} required={required}>
        {label}
      </Label>
      {control}
      {hint && !error && (
        <p id={hintId} className="flex items-start gap-1.5 rounded-lg border border-border bg-surface-input/80 px-2.5 py-2 text-xs leading-5 text-muted shadow-[inset_0_1px_0_var(--surface-highlight)]">
          <Info className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary/85" aria-hidden="true" />
          {hint}
        </p>
      )}
      {error && (
        <p
          id={errorId}
          className="flex items-start gap-1.5 rounded-lg border border-destructive/30 bg-destructive/10 px-2.5 py-2 text-xs font-medium leading-5 text-destructive shadow-[inset_0_1px_0_var(--surface-highlight)]"
          role="alert"
        >
          <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          {error}
        </p>
      )}
    </div>
  );
}
