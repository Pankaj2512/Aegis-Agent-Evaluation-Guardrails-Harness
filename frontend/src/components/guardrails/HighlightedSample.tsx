import { Fragment } from "react";
import type { GuardrailType } from "@/types/workflow";
import { Badge } from "@/components/ui/badge";

/**
 * Email/phone regexes mirrored from backend PII_PATTERNS.
 * See backend/app/services/guardrail.py:11-14.
 */
const PII_PATTERNS = {
  email: /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g,
  phone: /(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}/g,
};

/** Message prefix emitted by Presidio. See backend/app/services/guardrail_presidio.py:84. */
const PRESIDIO_PREFIX = "Presidio detected PII entities:";

export interface MatchSpan {
  start: number;
  end: number;
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/**
 * Replicate the backend keyword match exactly: case-insensitive whole-word
 * test per keyword, collecting every occurrence. Mirrors
 * backend/app/services/guardrail.py:validate_content, which blocks on
 * `re.search(rf"\b{re.escape(kw)}\b", lowered)` per lowercased keyword.
 */
export function findKeywordMatches(text: string, keywords: string[]): MatchSpan[] {
  const spans: MatchSpan[] = [];
  for (const raw of keywords) {
    const keyword = raw.trim();
    if (!keyword) continue;
    const regex = new RegExp(`\\b${escapeRegExp(keyword)}\\b`, "gi");
    let m: RegExpExecArray | null;
    while ((m = regex.exec(text)) !== null) {
      if (m[0].length === 0) {
        regex.lastIndex += 1;
        continue;
      }
      spans.push({ start: m.index, end: m.index + m[0].length });
    }
  }
  return mergeSpans(spans);
}

/** Approximate PII highlighting using the mirrored email/phone regexes. */
function findPiiMatches(text: string): MatchSpan[] {
  const spans: MatchSpan[] = [];
  for (const regex of Object.values(PII_PATTERNS)) {
    regex.lastIndex = 0;
    let m: RegExpExecArray | null;
    while ((m = regex.exec(text)) !== null) {
      if (m[0].length === 0) {
        regex.lastIndex += 1;
        continue;
      }
      spans.push({ start: m.index, end: m.index + m[0].length });
    }
  }
  return mergeSpans(spans);
}

function mergeSpans(spans: MatchSpan[]): MatchSpan[] {
  if (spans.length === 0) return [];
  const sorted = [...spans].sort((a, b) => a.start - b.start || a.end - b.end);
  const merged: MatchSpan[] = [sorted[0]];
  for (let i = 1; i < sorted.length; i += 1) {
    const last = merged[merged.length - 1];
    const cur = sorted[i];
    if (cur.start <= last.end) {
      last.end = Math.max(last.end, cur.end);
    } else {
      merged.push(cur);
    }
  }
  return merged;
}

function renderHighlighted(text: string, spans: MatchSpan[]) {
  if (spans.length === 0) {
    return <span>{text}</span>;
  }
  const parts: React.ReactNode[] = [];
  let cursor = 0;
  spans.forEach((span, i) => {
    if (span.start > cursor) {
      parts.push(<Fragment key={`t-${i}`}>{text.slice(cursor, span.start)}</Fragment>);
    }
    parts.push(
      <mark
        key={`m-${i}`}
        className="rounded bg-destructive/20 px-0.5 text-destructive"
      >
        {text.slice(span.start, span.end)}
      </mark>
    );
    cursor = span.end;
  });
  if (cursor < text.length) {
    parts.push(<Fragment key="t-last">{text.slice(cursor)}</Fragment>);
  }
  return parts;
}

interface HighlightedSampleProps {
  text: string;
  guardrailType: GuardrailType;
  keywords: string[];
  /** Result message — used to pull Presidio entity labels when present. */
  message?: string;
}

/**
 * Read-only re-render of the failing sample with matched substrings marked.
 * - rules: exact keyword highlighting (parity with backend).
 * - presidio: approximate regex highlighting, visibly labeled; entity chips
 *   when the message carries the known Presidio prefix.
 * - prompt_injection / llm: no highlighting (verdict only) — returns null.
 */
export function HighlightedSample({
  text,
  guardrailType,
  keywords,
  message,
}: HighlightedSampleProps) {
  if (guardrailType === "prompt_injection" || guardrailType === "llm") {
    return null;
  }

  const isPresidio = guardrailType === "presidio";
  const spans = isPresidio ? findPiiMatches(text) : findKeywordMatches(text, keywords);

  const entityLabels =
    isPresidio && message?.startsWith(PRESIDIO_PREFIX)
      ? message
          .slice(PRESIDIO_PREFIX.length)
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean)
      : [];

  if (spans.length === 0 && entityLabels.length === 0) {
    return null;
  }

  return (
    <div className="space-y-2 rounded-md border border-border bg-surface-input p-3">
      <div className="flex flex-wrap items-center gap-2">
        <p className="text-micro">
          Matched in sample
        </p>
        {isPresidio && (
          <span className="font-mono text-2xs text-subtle">(approximate)</span>
        )}
      </div>
      {entityLabels.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {entityLabels.map((label) => (
            <Badge key={label} variant="destructive" className="font-mono text-2xs">
              {label}
            </Badge>
          ))}
        </div>
      )}
      {spans.length > 0 && (
        <p className="whitespace-pre-wrap break-words font-mono text-xs leading-5 text-foreground">
          {renderHighlighted(text, spans)}
        </p>
      )}
    </div>
  );
}
