"use client";

import { useEffect, useState } from "react";
import { Bookmark } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

interface SnippetNameDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Node count in the selection being saved (for the description copy). */
  nodeCount: number;
  onConfirm: (name: string) => void;
}

/**
 * Minimal name prompt for saving a canvas selection as a snippet. Uses the house
 * Dialog primitives (mirrors ConfirmDialog's shell), with a single text field.
 */
export function SnippetNameDialog({
  open,
  onOpenChange,
  nodeCount,
  onConfirm,
}: SnippetNameDialogProps) {
  const [name, setName] = useState("");

  // Reset the field each time the dialog opens.
  useEffect(() => {
    if (open) setName("");
  }, [open]);

  const submit = () => {
    const trimmed = name.trim();
    if (!trimmed) return;
    onConfirm(trimmed);
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-1 pr-8">
          <span
            className="row-span-2 flex size-10 items-center justify-center rounded-lg border border-primary/25 bg-primary-muted text-primary"
            aria-hidden="true"
          >
            <Bookmark className="size-5" />
          </span>
          <DialogTitle>Save as snippet</DialogTitle>
          <DialogDescription className="col-start-2">
            Save {nodeCount} node{nodeCount === 1 ? "" : "s"} as a reusable snippet, insertable
            from the add-node menu. Snippets stay on this browser.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-2">
          <Label htmlFor="snippet-name">Name</Label>
          <Input
            id="snippet-name"
            autoFocus
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                submit();
              }
            }}
            placeholder="e.g. RAG retrieval + guardrail"
          />
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={!name.trim()}>
            Save snippet
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
