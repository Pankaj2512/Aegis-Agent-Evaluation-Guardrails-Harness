import { Trash2 } from "lucide-react";

import { cn } from "@/lib/utils";

interface RowDeleteButtonProps extends Omit<React.ComponentProps<"button">, "children"> {
  /** Required — the icon carries no text, so the row needs naming. */
  "aria-label": string;
}

/**
 * Hover-revealed destructive row action. Deliberately a plain <button>, not
 * Button: the recipe is opacity-driven reveal + focus-ring, which Button's
 * variant/shadow chrome would fight. The parent row must carry `group`.
 */
export function RowDeleteButton({ className, type = "button", ...props }: RowDeleteButtonProps) {
  return (
    <button
      type={type}
      className={cn(
        "focus-ring rounded-md p-1.5 text-muted opacity-0 transition-opacity hover:text-destructive focus-visible:opacity-100 group-hover:opacity-100",
        className
      )}
      {...props}
    >
      <Trash2 className="h-4 w-4" />
    </button>
  );
}
