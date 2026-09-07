"use client";

import { useState } from "react";
import { Loader2, RefreshCw, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import type { WorkflowGraph } from "@/types/workflow";

export interface GeneratedWorkflow {
  graph: WorkflowGraph;
  notes: string[];
}

interface DescribeWorkflowCardProps {
  /** The current description text; shared with the AI generator prompt. */
  description: string;
  onDescriptionChange: (value: string) => void;
  /** The most recent generated result, or null before the first generation. */
  result: GeneratedWorkflow | null;
  onResult: (result: GeneratedWorkflow | null) => void;
  /** Disables inputs while an outer create/import is in flight. */
  busy?: boolean;
  onError: (message: string) => void;
}

/**
 * "Describe it" launch shape: the operator types a natural-language description
 * and Aegis generates a canvas-shaped graph (server-assigned positions) plus a
 * list of follow-up notes. The generated graph feeds the shared preview.
 */
export function DescribeWorkflowCard({
  description,
  onDescriptionChange,
  result,
  onResult,
  busy = false,
  onError,
}: DescribeWorkflowCardProps) {
  const [generating, setGenerating] = useState(false);
  const trimmed = description.trim();

  const generate = async () => {
    if (!trimmed || generating) return;
    setGenerating(true);
    try {
      const generated = await api.generateWorkflow({ description: trimmed });
      onResult({ graph: generated.graph, notes: generated.notes ?? [] });
    } catch (error) {
      onError(error instanceof Error ? error.message : "Failed to generate workflow");
    } finally {
      setGenerating(false);
    }
  };

  const disabled = busy || generating;

  return (
    <div className="space-y-3">
      <Textarea
        value={description}
        onChange={(e) => onDescriptionChange(e.target.value)}
        disabled={disabled}
        placeholder="Describe the workflow you want — triggers, steps, checks…"
        className="min-h-28"
        aria-label="Describe the workflow you want"
      />
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-xs leading-5 text-muted">
          Aegis drafts a graph you can refine on the canvas.
        </p>
        {result ? (
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={generate}
            disabled={disabled || !trimmed}
          >
            {generating ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                Generating…
              </>
            ) : (
              <>
                <RefreshCw className="h-3.5 w-3.5" />
                Regenerate
              </>
            )}
          </Button>
        ) : (
          <Button
            type="button"
            size="sm"
            onClick={generate}
            disabled={disabled || !trimmed}
          >
            {generating ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Generating…
              </>
            ) : (
              <>
                <Sparkles className="h-4 w-4" />
                Generate workflow
              </>
            )}
          </Button>
        )}
      </div>
    </div>
  );
}

/** Quiet follow-up notes surfaced under the generated preview. */
export function GeneratedNotes({ notes }: { notes: string[] }) {
  if (notes.length === 0) return null;
  return (
    <div className="mt-4 rounded-lg border border-border bg-surface-input/60 p-3">
      <p className="text-xs font-medium text-foreground">You&rsquo;ll still need to…</p>
      <ul className="mt-2 space-y-1.5">
        {notes.map((note, index) => (
          <li key={index} className="flex gap-2 text-xs leading-5 text-muted">
            <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-subtle" aria-hidden />
            <span className="min-w-0">{note}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
