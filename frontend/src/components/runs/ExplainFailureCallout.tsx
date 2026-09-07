"use client";

import { useMutation } from "@tanstack/react-query";
import { Loader2, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

interface ExplainFailureCalloutProps {
  runId: string;
}

/**
 * Destructive-tinted callout that asks the assist backend to explain a failed
 * run and surface suggested fixes. Result persists in mutation state; the
 * button can re-run (server memoizes).
 */
export function ExplainFailureCallout({ runId }: ExplainFailureCalloutProps) {
  const mutation = useMutation({
    mutationFn: () => api.explainRun(runId),
    onError: (error: unknown) => {
      toast.error(error instanceof Error ? error.message : "Could not explain failure");
    },
  });

  const result = mutation.data;

  return (
    <div className="overflow-hidden rounded-lg border border-destructive/30 bg-destructive/5 p-4">
      <div className="flex items-start gap-3">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-destructive/25 bg-destructive/10 text-destructive">
          <Sparkles className="h-4 w-4" />
        </span>
        <div className="min-w-0 flex-1 space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm font-medium text-foreground">
              Something went wrong in this run.
            </p>
            <Button
              size="sm"
              variant="outline"
              onClick={() => mutation.mutate()}
              disabled={mutation.isPending}
            >
              {mutation.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Analyzing…
                </>
              ) : (
                <>
                  <Sparkles className="h-4 w-4" />
                  {result ? "Re-run explanation" : "Explain failure"}
                </>
              )}
            </Button>
          </div>

          {mutation.isError && (
            <p className="text-sm text-destructive">
              {mutation.error instanceof Error
                ? mutation.error.message
                : "Could not explain failure. Try again."}
            </p>
          )}

          {result && (
            <div className="space-y-3">
              {result.explanation_md && (
                <p className="whitespace-pre-wrap break-words text-sm leading-6 text-foreground/90">
                  {result.explanation_md}
                </p>
              )}
              {result.suggested_fixes.length > 0 && (
                <ul className="space-y-2 border-t border-destructive/20 pt-3">
                  {result.suggested_fixes.map((fix, index) => (
                    <li key={index} className="text-sm leading-6 text-foreground/90">
                      <strong className="font-semibold text-foreground">{fix.title}</strong>
                      {" — "}
                      {fix.detail}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
