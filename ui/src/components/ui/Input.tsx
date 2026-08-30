import { type InputHTMLAttributes, forwardRef, useId } from "react";
import { cn } from "../../utils/helpers";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  readonly label?: string;
  readonly description?: string;
  readonly error?: string;
  readonly leftIcon?: React.ElementType;
  readonly rightIcon?: React.ElementType;
  readonly onRightIconClick?: () => void;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  (
    {
      label,
      description,
      error,
      leftIcon: LeftIcon,
      rightIcon: RightIcon,
      onRightIconClick,
      className,
      id,
      ...props
    },
    ref,
  ) => {
    const generatedId = useId();
    const inputId =
      id ||
      (label ? `input-${label.toLowerCase().replace(/\s+/g, "-")}` : generatedId);
    return (
      <div className="w-full">
        {label && (
          <label
            htmlFor={inputId}
            className="block text-xs font-medium text-[var(--text-secondary)] mb-1.5"
          >
            {label}
            {props.required && <span className="text-[var(--color-danger)] ml-0.5">*</span>}
          </label>
        )}
        <div className="relative">
          {LeftIcon && (
            <LeftIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-muted)] pointer-events-none" />
          )}
          <input
            ref={ref}
            id={inputId}
            className={cn(
              "w-full rounded-lg border bg-[var(--bg-input)] px-3 py-2 text-sm",
              "text-[var(--text-primary)] placeholder:text-[var(--text-muted)]",
              "transition-all duration-150",
              "focus:outline-none focus:ring-2 focus:ring-[var(--color-brand-500)] focus:border-[var(--color-brand-500)]",
              "disabled:opacity-50 disabled:cursor-not-allowed",
              error
                ? "border-[var(--color-danger)] focus:ring-[var(--color-danger)]"
                : "border-[var(--border-primary)]",
              LeftIcon && "pl-9",
              RightIcon && "pr-9",
              className,
            )}
            {...props}
          />
          {RightIcon && (
            <button
              type="button"
              onClick={onRightIconClick}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors"
              tabIndex={-1}
            >
              <RightIcon className="w-4 h-4" />
            </button>
          )}
        </div>
        {description && !error && (
          <p className="mt-1 text-xs text-[var(--text-muted)]">{description}</p>
        )}
        {error && <p className="mt-1 text-xs text-[var(--color-danger)]">{error}</p>}
      </div>
    );
  },
);

Input.displayName = "Input";
