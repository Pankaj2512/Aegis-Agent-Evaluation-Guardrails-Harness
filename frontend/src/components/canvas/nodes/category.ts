export type NodeCategory =
  | "trigger"
  | "logic"
  | "llm"
  | "data"
  | "integration"
  | "quality"
  | "flow";

export const CATEGORY_LABEL: Record<NodeCategory, string> = {
  trigger: "Trigger",
  logic: "Logic",
  llm: "LLM",
  data: "Data",
  integration: "Integration",
  quality: "Quality",
  flow: "Flow control",
};

export const CATEGORY_COLOR_VAR: Record<NodeCategory, string> = {
  trigger: "var(--cat-trigger)",
  logic: "var(--cat-logic)",
  llm: "var(--cat-llm)",
  data: "var(--cat-data)",
  integration: "var(--cat-integration)",
  quality: "var(--cat-quality)",
  flow: "var(--cat-flow)",
};

/** Map a node-type string from the registry to a category. */
export function categorize(nodeType: string): NodeCategory {
  if (nodeType.startsWith("trigger") || nodeType === "trigger" || nodeType === "input_schema")
    return "trigger";
  if (["if", "switch", "router", "filter", "iteration"].includes(nodeType)) return "logic";
  if (["agent", "classifier", "summarizer", "translator", "extractor"].includes(nodeType))
    return "llm";
  if (
    [
      "kb_retrieve",
      "memory_store",
      "memory_retrieve",
      "json_parse",
      "code",
      "transform",
      "set_fields",
      "tool",
    ].includes(nodeType)
  )
    return "data";
  if (nodeType.startsWith("integration_") || nodeType === "integration")
    return "integration";
  if (["evaluation", "guardrail"].includes(nodeType)) return "quality";
  if (["join", "delay", "sub_workflow", "human_approval", "end", "note"].includes(nodeType))
    return "flow";
  return "flow";
}

/**
 * Node source types that may carry an error-branch edge (an outgoing edge with
 * `data.route = "error"`, rendered from a dedicated bottom source handle). This
 * mirrors the backend's SUPPORTED source-type list exactly — types that can fail
 * mid-run and hand the downstream branch a `{error, node_id, node_type}` payload.
 * Excluded (backend REJECTS an error edge from): trigger, end, note, group,
 * join, agent, summarizer, translator, extractor, evaluation.
 */
export const ERROR_BRANCH_SOURCE_TYPES: ReadonlySet<string> = new Set([
  "transform",
  "set_fields",
  "code",
  "json_parse",
  "delay",
  "filter",
  "if",
  "switch",
  "router",
  "classifier",
  "guardrail",
  "input_schema",
  "memory_store",
  "memory_retrieve",
  "kb_retrieve",
  "human_approval",
  "integration",
  "sub_workflow",
  "tool",
  "iteration",
]);

/** Whether a node type may originate an error-branch edge (Feature 2).
 *
 * Config-aware: a `tool` node with `toolType === "search"` and a Google
 * provider compiles to a bare ADK Agent that never sets `ctx.route`, so the
 * backend REJECTS an error edge from it (see graph_validation
 * `_error_branch_unsupported`). Mirror that here so the canvas never offers an
 * error handle the backend will refuse to save. Pass the node's data when
 * available; the bare-type overload stays permissive for `tool` (calculator/
 * http tools do support error branches).
 */
export function supportsErrorBranch(
  nodeType: string,
  data?: { toolType?: string | null; searchProvider?: string | null } | null,
): boolean {
  if (!ERROR_BRANCH_SOURCE_TYPES.has(nodeType)) return false;
  if (
    nodeType === "tool" &&
    data?.toolType === "search" &&
    (data?.searchProvider ?? "google") === "google"
  ) {
    return false;
  }
  return true;
}