"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { LayoutTemplate, Loader2, Plus, Sparkles, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import { createWorkflowFromTemplate } from "@/lib/create-from-template";
import { dismissOnboarding, isOnboardingDismissed } from "@/lib/onboarding";

/**
 * First-run panel shown in place of the empty-library EmptyState. Renders null
 * on the server and first client paint (hydration-safe) and when dismissed —
 * the page falls back to its existing EmptyState in that case.
 */
export function FirstRunHero({ fallback }: { fallback: React.ReactNode }) {
  const [ready, setReady] = useState(false);
  const [creating, setCreating] = useState(false);
  const router = useRouter();
  const queryClient = useQueryClient();

  useEffect(() => {
    setReady(!isOnboardingDismissed("dashboard"));
  }, []);

  if (!ready) return <>{fallback}</>;

  const handleDismiss = () => {
    dismissOnboarding("dashboard");
    setReady(false);
  };

  const handleCreateFromTemplate = async () => {
    if (creating) return;
    setCreating(true);
    try {
      const templates = await queryClient.fetchQuery({
        queryKey: queryKeys.templates,
        queryFn: api.listTemplates,
      });
      const first = templates[0];
      if (!first) {
        router.push("/templates");
        return;
      }
      // Route through useTemplate so usage_count increments and we create from
      // the canonical server graph_json (falls back to the listed graph).
      const used = await api.useTemplate(first.id);
      const workflow = await createWorkflowFromTemplate(
        queryClient,
        { ...first, graph_json: used.graph_json },
        { name: "My first workflow" }
      );
      router.push(`/workflows/${workflow.id}`);
    } catch {
      // toast surfaced by createWorkflowFromTemplate / fetch errors
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="relative rounded-lg border border-border bg-surface p-6 shadow-elev-1">
      <Button
        variant="ghost"
        size="icon"
        className="absolute right-3 top-3"
        onClick={handleDismiss}
        aria-label="Dismiss getting started"
      >
        <X className="h-4 w-4" />
      </Button>

      <div className="flex items-center gap-2 text-primary">
        <Sparkles className="h-4 w-4" />
        <span className="text-2xs font-medium uppercase tracking-wider">Get started</span>
      </div>
      <h2 className="mt-2 text-lg font-semibold text-foreground">Build your first agent workflow</h2>
      <p className="mt-1 max-w-xl text-sm text-muted">
        Compose agents, tools, and guardrails on a visual canvas — version each
        change and publish when it is ready to serve.
      </p>

      <div className="mt-5 grid gap-3 sm:grid-cols-3">
        <button
          type="button"
          onClick={handleCreateFromTemplate}
          disabled={creating}
          className="focus-ring flex flex-col items-start gap-2 rounded-lg border border-border bg-surface-input p-4 text-left transition-colors hover:border-border-strong hover:bg-surface-hover disabled:cursor-not-allowed disabled:opacity-60"
        >
          <span className="flex h-9 w-9 items-center justify-center rounded-lg border border-border bg-surface text-primary">
            {creating ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <LayoutTemplate className="h-4 w-4" />
            )}
          </span>
          <span className="text-sm font-medium text-foreground">
            {creating ? "Creating…" : "Create from template"}
          </span>
          <span className="text-xs text-muted">Start from a production-ready pattern.</span>
        </button>

        <Link
          href="/workflows/new"
          className="focus-ring flex flex-col items-start gap-2 rounded-lg border border-border bg-surface-input p-4 text-left transition-colors hover:border-border-strong hover:bg-surface-hover"
        >
          <span className="flex h-9 w-9 items-center justify-center rounded-lg border border-border bg-surface text-primary">
            <Sparkles className="h-4 w-4" />
          </span>
          <span className="text-sm font-medium text-foreground">Describe it with AI</span>
          <span className="text-xs text-muted">Draft a graph from a prompt.</span>
        </Link>

        <Link
          href="/workflows/new"
          className="focus-ring flex flex-col items-start gap-2 rounded-lg border border-border bg-surface-input p-4 text-left transition-colors hover:border-border-strong hover:bg-surface-hover"
        >
          <span className="flex h-9 w-9 items-center justify-center rounded-lg border border-border bg-surface text-primary">
            <Plus className="h-4 w-4" />
          </span>
          <span className="text-sm font-medium text-foreground">Start blank</span>
          <span className="text-xs text-muted">Open an empty canvas.</span>
        </Link>
      </div>
    </div>
  );
}
