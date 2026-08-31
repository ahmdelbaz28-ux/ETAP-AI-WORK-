import { Minus, Plus } from "lucide-react";
import { type InputHTMLAttributes, forwardRef, useId } from "react";
import { cn } from "../../utils/helpers";

interface NumberInputProps
  extends Omit<InputHTMLAttributes<HTMLInputElement>, "type" | "onChange"> {
  readonly label?: string;
  readonly description?: string;
  readonly error?: string;
  readonly onChange?: (value: number) => void;
  readonly min?: number;
  readonly max?: number;
  readonly step?: number;
  readonly precision?: number;
}

export const NumberInput = forwardRef<HTMLInputElement, NumberInputProps>(
  (
    { label, description, error, onChange, min, max, step = 1, precision, className, id, ...props },
    ref,
  ) => {
    const generatedId = useId();
    const inputId =
      id ||
      (label ? `number-${label.toLowerCase().replace(/\s+/g, "-")}` : generatedId);

    const clamp = (val: number): number => {
      let v = val;
      if (min !== undefined) v = Math.max(min, v);
      if (max !== undefined) v = Math.min(max, v);
      return v;
    };

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      const raw = e.target.value;
      if (raw === "" || raw === "-") {
        onChange?.(Number.NaN);
        return;
      }
      const num = Number.parseFloat(raw);
      if (!Number.isNaN(num)) {
        const clamped = clamp(num);
        onChange?.(precision !== undefined ? Number(clamped.toFixed(precision)) : clamped);
      }
    };

    const handleStep = (delta: number) => {
      const current = Number.parseFloat(props.value?.toString() || "0");
      const next = clamp(Number.isNaN(current) ? 0 : current + delta);
      onChange?.(precision !== undefined ? Number(next.toFixed(precision)) : next);
    };

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
        <div className="flex items-center">
          <button
            type="button"
            onClick={() => handleStep(-step)}
            className="px-2.5 py-2 rounded-l-lg border border-[var(--border-primary)] bg-[var(--bg-elevated)] text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)] transition-colors"
            tabIndex={-1}
          >
            <Minus className="w-3.5 h-3.5" />
          </button>
          <input
            ref={ref}
            id={inputId}
            type="number"
            inputMode="decimal"
            className={cn(
              "flex-1 rounded-none border-y border-[var(--border-primary)] bg-[var(--bg-input)] px-3 py-2 text-sm text-center",
              "text-[var(--text-primary)]",
              "transition-all duration-150",
              "focus:outline-none focus:ring-2 focus:ring-[var(--color-brand-500)] focus:border-[var(--color-brand-500)]",
              "disabled:opacity-50 disabled:cursor-not-allowed",
              error
                ? "border-[var(--color-danger)] focus:ring-[var(--color-danger)]"
                : "border-[var(--border-primary)]",
              className,
            )}
            onChange={handleChange}
            min={min}
            max={max}
            step={step}
            {...props}
          />
          <button
            type="button"
            onClick={() => handleStep(step)}
            className="px-2.5 py-2 rounded-r-lg border border-[var(--border-primary)] bg-[var(--bg-elevated)] text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)] transition-colors"
            tabIndex={-1}
          >
            <Plus className="w-3.5 h-3.5" />
          </button>
        </div>
        {description && !error && (
          <p className="mt-1 text-xs text-[var(--text-muted)]">{description}</p>
        )}
        {error && <p className="mt-1 text-xs text-[var(--color-danger)]">{error}</p>}
      </div>
    );
  },
);

NumberInput.displayName = "NumberInput";
