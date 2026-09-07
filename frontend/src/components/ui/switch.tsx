"use client";

import * as React from "react";
import { Switch as SwitchPrimitive } from "radix-ui";

import { cn } from "@/lib/utils";

function Switch({
  className,
  size = "default",
  ...props
}: React.ComponentProps<typeof SwitchPrimitive.Root> & {
  size?: "sm" | "default";
}) {
  return (
    <SwitchPrimitive.Root
      data-slot="switch"
      data-size={size}
      className={cn(
        "peer group/switch relative inline-flex shrink-0 items-center rounded-full border border-border bg-surface-input shadow-[inset_0_1px_0_var(--surface-highlight)] outline-none transition-colors after:absolute after:-inset-x-3 after:-inset-y-2 focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30 aria-invalid:border-destructive aria-invalid:ring-2 aria-invalid:ring-destructive/20 data-[size=default]:h-6 data-[size=default]:w-11 data-[size=sm]:h-5 data-[size=sm]:w-9 data-[state=checked]:border-primary/40 data-[state=checked]:bg-primary data-[state=unchecked]:bg-surface-input data-[disabled]:cursor-not-allowed data-[disabled]:opacity-60",
        className
      )}
      {...props}
    >
      <SwitchPrimitive.Thumb
        data-slot="switch-thumb"
        className={cn(
          "pointer-events-none block rounded-full shadow-elev-1 ring-0 transition-transform",
          "group-data-[size=default]/switch:size-5 group-data-[size=sm]/switch:size-4",
          /* Position from root data-state (Radix puts state on Root, not Thumb) */
          "group-data-[state=unchecked]/switch:translate-x-0.5",
          "group-data-[size=default]/switch:group-data-[state=checked]/switch:translate-x-5",
          "group-data-[size=sm]/switch:group-data-[state=checked]/switch:translate-x-4",
          "group-data-[state=checked]/switch:bg-primary-foreground",
          "group-data-[state=unchecked]/switch:bg-foreground"
        )}
      />
    </SwitchPrimitive.Root>
  );
}

export { Switch };
