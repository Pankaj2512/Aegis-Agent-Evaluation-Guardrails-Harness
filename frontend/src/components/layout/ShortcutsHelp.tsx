"use client";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { SHORTCUT_SECTIONS, formatShortcutKey } from "@/lib/shortcuts";
import { startCanvasTour } from "@/components/onboarding/CanvasTour";

export const SHORTCUTS_HELP_EVENT = "aegis:open-shortcuts-help";

/** Dispatch to open the keyboard-shortcuts dialog from anywhere (mirrors openCommandPalette). */
export function openShortcutsHelp() {
  window.dispatchEvent(new Event(SHORTCUTS_HELP_EVENT));
}

interface ShortcutsHelpProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCanvas?: boolean;
}

export function ShortcutsHelp({ open, onOpenChange, onCanvas = false }: ShortcutsHelpProps) {
  const sections = SHORTCUT_SECTIONS.filter(
    (section) => section.context === "global" || onCanvas
  );

  const handleTour = () => {
    onOpenChange(false);
    startCanvasTour();
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Keyboard shortcuts</DialogTitle>
          <DialogDescription>Productivity shortcuts across Aegis.</DialogDescription>
        </DialogHeader>

        <div className="grid gap-6 sm:grid-cols-2">
          {sections.map((section) => (
            <div key={section.title}>
              <h3 className="text-2xs font-semibold uppercase tracking-wider text-subtle">
                {section.title}
              </h3>
              <ul className="mt-2 space-y-1.5">
                {section.items.map((item) => (
                  <li
                    key={item.description}
                    className="flex items-center justify-between gap-4"
                  >
                    <span className="text-sm text-foreground">{item.description}</span>
                    <span className="flex shrink-0 gap-1">
                      {item.keys.map((key, index) => (
                        <kbd
                          key={index}
                          className="rounded border border-border bg-surface-input px-1.5 py-0.5 font-mono text-xs font-semibold text-muted shadow-[inset_0_1px_0_var(--surface-highlight)]"
                        >
                          {formatShortcutKey(key)}
                        </kbd>
                      ))}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        {onCanvas && (
          <>
            <div className="-mx-6 h-px bg-border" />
            <div className="flex justify-end">
              <Button variant="outline" size="sm" onClick={handleTour}>
                Take the canvas tour again
              </Button>
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
