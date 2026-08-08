import type { HTMLAttributes, ReactNode } from "react";
import { cn } from "../../utils/helpers";

interface DividerProps extends HTMLAttributes<HTMLDivElement> {
  readonly label?: ReactNode;
  readonly orientation?: "horizontal" | "vertical";
}

export function Divider({ label, orientation = "horizontal", className, ...props }: DividerProps) {
  if (orientation === "vertical") {
    return (
      <div
        role="separator"
        aria-orientation="vertical"
        tabIndex={0}
        className={cn("w-px self-stretch bg-[var(--border-primary)]", className)}
        {...props}
      />
    );
  }
  return (
    // biome-ignore lint/a11y/useSemanticElements: composite separator with optional label; <hr> cannot render a centered label
    <div
      role="separator"
      tabIndex={0}
      className={cn("flex items-center gap-3", className)}
      {...props}
    >
      <div className="flex-1 h-px bg-[var(--border-primary)]" />
      {label && <span className="text-xs text-[var(--text-muted)] whitespace-nowrap">{label}</span>}
      <div className="flex-1 h-px bg-[var(--border-primary)]" />
    </div>
  );
}
