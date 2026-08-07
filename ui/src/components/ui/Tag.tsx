import { X } from "lucide-react";
import { type HTMLAttributes, forwardRef } from "react";
import { cn } from "../../utils/helpers";

type TagVariant = "default" | "brand" | "success" | "warning" | "danger" | "info";

interface TagProps extends HTMLAttributes<HTMLSpanElement> {
  readonly variant?: TagVariant;
  readonly size?: "sm" | "md";
  readonly removable?: boolean;
  readonly onRemove?: () => void;
}

const variantStyles: Record<TagVariant, string> = {
  default: "bg-[var(--bg-elevated)] text-[var(--text-secondary)] border-[var(--border-primary)]",
  brand: "bg-brand-500/10 text-brand-400 border-brand-500/20",
  success: "bg-green-500/10 text-green-400 border-green-500/20",
  warning: "bg-amber-500/10 text-amber-400 border-amber-500/20",
  danger: "bg-red-500/10 text-red-400 border-red-500/20",
  info: "bg-blue-500/10 text-blue-400 border-blue-500/20",
};

export const Tag = forwardRef<HTMLSpanElement, TagProps>(
  (
    { variant = "default", size = "sm", removable, onRemove, className, children, ...props },
    ref,
  ) => {
    return (
      <span
        ref={ref}
        className={cn(
          "inline-flex items-center gap-1 font-medium rounded-full border",
          size === "sm" ? "px-2 py-0.5 text-[10px]" : "px-2.5 py-1 text-xs",
          variantStyles[variant],
          className,
        )}
        {...props}
      >
        {children}
        {removable && (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onRemove?.();
            }}
            className="ml-0.5 rounded-full hover:bg-black/10 p-0.5 transition-colors"
            tabIndex={-1}
          >
            <X className="w-3 h-3" />
          </button>
        )}
      </span>
    );
  },
);

Tag.displayName = "Tag";
