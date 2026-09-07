"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { Rocket } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { CopyButton } from "@/components/ui/copy-button";
import { EmptyState } from "@/components/ui/empty-state";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api } from "@/lib/api";
import { queryKeys } from "@/lib/query-keys";
import { cn } from "@/lib/utils";

/**
 * Detects the "no published version yet" case. The backend surfaces this as a
 * 409 whose detail message we can't read the status code of (request() throws a
 * plain Error with the detail string), so we match on the message shape.
 */
function isNoPublishedVersion(error: unknown): boolean {
  if (!(error instanceof Error)) return false;
  const msg = error.message.toLowerCase();
  return (
    msg.includes("no published") ||
    msg.includes("not published") ||
    msg.includes("publish") && msg.includes("first") ||
    msg.includes("409")
  );
}

type DeployTab = "curl" | "endpoint" | "embed" | "mcp";

/** Monospace code block with a hairline frame and a corner copy button. */
function CodeBlock({
  value,
  label,
  className,
}: {
  value: string;
  label: string;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "group relative overflow-hidden rounded-lg border border-border bg-surface-input",
        className
      )}
    >
      <div className="absolute right-2 top-2 z-10">
        <CopyButton
          text={value}
          label={`Copy ${label}`}
          className="bg-surface-overlay/80 backdrop-blur-sm"
        />
      </div>
      <pre className="max-h-[42vh] overflow-auto p-3 pr-10 font-mono text-xs leading-5 tabular-nums text-foreground">
        <code>{value}</code>
      </pre>
    </div>
  );
}

function FieldLabel({ children }: { children: React.ReactNode }) {
  return <p className="text-micro mb-1.5 text-subtle">{children}</p>;
}

function DeploySheetBody({ workflowId }: { workflowId: string }) {
  const publishedQuery = useQuery({
    queryKey: [...queryKeys.deployDescriptor(workflowId), "published"],
    queryFn: () => api.getPublished(workflowId),
    staleTime: 0,
  });

  const descriptorQuery = useQuery({
    queryKey: queryKeys.deployDescriptor(workflowId),
    queryFn: () => api.getDeployDescriptor(workflowId),
    // Only fetch the descriptor once we know something is published; otherwise
    // the descriptor endpoint 409s too.
    enabled: !!publishedQuery.data?.published_version_id,
    retry: false,
    staleTime: 0,
  });

  const [tab, setTab] = React.useState<DeployTab>("curl");

  // Loading: while we resolve whether there's a published version, or while the
  // descriptor loads for a published workflow.
  const loading =
    publishedQuery.isLoading ||
    (!!publishedQuery.data?.published_version_id && descriptorQuery.isLoading);

  if (loading) {
    return (
      <div className="flex-1 space-y-4 overflow-y-auto px-5 py-4" aria-busy="true">
        <div className="skeleton h-9 w-full rounded-lg" />
        <div className="space-y-2">
          <div className="skeleton h-3 w-24" />
          <div className="skeleton h-40 w-full rounded-lg" />
        </div>
      </div>
    );
  }

  // No published version — either getPublished says so, or the descriptor 409'd.
  const notPublished =
    (!publishedQuery.isLoading && !publishedQuery.data?.published_version_id) ||
    (descriptorQuery.isError && isNoPublishedVersion(descriptorQuery.error));

  if (notPublished) {
    return (
      <div className="flex-1 overflow-y-auto px-5 py-6">
        <EmptyState
          icon={Rocket}
          variant="info"
          title="Nothing published yet"
          description="Publish a version of this workflow to get an invoke URL, cURL snippet, embed code, and an MCP tool spec you can share."
        />
      </div>
    );
  }

  // Descriptor failed for some other reason.
  if (publishedQuery.isError || descriptorQuery.isError) {
    const err = publishedQuery.error ?? descriptorQuery.error;
    return (
      <div className="flex-1 overflow-y-auto px-5 py-6">
        <EmptyState
          variant="error"
          title="Couldn’t load deploy details"
          description={err instanceof Error ? err.message : "Please try again."}
        />
      </div>
    );
  }

  const descriptor = descriptorQuery.data;
  if (!descriptor) return null;

  const versionNumber =
    descriptor.published_version_number ??
    publishedQuery.data?.published_version_number ??
    null;

  const embedSnippet = `<iframe
  src="${descriptor.invoke_url}"
  title="${descriptor.workflow_name}"
  width="100%"
  height="600"
  style="border:0;border-radius:12px"
></iframe>`;

  const mcpJson = JSON.stringify(descriptor.mcp_tool, null, 2);

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      {/* Live status — the ONLY color in the sheet. */}
      <div className="flex items-center gap-2 border-b border-border px-5 py-3">
        <Badge variant="success" className="gap-1.5">
          <span
            className="h-1.5 w-1.5 rounded-full bg-success"
            aria-hidden="true"
          />
          {versionNumber != null ? `Live v${versionNumber}` : "Live"}
        </Badge>
        <span className="truncate font-mono text-xs text-muted tabular-nums">
          {descriptor.method} {descriptor.invoke_path}
        </span>
      </div>

      <Tabs
        value={tab}
        onValueChange={(v) => setTab(v as DeployTab)}
        className="flex flex-1 flex-col gap-0 overflow-hidden"
      >
        <div className="px-5 pt-3">
          <TabsList variant="line" className="w-full justify-start">
            <TabsTrigger value="curl">cURL</TabsTrigger>
            <TabsTrigger value="endpoint">Endpoint</TabsTrigger>
            <TabsTrigger value="embed">Embed</TabsTrigger>
            <TabsTrigger value="mcp">MCP tool</TabsTrigger>
          </TabsList>
        </div>

        <div className="flex-1 overflow-y-auto px-5 pb-6 pt-4">
          <TabsContent value="curl" className="space-y-1.5">
            <FieldLabel>Request</FieldLabel>
            <CodeBlock value={descriptor.curl} label="cURL command" />
            <p className="pt-2 text-xs leading-5 text-muted">
              Runs the published version over HTTP. Set your API key in the
              Authorization header if your deployment requires it.
            </p>
          </TabsContent>

          <TabsContent value="endpoint" className="space-y-4">
            <div>
              <FieldLabel>Invoke URL</FieldLabel>
              <CodeBlock value={descriptor.invoke_url} label="invoke URL" />
            </div>
            <div>
              <FieldLabel>Method &amp; path</FieldLabel>
              <CodeBlock
                value={`${descriptor.method} ${descriptor.invoke_path}`}
                label="method and path"
              />
            </div>
          </TabsContent>

          <TabsContent value="embed" className="space-y-1.5">
            <FieldLabel>Embed snippet</FieldLabel>
            <CodeBlock value={embedSnippet} label="embed snippet" />
            <p className="pt-2 text-xs leading-5 text-muted">
              Drop this iframe into any page to embed the invoke surface.
            </p>
          </TabsContent>

          <TabsContent value="mcp" className="space-y-1.5">
            <FieldLabel>MCP tool spec</FieldLabel>
            <CodeBlock value={mcpJson} label="MCP tool JSON" />
            <p className="pt-2 text-xs leading-5 text-muted">
              Register{" "}
              <span className="font-mono text-foreground">
                {descriptor.mcp_tool.name}
              </span>{" "}
              with any MCP client to call this workflow as a tool.
            </p>
          </TabsContent>
        </div>
      </Tabs>
    </div>
  );
}

/**
 * Publish & Deploy slide-over. Fetches the published-version state + the deploy
 * descriptor and presents copyable cURL / endpoint / embed / MCP snippets.
 *
 * Controlled: pass `open` + `onOpenChange`. `workflowId` is required to fetch;
 * the sheet body only mounts (and queries fire) while open.
 */
export function DeploySheet({
  open,
  onOpenChange,
  workflowId,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  workflowId: string;
}) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className="w-full gap-0 p-0 sm:max-w-md"
        aria-describedby={undefined}
      >
        <SheetHeader className="px-5">
          <SheetTitle className="flex items-center gap-2 text-base">
            <Rocket className="h-4 w-4 text-muted" aria-hidden="true" />
            Publish &amp; Deploy
          </SheetTitle>
          <SheetDescription>
            Ship this workflow — invoke over HTTP, embed it, or expose it as an
            MCP tool.
          </SheetDescription>
        </SheetHeader>

        {open && workflowId ? (
          <DeploySheetBody workflowId={workflowId} />
        ) : (
          <div className="flex-1" />
        )}
      </SheetContent>
    </Sheet>
  );
}
