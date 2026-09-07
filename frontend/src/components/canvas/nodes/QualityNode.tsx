"use client";

import { type NodeProps } from "@xyflow/react";
import { Shield } from "lucide-react";
import type { NodeData } from "@/types/workflow";
import { BaseNode, NodeChipRow } from "./BaseNode";

const ICON = <Shield className="h-3.5 w-3.5" />;

export function QualityNode(props: NodeProps) {
  const data = props.data as NodeData;

  const chips: string[] = [];
  if (data.evalType) chips.push(data.evalType);
  if (data.evalPreset) chips.push(String(data.evalPreset));
  if (data.rules?.guardrail_type) chips.push(data.rules.guardrail_type);
  if (data.rules?.fail_behavior) chips.push(data.rules.fail_behavior);

  const footer = chips.length ? <NodeChipRow chips={chips} /> : null;
  return <BaseNode {...props} icon={ICON} footer={footer} />;
}
