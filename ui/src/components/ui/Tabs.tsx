import { type ReactNode, useState } from "react";
import { cn } from "../../utils/helpers";

interface TabsProps {
  readonly tabs: { readonly id: string; readonly label: string; readonly icon?: ReactNode; readonly badge?: string | number }[];
  readonly activeTab: string;
  readonly onChange: (id: string) => void;
  readonly className?: string;
}

export function Tabs({ tabs, activeTab, onChange, className }: TabsProps) {
  return (
    <div
      className={cn("flex items-center gap-1 bg-[var(--bg-elevated)] rounded-lg p-1", className)}
    >
      {tabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onChange(tab.id)}
          className={cn(
            "flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-all",
            activeTab === tab.id
              ? "bg-[var(--bg-card)] text-[var(--text-primary)] shadow-sm"
              : "text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] hover:bg-[var(--bg-card)]/50",
          )}
         type="button">
          {tab.icon}
          {tab.label}
          {tab.badge !== undefined && (
            <span
              className={cn(
                "px-1.5 py-0.5 text-[10px] rounded-full font-medium",
                activeTab === tab.id
                  ? "bg-brand-500/20 text-brand-400"
                  : "bg-[var(--bg-elevated)] text-[var(--text-muted)]",
              )}
            >
              {tab.badge}
            </span>
          )}
        </button>
      ))}
    </div>
  );
}

interface TabPanelsProps {
  readonly children: ReactNode;
  readonly className?: string;
}

export function TabPanels({ children, className }: TabPanelsProps) {
  return <div className={cn("mt-4", className)}>{children}</div>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useTabState(defaultTab: string) {
  const [activeTab, setActiveTab] = useState(defaultTab);
  return { activeTab, setActiveTab };
}
