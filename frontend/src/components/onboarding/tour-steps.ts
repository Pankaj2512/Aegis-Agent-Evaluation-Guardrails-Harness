export interface TourStep {
  id: string;
  /** CSS selector for the anchor element; first VISIBLE match is used. */
  selector: string;
  title: string;
  body: string;
  placement: "top" | "bottom" | "left" | "right";
}

/**
 * Guided tour of the workflow canvas. Each anchor selector is verified against
 * the source that renders it — steps whose anchor is missing/hidden are skipped
 * at runtime (e.g. the panels tablist when the sidebar is collapsed).
 */
export const CANVAS_TOUR_STEPS: TourStep[] = [
  {
    // src/components/canvas/CanvasSidebar.tsx — role="tablist" aria-label="Workflow tools"
    id: "palette",
    selector: '[role="tablist"][aria-label="Workflow tools"]',
    title: "Node palette",
    body: "Browse triggers, agents, tools, and guardrails here. Drag a node onto the canvas to add it.",
    placement: "right",
  },
  {
    // src/components/canvas/WorkflowCanvas.tsx — .canvas-bg (the flow surface)
    id: "canvas",
    selector: ".canvas-bg",
    title: "The canvas",
    body: "Double-click empty canvas — or drag from a node handle — to quick-add and connect nodes.",
    placement: "top",
  },
  {
    // src/components/canvas/WorkflowCanvas.tsx — role="tablist" aria-label="Canvas panels" (hidden when collapsed → step skipped)
    id: "configure",
    selector: '[role="tablist"][aria-label="Canvas panels"]',
    title: "Configure & inspect",
    body: "Select a node to edit its settings, then check quality and knowledge from these panels.",
    placement: "left",
  },
  {
    // src/components/canvas/run/RunControl.tsx — aria-label="Run workflow" (two instances; the visible one is used)
    id: "run",
    selector: '[aria-label="Run workflow"]',
    title: "Run it",
    body: "Execute the workflow with sample input and watch each node light up as it runs.",
    placement: "bottom",
  },
  {
    // src/components/canvas/chrome/CanvasStatusBar.tsx — data-tour="status-bar" (added on root)
    id: "status",
    selector: '[data-tour="status-bar"]',
    title: "Status & validation",
    body: "Track node/edge counts, zoom, save state, and jump to any validation issues from here.",
    placement: "top",
  },
];
