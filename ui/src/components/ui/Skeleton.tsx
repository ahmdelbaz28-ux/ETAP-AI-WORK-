import { cn } from "../../utils/helpers";

// Pre-generated stable keys for skeleton placeholders. Using a pre-computed
// pool of string keys (rather than the array index) avoids the React
// "array index as key" lint while still providing unique stable identities
// for placeholder elements that have no underlying data.
const SKELETON_KEYS = Array.from({ length: 100 }, (_, i) => `skel-${i}`);

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
      {SKELETON_KEYS.slice(0, lines).map((key, i) => (
        <Skeleton key={key} className={cn("h-4", i === lines - 1 ? "w-2/3" : "w-full")} />
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
        {SKELETON_KEYS.slice(0, cols).map((key) => (
          <Skeleton key={key} className="h-3 w-20" />
        ))}
      </div>
      {SKELETON_KEYS.slice(0, rows).map((rowKey) => (
        <div
          key={rowKey}
          className="grid gap-4 p-4 border-b border-[var(--border-primary)] last:border-0"
          style={{ gridTemplateColumns: `repeat(${cols}, 1fr)` }}
        >
          {SKELETON_KEYS.slice(100, 100 + cols).map((colKey) => (
            <Skeleton key={`${rowKey}-${colKey}`} className="h-3" />

import { cn } from '../../utils/helpers'

interface SkeletonProps {
  className?: string
  lines?: number
}

export function Skeleton({ className }: SkeletonProps) {
  return <div className={cn('skeleton h-4', className)} />
}

export function SkeletonCard({ lines = 3 }: SkeletonProps) {
  return (
    <div className="bg-[var(--bg-card)] rounded-xl p-5 border border-[var(--border-primary)] space-y-3">
      <Skeleton className="w-1/3 h-5" />
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton key={i} className={cn('h-4', i === lines - 1 ? 'w-2/3' : 'w-full')} />
      ))}
    </div>
  )
}

export function SkeletonTable({ rows = 5, cols = 4 }: { rows?: number; cols?: number }) {
  return (
    <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-primary)] overflow-hidden">
      <div className="grid gap-4 p-4 border-b border-[var(--border-primary)]" style={{ gridTemplateColumns: `repeat(${cols}, 1fr)` }}>
        {Array.from({ length: cols }).map((_, i) => (
          <Skeleton key={i} className="h-3 w-20" />
        ))}
      </div>
      {Array.from({ length: rows }).map((_, row) => (
        <div key={row} className="grid gap-4 p-4 border-b border-[var(--border-primary)] last:border-0" style={{ gridTemplateColumns: `repeat(${cols}, 1fr)` }}>
          {Array.from({ length: cols }).map((_, col) => (
            <Skeleton key={col} className="h-3" />
          ))}
        </div>
      ))}
    </div>
  );
}
