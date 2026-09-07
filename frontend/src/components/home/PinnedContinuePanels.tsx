"use client";

import Link from "next/link";
import { Pin } from "lucide-react";
import {
  stageDotClass,
  versionLabel,
} from "@/lib/home-desk";
import { workflowLifecycleStage } from "@/lib/workflow-lifecycle";
import { formatRelativeTime } from "@/lib/format-date";
import { useNow } from "@/hooks/use-now";
import { cn } from "@/lib/utils";
import { SectionCard } from "@/components/ui/section-card";
import type { WorkflowListItem } from "@/types/workflow";

function WorkflowRow({
  workflow,
  trailing,
  onTogglePin,
  pinned,
  showPin,
}: {
  workflow: WorkflowListItem;
  trailing?: string;
  onTogglePin?: (id: string) => void;
  pinned?: boolean;
  showPin?: boolean;
}) {
  const stage = workflowLifecycleStage(workflow);

  return (
    <li className="group relative">
      <Link
        href={`/workflows/${workflow.id}`}
        className={cn(
          "flex items-center gap-2.5 px-3 py-2 pr-10 transition-colors",
          "hover:bg-surface-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary/30"
        )}
      >
        <span
          className={cn("h-1.5 w-1.5 shrink-0 rounded-full", stageDotClass(stage))}
          aria-hidden
        />
        <span className="min-w-0 flex-1 truncate text-sm text-foreground">
          {workflow.name}
        </span>
        <span className="shrink-0 font-mono text-2xs text-muted tabular-nums">
          {trailing ?? versionLabel(workflow)}
        </span>
      </Link>
      {showPin && onTogglePin && (
        <button
          type="button"
          aria-label={pinned ? `Unpin ${workflow.name}` : `Pin ${workflow.name}`}
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            onTogglePin(workflow.id);
          }}
          className={cn(
            "absolute right-2 top-1/2 -translate-y-1/2 rounded-md p-1 text-muted transition-colors",
            "hover:bg-surface-hover hover:text-foreground",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30",
            pinned ? "opacity-100 text-foreground" : "opacity-0 group-hover:opacity-100 focus-visible:opacity-100"
          )}
        >
          <Pin className={cn("h-3.5 w-3.5", pinned && "fill-current")} />
        </button>
      )}
    </li>
  );
}

export function PinnedContinuePanels({
  pinned,
  continueItems,
  onTogglePin,
  isPinned,
}: {
  pinned: WorkflowListItem[];
  continueItems: Array<{ workflow: WorkflowListItem; meta: string }>;
  onTogglePin: (id: string) => void;
  isPinned: (id: string) => boolean;
}) {
  const now = useNow();

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
      <SectionCard
        title="Pinned"
        description="Your shortcuts"
        flush
        actions={
          <span className="font-mono text-2xs text-muted tabular-nums">
            {pinned.length}
          </span>
        }
      >
        {pinned.length === 0 ? (
          <p className="px-3 py-6 text-center text-xs leading-5 text-muted">
            Pin workflows from the library below. They stay here across sessions.
          </p>
        ) : (
          <ul className="divide-y divide-border">
            {pinned.map((w) => (
              <WorkflowRow
                key={w.id}
                workflow={w}
                showPin
                pinned
                onTogglePin={onTogglePin}
                trailing={
                  w.updated_at
                    ? formatRelativeTime(w.updated_at, now)
                    : versionLabel(w)
                }
              />
            ))}
          </ul>
        )}
      </SectionCard>

      <SectionCard
        title="Continue"
        description="Recently opened or updated"
        flush
        actions={
          <span className="font-mono text-2xs text-muted tabular-nums">
            {continueItems.length}
          </span>
        }
      >
        {continueItems.length === 0 ? (
          <p className="px-3 py-6 text-center text-xs leading-5 text-muted">
            Open a workflow on the canvas — it will show up here.
          </p>
        ) : (
          <ul className="divide-y divide-border">
            {continueItems.map(({ workflow, meta }) => (
              <WorkflowRow
                key={workflow.id}
                workflow={workflow}
                trailing={meta}
                showPin
                pinned={isPinned(workflow.id)}
                onTogglePin={onTogglePin}
              />
            ))}
          </ul>
        )}
      </SectionCard>
    </div>
  );
}
