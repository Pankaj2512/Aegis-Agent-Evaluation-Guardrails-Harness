import * as React from "react"

import { cn } from "@/lib/utils"

const Textarea = React.forwardRef<HTMLTextAreaElement, React.ComponentProps<"textarea">>(
  function Textarea({ className, ...props }, ref) {
    return (
      <textarea
        ref={ref}
        data-slot="textarea"
        className={cn(
          "flex min-h-[88px] w-full min-w-0 rounded-lg border border-border bg-surface-input px-3 py-2.5 text-sm leading-6 text-foreground shadow-[inset_0_1px_0_var(--surface-highlight)] outline-none transition-[border-color,background-color,box-shadow,color] placeholder:text-muted hover:border-border-strong hover:bg-surface-hover/50 focus-visible:border-primary/55 focus-visible:bg-background focus-visible:ring-2 focus-visible:ring-primary/20 focus-visible:ring-offset-2 focus-visible:ring-offset-bg disabled:cursor-not-allowed disabled:bg-surface disabled:text-subtle disabled:opacity-70 aria-invalid:border-destructive aria-invalid:ring-2 aria-invalid:ring-destructive/20 aria-invalid:focus-visible:border-destructive aria-invalid:focus-visible:ring-destructive/20",
          className
        )}
        {...props}
      />
    )
  }
)

export { Textarea }
