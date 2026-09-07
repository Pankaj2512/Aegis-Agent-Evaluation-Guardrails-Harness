"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Chip } from "@/components/ui/chip";
import { EmptyState } from "@/components/ui/empty-state";
import { LoadingState } from "@/components/ui/loading-state";
import { SectionCard } from "@/components/ui/section-card";
import { api, type GuardrailPolicyTemplate } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import type { GuardrailMode, GuardrailType } from "@/types/workflow";
import type { PlaygroundConfig } from "@/components/guardrails/SavedPolicies";

interface PolicyTemplatesProps {
  /** Load a template's core config into the playground form for a quick test. */
  onLoad: (config: PlaygroundConfig) => void;
}

/** Best-effort playground config from a template's full rules. The playground
 *  form only tests type/mode/keywords; richer rules (presidio entities,
 *  moderation thresholds) survive only when the template is adopted. */
function toConfig(template: GuardrailPolicyTemplate): PlaygroundConfig {
  const r = template.rules_json;
  const keywords = Array.isArray(r.blocked_keywords)
    ? (r.blocked_keywords as unknown[]).filter((k): k is string => typeof k === "string")
    : [];
  return {
    guardrail_type: (typeof r.guardrail_type === "string"
      ? r.guardrail_type
      : "rules") as GuardrailType,
    mode: (r.mode === "input" ? "input" : "output") as GuardrailMode,
    blocked_keywords: keywords,
    sample: "",
  };
}

/** Compact "type · mode · behavior" descriptor line from a template's rules. */
function ruleSummary(r: Record<string, unknown>): string {
  const parts = [r.guardrail_type, r.mode, r.fail_behavior].filter(
    (p): p is string => typeof p === "string"
  );
  return parts.join(" · ");
}

/**
 * Built-in guardrail policy templates — one-click starting points. "Adopt"
 * creates an owned, editable copy in Saved policies; "Load" drops the core
 * config into the playground for a quick test.
 */
export function PolicyTemplates({ onLoad }: PolicyTemplatesProps) {
  const queryClient = useQueryClient();
  const [adopting, setAdopting] = useState<string | null>(null);

  const {
    data: templates = [],
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: queryKeys.guardrailPolicyTemplates,
    queryFn: api.getGuardrailPolicyTemplates,
    staleTime: 5 * 60_000,
  });

  const adopt = async (template: GuardrailPolicyTemplate) => {
    setAdopting(template.id);
    try {
      await api.createGuardrailPolicy({
        name: template.name,
        description: template.description,
        rules_json: template.rules_json,
      });
      await queryClient.invalidateQueries({ queryKey: queryKeys.guardrailPolicies });
      toast.success(`Adopted "${template.name}"`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Couldn't adopt template");
    } finally {
      setAdopting(null);
    }
  };

  return (
    <SectionCard
      title={
        <span className="flex items-center gap-1.5">
          <Sparkles className="h-3.5 w-3.5 text-muted" aria-hidden />
          Policy templates
        </span>
      }
      description="Pre-built guardrails — adopt one to add an editable copy to your saved policies."
    >
      {isLoading ? (
        <LoadingState variant="list" label="Loading templates…" />
      ) : isError ? (
        <div className="flex items-center justify-between gap-2 rounded-md border border-destructive/25 bg-destructive/10 px-2.5 py-1.5">
          <p className="text-xs text-destructive">Couldn&apos;t load policy templates</p>
          <Button type="button" variant="ghost" size="xs" onClick={() => void refetch()}>
            Retry
          </Button>
        </div>
      ) : templates.length === 0 ? (
        <EmptyState
          compact
          icon={Sparkles}
          title="No templates available"
          description="Nothing to adopt right now — configure a guardrail above and save it as your own policy."
        />
      ) : (
        <ul className="divide-y divide-border overflow-hidden rounded-md border border-border">
          {templates.map((template) => (
            <li
              key={template.id}
              className="flex items-start justify-between gap-3 px-3 py-2.5 transition-colors hover:bg-surface-hover"
            >
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <p className="truncate text-sm font-medium text-foreground">
                    {template.name}
                  </p>
                  <Chip className="shrink-0 lowercase">{template.category}</Chip>
                </div>
                <p className="mt-0.5 text-xs text-muted">{template.description}</p>
                <p className="mt-1 font-mono text-2xs lowercase text-subtle">
                  {ruleSummary(template.rules_json)}
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-1">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    onLoad(toConfig(template));
                    toast.success(`Loaded "${template.name}" into the playground`);
                  }}
                >
                  Load
                </Button>
                <Button
                  type="button"
                  size="sm"
                  disabled={adopting === template.id}
                  onClick={() => adopt(template)}
                >
                  <Download className="h-3.5 w-3.5" aria-hidden />
                  {adopting === template.id ? "Adopting…" : "Adopt"}
                </Button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </SectionCard>
  );
}
