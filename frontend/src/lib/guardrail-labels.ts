import type { GuardrailType } from "@/types/workflow";

/**
 * One name per guardrail rail. Five surfaces used to carry their own map and
 * the vocabulary had drifted (the same rail was "rules", "Rules", "keyword
 * rules", and "Rule-based (keywords, regex, PII)" depending on the screen, and
 * json_schema was missing entirely so the raw enum leaked into the Trust
 * dashboard). Short labels for chips, rows, and selects.
 */
export const GUARDRAIL_TYPE_LABELS: Record<GuardrailType, string> = {
  rules: "Keyword rules",
  presidio: "PII scan",
  prompt_injection: "Prompt injection",
  moderation: "Moderation",
  llm: "LLM classifier",
  json_schema: "Structured output",
};

/**
 * Long-form copy for the canvas NodeInspector engine select, where the operator
 * is picking an engine and needs the implementation detail. Each entry is a
 * complete option label — `${GUARDRAIL_TYPE_LABELS[t]} (detail)` — so render it
 * on its own; do not concatenate it with the short label.
 */
export const GUARDRAIL_TYPE_HINTS: Record<GuardrailType, string> = {
  rules: "Keyword rules (keywords, regex, PII)",
  presidio: "PII scan (Presidio entity detection)",
  prompt_injection: "Prompt injection (Gemini shield)",
  moderation: "Moderation (toxicity, hate, violence…)",
  llm: "LLM classifier (Gemini policy check)",
  json_schema: "Structured output (JSON schema + re-ask)",
};

/** Labels an unknown/legacy rail token without leaking the raw enum. */
export function guardrailTypeLabel(type: string | null | undefined): string {
  if (!type) return "Guardrail";
  return GUARDRAIL_TYPE_LABELS[type as GuardrailType] ?? type.replace(/_/g, " ");
}
