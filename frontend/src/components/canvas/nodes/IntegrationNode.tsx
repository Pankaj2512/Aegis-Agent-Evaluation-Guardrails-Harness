"use client";

import { type NodeProps } from "@xyflow/react";
import { Plug } from "lucide-react";
import type { NodeData } from "@/types/workflow";
import { BaseNode, NodeChipRow } from "./BaseNode";

const ICON = <Plug className="h-3.5 w-3.5" />;

export function IntegrationNode(props: NodeProps) {
  const data = props.data as NodeData;

  const chips: string[] = [];
  if (data.integrationType) chips.push(data.integrationType);
  if (data.credentialName) chips.push(data.credentialName);

  const footer = chips.length ? <NodeChipRow chips={chips} /> : null;
  return <BaseNode {...props} icon={ICON} footer={footer} />;
}
