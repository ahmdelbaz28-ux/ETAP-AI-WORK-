import { HelpCircle } from "lucide-react";
import { useTranslation } from "react-i18next";

interface ContextHelpButtonProps {
  /** The context ID to look up in the contextRegistry. */
  readonly contextId: string;
  /** Optional CSS class for custom positioning. */
  readonly className?: string;
  /** Optional size variant. */
  readonly size?: "sm" | "md" | "lg";
  /** Optional label override (defaults to localized "Help"). */
  readonly label?: string;
}

/**
 * A small help button that opens the Smart Help drawer with the topic
 * matching the given contextId.
 *
 * Place this button in the header of any page or section to give users
 * instant access to documentation for what they're looking at.
 *
 * Example:
 *   <ContextHelpButton contextId="studies.load-flow" />
 */
export function ContextHelpButton({
  contextId,
  className = "",
  size = "sm",
  label,
}: ContextHelpButtonProps) {
  const { i18n } = useTranslation();
  const lang = i18n.language === "ar" ? "ar" : "en";
  const displayLabel = label ?? (lang === "ar" ? "مساعدة" : "Help");

  const sizeClasses = {
    sm: "w-7 h-7",
    md: "w-8 h-8",
    lg: "w-9 h-9",
  };

  const iconSizes = {
    sm: "w-3.5 h-3.5",
    md: "w-4 h-4",
    lg: "w-4.5 h-4.5",
  };

  const handleClick = () => {
    // Dispatch a global event that App.tsx listens for; this opens the
    // SmartHelpDrawer with the resolved topic for this contextId.
    globalThis.dispatchEvent(
      new CustomEvent("open-smart-help", {
        detail: { contextId },
      }),
    );
  };

  return (
    <button
      type="button"
      onClick={handleClick}
      data-help-context="action.open-help"
      title={`${displayLabel} — ${contextId}`}
      aria-label={displayLabel}
      className={`inline-flex items-center justify-center rounded-md text-[var(--text-muted)] hover:bg-[var(--bg-elevated)] hover:text-[var(--accent-primary)] transition-colors ${sizeClasses[size]} ${className}`}
    >
      <HelpCircle className={iconSizes[size]} />
      <span className="sr-only">{displayLabel}</span>
    </button>
  );

import { HelpCircle } from 'lucide-react'
import { cn } from '../../utils/helpers'

interface ContextHelpButtonProps {
  contextId: string
  onClick: (contextId: string) => void
  size?: 'sm' | 'md'
  className?: string
  label?: string
}

export function ContextHelpButton({ contextId, onClick, size = 'sm', className, label }: ContextHelpButtonProps) {
  const sizeClasses = {
    sm: 'w-5 h-5',
    md: 'w-6 h-6',
  }

  return (
    <button
      onClick={() => onClick(contextId)}
      data-help-context={contextId}
      className={cn(
        'inline-flex items-center justify-center rounded-md transition-colors',
        'text-[var(--text-muted)] hover:text-[var(--accent-primary)] hover:bg-[var(--accent-glow)]',
        size === 'sm' ? 'p-1' : 'p-1.5',
        className
      )}
      title={`Help: ${contextId}`}
    >
      <HelpCircle className={sizeClasses[size]} />
      {label && <span className="ml-1 text-xs">{label}</span>}
    </button>
  )
}
