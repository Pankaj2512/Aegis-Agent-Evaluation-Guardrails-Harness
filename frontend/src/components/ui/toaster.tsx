"use client";

import { Toaster as Sonner, type ToasterProps } from "sonner";
import { useTheme } from "@/providers/ThemeProvider";

export function Toaster(props: ToasterProps) {
  const { theme } = useTheme();

  return (
    <Sonner
      theme={theme}
      position="bottom-right"
      closeButton
      expand
      visibleToasts={4}
      // Keep toasts clear of the canvas run FAB (bottom-right, ~68px tall zone).
      offset={{ bottom: 112 }}
      mobileOffset={{ bottom: 16 }}
      toastOptions={{
        duration: 3500,
        classNames: {
          toast:
            "group overflow-hidden rounded-lg border border-border bg-surface-elevated p-4 text-foreground shadow-elev-2 ",
          title: "text-sm font-semibold text-foreground",
          description: "text-xs leading-5 text-muted",
          success: "border-l-2 border-l-success",
          error: "border-l-2 border-l-destructive",
          warning: "border-l-2 border-l-warning",
          info: "border-l-2 border-l-primary",
          loading: "border-l-2 border-l-muted",
          actionButton:
            "rounded-md bg-primary px-2.5 py-1.5 text-xs font-semibold text-primary-foreground transition hover:bg-primary-600",
          cancelButton:
            "rounded-md border border-border bg-transparent px-2.5 py-1.5 text-xs font-semibold text-muted transition hover:bg-surface-hover hover:text-foreground",
          closeButton:
            "border-border bg-surface-elevated text-muted transition hover:bg-surface-hover hover:text-foreground",
        },
      }}
      {...props}
    />
  );
}
