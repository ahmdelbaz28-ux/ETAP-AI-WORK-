import { Check } from "lucide-react";
import { type ReactNode, useEffect, useRef, useState } from "react";
import { cn } from "../../utils/helpers";

interface MenuItem {
  readonly id: string;
  readonly label: string;
  readonly icon?: ReactNode;
  readonly disabled?: boolean;
  readonly danger?: boolean;
  readonly checked?: boolean;
  readonly onSelect?: () => void;
}

interface DropdownMenuProps {
  readonly trigger: ReactNode;
  readonly items: MenuItem[];
  readonly align?: "left" | "right";
  readonly className?: string;
}

export function DropdownMenu({ trigger, items, align = "right", className }: DropdownMenuProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    if (open) {
      document.addEventListener("mousedown", handleClickOutside);
      document.addEventListener("keydown", handleEsc);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleEsc);
    };
  }, [open]);

  return (
    <div ref={ref} className={cn("relative inline-flex", className)}>
      <div onClick={() => setOpen((p) => !p)}>{trigger}</div>
      {open && (
        <div
          className={cn(
            "absolute top-full mt-1.5 min-w-[200px] rounded-xl border border-[var(--border-primary)]",
            "bg-[var(--bg-secondary)] shadow-[var(--shadow-dropdown)] py-1.5 z-[var(--z-dropdown)]",
            "animate-scale-in",
            align === "right" ? "right-0" : "left-0",
          )}
          role="menu"
        >
          {items.map((item) => (
            <button
              key={item.id}
              role="menuitem"
              disabled={item.disabled}
              onClick={() => {
                item.onSelect?.();
                setOpen(false);
              }}
              className={cn(
                "w-full flex items-center gap-2.5 px-3 py-2 text-sm transition-colors duration-100",
                "text-left",
                item.danger
                  ? "text-[var(--color-danger)] hover:bg-[var(--color-danger)]/10"
                  : "text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]",
                item.disabled && "opacity-40 cursor-not-allowed",
              )}
            >
              {item.icon && <span className="w-4 h-4">{item.icon}</span>}
              <span className="flex-1">{item.label}</span>
              {item.checked !== undefined && item.checked && (
                <Check className="w-3.5 h-3.5 text-[var(--color-brand-500)]" />
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
