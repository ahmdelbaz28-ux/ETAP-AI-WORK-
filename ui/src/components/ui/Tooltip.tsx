import { type ReactNode, useEffect, useRef, useState } from "react";
import { cn } from "../../utils/helpers";

interface TooltipProps {
  readonly content: ReactNode;
  readonly children: ReactNode;
  readonly side?: "top" | "bottom" | "left" | "right";
  readonly delayMs?: number;
  readonly className?: string;
}

export function Tooltip({
  content,
  children,
  side = "top",
  delayMs = 300,
  className,
}: TooltipProps) {
  const [visible, setVisible] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const triggerRef = useRef<HTMLElement>(null);

  const show = () => {
    timerRef.current = setTimeout(() => setVisible(true), delayMs);
  };
  const hide = () => {
    if (timerRef.current) clearTimeout(timerRef.current);
    setVisible(false);
  };

  useEffect(
    () => () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    },
    [],
  );

  const positionClasses: Record<string, string> = {
    top: "bottom-full left-1/2 -translate-x-1/2 mb-2",
    bottom: "top-full left-1/2 -translate-x-1/2 mt-2",
    left: "right-full top-1/2 -translate-y-1/2 mr-2",
    right: "left-full top-1/2 -translate-y-1/2 ml-2",
  };

  return (
    <span
      className={cn("relative inline-flex", className)}
      onMouseEnter={show}
      onMouseLeave={hide}
      onFocus={show}
      onBlur={hide}
    >
      <span ref={triggerRef} className="inline-flex">
        {children}
      </span>
      {visible && (
        <span
          role="tooltip"
          className={cn(
            "absolute z-[var(--z-tooltip)] px-2.5 py-1.5 rounded-lg",
            "bg-[var(--bg-elevated)] border border-[var(--border-primary)]",
            "text-xs text-[var(--text-secondary)] whitespace-nowrap",
            "shadow-[var(--shadow-dropdown)]",
            "animate-scale-in",
            positionClasses[side],
          )}
        >
          {content}
        </span>
      )}
    </span>
  );
}
