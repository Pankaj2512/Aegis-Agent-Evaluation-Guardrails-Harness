"use client";

import { useId, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, Plus } from "lucide-react";
import { EmptyState } from "@/components/ui/empty-state";
import { LoadingState } from "@/components/ui/loading-state";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { InlineQueryError } from "@/components/settings/InlineQueryError";
import { SettingsSection } from "@/components/settings/SettingsSection";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RowDeleteButton } from "@/components/ui/row-delete-button";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { api } from "@/lib/api";
import { formatFullTimestamp, formatRelativeTime } from "@/lib/format-date";
import { queryKeys } from "@/lib/query-keys";
import { cn } from "@/lib/utils";

const METRICS = [
  { value: "failure_rate", label: "Failure rate", hint: "0–1 over window" },
  { value: "eval_avg", label: "Avg eval score", hint: "1–5, use < operator" },
  { value: "guardrail_blocks", label: "Guardrail blocks", hint: "count over window" },
  { value: "cost_usd", label: "Cost (USD)", hint: "sum over window" },
  { value: "latency_p95", label: "Latency p95 (ms)", hint: "95th pct over window" },
  { value: "latency_p99", label: "Latency p99 (ms)", hint: "99th pct over window" },
];

/** Alert rules: evaluated every scheduler tick; breaches fire the webhook. */
export function AlertsCard() {
  const queryClient = useQueryClient();
  const baseId = useId();
  const fieldId = (name: string) => `${baseId}-${name}`;
  const [metric, setMetric] = useState("failure_rate");
  const [operator, setOperator] = useState<"gt" | "lt">("gt");
  const [threshold, setThreshold] = useState("0.5");
  const [windowMinutes, setWindowMinutes] = useState("60");
  const [comparison, setComparison] = useState<"absolute" | "baseline">("absolute");
  const [baselineWindow, setBaselineWindow] = useState("360");
  const [channelUrl, setChannelUrl] = useState("");
  const [saving, setSaving] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [togglingId, setTogglingId] = useState<string | null>(null);

  const {
    data: rules = [],
    isLoading: rulesLoading,
    isError: rulesError,
    refetch: refetchRules,
  } = useQuery({ queryKey: queryKeys.alertRules, queryFn: api.listAlertRules });
  const {
    data: events = [],
    isError: eventsError,
    refetch: refetchEvents,
  } = useQuery({
    queryKey: queryKeys.alertEvents,
    queryFn: api.listAlertEvents,
    refetchInterval: 60_000,
  });

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: queryKeys.alertRules });
    void queryClient.invalidateQueries({ queryKey: queryKeys.alertEvents });
  };

  const create = async () => {
    if (saving) return;
    const value = Number(threshold);
    if (!Number.isFinite(value)) {
      toast.error("Threshold must be a number");
      return;
    }
    setSaving(true);
    try {
      await api.createAlertRule({
        workflow_id: null,
        metric,
        operator,
        threshold: value,
        window_minutes: Number(windowMinutes) || 60,
        comparison,
        baseline_window_minutes:
          comparison === "baseline" ? Number(baselineWindow) || 360 : null,
        channel_url: channelUrl.trim() || null,
        enabled: true,
      });
      refresh();
      toast.success("Alert rule created");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to create rule");
    } finally {
      setSaving(false);
    }
  };

  return (
    <SettingsSection
      id="settings-alerts"
      title="Alerts"
      description="Evaluated every scheduler tick. Breaches log and hit the webhook if set."
    >
      <div className="grid gap-2 sm:grid-cols-5">
          <div className="space-y-1.5 sm:col-span-2">
            <Label htmlFor={fieldId("metric")}>Metric</Label>
            <Select value={metric} onValueChange={setMetric}>
              <SelectTrigger
                id={fieldId("metric")}
                className="w-full"
                aria-label="Alert metric"
              >
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {METRICS.map((m) => (
                  <SelectItem key={m.value} value={m.value}>
                    {m.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor={fieldId("operator")}>Operator</Label>
            <Select value={operator} onValueChange={(v) => setOperator(v as "gt" | "lt")}>
              <SelectTrigger
                id={fieldId("operator")}
                className="w-full"
                aria-label="Comparison operator"
              >
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="gt">&gt;</SelectItem>
                <SelectItem value="lt">&lt;</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor={fieldId("threshold")}>Threshold</Label>
            <Input
              id={fieldId("threshold")}
              value={threshold}
              onChange={(e) => setThreshold(e.target.value)}
              placeholder="0.5"
              aria-label="Threshold"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor={fieldId("window")}>Window (min)</Label>
            <Input
              id={fieldId("window")}
              value={windowMinutes}
              onChange={(e) => setWindowMinutes(e.target.value)}
              placeholder="60"
              aria-label="Window minutes"
            />
          </div>
        </div>
        <div className="grid gap-2 sm:grid-cols-5">
          <div className="space-y-1.5 sm:col-span-2">
            <Label htmlFor={fieldId("comparison")}>Comparison</Label>
            <Select
              value={comparison}
              onValueChange={(v) => setComparison(v as "absolute" | "baseline")}
            >
              <SelectTrigger
                id={fieldId("comparison")}
                className="w-full"
                aria-label="Comparison mode"
              >
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="absolute">Absolute threshold</SelectItem>
                <SelectItem value="baseline">Anomaly (vs baseline ×)</SelectItem>
              </SelectContent>
            </Select>
          </div>
          {comparison === "baseline" && (
            <div className="space-y-1.5 sm:col-span-2">
              <Label htmlFor={fieldId("baseline-window")}>Baseline window (min)</Label>
              <Input
                id={fieldId("baseline-window")}
                value={baselineWindow}
                onChange={(e) => setBaselineWindow(e.target.value)}
                placeholder="360"
                aria-label="Baseline window minutes"
              />
            </div>
          )}
          {/* Full width so the longer baseline copy isn't squeezed into a 1/5 column. */}
          <p className="form-hint sm:col-span-5">
            {comparison === "baseline"
              ? "Threshold is a ratio — e.g. 2 means 2× the baseline window."
              : "Threshold is a raw value in the metric's own units."}
          </p>
        </div>
        <div className="flex gap-2">
          <Input
            value={channelUrl}
            onChange={(e) => setChannelUrl(e.target.value)}
            placeholder="Webhook URL (optional — Slack incoming webhook works)"
            className="flex-1"
            aria-label="Webhook URL"
          />
          <Button variant="outline" onClick={create} disabled={saving}>
            <Plus className="h-4 w-4" />
            {saving ? "Saving…" : "Add rule"}
          </Button>
        </div>

        <div className="space-y-1.5">
          {rules.map((rule) => (
            <div
              key={rule.id}
              className="group flex items-center justify-between gap-2 rounded-md border border-border bg-surface-input px-3 py-2"
            >
              <span
                className={cn(
                  "font-mono text-xs text-foreground",
                  !rule.enabled && "text-muted line-through"
                )}
              >
                {rule.metric} {rule.operator === "gt" ? ">" : "<"} {rule.threshold}
                {rule.comparison === "baseline" ? "× baseline" : ""} · {rule.window_minutes}m
                {rule.comparison === "baseline" && rule.baseline_window_minutes
                  ? ` / ${rule.baseline_window_minutes}m`
                  : ""}
                {rule.channel_url ? " · webhook" : ""}
              </span>
              <div className="flex items-center gap-2">
                {rule.last_fired_at && (
                  <Badge variant="warning" title={formatFullTimestamp(rule.last_fired_at)}>
                    fired{" "}
                    <span className="font-mono tabular-nums">
                      {formatRelativeTime(rule.last_fired_at)}
                    </span>
                  </Badge>
                )}
                <Switch
                  size="sm"
                  checked={rule.enabled}
                  disabled={togglingId === rule.id}
                  aria-label={rule.enabled ? "Disable rule" : "Enable rule"}
                  onCheckedChange={async (next) => {
                    setTogglingId(rule.id);
                    try {
                      await api.updateAlertRule(rule.id, { enabled: next });
                      refresh();
                    } catch (error) {
                      toast.error(
                        error instanceof Error ? error.message : "Failed to update rule"
                      );
                    } finally {
                      setTogglingId(null);
                    }
                  }}
                />
                <RowDeleteButton
                  aria-label={`Delete rule ${rule.metric}`}
                  disabled={deletingId === rule.id}
                  onClick={async () => {
                    setDeletingId(rule.id);
                    try {
                      await api.deleteAlertRule(rule.id);
                      refresh();
                      toast.success("Rule deleted");
                    } catch (error) {
                      toast.error(error instanceof Error ? error.message : "Failed to delete rule");
                    } finally {
                      setDeletingId(null);
                    }
                  }}
                />
              </div>
            </div>
          ))}
          {rulesLoading ? (
            <LoadingState variant="list" label="Loading alert rules…" />
          ) : rulesError ? (
            <InlineQueryError
              message="Couldn't load alert rules"
              onRetry={() => void refetchRules()}
            />
          ) : rules.length === 0 ? (
            <EmptyState
              compact
              icon={Bell}
              title="No alert rules yet"
              description="Add a rule above — breaches are logged and sent to your webhook."
            />
          ) : null}
        </div>

        {(eventsError || events.length > 0) && (
          <div className="space-y-1 border-t border-border pt-3">
            <p className="text-micro">Recent alert events</p>
            {eventsError ? (
              <InlineQueryError
                message="Couldn't load recent alert events"
                onRetry={() => void refetchEvents()}
              />
            ) : (
              events.slice(0, 5).map((event) => (
                <p key={event.id} className="font-mono text-xs text-warning">
                  <span className="tabular-nums">
                    {event.fired_at ? formatFullTimestamp(event.fired_at) : "—"}
                  </span>{" "}
                  — {event.message}
                </p>
              ))
            )}
          </div>
        )}
    </SettingsSection>
  );
}

const OPS_LABELS: Record<string, string> = {
  retention_enabled: "Run retention purge",
  run_retention_days: "Retention window (days)",
  online_eval_sample_rate: "Online eval sample rate",
  otel_enabled: "OpenTelemetry export",
  otel_sample_rate: "OTel sample rate",
  schedule_poll_seconds: "Scheduler poll (s)",
  max_concurrent_runs: "Max concurrent runs",
};

/** Read-only operational knobs (env-driven; see backend .env). */
export function OpsConfigCard() {
  const { data } = useQuery({ queryKey: ["ops-config"], queryFn: api.getOpsConfig });
  if (!data) return null;
  return (
    <SettingsSection
      id="settings-ops"
      title="Operational config"
      description="Env-driven knobs. Edit backend/.env and restart to change."
    >
      <div className="space-y-1.5">
        {Object.entries(OPS_LABELS).map(([key, label]) => (
          <div key={key} className="flex items-center justify-between font-mono text-xs">
            <span className="text-muted">{label}</span>
            <span className="text-foreground">
              {typeof data[key] === "boolean"
                ? data[key]
                  ? "enabled"
                  : "disabled"
                : String(data[key] ?? "—")}
            </span>
          </div>
        ))}
      </div>
    </SettingsSection>
  );
}
