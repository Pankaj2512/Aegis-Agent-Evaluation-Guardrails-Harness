"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Bookmark, Download, Plus } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { EmptyState } from "@/components/ui/empty-state";
import { LoadingState } from "@/components/ui/loading-state";
import { RowDeleteButton } from "@/components/ui/row-delete-button";
import { SectionCard } from "@/components/ui/section-card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { api, type GuardrailPolicy } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import type { GuardrailMode, GuardrailType } from "@/types/workflow";

/** The playground config a policy captures — kept flat inside rules_json. */
export interface PlaygroundConfig {
  guardrail_type: GuardrailType;
  mode: GuardrailMode;
  blocked_keywords: string[];
  sample: string;
}

interface SavedPoliciesProps {
  /** Snapshot of the current playground config, saved on "Save as policy". */
  currentConfig: PlaygroundConfig;
  /** Load a policy's config back into the playground. */
  onLoad: (config: PlaygroundConfig) => void;
}

const GUARDRAIL_TYPES: GuardrailType[] = [
  "rules",
  "presidio",
  "prompt_injection",
  "moderation",
  "json_schema",
  "llm",
];

/** Rails the playground can actually exercise — its Type select renders exactly
 *  these. json_schema is deliberately absent: schema validation needs the node's
 *  schema + re-ask config, so those policies are tested on the canvas. Loading
 *  one here would leave the Select on a value with no matching item. */
export const PLAYGROUND_GUARDRAIL_TYPES: GuardrailType[] = GUARDRAIL_TYPES.filter(
  (type) => type !== "json_schema"
);

/** Coerce a policy's stored rules_json into a valid playground config. */
function configFromRules(rules: Record<string, unknown>): PlaygroundConfig {
  const type = rules.guardrail_type;
  const mode = rules.mode;
  const keywords = rules.blocked_keywords;
  return {
    guardrail_type: GUARDRAIL_TYPES.includes(type as GuardrailType)
      ? (type as GuardrailType)
      : "rules",
    mode: mode === "input" ? "input" : "output",
    blocked_keywords: Array.isArray(keywords)
      ? keywords.filter((k): k is string => typeof k === "string")
      : [],
    sample: typeof rules.sample === "string" ? rules.sample : "",
  };
}

export function SavedPolicies({ currentConfig, onLoad }: SavedPoliciesProps) {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<GuardrailPolicy | null>(null);

  const {
    data: policies = [],
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: queryKeys.guardrailPolicies,
    queryFn: api.listGuardrailPolicies,
  });

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: queryKeys.guardrailPolicies });

  const handleSave = async () => {
    if (!name.trim()) {
      toast.error("Name the policy before saving");
      return;
    }
    setSaving(true);
    try {
      await api.createGuardrailPolicy({
        name: name.trim(),
        rules_json: {
          guardrail_type: currentConfig.guardrail_type,
          mode: currentConfig.mode,
          blocked_keywords: currentConfig.blocked_keywords,
          sample: currentConfig.sample,
        },
      });
      await invalidate();
      setName("");
      toast.success(`Saved policy "${name.trim()}"`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to save policy");
    } finally {
      setSaving(false);
    }
  };

  /** The playground can't render a json_schema rail (no Select item, and schema
   *  validation is node-level config), so load it as keyword rules and say why
   *  rather than stranding the Type select on a value with no option. */
  const handleLoad = (policy: GuardrailPolicy, config: PlaygroundConfig) => {
    if (PLAYGROUND_GUARDRAIL_TYPES.includes(config.guardrail_type)) {
      onLoad(config);
      toast.success(`Loaded "${policy.name}"`);
      return;
    }
    onLoad({ ...config, guardrail_type: "rules" });
    toast.info(
      `"${policy.name}" checks structured output — loaded as keyword rules. Schema policies are tested on the canvas.`
    );
  };

  return (
    <SectionCard
      title="Saved policies"
      description="Save the current playground configuration and reload it later."
    >
      <div className="space-y-4">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
          <div className="flex-1 space-y-1.5">
            <Label htmlFor="policy-name">Policy name</Label>
            <Input
              id="policy-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="pii_output_block"
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  void handleSave();
                }
              }}
            />
          </div>
          <Button
            type="button"
            size="sm"
            onClick={handleSave}
            disabled={saving}
            className="gap-1.5"
          >
            <Plus className="h-3.5 w-3.5" />
            {saving ? "Saving…" : "Save current config"}
          </Button>
        </div>

        {isLoading ? (
          <LoadingState variant="list" label="Loading policies…" />
        ) : isError ? (
          <div className="flex items-center justify-between gap-2 rounded-md border border-destructive/25 bg-destructive/10 px-2.5 py-1.5">
            <p className="text-xs text-destructive">Couldn&apos;t load saved policies</p>
            <Button type="button" variant="ghost" size="xs" onClick={() => void refetch()}>
              Retry
            </Button>
          </div>
        ) : policies.length === 0 ? (
          <EmptyState
            compact
            icon={Bookmark}
            title="No saved policies yet"
            description="Configure a guardrail above, then save it to reuse the setup."
          />
        ) : (
          <ul className="divide-y divide-border overflow-hidden rounded-md border border-border">
            {policies.map((policy) => {
              const config = configFromRules(policy.rules_json);
              return (
                <li
                  key={policy.id}
                  className="group flex items-center justify-between gap-3 px-3 py-2.5 transition-colors hover:bg-surface-hover"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-foreground">
                      {policy.name}
                    </p>
                    <p className="mt-0.5 truncate font-mono text-2xs lowercase text-muted">
                      {config.guardrail_type} · {config.mode}
                      {config.blocked_keywords.length > 0
                        ? ` · ${config.blocked_keywords.length} keywords`
                        : ""}
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-1">
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => handleLoad(policy, config)}
                    >
                      <Download className="h-3.5 w-3.5" />
                      Load
                    </Button>
                    <RowDeleteButton
                      aria-label={`Delete policy ${policy.name}`}
                      onClick={() => setDeleteTarget(policy)}
                    />
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      <ConfirmDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null);
        }}
        title="Delete policy?"
        description={
          deleteTarget
            ? `"${deleteTarget.name}" will be removed. Workflows referencing it fall back to node-level rules.`
            : ""
        }
        confirmLabel={deleteTarget ? `Delete '${deleteTarget.name}'` : "Delete"}
        loadingLabel="Deleting policy…"
        variant="destructive"
        onConfirm={async () => {
          if (!deleteTarget) return;
          try {
            await api.deleteGuardrailPolicy(deleteTarget.id);
            await invalidate();
            toast.success("Policy deleted");
          } catch (error) {
            toast.error(
              error instanceof Error ? error.message : "Failed to delete policy"
            );
          }
        }}
      />
    </SectionCard>
  );
}
