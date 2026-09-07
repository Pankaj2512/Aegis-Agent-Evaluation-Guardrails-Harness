"use client";

import { useId } from "react";
import { Cable, Route, Trash2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { Edge } from "@xyflow/react";

interface EdgeInspectorProps {
  edge: Edge | null;
  sourceLabel?: string;
  targetLabel?: string;
  routerRoutes?: string[];
  onChange: (edgeId: string, updates: { route?: string; label?: string }) => void;
  /** Omitted when structural edits are locked (small screens). */
  onDelete?: (edgeId: string) => void;
}

export function EdgeInspector({
  edge,
  sourceLabel,
  targetLabel,
  routerRoutes,
  onChange,
  onDelete,
}: EdgeInspectorProps) {
  const routeLabelId = useId();

  if (!edge) {
    return (
      <div className="inspector-empty gap-3 rounded-xl border border-dashed border-border bg-surface p-5 text-center">
        <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-xl bg-primary-muted text-primary">
          <Cable className="h-5 w-5" />
        </div>
        <div className="space-y-1">
          <p className="text-sm font-medium text-foreground">No connection selected</p>
          <p className="text-xs leading-relaxed text-muted">
            Select an edge on the canvas to name routes for router, IF, and Switch branches.
          </p>
        </div>
      </div>
    );
  }

  const route = (edge.data as { route?: string } | undefined)?.route ?? edge.label ?? "";
  const isErrorRoute = route === "error";

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-border bg-surface-elevated p-3 shadow-elev-1">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary-muted text-primary">
                <Cable className="h-3.5 w-3.5" />
              </div>
              <p className="text-sm font-semibold text-foreground">Connection</p>
            </div>
            <div className="mt-3 flex min-w-0 items-center gap-2 text-xs">
              <Badge variant="outline" className="min-w-0 truncate px-2 py-0.5">
                {sourceLabel ?? edge.source}
              </Badge>
              <Route className="h-3.5 w-3.5 shrink-0 text-muted" />
              <Badge variant="outline" className="min-w-0 truncate px-2 py-0.5">
                {targetLabel ?? edge.target}
              </Badge>
            </div>
            <p className="mt-2 text-xs text-muted">
              {isErrorRoute
                ? "Error route"
                : route
                  ? `Route "${String(route)}"`
                  : "Default route"}
            </p>
          </div>
          {onDelete && (
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label="Delete connection"
              onClick={() => onDelete(edge.id)}
              className="text-muted hover:text-destructive"
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          )}
        </div>
      </div>

      {isErrorRoute ? (
        <div className="space-y-2 rounded-xl border border-destructive/30 bg-destructive/5 p-3">
          <Badge
            variant="outline"
            className="border-destructive/40 px-2 py-0.5 text-2xs text-destructive"
          >
            error route
          </Badge>
          <p className="text-xs leading-relaxed text-muted">
            Runs when{" "}
            <span className="text-foreground">{sourceLabel ?? edge.source}</span> fails,
            receiving a JSON{" "}
            <code className="font-mono text-2xs text-foreground">
              {"{ error, node_id, node_type }"}
            </code>{" "}
            payload. Reconnect its start from the node&apos;s bottom handle to change it.
          </p>
        </div>
      ) : (
      <div className="space-y-2 rounded-xl border border-border bg-surface p-3">
        <div className="flex items-center justify-between gap-2">
          <Label htmlFor={routeLabelId}>Route label</Label>
          <Badge variant={route ? "primary" : "outline"} className="px-2 py-0.5 text-2xs">
            {route ? "named" : "default"}
          </Badge>
        </div>
        {routerRoutes && routerRoutes.length > 0 ? (
          <Select
            value={String(route) || "__default__"}
            onValueChange={(value) => {
              const next = value === "__default__" ? "" : value;
              onChange(edge.id, { route: next, label: next });
            }}
          >
            <SelectTrigger id={routeLabelId} className="w-full">
              <SelectValue placeholder="Default (no route)" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__default__">Default (no route)</SelectItem>
              {routerRoutes.map((r) => (
                <SelectItem key={r} value={r}>
                  {r}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        ) : (
          <Input
            id={routeLabelId}
            value={String(route)}
            onChange={(e) => onChange(edge.id, { route: e.target.value, label: e.target.value })}
            placeholder="e.g. route_a"
          />
        )}
        <p className="form-hint">Required for router, IF, and Switch branches.</p>
      </div>
      )}
    </div>
  );
}
