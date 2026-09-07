import { AlertTriangle, CheckCircle2, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";

export interface GuardrailEvent {
  node_id: string;
  node_label?: string;
  status: string;
  message?: string;
  mode?: string;
  fail_behavior?: string;
}

function guardrailVariant(status: string) {
  if (status === "passed") return "success" as const;
  if (status === "warned") return "warning" as const;
  if (status === "failed") return "destructive" as const;
  return "outline" as const;
}

function guardrailIcon(status: string) {
  if (status === "passed") return CheckCircle2;
  if (status === "warned") return AlertTriangle;
  if (status === "failed") return XCircle;
  return null;
}

interface GuardrailEventsPanelProps {
  events: GuardrailEvent[];
  failedNodeIds?: string[];
  compact?: boolean;
}

export function GuardrailEventsPanel({
  events,
  failedNodeIds = [],
  compact = false,
}: GuardrailEventsPanelProps) {
  const items: GuardrailEvent[] =
    events.length > 0
      ? events
      : failedNodeIds.map((nodeId) => ({
          node_id: nodeId,
          node_label: nodeId,
          status: "failed",
          message: "Guardrail check failed",
        }));

  if (items.length === 0) return null;

  return (
    <div className={compact ? "space-y-2" : "space-y-3"}>
      {items.map((event) => {
        const Icon = guardrailIcon(event.status);
        const variant = guardrailVariant(event.status);
        const toneClass =
          event.status === "passed"
            ? "border-success/25 bg-success/8 text-success"
            : event.status === "warned"
              ? "border-warning/25 bg-warning/10 text-warning"
              : event.status === "failed"
                ? "border-destructive/25 bg-destructive/10 text-destructive"
                : "border-border bg-surface-input text-muted";

        return (
          <div
            key={`${event.node_id}-${event.status}`}
            className="group rounded-lg border border-border bg-surface-input/70 px-3 py-3 shadow-[inset_0_1px_0_var(--surface-highlight)] transition-colors hover:border-border-strong hover:bg-surface-hover/70"
          >
            <div className="flex items-start gap-3">
              <span
                className={`mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg border shadow-[inset_0_1px_0_var(--surface-highlight)] ${toneClass}`}
                aria-hidden="true"
              >
                {Icon ? <Icon className="size-4" /> : <span className="size-1.5 rounded-full bg-current" />}
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="truncate text-sm font-semibold text-foreground">
                    {event.node_label || event.node_id}
                  </span>
                  <Badge variant={variant} className="gap-1 capitalize">
                    {event.status}
                  </Badge>
                  {event.mode && (
                    <span className="rounded border border-border bg-background px-1.5 py-0.5 text-xs font-semibold text-muted">
                      {event.mode} mode
                    </span>
                  )}
                </div>
                {event.message && (
                  <p className="mt-1 text-xs leading-5 text-muted">{event.message}</p>
                )}
              </div>
              {event.fail_behavior && (
                <span className="shrink-0 rounded border border-border bg-background px-1.5 py-0.5 text-xs font-semibold text-subtle">
                  {event.fail_behavior}
                </span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
