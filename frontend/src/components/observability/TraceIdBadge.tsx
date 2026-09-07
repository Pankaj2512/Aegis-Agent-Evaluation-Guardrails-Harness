"use client";

import { ExternalLink } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";

export function TraceIdBadge({
  traceId,
  uiBaseUrl,
  compact = false,
}: {
  traceId: string;
  uiBaseUrl?: string | null;
  compact?: boolean;
}) {
  const shortId = compact ? traceId.slice(0, 8) : traceId;
  const traceUrl = uiBaseUrl
    ? uiBaseUrl.includes("{trace_id}")
      ? uiBaseUrl.replace("{trace_id}", traceId)
      : `${uiBaseUrl.replace(/\/$/, "")}/trace/${traceId}`
    : null;

  return (
    <span className="inline-flex items-center gap-1 rounded font-mono text-xs text-muted">
      <button
        type="button"
        className="rounded transition hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/25 focus-visible:ring-offset-2 focus-visible:ring-offset-bg"
        title={`Trace ${traceId}`}
        onClick={async () => {
          try {
            await navigator.clipboard.writeText(traceId);
            toast.success("Trace ID copied");
          } catch {
            toast.error("Could not copy trace ID");
          }
        }}
      >
        <Badge variant="outline" className="font-mono text-xs">
          trace {shortId}
        </Badge>
      </button>
      {traceUrl && (
        <a
          href={traceUrl}
          target="_blank"
          rel="noreferrer"
          className="inline-flex size-6 items-center justify-center rounded-md border border-border bg-surface-input text-primary shadow-[inset_0_1px_0_var(--surface-highlight)] transition-colors hover:border-border-strong hover:bg-surface-hover hover:text-primary-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/25 focus-visible:ring-offset-2 focus-visible:ring-offset-bg"
          aria-label="Open trace in APM UI"
        >
          <ExternalLink className="h-3.5 w-3.5" />
        </a>
      )}
    </span>
  );
}
