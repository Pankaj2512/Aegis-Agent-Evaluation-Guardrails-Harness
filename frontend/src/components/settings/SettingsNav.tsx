"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";

const SECTIONS = [
  { id: "settings-appearance", label: "Appearance" },
  { id: "settings-api", label: "API key" },
  { id: "settings-credentials", label: "Credentials" },
  { id: "settings-presets", label: "Eval rubrics" },
  { id: "settings-alerts", label: "Alerts" },
  { id: "settings-ops", label: "Operational config" },
] as const;

/** Sticky anchor list with a single-observer scroll-spy (lg and up). */
export function SettingsNav() {
  const [active, setActive] = useState<string>(SECTIONS[0].id);

  useEffect(() => {
    const visible = new Map<string, number>();
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            visible.set(entry.target.id, entry.intersectionRatio);
          } else {
            visible.delete(entry.target.id);
          }
        }
        // Pick the topmost visible section (document order).
        const topmost = SECTIONS.find((s) => visible.has(s.id));
        if (topmost) setActive(topmost.id);
      },
      {
        // Activate the section sitting just below the sticky header.
        rootMargin: "-80px 0px -55% 0px",
        threshold: [0, 0.1, 0.5, 1],
      }
    );

    // Sections mount asynchronously (e.g. OpsConfigCard returns null until its
    // query resolves), so re-collect and observe any not-yet-seen sections
    // whenever the DOM changes rather than only once on mount.
    const observed = new Set<string>();
    const collect = () => {
      for (const s of SECTIONS) {
        if (observed.has(s.id)) continue;
        const el = document.getElementById(s.id);
        if (el) {
          observer.observe(el);
          observed.add(s.id);
        }
      }
    };

    collect();

    const mutationObserver = new MutationObserver(collect);
    mutationObserver.observe(document.body, { childList: true, subtree: true });

    return () => {
      observer.disconnect();
      mutationObserver.disconnect();
    };
  }, []);

  return (
    <nav
      aria-label="Settings sections"
      className="sticky top-6 hidden self-start lg:block"
    >
      <ul className="space-y-0.5">
        {SECTIONS.map((section) => {
          const isActive = active === section.id;
          return (
            <li key={section.id}>
              <a
                href={`#${section.id}`}
                aria-current={isActive ? "true" : undefined}
                className={cn(
                  "focus-ring relative flex items-center rounded-md py-1.5 pl-3 pr-2 text-sm transition-colors",
                  isActive
                    ? "text-foreground"
                    : "text-muted hover:text-foreground"
                )}
              >
                <span
                  aria-hidden
                  className={cn(
                    "absolute left-0 top-1/2 h-4 w-px -translate-y-1/2 transition-colors",
                    isActive ? "bg-foreground" : "bg-transparent"
                  )}
                />
                {section.label}
              </a>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
