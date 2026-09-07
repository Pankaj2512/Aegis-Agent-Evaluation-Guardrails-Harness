"use client";

import { type NodeProps } from "@xyflow/react";
import { GitBranch, Repeat } from "lucide-react";
import type { NodeData } from "@/types/workflow";
import { BaseNode, NodeChipRow } from "./BaseNode";

const BRANCH_ICON = <GitBranch className="h-3.5 w-3.5" />;
const LOOP_ICON = <Repeat className="h-3.5 w-3.5" />;

export function LogicNode(props: NodeProps) {
  const data = props.data as NodeData;

  const chips: string[] = [];
  if (data.ifCondition?.operator) chips.push(data.ifCondition.operator);
  if (data.filterCondition?.operator) chips.push(data.filterCondition.operator);
  if (data.switchCases?.length) chips.push(`${data.switchCases.length} cases`);
  if (data.routes?.length) chips.push(`${data.routes.length} routes`);
  if (data.nodeType === "iteration") {
    // e.g. "parallel · 25" — mode then item cap, mirroring existing chip density.
    chips.push(`${data.iterationMode ?? "sequential"} · ${data.maxItems ?? 25}`);
  }

  const icon = data.nodeType === "iteration" ? LOOP_ICON : BRANCH_ICON;
  const footer = chips.length ? <NodeChipRow chips={chips} /> : null;
  return <BaseNode {...props} icon={icon} footer={footer} />;
}
