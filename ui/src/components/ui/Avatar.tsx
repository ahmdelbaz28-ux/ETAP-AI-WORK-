import type { HTMLAttributes } from "react";
import { cn } from "../../utils/helpers";

interface AvatarProps extends HTMLAttributes<HTMLDivElement> {
  readonly src?: string;
  readonly alt?: string;
  readonly fallback?: string;
  readonly size?: "xs" | "sm" | "md" | "lg" | "xl";
  readonly status?: "online" | "offline" | "away" | "busy";
}

const sizeClasses: Record<string, string> = {
  xs: "w-6 h-6 text-[10px]",
  sm: "w-8 h-8 text-xs",
  md: "w-10 h-10 text-sm",
  lg: "w-12 h-12 text-base",
  xl: "w-16 h-16 text-lg",
};

const statusColors: Record<string, string> = {
  online: "bg-green-400",
  offline: "bg-gray-400",
  away: "bg-amber-400",
  busy: "bg-red-400",
};

export function Avatar({
  src,
  alt = "User avatar",
  fallback,
  size = "md",
  status,
  className,
  ...props
}: AvatarProps) {
  const initials =
    fallback
      ?.split(" ")
      .map((w) => w[0])
      .join("")
      .toUpperCase()
      .slice(0, 2) || "?";

  return (
    <div className={cn("relative inline-flex shrink-0", className)} {...props}>
      {src ? (
        <img
          src={src}
          alt={alt}
          className={cn("rounded-full object-cover bg-[var(--bg-elevated)]", sizeClasses[size])}
        />
      ) : (
        <div
          className={cn(
            "rounded-full bg-[var(--bg-elevated)] flex items-center justify-center font-semibold text-[var(--text-secondary)]",
            sizeClasses[size],
          )}
        >
          {initials}
        </div>
      )}
      {status && (
        <span
          className={cn(
            "absolute bottom-0 right-0 rounded-full ring-2 ring-[var(--bg-card)]",
            statusColors[status],
            size === "xs" || size === "sm" ? "w-2 h-2" : "w-3 h-3",
          )}
        />
      )}
    </div>
  );
}
