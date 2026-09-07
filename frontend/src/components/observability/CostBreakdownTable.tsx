"use client";

import { useMemo } from "react";
import { cn } from "@/lib/utils";
import { formatCostUsd } from "@/lib/format";

type CellValue = string | number;

/** How the column footer summarizes its column across all rows. */
type AggregateKind = "sum" | "sumCost";

export interface CostBreakdownColumn {
  key: string;
  header: string;
  align?: "left" | "right";
  /** Braintrust-style footer aggregate. Omit for no footer total. */
  aggregate?: AggregateKind;
  /** Render non-zero numeric values in the destructive hue (e.g. failed). */
  status?: boolean;
}

export interface CostBreakdownRow {
  id: string;
  /** Optional category color var — drawn as a <=2px left rule only. */
  accentVar?: string;
  cells: Record<string, CellValue>;
}

interface CostBreakdownTableProps {
  columns: CostBreakdownColumn[];
  rows: CostBreakdownRow[];
  /** Accessible table name. */
  "aria-label": string;
  className?: string;
}

function formatCell(
  value: CellValue,
  col: CostBreakdownColumn
): { text: string; danger: boolean } {
  if (typeof value === "string") return { text: value, danger: false };
  if (col.aggregate === "sumCost") return { text: formatCostUsd(value), danger: false };
  const danger = Boolean(col.status) && value > 0;
  return { text: value.toLocaleString(), danger };
}

/**
 * Braintrust-style aggregate table: mono/tabular numeric columns, a hairline
 * header row, and a footer that sums the flagged columns. The only chroma is an
 * optional <=2px category rule per row and status hue on flagged non-zero cells.
 */
export function CostBreakdownTable({
  columns,
  rows,
  "aria-label": ariaLabel,
  className,
}: CostBreakdownTableProps) {
  const totals = useMemo(() => {
    const acc: Record<string, number> = {};
    for (const col of columns) {
      if (!col.aggregate) continue;
      acc[col.key] = rows.reduce((sum, row) => {
        const v = row.cells[col.key];
        return sum + (typeof v === "number" ? v : 0);
      }, 0);
    }
    return acc;
  }, [columns, rows]);

  const hasFooter = columns.some((c) => c.aggregate);
  const hasAccent = rows.some((r) => r.accentVar);

  /** The single slack-absorbing label column (everything else is numeric). */
  const nameKey = columns.find((c) => c.align !== "right")?.key;

  /**
   * Distinct workflows can share a display name, and identical rows are
   * indistinguishable — tag only the collisions with a short id so the common
   * case stays clean.
   */
  const duplicateNames = useMemo(() => {
    const counts = new Map<string, number>();
    if (!nameKey) return new Set<string>();
    for (const row of rows) {
      const value = row.cells[nameKey];
      if (typeof value !== "string") continue;
      counts.set(value, (counts.get(value) ?? 0) + 1);
    }
    return new Set(
      Array.from(counts.entries())
        .filter(([, n]) => n > 1)
        .map(([value]) => value)
    );
  }, [nameKey, rows]);

  if (rows.length === 0) {
    return (
      <p className="px-4 py-6 text-sm text-muted">No data in the selected window.</p>
    );
  }

  return (
    <div className={cn("overflow-x-auto", className)}>
      <table
        aria-label={ariaLabel}
        className="w-full border-collapse text-sm"
      >
        <thead>
          <tr className="border-b border-border">
            {hasAccent && <th className="w-0.5 p-0" aria-hidden />}
            {columns.map((col) => (
              <th
                key={col.key}
                scope="col"
                className={cn(
                  "px-4 py-2 font-mono text-2xs font-medium uppercase tracking-wide text-subtle",
                  col.align === "right" ? "text-right" : "text-left",
                  // Absorb the table's slack so the label cell can actually
                  // ellipsize instead of forcing whole-table horizontal scroll.
                  col.key === nameKey && "w-full max-w-0"
                )}
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {rows.map((row) => (
            <tr key={row.id} className="transition-colors duration-fast hover:bg-surface-hover">
              {hasAccent && (
                <td className="w-0.5 p-0">
                  {row.accentVar && (
                    <span
                      className="block h-full w-0.5"
                      style={{ backgroundColor: row.accentVar }}
                      aria-hidden
                    />
                  )}
                </td>
              )}
              {columns.map((col) => {
                const { text, danger } = formatCell(row.cells[col.key], col);
                const isName = col.align !== "right";
                const showId = col.key === nameKey && duplicateNames.has(text);
                return (
                  <td
                    key={col.key}
                    className={cn(
                      "px-4 py-2",
                      col.align === "right"
                        ? "text-right font-mono tabular-nums"
                        : "text-left",
                      col.key === nameKey && "w-full max-w-0",
                      isName ? "text-foreground" : "text-muted",
                      danger && "text-destructive"
                    )}
                  >
                    {isName ? (
                      <span className="flex min-w-0 items-baseline gap-1.5">
                        <span className="truncate font-medium">{text}</span>
                        {showId && (
                          <span
                            className="shrink-0 font-mono text-2xs tabular-nums text-subtle"
                            title={row.id}
                          >
                            {row.id.slice(0, 8)}
                          </span>
                        )}
                      </span>
                    ) : (
                      text
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
        {hasFooter && (
          <tfoot>
            <tr className="border-t border-border bg-surface-input/40">
              {hasAccent && <td className="w-0.5 p-0" aria-hidden />}
              {columns.map((col, idx) => {
                const isFirst = idx === 0;
                if (!col.aggregate) {
                  return (
                    <td
                      key={col.key}
                      className={cn(
                        "px-4 py-2 font-mono text-2xs uppercase tracking-wide text-subtle",
                        col.align === "right" ? "text-right" : "text-left",
                        col.key === nameKey && "w-full max-w-0"
                      )}
                    >
                      {isFirst ? "Total" : ""}
                    </td>
                  );
                }
                const total = totals[col.key] ?? 0;
                const text =
                  col.aggregate === "sumCost"
                    ? formatCostUsd(total)
                    : total.toLocaleString();
                return (
                  <td
                    key={col.key}
                    className="px-4 py-2 text-right font-mono tabular-nums font-semibold text-foreground"
                  >
                    {text}
                  </td>
                );
              })}
            </tr>
          </tfoot>
        )}
      </table>
    </div>
  );
}
