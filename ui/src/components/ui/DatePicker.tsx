import { Calendar } from "lucide-react";
import { type InputHTMLAttributes, forwardRef } from "react";
import { cn } from "../../utils/helpers";

interface DatePickerProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "type" | "onChange"> {
  readonly label?: string;
  readonly description?: string;
  readonly error?: string;
  readonly onChange?: (value: string) => void;
}

export const DatePicker = forwardRef<HTMLInputElement, DatePickerProps>(
  ({ label, description, error, className, id, onChange, ...props }, ref) => {
    const pickerId =
      id ||
      `date-${label?.toLowerCase().replace(/\s+/g, "-") || Math.random().toString(36).slice(2, 9)}`;
    return (
      <div className="w-full">
        {label && (
          <label
            htmlFor={pickerId}
            className="block text-xs font-medium text-[var(--text-secondary)] mb-1.5"
          >
            {label}
            {props.required && <span className="text-[var(--color-danger)] ml-0.5">*</span>}
          </label>
        )}
        <div className="relative">
          <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-muted)] pointer-events-none" />
          <input
            ref={ref}
            id={pickerId}
            type="date"
            className={cn(
              "w-full rounded-lg border bg-[var(--bg-input)] pl-9 pr-3 py-2 text-sm",
              "text-[var(--text-primary)]",
              "transition-all duration-150",
              "focus:outline-none focus:ring-2 focus:ring-[var(--color-brand-500)] focus:border-[var(--color-brand-500)]",
              "disabled:opacity-50 disabled:cursor-not-allowed",
              error
                ? "border-[var(--color-danger)] focus:ring-[var(--color-danger)]"
                : "border-[var(--border-primary)]",
              className,
            )}
            onChange={(e) => onChange?.(e.target.value)}
            {...props}
          />
        </div>
        {description && !error && (
          <p className="mt-1 text-xs text-[var(--text-muted)]">{description}</p>
        )}
        {error && <p className="mt-1 text-xs text-[var(--color-danger)]">{error}</p>}
      </div>
    );
  },
);

DatePicker.displayName = "DatePicker";
