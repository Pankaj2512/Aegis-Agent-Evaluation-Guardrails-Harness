"use client";

import { type NodeProps } from "@xyflow/react";
import { Workflow } from "lucide-react";
import type { NodeData } from "@/types/workflow";
import { BaseNode, NodeChipRow } from "./BaseNode";

const ICON = <Workflow className="h-3.5 w-3.5" />;

export function FlowNode(props: NodeProps) {
  const data = props.data as NodeData;

  const chips: string[] = [];
  if (data.delaySeconds != null) chips.push(`${data.delaySeconds}s`);

  const footer = chips.length ? <NodeChipRow chips={chips} /> : null;
  return <BaseNode {...props} icon={ICON} footer={footer} />;
}
