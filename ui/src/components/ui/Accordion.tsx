import { ChevronDown } from "lucide-react";
import { type ReactNode, useState } from "react";
import { cn } from "../../utils/helpers";

interface AccordionItem {
  readonly id: string;
  readonly title: string;
  readonly description?: string;
  readonly icon?: ReactNode;
  readonly disabled?: boolean;
}

interface AccordionProps {
  readonly items: AccordionItem[];
  readonly children: (item: AccordionItem) => ReactNode;
  readonly allowMultiple?: boolean;
  readonly defaultOpen?: string[];
  readonly className?: string;
}

export function Accordion({
  items,
  children,
  allowMultiple = false,
  defaultOpen = [],
  className,
}: AccordionProps) {
  const [openIds, setOpenIds] = useState<Set<string>>(new Set(defaultOpen));

  const toggle = (id: string) => {
    setOpenIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else {
        if (!allowMultiple) next.clear();
        next.add(id);
      }
      return next;
    });
  };

  return (
    <div className={cn("space-y-2", className)}>
      {items.map((item) => {
        const isOpen = openIds.has(item.id);
        return (
          <div
            key={item.id}
            className={cn(
              "rounded-xl border border-[var(--border-primary)] bg-[var(--bg-card)] overflow-hidden transition-all duration-200",
              isOpen && "border-[var(--color-brand-500)]/30",
            )}
          >
            <button
              type="button"
              onClick={() => !item.disabled && toggle(item.id)}
              disabled={item.disabled}
              className={cn(
                "w-full flex items-center justify-between px-4 py-3 text-left",
                "hover:bg-[var(--bg-elevated)] transition-colors duration-150",
                "focus:outline-none focus:ring-2 focus:ring-[var(--color-brand-500)] focus:ring-inset",
                item.disabled && "opacity-50 cursor-not-allowed",
              )}
              aria-expanded={isOpen}
            >
              <div className="flex items-center gap-3">
                {item.icon && <span className="text-[var(--text-muted)]">{item.icon}</span>}
                <div>
                  <span className="text-sm font-medium text-[var(--text-primary)]">
                    {item.title}
                  </span>
                  {item.description && (
                    <p className="text-xs text-[var(--text-muted)] mt-0.5">{item.description}</p>
                  )}
                </div>
              </div>
              <ChevronDown
                className={cn(
                  "w-4 h-4 text-[var(--text-muted)] transition-transform duration-200",
                  isOpen && "rotate-180",
                )}
              />
            </button>
            {isOpen && <div className="px-4 pb-4 animate-fade-in">{children(item)}</div>}
          </div>
        );
      })}
    </div>
  );
}
