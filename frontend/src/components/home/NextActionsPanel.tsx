"use client";

import Link from "next/link";
import { actionDotClass, type NextAction } from "@/lib/home-desk";
import { cn } from "@/lib/utils";
import { SectionCard } from "@/components/ui/section-card";

export function NextActionsPanel({ actions }: { actions: NextAction[] }) {
  return (
    <SectionCard
      title="Next"
      description="What needs you — failures, approvals, alerts, review backlog"
      flush
      actions={
        actions.length > 0 ? (
          <span className="font-mono text-2xs text-muted tabular-nums">
            {actions.length}
          </span>
        ) : null
      }
    >
      {actions.length === 0 ? (
        <p className="px-4 py-6 text-center text-xs text-muted">
          Nothing in the queue. Runs and review items will land here.
        </p>
      ) : (
        <ul className="divide-y divide-border">
          {actions.map((action) => (
            <li key={action.id}>
              <Link
                href={action.href}
                className={cn(
                  "group flex items-center gap-3 px-4 py-2.5 transition-colors",
                  "hover:bg-surface-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary/30"
                )}
              >
                <span
                  className={cn(
                    "h-1.5 w-1.5 shrink-0 rounded-full",
                    actionDotClass(action.kind)
                  )}
                  aria-hidden
                />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm text-foreground">
                    {action.title}
                  </span>
                  <span className="block truncate text-2xs text-subtle">
                    {action.detail}
                  </span>
                </span>
                {action.meta && (
                  <span className="shrink-0 font-mono text-2xs text-muted tabular-nums">
                    {action.meta}
                  </span>
                )}
                <span className="shrink-0 text-2xs text-muted opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100">
                  Open
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </SectionCard>
  );
}
