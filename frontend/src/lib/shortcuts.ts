export interface ShortcutItem {
  keys: string[];
  description: string;
  context?: "global" | "canvas";
}

export const SHORTCUTS: ShortcutItem[] = [
  { keys: ["⌘", "K"], description: "Open command palette", context: "global" },
  { keys: ["?"], description: "Show keyboard shortcuts", context: "global" },
  { keys: ["⌘", "S"], description: "Save workflow", context: "canvas" },
  { keys: ["Delete"], description: "Delete selected node or edge", context: "canvas" },
  { keys: ["⌘", "D"], description: "Duplicate selected node", context: "canvas" },
  { keys: ["⌘", "C"], description: "Copy selected node", context: "canvas" },
  { keys: ["⌘", "V"], description: "Paste node", context: "canvas" },
  { keys: ["⌘", "Z"], description: "Undo", context: "canvas" },
  { keys: ["⇧", "⌘", "Z"], description: "Redo", context: "canvas" },
  { keys: ["Esc"], description: "Close dialogs and menus", context: "global" },
];

export function formatShortcutKeys(keys: string[]): string {
  const isMac =
    typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform);
  return keys
    .map((key) => (key === "⌘" ? (isMac ? "⌘" : "Ctrl") : key))
    .join(isMac && keys.includes("⌘") ? "" : " + ");
}

/** Single-key variant: maps ⌘ to the platform label for one chip. */
export function formatShortcutKey(key: string): string {
  if (key !== "⌘") return key;
  const isMac =
    typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform);
  return isMac ? "⌘" : "Ctrl";
}

export interface ShortcutSection {
  title: string;
  context: "global" | "canvas";
  items: ShortcutItem[];
}

/**
 * Grouped shortcut reference for the help dialog. Canvas bindings are audited
 * against WorkflowCanvas's keydown handler (⌘S/⌘C/⌘V/⌘D/⌘Z/⇧⌘Z/Delete) —
 * only bindings that actually exist are listed here.
 */
export const SHORTCUT_SECTIONS: ShortcutSection[] = [
  {
    title: "Global",
    context: "global",
    items: [
      { keys: ["⌘", "K"], description: "Open command palette" },
      { keys: ["N"], description: "New workflow" },
      { keys: ["?"], description: "Show keyboard shortcuts" },
      { keys: ["Esc"], description: "Close dialogs and menus" },
    ],
  },
  {
    title: "Canvas editing",
    context: "canvas",
    items: [
      { keys: ["⌘", "S"], description: "Save workflow" },
      { keys: ["⌘", "C"], description: "Copy selected node" },
      { keys: ["⌘", "V"], description: "Paste node" },
      { keys: ["⌘", "D"], description: "Duplicate selected node" },
      { keys: ["⌘", "Z"], description: "Undo" },
      { keys: ["⇧", "⌘", "Z"], description: "Redo" },
      { keys: ["Delete"], description: "Delete selected node or edge" },
    ],
  },
];

export function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName;
  return (
    tag === "INPUT" ||
    tag === "TEXTAREA" ||
    tag === "SELECT" ||
    target.isContentEditable
  );
}

const OVERLAY_SELECTOR =
  '[role="dialog"],[role="menu"],[role="listbox"],[role="alertdialog"],[data-radix-popper-content-wrapper]';

/**
 * True when the event target sits inside a Radix overlay (dialog, popover,
 * menu, listbox). Canvas global shortcuts bail on these so keys don't leak to
 * the canvas while focus rests on a button inside an overlay.
 */
export function isInOverlay(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return target.closest(OVERLAY_SELECTOR) !== null;
}