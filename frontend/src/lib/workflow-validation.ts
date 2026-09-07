import type { Node } from "@xyflow/react";
import type { NodeData } from "@/types/workflow";

export interface WorkflowFieldIssue {
  nodeId: string;
  nodeLabel: string;
  field: string;
  message: string;
}

/** Validate a 5-field cron expression (minute hour dom month dow). */
export function isValidCronExpression(expr: string): boolean {
  const parts = expr.trim().split(/\s+/);
  if (parts.length !== 5) return false;

  const isField = (part: string, min: number, max: number): boolean => {
    // Allow *, ranges, lists, steps — e.g. *, */5, 1-5, 1,15, 0-30/5
    const segments = part.split(",");
    for (const seg of segments) {
      if (!seg) return false;
      const [rangePart, stepPart] = seg.split("/");
      if (stepPart !== undefined) {
        if (!/^\d+$/.test(stepPart)) return false;
        const step = Number(stepPart);
        if (!Number.isFinite(step) || step < 1) return false;
      }
      if (rangePart === "*") continue;
      const [lo, hi] = rangePart.split("-");
      if (hi !== undefined) {
        if (!/^\d+$/.test(lo) || !/^\d+$/.test(hi)) return false;
        const a = Number(lo);
        const b = Number(hi);
        if (a < min || b > max || a > b) return false;
      } else {
        if (!/^\d+$/.test(rangePart)) return false;
        const n = Number(rangePart);
        if (n < min || n > max) return false;
      }
    }
    return true;
  };

  const [minute, hour, dom, month, dow] = parts;
  return (
    isField(minute, 0, 59) &&
    isField(hour, 0, 23) &&
    isField(dom, 1, 31) &&
    isField(month, 1, 12) &&
    isField(dow, 0, 7) // 0 and 7 both Sunday in common cron dialects
  );
}

export function getWorkflowValidationIssues(nodes: Node[]): WorkflowFieldIssue[] {
  const issues: WorkflowFieldIssue[] = [];

  for (const node of nodes) {
    const data = node.data as NodeData;
    const label = data.label?.trim() || node.id;

    if (data.nodeType === "agent" && !data.instruction?.trim()) {
      issues.push({
        nodeId: node.id,
        nodeLabel: label,
        field: "instruction",
        message: "Instruction is required",
      });
    }

    if (data.nodeType === "trigger" && data.triggerType === "schedule") {
      const cron = data.scheduleCron?.trim() ?? "";
      if (!cron) {
        issues.push({
          nodeId: node.id,
          nodeLabel: label,
          field: "scheduleCron",
          message: "Cron expression is required for scheduled triggers",
        });
      } else if (!isValidCronExpression(cron)) {
        issues.push({
          nodeId: node.id,
          nodeLabel: label,
          field: "scheduleCron",
          message: "Cron expression is invalid (expected 5 fields: min hour dom month dow)",
        });
      }
    }

    if (data.nodeType === "tool" && data.toolType === "http" && !data.httpUrl?.trim()) {
      issues.push({
        nodeId: node.id,
        nodeLabel: label,
        field: "httpUrl",
        message: "Request URL is required",
      });
    }

    if (data.nodeType === "integration") {
      if (!data.credentialName?.trim()) {
        issues.push({
          nodeId: node.id,
          nodeLabel: label,
          field: "credentialName",
          message: "Credential is required",
        });
      }
      if (data.integrationType === "postgres" && !data.integrationQuery?.trim()) {
        issues.push({
          nodeId: node.id,
          nodeLabel: label,
          field: "integrationQuery",
          message: "SQL query is required",
        });
      }
    }
  }

  return issues;
}

export function formatValidationToast(issues: WorkflowFieldIssue[]): string {
  const first = issues[0];
  const nodeTypeLabel =
    first.field === "instruction"
      ? "Agent"
      : first.field === "scheduleCron"
        ? "Schedule trigger"
        : first.field === "credentialName"
          ? "Integration"
          : first.field === "httpUrl"
            ? "HTTP Request"
            : "Node";
  return `${nodeTypeLabel} node '${first.nodeLabel}' is missing required fields`;
}