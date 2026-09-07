"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useId, useState } from "react";
import { Compass, KeyRound, Moon, Plus, Sun, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ApiConnectionState } from "@/components/ui/connection-state";
import { EmptyState } from "@/components/ui/empty-state";
import { AlertsCard, OpsConfigCard } from "@/components/settings/AlertsCard";
import { EvalRubricCard } from "@/components/settings/EvalRubricCard";
import { SettingsSection } from "@/components/settings/SettingsSection";
import { SettingsNav } from "@/components/settings/SettingsNav";
import { PageHeader } from "@/components/ui/page-header";
import { PageEnter } from "@/components/motion";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { LoadingState } from "@/components/ui/loading-state";
import { useTheme } from "@/providers/ThemeProvider";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { api } from "@/lib/api";
import {
  clearApiKey,
  getApiKey,
  getApiKeyAuditLog,
  rotateApiKey,
  setApiKey,
  type ApiKeyAuditEntry,
} from "@/lib/auth";
import { formatFullTimestamp } from "@/lib/format-date";
import { resetOnboarding } from "@/lib/onboarding";
import { cn } from "@/lib/utils";
import type { IntegrationType } from "@/types/workflow";


const REQUIRED_CREDENTIAL_FIELDS: Record<IntegrationType, string[]> = {
  slack: ["webhook_url"],
  discord: ["webhook_url"],
  postgres: ["connection_url"],
  email: ["smtp_host", "smtp_user", "smtp_password"],
};

const CONFIG_HINTS: Record<
  IntegrationType,
  Array<{ key: string; label: string; secret?: boolean }>
> = {
  slack: [{ key: "webhook_url", label: "Webhook URL", secret: true }],
  discord: [{ key: "webhook_url", label: "Webhook URL", secret: true }],
  email: [
    { key: "smtp_host", label: "SMTP host" },
    { key: "smtp_port", label: "SMTP port" },
    { key: "smtp_user", label: "SMTP user" },
    { key: "smtp_password", label: "SMTP password", secret: true },
    { key: "from", label: "From address" },
    { key: "to", label: "Default to address" },
  ],
  postgres: [{ key: "connection_url", label: "Connection URL", secret: true }],
};

export default function SettingsPage() {
  const queryClient = useQueryClient();
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  const [apiKey, setApiKeyState] = useState("");
  const [auditLog, setAuditLog] = useState<ApiKeyAuditEntry[]>([]);
  const [credName, setCredName] = useState("");
  const [credType, setCredType] = useState<IntegrationType>("slack");
  const [credConfig, setCredConfig] = useState<Record<string, string>>({});
  const [savingCred, setSavingCred] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<
    { type: "credential"; id: string; name: string } | null
  >(null);
  const [credFieldErrors, setCredFieldErrors] = useState<Record<string, string>>({});
  const baseId = useId();
  const fieldId = (name: string) => `${baseId}-${name}`;

  const {
    data: credentials = [],
    isLoading: credentialsLoading,
    isError: credentialsError,
    error: credentialsQueryError,
    refetch: refetchCredentials,
  } = useQuery({
    queryKey: ["credentials"],
    queryFn: api.listCredentials,
  });

  useEffect(() => {
    setMounted(true);
    setApiKeyState(getApiKey() || "");
    setAuditLog(getApiKeyAuditLog());
  }, []);

  const refreshAuditLog = () => setAuditLog(getApiKeyAuditLog());

  const handleSave = () => {
    if (apiKey.trim()) {
      setApiKey(apiKey.trim());
      refreshAuditLog();
      toast.success("API key saved");
    } else {
      clearApiKey();
      refreshAuditLog();
      toast.info("API key cleared");
    }
  };

  const handleRotate = () => {
    if (!apiKey.trim()) {
      toast.error("Enter a new API key before rotating");
      return;
    }
    rotateApiKey(apiKey.trim());
    refreshAuditLog();
    toast.success("API key rotated");
  };

  const validateCredField = (fieldKey: string, value = credConfig[fieldKey]) => {
    const required = REQUIRED_CREDENTIAL_FIELDS[credType];
    if (!required.includes(fieldKey)) return true;
    const valid = Boolean(value?.trim());
    setCredFieldErrors((prev) => ({
      ...prev,
      [fieldKey]: valid ? "" : "This field is required",
    }));
    return valid;
  };

  const validateAllCredFields = () => {
    const errors: Record<string, string> = {};
    for (const fieldKey of REQUIRED_CREDENTIAL_FIELDS[credType]) {
      if (!credConfig[fieldKey]?.trim()) {
        errors[fieldKey] = "This field is required";
      }
    }
    setCredFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleCreateCredential = async () => {
    if (!credName.trim()) {
      toast.error("Credential name is required");
      return;
    }
    if (!validateAllCredFields()) {
      toast.error("Fill in all required credential fields");
      return;
    }
    setSavingCred(true);
    try {
      const created = await api.createCredential({
        name: credName.trim(),
        type: credType,
        config: credConfig,
      });
      await queryClient.invalidateQueries({ queryKey: ["credentials"] });
      setCredName("");
      setCredConfig({});
      setCredFieldErrors({});
      toast.success(`Credential "${created.name}" saved`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to save credential");
    } finally {
      setSavingCred(false);
    }
  };

  const handleDeleteCredential = async (id: string) => {
    try {
      await api.deleteCredential(id);
      await queryClient.invalidateQueries({ queryKey: ["credentials"] });
      toast.success("Credential deleted");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to delete credential");
    }
  };

  if (credentialsError) {
    return (
      <div className="page-container">
        <ApiConnectionState
          description="Settings data could not be loaded. Check the API target, then retry."
          error={credentialsQueryError}
          onRetry={() => {
            void refetchCredentials();
          }}
        />
      </div>
    );
  }

  return (
    <PageEnter className="page-container space-y-6">
      <PageHeader
        title="Settings"
        description="Appearance, API access, credentials, eval rubrics, and alerts."
      />

      <div className="lg:grid lg:grid-cols-[200px_minmax(0,1fr)] lg:gap-8">
        <SettingsNav />
        <div className="space-y-6">
      {/* 0 · Appearance */}
      <SettingsSection
        id="settings-appearance"
        title="Appearance"
        description="Obsidian instrument chrome — dark by default, with a quiet oxidized-paper light counterpart."
      >
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex min-w-0 items-start gap-3">
            <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-border bg-surface-input text-muted">
              {/* Both icons in the markup, CSS picks one so server/client HTML
                  match — the theme class is applied pre-hydration. */}
              <Moon className="hidden h-4 w-4 dark:block" aria-hidden />
              <Sun className="h-4 w-4 dark:hidden" aria-hidden />
            </span>
            <div className="min-w-0">
              <p className="text-sm font-medium text-foreground">
                <span className="hidden dark:inline">Dark</span>
                <span className="dark:hidden">Light</span>
              </p>
              <p className="mt-0.5 text-xs text-muted">
                <span className="hidden dark:inline">
                  Matte obsidian workbench with copper live-state cues (default).
                </span>
                <span className="dark:hidden">
                  Quiet oxidized paper with the same copper and sage signals.
                </span>
              </p>
            </div>
          </div>
          <div
            className="inline-flex shrink-0 rounded-lg border border-border bg-surface-input p-0.5"
            role="group"
            aria-label="Color theme"
          >
            <button
              type="button"
              onClick={() => setTheme("dark")}
              aria-pressed={mounted ? theme === "dark" : undefined}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
                "text-muted hover:text-foreground",
                "dark:bg-surface-elevated dark:text-foreground dark:shadow-elev-1"
              )}
            >
              <Moon className="h-3.5 w-3.5" aria-hidden />
              Dark
            </button>
            <button
              type="button"
              onClick={() => setTheme("light")}
              aria-pressed={mounted ? theme === "light" : undefined}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
                "bg-surface-elevated text-foreground shadow-elev-1",
                "dark:bg-transparent dark:text-muted dark:shadow-none dark:hover:text-foreground"
              )}
            >
              <Sun className="h-3.5 w-3.5" aria-hidden />
              Light
            </button>
          </div>
        </div>
      </SettingsSection>

      {/* 1 · Onboarding */}
      <SettingsSection
        id="settings-onboarding"
        title="Onboarding"
        description="Getting-started banners and the canvas tour, per browser."
      >
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex min-w-0 items-start gap-3">
            <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-border bg-surface-input text-muted">
              <Compass className="h-4 w-4" aria-hidden />
            </span>
            <div className="min-w-0">
              <p className="text-sm font-medium text-foreground">Replay tips &amp; tour</p>
              <p className="mt-0.5 text-xs text-muted">
                Restore every dismissed getting-started banner and the canvas tour.
              </p>
            </div>
          </div>
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="shrink-0"
            onClick={() => {
              resetOnboarding();
              toast.success("Tips & tour restored");
            }}
          >
            Replay tips &amp; tour
          </Button>
        </div>
      </SettingsSection>

      {/* 2 · API key */}
      <SettingsSection
        id="settings-api"
        title="API key"
        description="Local request identity for secured backend calls (X-Aegis-API-Key)."
      >
        <div className="space-y-1.5">
          <Label htmlFor="api-key">Key</Label>
          <Input
            id="api-key"
            type="password"
            value={apiKey}
            onChange={(e) => setApiKeyState(e.target.value)}
            placeholder="your-aegis-api-key"
            className="max-w-xl font-mono text-sm"
          />
        </div>
        <div className="flex flex-wrap gap-2">
          <Button type="button" size="sm" onClick={handleSave}>
            Save
          </Button>
          <Button type="button" size="sm" variant="outline" onClick={handleRotate}>
            Rotate
          </Button>
          <Button
            type="button"
            size="sm"
            variant="ghost"
            onClick={() => {
              setApiKeyState("");
              clearApiKey();
              refreshAuditLog();
              toast.info("API key cleared");
            }}
          >
            Clear
          </Button>
        </div>
        {auditLog.length > 0 && (
          <div className="border-t border-border pt-3">
            <p className="mb-2 text-2xs font-medium uppercase tracking-wider text-muted">
              Audit · {auditLog.length}
            </p>
            <ul className="max-h-36 space-y-1 overflow-y-auto font-mono text-2xs text-subtle">
              {auditLog.map((entry, index) => (
                <li key={`${entry.at}-${index}`} className="flex justify-between gap-3">
                  <span className="capitalize text-muted">{entry.action}</span>
                  <span>
                    {entry.keyHint ?? "—"} · {formatFullTimestamp(entry.at)}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </SettingsSection>

      {/* 3 · Credentials */}
      <SettingsSection
        id="settings-credentials"
        title="Credentials"
        description="Named secrets for Slack, Discord, Email, and Postgres nodes."
      >
        {credentialsLoading ? (
          <LoadingState variant="list" />
        ) : credentials.length === 0 ? (
          <EmptyState
            compact
            icon={KeyRound}
            title="No credentials yet"
            description="Add one below — Slack, Discord, Email, and Postgres nodes reference credentials by name."
          />
        ) : (
          <ul className="divide-y divide-border overflow-hidden rounded-md border border-border">
            {credentials.map((cred) => (
              <li
                key={cred.id}
                className="group flex items-center justify-between gap-3 px-3 py-2.5 transition-colors hover:bg-surface-hover"
              >
                <div className="flex min-w-0 items-center gap-2.5">
                  <p className="truncate text-sm font-medium text-foreground">{cred.name}</p>
                  <Badge variant="outline" className="font-mono text-2xs lowercase">
                    {cred.type}
                  </Badge>
                </div>
                <button
                  type="button"
                  aria-label={`Delete credential ${cred.name}`}
                  onClick={() =>
                    setDeleteTarget({ type: "credential", id: cred.id, name: cred.name })
                  }
                  className="focus-ring shrink-0 rounded-md p-1.5 text-muted opacity-0 transition-opacity hover:text-destructive group-hover:opacity-100 focus-visible:opacity-100"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </li>
            ))}
          </ul>
        )}

        <div className="space-y-3 border-t border-border pt-4">
          <p className="text-2xs font-medium uppercase tracking-wider text-muted">Add credential</p>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor={fieldId("cred-name")}>Name</Label>
              <Input
                id={fieldId("cred-name")}
                value={credName}
                onChange={(e) => setCredName(e.target.value)}
                placeholder="slack_default"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor={fieldId("cred-type")}>Type</Label>
              <Select
                value={credType}
                onValueChange={(value) => {
                  setCredType(value as IntegrationType);
                  setCredConfig({});
                  setCredFieldErrors({});
                }}
              >
                <SelectTrigger id={fieldId("cred-type")} className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="slack">Slack</SelectItem>
                  <SelectItem value="discord">Discord</SelectItem>
                  <SelectItem value="email">Email</SelectItem>
                  <SelectItem value="postgres">Postgres</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {CONFIG_HINTS[credType].map((field) => {
              const fid = fieldId(`cred-field-${field.key}`);
              return (
                <div key={field.key} className="space-y-1.5">
                  <Label
                    htmlFor={fid}
                    required={REQUIRED_CREDENTIAL_FIELDS[credType].includes(field.key)}
                  >
                    {field.label}
                  </Label>
                  <Input
                    id={fid}
                    type={field.secret ? "password" : "text"}
                    value={credConfig[field.key] || ""}
                    onChange={(e) =>
                      setCredConfig((prev) => ({ ...prev, [field.key]: e.target.value }))
                    }
                    onBlur={() => validateCredField(field.key)}
                    className={cn(credFieldErrors[field.key] && "border-destructive")}
                  />
                  {credFieldErrors[field.key] && (
                    <p className="text-xs text-destructive">{credFieldErrors[field.key]}</p>
                  )}
                </div>
              );
            })}
          </div>
          <Button
            type="button"
            size="sm"
            onClick={handleCreateCredential}
            disabled={savingCred}
            className="gap-1.5"
          >
            <Plus className="h-3.5 w-3.5" />
            {savingCred ? "Saving…" : "Add credential"}
          </Button>
        </div>
      </SettingsSection>

      {/* 4 · Eval rubrics */}
      <EvalRubricCard />

      {/* 5 · Alerts + ops */}
      <AlertsCard />
      <OpsConfigCard />
        </div>
      </div>

      <ConfirmDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null);
        }}
        title="Delete credential?"
        description="This will break any workflow that uses this credential. The change cannot be undone."
        confirmLabel={deleteTarget ? `Delete credential '${deleteTarget.name}'` : "Delete"}
        loadingLabel="Deleting credential…"
        variant="destructive"
        onConfirm={async () => {
          if (!deleteTarget) return;
          await handleDeleteCredential(deleteTarget.id);
        }}
      />
    </PageEnter>
  );
}
