"use client";

import * as React from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Compass, Download, MoreHorizontal, Rocket, Save, Upload } from "lucide-react";

import { startCanvasTour } from "@/components/onboarding/CanvasTour";
import { DeploySheet } from "@/components/canvas/chrome/DeploySheet";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { api } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import { toast } from "@/lib/toast";
import { formatShortcutKeys } from "@/lib/shortcuts";

export function HeaderActions({
  workflowId,
  versionId,
  onSave,
  onSaveAsNew,
  onImport,
  onExport,
  isSaving,
  disabled,
}: {
  /** Current workflow — required to publish/deploy. */
  workflowId?: string;
  /** Active/current version to publish. When absent, Publish is disabled. */
  versionId?: string;
  onSave: () => void;
  onSaveAsNew: () => void;
  onImport: () => void;
  onExport: () => void;
  isSaving?: boolean;
  disabled?: boolean;
}) {
  const [deployOpen, setDeployOpen] = React.useState(false);
  const queryClient = useQueryClient();

  const publish = useMutation({
    mutationFn: () => {
      if (!workflowId || !versionId) {
        throw new Error("Save a version before publishing.");
      }
      return api.publishVersion(workflowId, versionId);
    },
    onSuccess: (data) => {
      toast.success(`Published v${data.published_version_number}`);
      if (workflowId) {
        // Keep VersionHistory / DeploySheet / any getPublished consumer in sync.
        void queryClient.invalidateQueries({ queryKey: queryKeys.published(workflowId) });
        void queryClient.invalidateQueries({ queryKey: queryKeys.deployDescriptor(workflowId) });
        void queryClient.invalidateQueries({ queryKey: queryKeys.workflow(workflowId) });
      }
      setDeployOpen(true);
    },
    onError: (error) => {
      toast.error(
        error instanceof Error ? error.message : "Failed to publish version"
      );
    },
  });

  const canPublish = !!workflowId && !!versionId;

  return (
    <div className="flex items-center gap-2">
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            variant="outline"
            size="sm"
            onClick={onSave}
            disabled={disabled || isSaving}
          >
            <Save className="h-4 w-4" />
            {isSaving ? "Saving…" : "Save"}
          </Button>
        </TooltipTrigger>
        <TooltipContent>Save · {formatShortcutKeys(["⌘", "S"])}</TooltipContent>
      </Tooltip>

      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            size="sm"
            onClick={() => publish.mutate()}
            disabled={disabled || !canPublish || publish.isPending}
          >
            <Rocket className="h-4 w-4" />
            {publish.isPending ? "Publishing…" : "Publish"}
          </Button>
        </TooltipTrigger>
        <TooltipContent>
          {canPublish
            ? "Publish this version & get deploy details"
            : "Save a version to publish"}
        </TooltipContent>
      </Tooltip>

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="outline"
            size="icon-sm"
            aria-label="More actions"
            disabled={disabled}
          >
            <MoreHorizontal className="h-4 w-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-48">
          <DropdownMenuItem onSelect={onSaveAsNew}>
            <Save className="h-4 w-4" />
            Save as new version
          </DropdownMenuItem>
          <DropdownMenuItem
            onSelect={() => setDeployOpen(true)}
            disabled={!workflowId}
          >
            <Rocket className="h-4 w-4" />
            Deploy details…
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem onSelect={onImport}>
            <Upload className="h-4 w-4" />
            Import JSON…
          </DropdownMenuItem>
          <DropdownMenuItem onSelect={onExport}>
            <Download className="h-4 w-4" />
            Export JSON
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem onSelect={() => startCanvasTour()}>
            <Compass className="h-4 w-4" />
            Canvas tour
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      {workflowId ? (
        <DeploySheet
          open={deployOpen}
          onOpenChange={setDeployOpen}
          workflowId={workflowId}
        />
      ) : null}
    </div>
  );
}
