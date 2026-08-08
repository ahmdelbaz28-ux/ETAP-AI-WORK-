import { ChevronLeft, ChevronRight } from "lucide-react";
import { cn } from "../../utils/helpers";
import { Button } from "./Button";

interface PaginationProps {
  readonly page: number;
  readonly totalPages: number;
  readonly onPageChange: (page: number) => void;
  readonly pageSize?: number;
  readonly totalItems?: number;
  readonly pageSizeOptions?: number[];
  readonly onPageSizeChange?: (size: number) => void;
  readonly className?: string;
}

export function Pagination({
  page,
  totalPages,
  onPageChange,
  totalItems,
  pageSize,
  pageSizeOptions = [10, 25, 50, 100],
  onPageSizeChange,
  className,
}: PaginationProps) {
  const start = totalItems ? (page - 1) * (pageSize ?? 25) + 1 : 0;
  const end = totalItems ? Math.min(page * (pageSize ?? 25), totalItems) : 0;

  const getPageNumbers = (): { key: string; value: number | "..." }[] => {
    if (totalPages <= 7)
      return Array.from({ length: totalPages }, (_, i) => ({
        key: `page-${i + 1}`,
        value: i + 1,
      }));
    const pages: { key: string; value: number | "..." }[] = [{ key: "page-1", value: 1 }];
    if (page > 3) pages.push({ key: "ellipsis-start", value: "..." });
    for (let i = Math.max(2, page - 1); i <= Math.min(totalPages - 1, page + 1); i++) {
      pages.push({ key: `page-${i}`, value: i });
    }
    if (page < totalPages - 2) pages.push({ key: "ellipsis-end", value: "..." });
    if (totalPages > 1) pages.push({ key: `page-${totalPages}`, value: totalPages });
    return pages;
  };

  return (
    <div className={cn("flex items-center justify-between", className)}>
      <div className="flex items-center gap-4">
        {totalItems !== undefined && (
          <span className="text-xs text-[var(--text-muted)]">
            Showing {start}–{end} of {totalItems}
          </span>
        )}
        {onPageSizeChange && pageSize && (
          <select
            value={pageSize}
            onChange={(e) => onPageSizeChange(Number(e.target.value))}
            className="rounded-lg border border-[var(--border-primary)] bg-[var(--bg-input)] px-2 py-1 text-xs text-[var(--text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-brand-500)]"
          >
            {pageSizeOptions.map((opt) => (
              <option key={opt} value={opt}>
                {opt}/page
              </option>
            ))}
          </select>
        )}
      </div>
      <div className="flex items-center gap-1">
        <Button
          variant="ghost"
          size="sm"
          icon={ChevronLeft}
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
        />
        {getPageNumbers().map(({ key, value }) =>
          value === "..." ? (
            <span key={key} className="px-2 text-xs text-[var(--text-muted)]">
              ...
            </span>
          ) : (
            <Button
              key={key}
              variant={value === page ? "primary" : "ghost"}
              size="sm"
              onClick={() => onPageChange(value)}
              className="min-w-[32px]"
            >
              {value}
            </Button>
          ),
        )}
        <Button
          variant="ghost"
          size="sm"
          icon={ChevronRight}
          disabled={page >= totalPages}
          onClick={() => onPageChange(page + 1)}
        />
      </div>
    </div>
  );
}
