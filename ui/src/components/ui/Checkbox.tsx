import { Check } from "lucide-react";
import { type InputHTMLAttributes, forwardRef } from "react";
import { cn } from "../../utils/helpers";

interface CheckboxProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "type"> {
  readonly label?: string;
  readonly description?: string;
}

export const Checkbox = forwardRef<HTMLInputElement, CheckboxProps>(
  ({ label, description, className, id, ...props }, ref) => {
    const checkboxId =
      id ||
      `checkbox-${label?.toLowerCase().replace(/\s+/g, "-") || Math.random().toString(36).slice(2, 9)}`;
    return (
      <div className="flex items-start gap-2.5">
        <div className="relative flex items-center pt-0.5">
          <input
            ref={ref}
            type="checkbox"
            id={checkboxId}
            className={cn(
              "peer h-4 w-4 rounded border-[var(--border-primary)] bg-[var(--bg-input)]",
              "appearance-none cursor-pointer transition-all duration-150",
              "checked:bg-[var(--color-brand-500)] checked:border-[var(--color-brand-500)]",
              "focus:outline-none focus:ring-2 focus:ring-[var(--color-brand-500)] focus:ring-offset-2 focus:ring-offset-[var(--bg-primary)]",
              "disabled:opacity-50 disabled:cursor-not-allowed",
              className,
            )}
            {...props}
          />
          <Check className="absolute w-3 h-3 text-white pointer-events-none opacity-0 peer-checked:opacity-100 transition-opacity left-0.5 top-0.5" />
        </div>
        {(label || description) && (
          <div className="flex flex-col">
            {label && (
              <label
                htmlFor={checkboxId}
                className="text-sm text-[var(--text-secondary)] cursor-pointer select-none"
              >
                {label}
              </label>
            )}
            {description && <span className="text-xs text-[var(--text-muted)]">{description}</span>}
          </div>
        )}
      </div>
    );
  },
);

Checkbox.displayName = "Checkbox";
