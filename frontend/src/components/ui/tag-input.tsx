"use client";

import { useState } from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

interface TagInputProps {
  id?: string;
  values: string[];
  onChange: (values: string[]) => void;
  placeholder?: string;
  /** Order is preserved — some consumers (routes, cases) are order-sensitive. */
  className?: string;
  "aria-label"?: string;
}

/** Chip editor for string lists: Enter/comma adds, Backspace on empty
 *  removes the last, pasting a comma-separated list splits it. */
export function TagInput({
  id,
  values,
  onChange,
  placeholder,
  className,
  "aria-label": ariaLabel,
}: TagInputProps) {
  const [draft, setDraft] = useState("");

  const commit = (raw: string) => {
    const parts = raw
      .split(",")
      .map((part) => part.trim())
      .filter(Boolean)
      .filter((part) => !values.includes(part));
    if (parts.length > 0) onChange([...values, ...parts]);
    setDraft("");
  };

  return (
    <div
      className={cn(
        "flex min-h-10 flex-wrap items-center gap-1.5 rounded-lg border border-border bg-surface-input px-2 py-1.5",
        "focus-within:border-border-strong",
        className
      )}
    >
      {values.map((value, index) => (
        <span
          key={`${value}-${index}`}
          className="inline-flex items-center gap-1 rounded border border-border bg-surface px-1.5 py-0.5 font-mono text-xs text-foreground"
        >
          {value}
          <button
            type="button"
            aria-label={`Remove ${value}`}
            className="focus-ring rounded text-muted transition-colors hover:text-destructive"
            onClick={() => onChange(values.filter((_, i) => i !== index))}
          >
            <X className="h-3 w-3" />
          </button>
        </span>
      ))}
      <input
        id={id}
        aria-label={ariaLabel}
        value={draft}
        onChange={(e) => {
          const value = e.target.value;
          if (value.includes(",")) commit(value);
          else setDraft(value);
        }}
        onKeyDown={(e) => {
          // IME composition (e.g. Japanese/Chinese): Enter confirms a candidate
          // and must not also commit the tag.
          if (e.nativeEvent.isComposing || e.key === "Process") return;
          if (e.key === "Enter") {
            e.preventDefault();
            commit(draft);
          } else if (e.key === "Backspace" && draft === "" && values.length > 0) {
            onChange(values.slice(0, -1));
          }
        }}
        onBlur={() => {
          if (draft.trim()) commit(draft);
        }}
        placeholder={values.length === 0 ? placeholder : undefined}
        className="min-w-[80px] flex-1 bg-transparent text-sm text-foreground outline-none placeholder:text-subtle"
      />
    </div>
  );
}
