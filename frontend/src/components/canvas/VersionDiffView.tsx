"use client";

import type { WorkflowGraph, WorkflowVersion } from "@/types/workflow";

export type DiffKind = "added" | "removed" | "changed";

type DiffRow = {
  kind: DiffKind;
  nodeId: string;
  label: string;
  detail?: string;
};

function nodeMap(graph: WorkflowGraph) {
  return new Map(graph.nodes.map((node) => [node.id, node]));
}

export function diffWorkflowVersions(
  left: WorkflowVersion,
  right: WorkflowVersion
): DiffRow[] {
  const leftNodes = nodeMap(left.graph_json);
  const rightNodes = nodeMap(right.graph_json);
  const rows: DiffRow[] = [];

  rightNodes.forEach((node, id) => {
    if (!leftNodes.has(id)) {
      rows.push({
        kind: "added",
        nodeId: id,
        label: String(node.data.label || node.data.nodeType || id),
      });
    }
  });
  leftNodes.forEach((node, id) => {
    if (!rightNodes.has(id)) {
      rows.push({
        kind: "removed",
        nodeId: id,
        label: String(node.data.label || node.data.nodeType || id),
      });
      return;
    }
    const other = rightNodes.get(id)!;
    if (JSON.stringify(node.data) !== JSON.stringify(other.data)) {
      rows.push({
        kind: "changed",
        nodeId: id,
        label: String(node.data.label || node.data.nodeType || id),
        detail: `${node.data.nodeType} → config changed`,
      });
    }
  });

  const leftEdges = new Set(left.graph_json.edges.map((e) => `${e.source}->${e.target}`));
  const rightEdges = new Set(right.graph_json.edges.map((e) => `${e.source}->${e.target}`));
  Array.from(rightEdges).forEach((edge) => {
    if (!leftEdges.has(edge)) {
      rows.push({ kind: "added", nodeId: edge, label: "Edge", detail: edge });
    }
  });
  Array.from(leftEdges).forEach((edge) => {
    if (!rightEdges.has(edge)) {
      rows.push({ kind: "removed", nodeId: edge, label: "Edge", detail: edge });
    }
  });
  return rows;
}

export function buildDiffHighlightMap(
  left: WorkflowVersion,
  right: WorkflowVersion
): Record<string, DiffKind> {
  const map: Record<string, DiffKind> = {};
  for (const row of diffWorkflowVersions(left, right)) {
    if (row.label === "Edge") continue;
    map[row.nodeId] = row.kind;
  }
  return map;
}

export function VersionDiffView({
  left,
  right,
}: {
  left: WorkflowVersion;
  right: WorkflowVersion;
}) {
  const rows = diffWorkflowVersions(left, right);
  if (!rows.length) {
    return <p className="text-sm text-muted">No structural differences between versions.</p>;
  }
  return (
    <div className="max-h-48 space-y-1 overflow-y-auto rounded-lg border border-border p-2 text-xs">
      {rows.map((row) => (
        <div key={`${row.kind}-${row.nodeId}`} className="flex gap-2">
          <span
            className={
              row.kind === "added"
                ? "text-success"
                : row.kind === "removed"
                  ? "text-destructive"
                  : "text-warning"
            }
          >
            {row.kind}
          </span>
          <span className="font-medium text-foreground">{row.label}</span>
          {row.detail && <span className="text-muted">{row.detail}</span>}
        </div>
      ))}
    </div>
  );
}