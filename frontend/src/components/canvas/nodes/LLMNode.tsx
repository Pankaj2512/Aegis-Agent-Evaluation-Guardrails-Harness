"use client";

import { type NodeProps } from "@xyflow/react";
import { Sparkles } from "lucide-react";
import type { NodeData } from "@/types/workflow";
import { BaseNode, NodeChipRow } from "./BaseNode";

// Hoisted so the icon element identity is stable across renders (BaseNode memo).
const ICON = <Sparkles className="h-3.5 w-3.5" />;

export function LLMNode(props: NodeProps) {
  const data = props.data as NodeData & { config?: { model?: string } };
  const model = data.config?.model;

  const chips: string[] = [];
  if (model) chips.push(model);
  if (data.summaryStyle) chips.push(data.summaryStyle);
  if (data.targetLanguage) chips.push(data.targetLanguage);
  if (data.searchProvider) chips.push(data.searchProvider);
  // Classifier renders here but branches on categories like router/switch —
  // surface a route count so its fan-out is legible on the canvas.
  if (data.nodeType === "classifier" && data.categories?.length) {
    chips.push(`${data.categories.length} categories`);
  }

  const footer = chips.length ? <NodeChipRow chips={chips} /> : null;
  return <BaseNode {...props} icon={ICON} footer={footer} />;
}
