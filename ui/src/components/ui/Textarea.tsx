import { type TextareaHTMLAttributes, forwardRef } from "react";
import { cn } from "../../utils/helpers";

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  readonly label?: string;
  readonly description?: string;
  readonly error?: string;
  readonly maxRows?: number;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ label, description, error, maxRows = 12, className, id, ...props }, ref) => {
    const textareaId =
      id ||
      `textarea-${label?.toLowerCase().replace(/\s+/g, "-") || Math.random().toString(36).slice(2, 9)}`;
    return (
      <div className="w-full">
        {label && (
          <label
            htmlFor={textareaId}
            className="block text-xs font-medium text-[var(--text-secondary)] mb-1.5"
          >
            {label}
            {props.required && <span className="text-[var(--color-danger)] ml-0.5">*</span>}
          </label>
        )}
        <textarea
          ref={ref}
          id={textareaId}
          className={cn(
            "w-full rounded-lg border bg-[var(--bg-input)] px-3 py-2 text-sm",
            "text-[var(--text-primary)] placeholder:text-[var(--text-muted)]",
            "transition-all duration-150 resize-y",
            "focus:outline-none focus:ring-2 focus:ring-[var(--color-brand-500)] focus:border-[var(--color-brand-500)]",
            "disabled:opacity-50 disabled:cursor-not-allowed",
            error
              ? "border-[var(--color-danger)] focus:ring-[var(--color-danger)]"
              : "border-[var(--border-primary)]",
            className,
          )}
          {...props}
        />
        {description && !error && (
          <p className="mt-1 text-xs text-[var(--text-muted)]">{description}</p>
        )}
        {error && <p className="mt-1 text-xs text-[var(--color-danger)]">{error}</p>}
      </div>
    );
  },
);

Textarea.displayName = "Textarea";
