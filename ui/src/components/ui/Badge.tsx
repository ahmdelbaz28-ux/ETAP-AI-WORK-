import type { HTMLAttributes } from "react";
import { cn } from "../../utils/helpers";

type BadgeVariant = "default" | "success" | "warning" | "danger" | "info" | "brand" | "neutral";
type BadgeSize = "sm" | "md";

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
  size?: BadgeSize;
  dot?: boolean;
}

const variantStyles: Record<BadgeVariant, string> = {
  default: "bg-[var(--bg-elevated)] text-[var(--text-secondary)] border-[var(--border-primary)]",
  success: "bg-green-500/10 text-green-400 border-green-500/20",
  warning: "bg-amber-500/10 text-amber-400 border-amber-500/20",
  danger: "bg-red-500/10 text-red-400 border-red-500/20",
  info: "bg-blue-500/10 text-blue-400 border-blue-500/20",
  brand: "bg-brand-500/10 text-brand-400 border-brand-500/20",
  neutral: "bg-surface-500/10 text-surface-400 border-surface-500/20",
};

const dotColors: Record<BadgeVariant, string> = {
  default: "bg-[var(--text-tertiary)]",
  success: "bg-green-400",
  warning: "bg-amber-400",
  danger: "bg-red-400",
  info: "bg-blue-400",
  brand: "bg-brand-400",
  neutral: "bg-surface-400",
};

export function Badge({
  variant = "default",
  size = "sm",
  dot,
  className,
  children,
  ...props
}: BadgeProps) {
  // NOSONAR — S6759: React props read-only; requires `readonly` refactor across component tree
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 font-medium rounded-full border",
        size === "sm" ? "px-2 py-0.5 text-[10px]" : "px-2.5 py-1 text-xs",
        variantStyles[variant],
        className,
      )}
      {...props}
    >
      {dot && <span className={cn("w-1.5 h-1.5 rounded-full", dotColors[variant])} />}
      {children}
    </span>
  );
}
