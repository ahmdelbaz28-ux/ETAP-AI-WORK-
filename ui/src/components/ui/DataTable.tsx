import { ArrowDown, ArrowUp, ArrowUpDown, ChevronLeft, ChevronRight, Search } from "lucide-react";
import { type ReactNode, useMemo, useState } from "react";
import { cn } from "../../utils/helpers";
import { Button } from "./Button";
import { Checkbox } from "./Checkbox";

// ─── Types ──────────────────────────────────────────────────────────
export type SortDirection = "asc" | "desc" | null;

export interface Column<T> {
  readonly key: string;
  readonly label: string;
  readonly sortable?: boolean;
  readonly width?: string;
  readonly align?: "left" | "center" | "right";
  readonly render?: (row: T, index: number) => ReactNode;
}

export interface DataTableProps<T> {
  readonly data: T[];
  readonly columns: Column<T>[];
  readonly keyExtractor: (row: T, index: number) => string | number;
  readonly loading?: boolean;
  readonly emptyState?: ReactNode;
  readonly selectable?: boolean;
  readonly selectedKeys?: Set<string | number>;
  readonly onSelectionChange?: (keys: Set<string | number>) => void;
  readonly pageSize?: number;
  readonly className?: string;
}

// ─── Component ──────────────────────────────────────────────────────
export function DataTable<T>({
  data,
  columns,
  keyExtractor,
  loading = false,
  emptyState,
  selectable = false,
  selectedKeys = new Set(),
  onSelectionChange,
  pageSize = 25,
  className,
}: DataTableProps<T>) {
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<SortDirection>(null);
  const [search, setSearch] = useState("");
  const [currentPage, setCurrentPage] = useState(1);

  const handleSort = (key: string) => {
    if (sortKey === key) {
      if (sortDir === "asc") setSortDir("desc");
      else if (sortDir === "desc") {
        setSortKey(null);
        setSortDir(null);
      } else setSortDir("asc");
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
  };

  const processed = useMemo(() => {
    let result = [...data];
    if (search.trim()) {
      const q = search.toLowerCase();
      result = result.filter((row) =>
        columns.some((col) => {
          const val = (row as Record<string, unknown>)[col.key];
          return String(val ?? "")
            .toLowerCase()
            .includes(q);
        }),
      );
    }
    if (sortKey && sortDir) {
      result.sort((a, b) => {
        const av = (a as Record<string, unknown>)[sortKey];
        const bv = (b as Record<string, unknown>)[sortKey];
        const aStr = String(av ?? "");
        const bStr = String(bv ?? "");
        const cmp = aStr.localeCompare(bStr, undefined, { numeric: true });
        return sortDir === "asc" ? cmp : -cmp;
      });
    }
    return result;
  }, [data, search, sortKey, sortDir, columns]);

  const totalPages = Math.max(1, Math.ceil(processed.length / pageSize));
  const safePage = Math.min(currentPage, totalPages);
  const paged = processed.slice((safePage - 1) * pageSize, safePage * pageSize);

  const allOnPageSelected =
    selectable && paged.length > 0 && paged.every((r) => selectedKeys.has(keyExtractor(r, 0)));

  const toggleAll = () => {
    if (!onSelectionChange) return;
    const next = new Set(selectedKeys);
    if (allOnPageSelected) {
      for (const r of paged) next.delete(keyExtractor(r, 0));
    } else {
      for (const r of paged) next.add(keyExtractor(r, 0));
    }
    onSelectionChange(next);
  };

  const toggleOne = (key: string | number) => {
    if (!onSelectionChange) return;
    const next = new Set(selectedKeys);
    next.has(key) ? next.delete(key) : next.add(key);
    onSelectionChange(next);
  };

  const SortIcon = ({ colKey }: { colKey: string }) => {
    if (sortKey !== colKey || !sortDir) return <ArrowUpDown className="w-3.5 h-3.5 opacity-40" />;
    return sortDir === "asc" ? (
      <ArrowUp className="w-3.5 h-3.5 text-[var(--color-brand-500)]" />
    ) : (
      <ArrowDown className="w-3.5 h-3.5 text-[var(--color-brand-500)]" />
    );
  };

  return (
    <div className={cn("space-y-3", className)}>
      {/* Search */}
      <div className="flex items-center gap-2">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-muted)]" />
          <input
            type="text"
            placeholder="Search..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setCurrentPage(1);
            }}
            className="w-full rounded-lg border border-[var(--border-primary)] bg-[var(--bg-input)] pl-9 pr-3 py-1.5 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--color-brand-500)]"
          />
        </div>
      </div>

      {/* Table */}
      <div className="rounded-xl border border-[var(--border-primary)] overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-[var(--bg-elevated)] border-b border-[var(--border-primary)]">
                {selectable && (
                  <th className="w-10 px-3 py-2.5">
                    <Checkbox
                      checked={allOnPageSelected}
                      ref={undefined as never}
                      onChange={() => toggleAll()}
                      aria-label="Select all"
                    />
                  </th>
                )}
                {columns.map((col) => (
                  <th
                    key={col.key}
                    scope="col"
                    tabIndex={col.sortable !== false ? 0 : undefined}
                    className={cn(
                      "px-3 py-2.5 text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider",
                      col.align === "center" && "text-center",
                      col.align === "right" && "text-right",
                      col.sortable !== false &&
                        "cursor-pointer select-none hover:text-[var(--text-secondary)]",
                    )}
                    style={{ width: col.width }}
                    onClick={() => col.sortable !== false && handleSort(col.key)}
                    onKeyDown={(e) => {
                      if (col.sortable !== false && (e.key === "Enter" || e.key === " ")) {
                        e.preventDefault();
                        handleSort(col.key);
                      }
                    }}
                  >
                    <span className="inline-flex items-center gap-1.5">
                      {col.label}
                      {col.sortable !== false && <SortIcon colKey={col.key} />}
                    </span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border-primary)]">
              {loading ? (
                <tr>
                  <td
                    colSpan={columns.length + (selectable ? 1 : 0)}
                    className="px-3 py-8 text-center text-xs text-[var(--text-muted)]"
                  >
                    Loading...
                  </td>
                </tr>
              ) : paged.length === 0 ? (
                <tr>
                  <td colSpan={columns.length + (selectable ? 1 : 0)} className="px-3 py-8">
                    {emptyState || (
                      <p className="text-center text-xs text-[var(--text-muted)]">No data found</p>
                    )}
                  </td>
                </tr>
              ) : (
                paged.map((row, i) => {
                  const key = keyExtractor(row, i);
                  const isSelected = selectedKeys.has(key);
                  return (
                    <tr
                      key={key}
                      className={cn(
                        "transition-colors duration-100",
                        isSelected
                          ? "bg-[var(--color-brand-500)]/5 border-l-2 border-l-[var(--color-brand-500)]"
                          : "hover:bg-[var(--bg-elevated)]/50",
                      )}
                    >
                      {selectable && (
                        <td className="px-3 py-2">
                          <Checkbox
                            checked={isSelected}
                            onChange={() => toggleOne(key)}
                            aria-label={`Select row ${i + 1}`}
                          />
                        </td>
                      )}
                      {columns.map((col) => (
                        <td
                          key={col.key}
                          className={cn(
                            "px-3 py-2.5 text-[var(--text-secondary)]",
                            col.align === "center" && "text-center",
                            col.align === "right" && "text-right",
                          )}
                        >
                          {col.render
                            ? col.render(row, i)
                            : String((row as Record<string, unknown>)[col.key] ?? "")}
                        </td>
                      ))}
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <span className="text-xs text-[var(--text-muted)]">
            {(safePage - 1) * pageSize + 1}–{Math.min(safePage * pageSize, processed.length)} of{" "}
            {processed.length}
          </span>
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="sm"
              icon={ChevronLeft}
              disabled={safePage <= 1}
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
            />
            {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
              let page: number;
              if (totalPages <= 7) page = i + 1;
              else if (safePage <= 3) page = i + 1;
              else if (safePage >= totalPages - 2) page = totalPages - 6 + i;
              else page = safePage - 3 + i;
              return (
                <Button
                  key={page}
                  variant={page === safePage ? "primary" : "ghost"}
                  size="sm"
                  onClick={() => setCurrentPage(page)}
                  className="min-w-[32px]"
                >
                  {page}
                </Button>
              );
            })}
            <Button
              variant="ghost"
              size="sm"
              icon={ChevronRight}
              disabled={safePage >= totalPages}
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
            />
          </div>
        </div>
      )}
    </div>
  );
}
