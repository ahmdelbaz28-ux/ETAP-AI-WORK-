import { cn } from "../../utils/helpers";

interface SkeletonProps {
  readonly className?: string;
}

interface SkeletonCardProps {
  readonly lines?: number;
}

interface SkeletonTableProps {
  readonly rows?: number;
  readonly cols?: number;
}

export function Skeleton({ className }: SkeletonProps) {
  return <div className={cn("skeleton h-4", className)} />;
}

export function SkeletonCard({ lines = 3 }: SkeletonCardProps) {
  return (
    <div className="bg-[var(--bg-card)] rounded-xl p-5 border border-[var(--border-primary)] space-y-3">
      <Skeleton className="w-1/3 h-5" />
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton key={`line-${i}`} className={cn("h-4", i === lines - 1 ? "w-2/3" : "w-full")} />
      ))}
    </div>
  );
}

export function SkeletonTable({ rows = 5, cols = 4 }: SkeletonTableProps) {
  return (
    <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-primary)] overflow-hidden">
      <div
        className="grid gap-4 p-4 border-b border-[var(--border-primary)]"
        style={{ gridTemplateColumns: `repeat(${cols}, 1fr)` }}
      >
        {Array.from({ length: cols }).map((_, i) => (
          <Skeleton key={`col-${i}`} className="h-3 w-20" />
        ))}
      </div>
      {Array.from({ length: rows }).map((_, row) => (
        <div
          key={`row-${row}`}
          className="grid gap-4 p-4 border-b border-[var(--border-primary)] last:border-0"
          style={{ gridTemplateColumns: `repeat(${cols}, 1fr)` }}
        >
          {Array.from({ length: cols }).map((_, col) => (
            <Skeleton key={`cell-${row}-${col}`} className="h-3" />
          ))}
        </div>
      ))}
    </div>
  );
}
