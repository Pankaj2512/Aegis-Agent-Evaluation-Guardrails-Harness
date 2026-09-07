"use client";

import { usePathname } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AppRail } from "@/components/layout/AppRail";
import { CommandPalette } from "@/components/layout/CommandPalette";
import { ShortcutsHelp, SHORTCUTS_HELP_EVENT } from "@/components/layout/ShortcutsHelp";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { isEditableTarget } from "@/lib/shortcuts";

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const onCanvas = pathname.startsWith("/workflows/") && pathname !== "/workflows/new";
  const [helpOpen, setHelpOpen] = useState(false);

  const openHelp = useCallback(() => setHelpOpen(true), []);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "?" && !isEditableTarget(e.target)) {
        e.preventDefault();
        setHelpOpen(true);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  // The command palette (and other surfaces) open the shortcuts dialog via event.
  useEffect(() => {
    const handler = () => setHelpOpen(true);
    window.addEventListener(SHORTCUTS_HELP_EVENT, handler);
    return () => window.removeEventListener(SHORTCUTS_HELP_EVENT, handler);
  }, []);

  const content = (
    <>
      {!onCanvas && (
        <>
          <a href="#main-content" className="skip-link">
            Skip to content
          </a>
          <AppRail onOpenShortcutsHelp={openHelp} />
        </>
      )}
      <ErrorBoundary title="Something went wrong">
        <main id="main-content" tabIndex={-1} className={onCanvas ? undefined : "pl-14"}>
          {children}
        </main>
      </ErrorBoundary>
      <CommandPalette />
      <ShortcutsHelp open={helpOpen} onOpenChange={setHelpOpen} onCanvas={onCanvas} />
    </>
  );

  return <div className="app-shell">{content}</div>;
}
