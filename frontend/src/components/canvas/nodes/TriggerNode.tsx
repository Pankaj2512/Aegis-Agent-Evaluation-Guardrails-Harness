"use client";

import { type NodeProps } from "@xyflow/react";
import { Zap } from "lucide-react";
import type { NodeData } from "@/types/workflow";
import { BaseNode, NodeChipRow } from "./BaseNode";

const ICON = <Zap className="h-3.5 w-3.5" />;

export function TriggerNode(props: NodeProps) {
  const data = props.data as NodeData;

  const chips: string[] = [];
  if (data.triggerType) chips.push(data.triggerType);
  if (data.scheduleCron) chips.push(data.scheduleCron);

  const footer = chips.length ? <NodeChipRow chips={chips} /> : null;
  return <BaseNode {...props} icon={ICON} footer={footer} />;
}
