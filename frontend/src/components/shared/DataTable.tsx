/**
 * DataTable — generic table for displaying backend data.
 * Shows a loading skeleton, empty state, and error state.
 */

import { cn } from "@/lib/utils";
import { Loader2, AlertCircle, Inbox } from "lucide-react";

export interface Column<T> {
  key: keyof T | string;
  header: string;
  render?: (row: T) => React.ReactNode;
  className?: string;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  data: T[] | undefined;
  isLoading?: boolean;
  error?: Error | null;
  emptyMessage?: string;
  keyField?: keyof T;
  className?: string;
}

export function DataTable<T extends Record<string, unknown>>({
  columns,
  data,
  isLoading,
  error,
  emptyMessage = "No data available",
  keyField,
  className,
}: DataTableProps<T>) {
  return (
    <div className={cn("overflow-x-auto", className)}>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-white/[0.06]">
            {columns.map((col) => (
              <th
                key={String(col.key)}
                className={cn(
                  "text-left px-4 py-3 text-text-muted font-medium text-xs uppercase tracking-wider",
                  col.className
                )}
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>

        <tbody>
          {isLoading && (
            <tr>
              <td colSpan={columns.length} className="px-4 py-12 text-center">
                <div className="flex items-center justify-center gap-2 text-text-muted">
                  <Loader2 size={16} className="animate-spin" />
                  <span>Loading…</span>
                </div>
              </td>
            </tr>
          )}

          {!isLoading && error && (
            <tr>
              <td colSpan={columns.length} className="px-4 py-12 text-center">
                <div className="flex items-center justify-center gap-2 text-status-failed">
                  <AlertCircle size={16} />
                  <span>Backend unavailable — {error.message}</span>
                </div>
              </td>
            </tr>
          )}

          {!isLoading && !error && (!data || data.length === 0) && (
            <tr>
              <td colSpan={columns.length} className="px-4 py-12 text-center">
                <div className="flex items-center justify-center gap-2 text-text-muted">
                  <Inbox size={16} />
                  <span>{emptyMessage}</span>
                </div>
              </td>
            </tr>
          )}

          {!isLoading && !error && data?.map((row, i) => (
            <tr
              key={keyField ? String(row[keyField]) : i}
              className="border-b border-white/[0.04] hover:bg-white/[0.02] transition-colors"
            >
              {columns.map((col) => (
                <td
                  key={String(col.key)}
                  className={cn("px-4 py-3 text-text-primary", col.className)}
                >
                  {col.render
                    ? col.render(row)
                    : String(row[col.key as keyof T] ?? "—")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
