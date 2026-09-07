import type { WorkflowGraph } from "@/types/workflow";

export const WORKFLOW_EXPORT_FORMAT = "aegis-workflow-v1";

export interface WorkflowExportPayload {
  format?: string;
  workflow_id?: string;
  name?: string;
  description?: string | null;
  version_number?: number;
  version_id?: string;
  graph_json: WorkflowGraph;
  exported_at?: string;
}

export class WorkflowImportError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "WorkflowImportError";
  }
}

export function parseWorkflowExport(raw: unknown): WorkflowExportPayload {
  if (!raw || typeof raw !== "object") {
    throw new WorkflowImportError("Import file must contain a JSON object");
  }

  const payload = raw as Record<string, unknown>;
  const format = payload.format;
  if (format !== undefined && format !== WORKFLOW_EXPORT_FORMAT) {
    throw new WorkflowImportError(
      `Unsupported format: ${String(format)} (expected ${WORKFLOW_EXPORT_FORMAT})`
    );
  }

  const graph = payload.graph_json;
  if (!graph || typeof graph !== "object") {
    throw new WorkflowImportError("Missing or invalid graph_json");
  }

  const graphJson = graph as WorkflowGraph;
  if (!Array.isArray(graphJson.nodes) || !Array.isArray(graphJson.edges)) {
    throw new WorkflowImportError("graph_json must include nodes and edges arrays");
  }

  return {
    format: typeof format === "string" ? format : WORKFLOW_EXPORT_FORMAT,
    workflow_id: typeof payload.workflow_id === "string" ? payload.workflow_id : undefined,
    name: typeof payload.name === "string" ? payload.name : undefined,
    description:
      typeof payload.description === "string" || payload.description === null
        ? payload.description
        : undefined,
    version_number:
      typeof payload.version_number === "number" ? payload.version_number : undefined,
    version_id: typeof payload.version_id === "string" ? payload.version_id : undefined,
    graph_json: graphJson,
    exported_at: typeof payload.exported_at === "string" ? payload.exported_at : undefined,
  };
}

export async function readWorkflowExportFile(file: File): Promise<WorkflowExportPayload> {
  const text = await file.text();
  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch {
    throw new WorkflowImportError("File is not valid JSON");
  }
  return parseWorkflowExport(parsed);
}