"use client";

import { type NodeProps } from "@xyflow/react";
import { Database } from "lucide-react";
import type { NodeData } from "@/types/workflow";
import { BaseNode, NodeChipRow } from "./BaseNode";

const ICON = <Database className="h-3.5 w-3.5" />;

export function DataNode(props: NodeProps) {
  const data = props.data as NodeData;

  const chips: string[] = [];
  if (data.toolType) chips.push(data.toolType);
  if (data.httpMethod) chips.push(data.httpMethod);
  if (data.memoryNamespace) chips.push(data.memoryNamespace);
  if (data.kbMethod) chips.push(data.kbMethod);

  const footer = chips.length ? <NodeChipRow chips={chips} /> : null;
  return <BaseNode {...props} icon={ICON} footer={footer} />;
}
