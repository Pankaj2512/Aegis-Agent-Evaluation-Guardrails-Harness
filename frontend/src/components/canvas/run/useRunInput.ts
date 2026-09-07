"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import type { Node } from "@xyflow/react";
import type { NodeData } from "@/types/workflow";

export interface RunField {
  key: string;
  type: "string" | "number" | "boolean";
  required: boolean;
  defaultValue?: string;
}

interface StoredInput {
  values: Record<string, string>;
  freeText: string;
}

const STORAGE_PREFIX = "aegis:run-input:";

/**
 * The stored `inputFields` shape (verified against NodeInspector ~514-535 and
 * the node-registry default ~93-96) is an array of objects:
 *   { key: string; type?: "string" | "number" | "boolean"; default?: string; required?: boolean }
 * Older/hand-authored graphs may store bare strings, so we normalize both.
 */
function normalizeField(raw: unknown): RunField | null {
  if (typeof raw === "string") {
    const key = raw.trim();
    if (!key) return null;
    return { key, type: "string", required: false };
  }
  if (raw && typeof raw === "object") {
    const obj = raw as Record<string, unknown>;
    const key = typeof obj.key === "string" ? obj.key.trim() : "";
    if (!key) return null;
    const type =
      obj.type === "number" || obj.type === "boolean" || obj.type === "string"
        ? obj.type
        : "string";
    const defaultValue =
      obj.default === undefined || obj.default === null ? undefined : String(obj.default);
    return {
      key,
      type,
      required: obj.required === true,
      defaultValue,
    };
  }
  return null;
}

function deriveFields(nodes: Node[]): RunField[] {
  const schemaNode = nodes.find((n) => {
    const data = n.data as NodeData | undefined;
    return (
      data?.nodeType === "input_schema" &&
      Array.isArray(data.inputFields) &&
      data.inputFields.length > 0
    );
  });
  if (!schemaNode) return [];
  const raw = (schemaNode.data as NodeData).inputFields as unknown[];
  const seen = new Set<string>();
  const fields: RunField[] = [];
  for (const entry of raw) {
    const field = normalizeField(entry);
    if (field && !seen.has(field.key)) {
      seen.add(field.key);
      fields.push(field);
    }
  }
  return fields;
}

function readStored(workflowId: string): StoredInput {
  if (typeof window === "undefined") return { values: {}, freeText: "" };
  try {
    const raw = window.localStorage.getItem(`${STORAGE_PREFIX}${workflowId}`);
    if (!raw) return { values: {}, freeText: "" };
    const parsed = JSON.parse(raw) as Partial<StoredInput>;
    return {
      values:
        parsed.values && typeof parsed.values === "object"
          ? (parsed.values as Record<string, string>)
          : {},
      freeText: typeof parsed.freeText === "string" ? parsed.freeText : "",
    };
  } catch {
    return { values: {}, freeText: "" };
  }
}

function coerce(field: RunField, value: string): string | number | boolean {
  if (field.type === "number") {
    const num = Number(value);
    return Number.isFinite(num) && value.trim() !== "" ? num : value;
  }
  if (field.type === "boolean") {
    return value === "true";
  }
  return value;
}

export interface UseRunInputResult {
  fields: RunField[];
  values: Record<string, string>;
  setValue: (key: string, v: string) => void;
  freeText: string;
  setFreeText: (v: string) => void;
  composed: string;
  hasStored: boolean;
}

export function useRunInput(
  workflowId: string,
  nodes: Node[]
): UseRunInputResult {
  const fields = useMemo(() => deriveFields(nodes), [nodes]);

  const [values, setValues] = useState<Record<string, string>>({});
  const [freeText, setFreeTextState] = useState("");
  const [hasStored, setHasStored] = useState(false);

  // Hydrate from storage on mount / workflow change, then reconcile against
  // the current field set (drop stale keys, seed defaults for new ones).
  useEffect(() => {
    const stored = readStored(workflowId);
    const hadValues =
      Object.keys(stored.values).length > 0 || stored.freeText.trim().length > 0;
    setFreeTextState(stored.freeText);
    setValues(() => {
      if (fields.length === 0) return {};
      const next: Record<string, string> = {};
      for (const field of fields) {
        if (Object.prototype.hasOwnProperty.call(stored.values, field.key)) {
          next[field.key] = stored.values[field.key];
        } else if (field.defaultValue !== undefined) {
          next[field.key] = field.defaultValue;
        } else if (field.type === "boolean") {
          next[field.key] = "false";
        } else {
          next[field.key] = "";
        }
      }
      return next;
    });
    setHasStored(hadValues);
    // Re-run when the field identity changes so new fields pick up defaults.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workflowId, fields.map((f) => `${f.key}:${f.type}`).join("|")]);

  const persist = useCallback(
    (nextValues: Record<string, string>, nextFreeText: string) => {
      if (typeof window === "undefined") return;
      try {
        window.localStorage.setItem(
          `${STORAGE_PREFIX}${workflowId}`,
          JSON.stringify({ values: nextValues, freeText: nextFreeText })
        );
      } catch {
        /* storage unavailable — non-fatal */
      }
    },
    [workflowId]
  );

  const setValue = useCallback(
    (key: string, v: string) => {
      setValues((prev) => {
        const next = { ...prev, [key]: v };
        persist(next, freeText);
        return next;
      });
      setHasStored(true);
    },
    [freeText, persist]
  );

  const setFreeText = useCallback(
    (v: string) => {
      setFreeTextState(v);
      persist(values, v);
      if (v.trim().length > 0) setHasStored(true);
    },
    [values, persist]
  );

  const composed = useMemo(() => {
    if (fields.length === 0) return freeText;
    const record: Record<string, string | number | boolean> = {};
    for (const field of fields) {
      const raw = values[field.key] ?? field.defaultValue ?? "";
      const isEmpty = raw === "";
      // Skip empty optional fields; keep required even when empty.
      if (isEmpty && !field.required && field.type !== "boolean") continue;
      record[field.key] = coerce(field, raw);
    }
    return JSON.stringify(record);
  }, [fields, values, freeText]);

  return {
    fields,
    values,
    setValue,
    freeText,
    setFreeText,
    composed,
    hasStored,
  };
}
