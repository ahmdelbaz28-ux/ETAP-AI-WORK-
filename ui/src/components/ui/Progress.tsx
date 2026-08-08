import { cn } from "../../utils/helpers";

type ProgressVariant = "default" | "success" | "warning" | "danger";

interface ProgressProps {
  readonly value?: number;
  readonly max?: number;
  readonly variant?: ProgressVariant;
  readonly size?: "sm" | "md" | "lg";
  readonly label?: string;
  readonly showValue?: boolean;
  readonly className?: string;
}

export function Progress({
  value = 0,
  max = 100,
  variant = "default",
  size = "md",
  label,
  showValue = false,
  className,
}: ProgressProps) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100));
  const variantColors: Record<ProgressVariant, string> = {
    default: "bg-[var(--color-brand-500)]",
    success: "bg-[var(--color-success)]",
    warning: "bg-[var(--color-warning)]",
    danger: "bg-[var(--color-danger)]",
  };
  const sizeClasses: Record<string, string> = {
    sm: "h-1",
    md: "h-2",
    lg: "h-3",
  };
  return (
    <div className={cn("w-full", className)}>
      {(label || showValue) && (
        <div className="flex items-center justify-between mb-1.5">
          {label && <span className="text-xs text-[var(--text-secondary)]">{label}</span>}
          {showValue && (
            <span className="text-xs text-[var(--text-muted)] mono-engineering">
              {Math.round(pct)}%
            </span>
          )}
        </div>
      )}
      <div
        className={cn(
          "w-full rounded-full bg-[var(--bg-elevated)] overflow-hidden",
          sizeClasses[size],
        )}
        role="progressbar"
        tabIndex={0}
        aria-valuenow={Math.round(pct)}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div
          className={cn(
            "h-full rounded-full transition-all duration-500 ease-out",
            variantColors[variant],
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
