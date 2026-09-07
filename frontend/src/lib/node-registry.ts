import {
  Bot,
  BookOpen,
  Braces,
  Calculator,
  CircleStop,
  Clock,
  Code2,
  Database,
  FileJson,
  Filter,
  FormInput,
  GitBranch,
  GitMerge,
  Globe,
  Languages,
  Mail,
  MessageSquare,
  Network,
  ListTree,
  Repeat,
  Search,
  Shield,
  Sparkles,
  Split,
  StickyNote,
  TableProperties,
  UserCheck,
  Wand2,
  Zap,
  type LucideIcon,
} from "lucide-react";
import type { NodeData, NodeType } from "@/types/workflow";

export type NodeCategory = "flow" | "llm" | "tools" | "data" | "quality" | "annotate";

/**
 * Coarse shape of a node's output, used only for SOFT typed-port validation
 * (Feature 3). The runtime stringifies everything, so this never blocks a
 * connection — it only powers a one-shot heads-up when a clear mismatch (e.g. a
 * list feeding a text-only consumer) would silently stringify.
 */
export type NodeOutputKind = "text" | "json" | "list" | "none";
/** Coarse shape a node's target port is happy to receive. */
export type NodeAcceptsKind = "any" | "text" | "json";

export interface NodeDefinition {
  type: NodeType;
  label: string;
  category: NodeCategory;
  description: string;
  icon: LucideIcon;
  defaultData: NodeData;
  accent: { ring: string; label: string; icon: string };
  supportsExpressions?: boolean;
  /** Concise (1–2 sentence) contextual help for the inspector, resolved from
   *  NODE_HELP by node type. Authored for high-confusion types first. */
  help?: string;
  /** Optional deep link to fuller docs for this node type. */
  docUrl?: string;
  /** SOFT-validation output shape. Omit to default to "text" (see resolvers). */
  outputKind?: NodeOutputKind;
  /** SOFT-validation accepted shape. Omit to default to "any". */
  acceptsKind?: NodeAcceptsKind;
}

/**
 * Per-node contextual help, keyed by node type. Kept co-located (rather than
 * inlined into every registry entry) so the registry stays lean and help copy
 * can be authored/edited in one place. High-confusion node types are covered
 * first; the inspector renders these in a collapsible help block. `docUrl` is
 * optional and omitted until real docs exist.
 */
export const NODE_HELP: Partial<Record<NodeType, { help: string; docUrl?: string }>> = {
  agent: {
    help: "An LLM step that runs your instruction against the incoming context. Reference upstream data with {{expressions}} in the instruction to ground the model on prior steps.",
  },
  classifier: {
    help: "Sorts each input into exactly one of your categories, then branches. Label outgoing edges to match category names so the run follows the right path.",
  },
  evaluation: {
    help: "Scores the output for quality (LLM grading, exact/regex/schema match, or similarity). Parallel mode scores after the run; set a threshold and fail behavior to gate on quality.",
  },
  guardrail: {
    help: "Validates input or output against rules, an LLM policy, or PII detection before the run continues. Fail behavior decides whether to block, warn, mask, or route around a violation.",
  },
  kb_retrieve: {
    help: "Retrieves the most relevant document chunks for a query (RAG) and passes them downstream. Ground the query on prior steps with {{expressions}} and tune Top K for recall vs. noise.",
  },
  code: {
    help: "Runs sandboxed Python with input, steps, memory, and last_output in scope — set result to return a value. No imports or network access are available.",
  },
  sub_workflow: {
    help: "Invokes another workflow by ID and returns its output as this step's result. Use it to reuse a shared flow; the child receives the input expression you provide.",
  },
  iteration: {
    help: "Loops over a list resolved from an expression, running a per-item template (or a whole sub-workflow) for each entry. Reference {{item}}, {{item.field}}, and {{index}} inside the template. Returns a JSON array of the results.",
  },
};

export const NODE_CATEGORIES: Array<{ id: NodeCategory; label: string }> = [
  { id: "flow", label: "Flow" },
  { id: "llm", label: "Agents" },
  { id: "tools", label: "Tools" },
  { id: "data", label: "Data" },
  { id: "quality", label: "Eval & safety" },
  { id: "annotate", label: "Annotate" },
];

const accent = {
  flow: { ring: "border-primary/40", label: "text-primary", icon: "bg-primary-muted text-primary" },
  llm: { ring: "border-primary/40", label: "text-primary", icon: "bg-primary-muted text-primary" },
  tools: { ring: "border-accent/40", label: "text-accent", icon: "bg-accent-muted text-accent" },
  data: { ring: "border-warning/40", label: "text-warning", icon: "bg-warning/10 text-warning" },
  quality: { ring: "border-success/40", label: "text-success", icon: "bg-success/10 text-success" },
  annotate: { ring: "border-border-strong", label: "text-muted", icon: "bg-surface-hover text-muted" },
} as const;

export const NODE_REGISTRY: NodeDefinition[] = [
  {
    type: "trigger",
    label: "Trigger",
    category: "flow",
    description: "Workflow entry point",
    icon: Zap,
    defaultData: { label: "Trigger", nodeType: "trigger", triggerType: "manual" },
    accent: { ring: "border-success/50", label: "text-success", icon: "bg-success/10 text-success" },
  },
  {
    type: "end",
    label: "End",
    category: "flow",
    description: "Workflow exit & output",
    icon: CircleStop,
    defaultData: { label: "End", nodeType: "end" },
    accent: { ring: "border-destructive/40", label: "text-destructive", icon: "bg-destructive/10 text-destructive" },
    outputKind: "none",
    acceptsKind: "any",
  },
  {
    type: "input_schema",
    label: "Input Schema",
    category: "flow",
    description: "Define structured workflow inputs",
    icon: FormInput,
    defaultData: {
      label: "Input Schema",
      nodeType: "input_schema",
      inputFields: [
        { key: "message", type: "string", required: true },
        { key: "priority", type: "string", default: "normal" },
      ],
    },
    accent: accent.flow,
    outputKind: "json",
  },
  {
    type: "if",
    label: "IF",
    category: "flow",
    description: "Branch on expression (true / false)",
    icon: Split,
    defaultData: {
      label: "IF",
      nodeType: "if",
      ifCondition: { left: "{{input.priority}}", operator: "eq", right: "high" },
    },
    accent: accent.flow,
  },
  {
    type: "switch",
    label: "Switch",
    category: "flow",
    description: "Route by matched value",
    icon: GitBranch,
    defaultData: {
      label: "Switch",
      nodeType: "switch",
      switchValue: "{{input.priority}}",
      switchCases: ["high", "normal", "low"],
      switchDefault: "default",
    },
    accent: accent.flow,
  },
  {
    type: "filter",
    label: "Filter",
    category: "flow",
    description: "Pass data only when condition matches",
    icon: Filter,
    defaultData: {
      label: "Filter",
      nodeType: "filter",
      filterCondition: { left: "{{last_output}}", operator: "not_empty" },
    },
    accent: accent.flow,
  },
  {
    type: "iteration",
    label: "Iteration",
    category: "flow",
    description: "Loop over a list, per item or sub-workflow",
    icon: Repeat,
    defaultData: {
      label: "Iteration",
      nodeType: "iteration",
      itemsExpression: "{{last_output}}",
      itemTemplate: "{{item}}",
      iterationMode: "sequential",
      maxItems: 25,
      onItemError: "fail",
    },
    accent: accent.flow,
    supportsExpressions: true,
    outputKind: "list",
  },
  {
    type: "router",
    label: "Router",
    category: "flow",
    description: "AI conditional branching",
    icon: GitBranch,
    defaultData: { label: "Router", nodeType: "router", routes: ["route_a", "route_b"] },
    accent: accent.flow,
  },
  {
    type: "classifier",
    label: "Classifier",
    category: "flow",
    description: "Categorize & branch",
    icon: ListTree,
    defaultData: { label: "Classifier", nodeType: "classifier", categories: ["support", "sales", "other"] },
    accent: accent.flow,
  },
  {
    type: "join",
    label: "Join",
    category: "flow",
    description: "Merge parallel paths",
    icon: GitMerge,
    defaultData: { label: "Join", nodeType: "join" },
    accent: accent.flow,
  },
  {
    type: "human_approval",
    label: "Human Approval",
    category: "flow",
    description: "Pause for human review before continuing",
    icon: UserCheck,
    defaultData: {
      label: "Human Approval",
      nodeType: "human_approval",
      approvalReview: "{{last_output}}",
    },
    accent: accent.flow,
    supportsExpressions: true,
  },
  {
    type: "sub_workflow",
    label: "Sub-workflow",
    category: "flow",
    description: "Execute another workflow by ID",
    icon: Network,
    defaultData: {
      label: "Sub-workflow",
      nodeType: "sub_workflow",
      subWorkflowInput: "{{last_output}}",
    },
    accent: accent.flow,
    supportsExpressions: true,
  },
  {
    type: "agent",
    label: "LLM Agent",
    category: "llm",
    description: "Gemini-powered reasoning",
    icon: Bot,
    defaultData: {
      label: "LLM Agent",
      nodeType: "agent",
      instruction: "You are a helpful AI assistant. Respond clearly and concisely.",
    },
    accent: accent.llm,
    supportsExpressions: true,
  },
  {
    type: "summarizer",
    label: "Summarizer",
    category: "llm",
    description: "Condense long text",
    icon: FileJson,
    defaultData: { label: "Summarizer", nodeType: "summarizer", summaryStyle: "concise" },
    accent: accent.llm,
    acceptsKind: "text",
  },
  {
    type: "translator",
    label: "Translator",
    category: "llm",
    description: "Translate to any language",
    icon: Languages,
    defaultData: { label: "Translator", nodeType: "translator", targetLanguage: "Spanish" },
    accent: accent.llm,
    acceptsKind: "text",
  },
  {
    type: "extractor",
    label: "Extractor",
    category: "llm",
    description: "Structured JSON extraction",
    icon: Braces,
    defaultData: {
      label: "Extractor",
      nodeType: "extractor",
      extractFields: ["summary", "entities", "action_items"],
    },
    accent: accent.llm,
    outputKind: "json",
  },
  {
    type: "tool",
    label: "Calculator",
    category: "tools",
    description: "Safe math evaluation",
    icon: Calculator,
    defaultData: { label: "Calculator", nodeType: "tool", toolType: "calculator" },
    accent: accent.tools,
  },
  {
    type: "tool",
    label: "Web Search",
    category: "tools",
    description: "Google, EXA, DuckDuckGo",
    icon: Search,
    defaultData: { label: "Web Search", nodeType: "tool", toolType: "search", searchProvider: "google" },
    accent: accent.tools,
  },
  {
    type: "tool",
    label: "HTTP Request",
    category: "tools",
    description: "Call external APIs",
    icon: Globe,
    defaultData: {
      label: "HTTP Request",
      nodeType: "tool",
      toolType: "http",
      httpMethod: "GET",
      httpUrl: "https://httpbin.org/get",
    },
    accent: accent.tools,
    supportsExpressions: true,
    outputKind: "json",
  },
  {
    type: "integration",
    label: "Discord",
    category: "tools",
    description: "Post to Discord webhook",
    icon: MessageSquare,
    defaultData: {
      label: "Discord",
      nodeType: "integration",
      integrationType: "discord",
      integrationMessage: "{{last_output}}",
    },
    accent: accent.tools,
    supportsExpressions: true,
  },
  {
    type: "integration",
    label: "Slack",
    category: "tools",
    description: "Post to Slack webhook",
    icon: MessageSquare,
    defaultData: {
      label: "Slack",
      nodeType: "integration",
      integrationType: "slack",
      integrationMessage: "{{last_output}}",
    },
    accent: accent.tools,
    supportsExpressions: true,
  },
  {
    type: "integration",
    label: "Email",
    category: "tools",
    description: "Send email notification",
    icon: Mail,
    defaultData: {
      label: "Email",
      nodeType: "integration",
      integrationType: "email",
      integrationSubject: "Aegis workflow notification",
      integrationBody: "{{last_output}}",
    },
    accent: accent.tools,
    supportsExpressions: true,
  },
  {
    type: "integration",
    label: "Postgres",
    category: "tools",
    description: "Read-only SQL query",
    icon: Database,
    defaultData: {
      label: "Postgres",
      nodeType: "integration",
      integrationType: "postgres",
      integrationQuery: "SELECT 1 AS ok",
    },
    accent: accent.tools,
    supportsExpressions: true,
    outputKind: "json",
  },
  {
    type: "transform",
    label: "Transform",
    category: "data",
    description: "Map data with {{expressions}}",
    icon: Wand2,
    defaultData: { label: "Transform", nodeType: "transform", template: "{{input}}" },
    accent: accent.data,
    supportsExpressions: true,
  },
  {
    type: "set_fields",
    label: "Set Fields",
    category: "data",
    description: "Write fields into workflow context",
    icon: TableProperties,
    defaultData: {
      label: "Set Fields",
      nodeType: "set_fields",
      setFields: { summary: "{{steps.node_1.output}}" },
    },
    accent: accent.data,
    supportsExpressions: true,
    outputKind: "json",
  },
  {
    type: "json_parse",
    label: "JSON Parse",
    category: "data",
    description: "Parse & extract JSON fields",
    icon: Braces,
    defaultData: { label: "JSON Parse", nodeType: "json_parse", jsonPath: "" },
    accent: accent.data,
    outputKind: "json",
  },
  {
    type: "delay",
    label: "Delay",
    category: "data",
    description: "Pause before next step",
    icon: Clock,
    defaultData: { label: "Delay", nodeType: "delay", delaySeconds: 1 },
    accent: accent.data,
  },
  {
    type: "code",
    label: "Code",
    category: "data",
    description: "Sandboxed Python transform",
    icon: Code2,
    defaultData: {
      label: "Code",
      nodeType: "code",
      code: "result = last_output",
    },
    accent: accent.data,
  },
  {
    type: "memory_store",
    label: "Memory Store",
    category: "data",
    description: "Save a value to run memory",
    icon: Database,
    defaultData: {
      label: "Memory Store",
      nodeType: "memory_store",
      memoryNamespace: "default",
      memoryKey: "{{input.text}}",
      memoryValue: "{{last_output}}",
      memoryPersistent: true,
    },
    accent: accent.data,
    supportsExpressions: true,
  },
  {
    type: "memory_retrieve",
    label: "Memory Retrieve",
    category: "data",
    description: "Read a value from run memory",
    icon: Database,
    defaultData: {
      label: "Memory Retrieve",
      nodeType: "memory_retrieve",
      memoryNamespace: "default",
      memoryKey: "{{input.text}}",
    },
    accent: accent.data,
    supportsExpressions: true,
  },
  {
    type: "kb_retrieve",
    label: "KB Retrieve",
    category: "data",
    description: "Retrieve knowledge-base chunks for RAG",
    icon: BookOpen,
    defaultData: {
      label: "KB Retrieve",
      nodeType: "kb_retrieve",
      kbQuery: "{{input.query}}",
      kbTopK: 3,
      kbSource: "inline",
      kbMethod: "bm25",
      kbDocuments: [
        { id: "doc1", title: "Getting started", text: "Aegis is an agentic workflow builder." },
      ],
    },
    accent: accent.data,
    supportsExpressions: true,
  },
  {
    type: "evaluation",
    label: "Evaluation",
    category: "quality",
    description: "Score output quality",
    icon: Sparkles,
    defaultData: { label: "Evaluation", nodeType: "evaluation", criteria: "faithfulness and helpfulness" },
    accent: accent.quality,
  },
  {
    type: "guardrail",
    label: "Guardrail",
    category: "quality",
    description: "Validate input/output",
    icon: Shield,
    defaultData: { label: "Guardrail", nodeType: "guardrail", rules: { blocked_keywords: [], pattern: "" } },
    accent: accent.quality,
  },
  {
    type: "note",
    label: "Sticky Note",
    category: "annotate",
    description: "Canvas annotation only",
    icon: StickyNote,
    defaultData: { label: "Sticky Note", nodeType: "note", noteText: "Document your workflow here" },
    accent: accent.annotate,
  },
];

const registryByKey = new Map(
  NODE_REGISTRY.map((def) => [`${def.type}:${def.label}`, def])
);

/** Multi-variant tool/integration entries share a nodeType — disambiguate by the
 *  discriminator on the node data (toolType/integrationType) so renaming a node
 *  never selects the wrong variant's metadata. */
function variantKey(def: NodeDefinition): string | undefined {
  const dt = def.defaultData.toolType;
  if (dt) return `tool:${dt}`;
  const it = def.defaultData.integrationType;
  if (it) return `integration:${it}`;
  return undefined;
}

const registryByVariant = new Map<string, NodeDefinition>();
for (const def of NODE_REGISTRY) {
  const key = variantKey(def);
  if (key && !registryByVariant.has(key)) registryByVariant.set(key, def);
}

/**
 * Resolve a node's registry definition.
 *
 * Preferred call: pass the node data as the second argument — variants are
 * disambiguated by toolType/integrationType. A string `label` is still accepted
 * as a legacy fallback for external callers.
 */
/** Fold the co-located NODE_HELP entry (if any) onto a resolved definition so
 *  callers can read `def.help` / `def.docUrl` directly. */
function withHelp(def: NodeDefinition | undefined): NodeDefinition | undefined {
  if (!def) return def;
  const authored = NODE_HELP[def.type];
  if (!authored) return def;
  return { ...def, help: authored.help, docUrl: authored.docUrl };
}

export function getNodeDefinition(
  nodeType: string,
  labelOrData?: string | Pick<NodeData, "toolType" | "integrationType" | "label">
): NodeDefinition | undefined {
  if (labelOrData && typeof labelOrData === "object") {
    if (labelOrData.toolType) {
      const match = registryByVariant.get(`tool:${labelOrData.toolType}`);
      if (match) return withHelp(match);
    }
    if (labelOrData.integrationType) {
      const match = registryByVariant.get(`integration:${labelOrData.integrationType}`);
      if (match) return withHelp(match);
    }
    if (labelOrData.label) {
      const match = registryByKey.get(`${nodeType}:${labelOrData.label}`);
      if (match) return withHelp(match);
    }
  } else if (typeof labelOrData === "string") {
    const match = registryByKey.get(`${nodeType}:${labelOrData}`);
    if (match) return withHelp(match);
  }
  return withHelp(NODE_REGISTRY.find((def) => def.type === nodeType));
}

export function getNodesByCategory(category: NodeCategory): NodeDefinition[] {
  return NODE_REGISTRY.filter((def) => def.category === category);
}

export const EXPRESSION_HINT =
  "Use {{input.field}}, {{steps.node_id.output}}, {{input.user.email}}, or {{input.items.0.name}}.";

// ── Typed-port SOFT validation (Feature 3) ──────────────────────────────────
// The runtime stringifies every value between nodes, so these kinds NEVER block
// a connection — they only power a single, quiet heads-up when a clear mismatch
// (a list/JSON feeding a text-only consumer) would silently stringify.
//
// Defaults: a node with no `outputKind` is assumed to emit "text" (the common
// case: agents, transforms, routers, classifiers, delays, pass-through logic);
// a node with no `acceptsKind` accepts "any". Only summarizer/translator declare
// `acceptsKind: "text"` today, so warnings stay rare and high-signal.

/** Resolve a node's output kind, honoring tool/integration variants via data. */
export function resolveNodeOutputKind(
  nodeType: string,
  data?: Pick<NodeData, "toolType" | "integrationType" | "label">
): NodeOutputKind {
  const def = getNodeDefinition(nodeType, data);
  return def?.outputKind ?? "text";
}

/** Resolve what shape a node's target port accepts. */
export function resolveNodeAcceptsKind(
  nodeType: string,
  data?: Pick<NodeData, "toolType" | "integrationType" | "label">
): NodeAcceptsKind {
  const def = getNodeDefinition(nodeType, data);
  return def?.acceptsKind ?? "any";
}

const KIND_NOUN: Record<NodeOutputKind, string> = {
  text: "text",
  json: "JSON",
  list: "a list",
  none: "nothing",
};
const ACCEPTS_NOUN: Record<Exclude<NodeAcceptsKind, "any">, string> = {
  text: "text",
  json: "JSON",
};

/**
 * Returns a one-line warning when `out` is a clear mismatch for `accepts`, or
 * null when compatible. "any" and "none" never warn (nothing to stringify, or
 * the target is happy with anything).
 */
export function describeKindMismatch(
  sourceLabel: string,
  targetLabel: string,
  out: NodeOutputKind,
  accepts: NodeAcceptsKind
): string | null {
  if (accepts === "any" || out === "none" || out === accepts) return null;
  return `${sourceLabel} outputs ${KIND_NOUN[out]}; ${targetLabel} expects ${ACCEPTS_NOUN[accepts]} — it will be stringified`;
}

// ── Live config linting (Feature 4) ─────────────────────────────────────────
// Registry-driven "required config" rules, the single source for both the quiet
// node-card warning glyph and the inspector's per-issue hint list. Kept honest:
// only flag a field whose emptiness would clearly break (or no-op) the node. The
// `field` mirrors the structural-validation field name where they overlap, so
// callers can dedupe against getWorkflowValidationIssues.

export interface LintRule {
  /** Stable field id — matches workflow-validation field names where overlapping. */
  field: string;
  /** Short human noun for the "Missing: <label>" message. */
  label: string;
  /** True when this required field is missing/empty for the given node data. */
  missing: (data: NodeData) => boolean;
}

export interface LintIssue {
  field: string;
  message: string;
}

function isBlank(value: unknown): boolean {
  return typeof value !== "string" || value.trim().length === 0;
}

/** Whether a guardrail node has at least one enforceable rule/policy configured. */
function guardrailHasRule(data: NodeData): boolean {
  const r = data.rules;
  if (!r) return false;
  const type = r.guardrail_type || "rules";
  if (type === "llm" || type === "prompt_injection") return !isBlank(r.llm_instruction);
  if (type === "json_schema") return !isBlank(r.json_schema);
  if (type === "presidio") return true; // engine has sensible built-in entities
  if (type === "moderation") return true; // engine has built-in category thresholds
  // "rules" engine: any concrete constraint counts.
  return (
    (r.blocked_keywords?.length ?? 0) > 0 ||
    (r.required_keywords?.length ?? 0) > 0 ||
    (r.blocked_patterns?.length ?? 0) > 0 ||
    !isBlank(r.pattern) ||
    r.min_length != null ||
    r.max_length != null ||
    !!r.detect_pii
  );
}

const NODE_LINT_RULES: Partial<Record<NodeType, LintRule[]>> = {
  agent: [{ field: "instruction", label: "instruction", missing: (d) => isBlank(d.instruction) }],
  iteration: [
    { field: "itemsExpression", label: "items expression", missing: (d) => isBlank(d.itemsExpression) },
  ],
  kb_retrieve: [{ field: "kbQuery", label: "query", missing: (d) => isBlank(d.kbQuery) }],
  sub_workflow: [
    { field: "subWorkflowId", label: "target workflow", missing: (d) => isBlank(d.subWorkflowId) },
  ],
  tool: [
    // Only the HTTP variant needs a URL; calculator/search self-configure.
    { field: "httpUrl", label: "request URL", missing: (d) => d.toolType === "http" && isBlank(d.httpUrl) },
  ],
  integration: [
    { field: "credentialName", label: "credential", missing: (d) => isBlank(d.credentialName) },
    {
      field: "integrationQuery",
      label: "SQL query",
      missing: (d) => d.integrationType === "postgres" && isBlank(d.integrationQuery),
    },
  ],
  trigger: [
    {
      field: "scheduleCron",
      label: "cron schedule",
      missing: (d) => d.triggerType === "schedule" && isBlank(d.scheduleCron),
    },
  ],
  guardrail: [
    { field: "rules", label: "a rule or policy", missing: (d) => !guardrailHasRule(d) },
  ],
  classifier: [
    { field: "categories", label: "categories", missing: (d) => (d.categories?.length ?? 0) === 0 },
  ],
  router: [{ field: "routes", label: "routes", missing: (d) => (d.routes?.length ?? 0) === 0 }],
};

/**
 * Registry-driven config lint for a single node. Returns the missing-field
 * issues (empty when the node is well-configured). Both the node-card glyph and
 * the inspector hint list read from this; the status bar dedupes by `field`
 * against structural validation before appending.
 */
export function getNodeLintIssues(data: NodeData): LintIssue[] {
  const rules = NODE_LINT_RULES[data.nodeType];
  if (!rules) return [];
  const issues: LintIssue[] = [];
  for (const rule of rules) {
    if (rule.missing(data)) issues.push({ field: rule.field, message: `Missing: ${rule.label}` });
  }
  return issues;
}