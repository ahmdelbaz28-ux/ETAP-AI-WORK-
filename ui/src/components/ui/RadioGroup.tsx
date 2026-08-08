import { cn } from "../../utils/helpers";

interface RadioOption {
  readonly value: string;
  readonly label: string;
  readonly description?: string;
  readonly disabled?: boolean;
}

interface RadioGroupProps {
  readonly name: string;
  readonly value?: string;
  readonly onChange: (value: string) => void;
  readonly options: RadioOption[];
  readonly label?: string;
  readonly description?: string;
  readonly orientation?: "horizontal" | "vertical";
  readonly disabled?: boolean;
}

export function RadioGroup({
  name,
  value,
  onChange,
  options,
  label,
  description,
  orientation = "vertical",
  disabled,
}: RadioGroupProps) {
  return (
    <fieldset className="w-full border-none p-0 m-0">
      {label && (
        <legend className="block text-xs font-medium text-[var(--text-secondary)] mb-1.5">
          {label}
        </legend>
      )}
      {description && <p className="text-xs text-[var(--text-muted)] mb-2">{description}</p>}
      <div
        className={cn("flex gap-3", orientation === "vertical" ? "flex-col" : "flex-wrap")}
        role="radiogroup"
      >
        {options.map((opt) => {
          const id = `${name}-${opt.value}`;
          const checked = value === opt.value;
          return (
            <label
              key={opt.value}
              htmlFor={id}
              className={cn(
                "flex items-center gap-2.5 cursor-pointer group",
                (disabled || opt.disabled) && "opacity-50 cursor-not-allowed",
              )}
            >
              <div className="relative flex items-center">
                <input
                  type="radio"
                  id={id}
                  name={name}
                  value={opt.value}
                  checked={checked}
                  onChange={() => !(disabled || opt.disabled) && onChange(opt.value)}
                  disabled={disabled || opt.disabled}
                  className={cn(
                    "h-4 w-4 rounded-full border-[var(--border-primary)] bg-[var(--bg-input)]",
                    "appearance-none cursor-pointer transition-all duration-150",
                    "checked:border-[var(--color-brand-500)]",
                    "focus:outline-none focus:ring-2 focus:ring-[var(--color-brand-500)] focus:ring-offset-2 focus:ring-offset-[var(--bg-primary)]",
                  )}
                />
                {checked && (
                  <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-2 h-2 rounded-full bg-[var(--color-brand-500)]" />
                )}
              </div>
              <div className="flex flex-col">
                <span className="text-sm text-[var(--text-secondary)] group-hover:text-[var(--text-primary)] transition-colors select-none">
                  {opt.label}
                </span>
                {opt.description && (
                  <span className="text-xs text-[var(--text-muted)]">{opt.description}</span>
                )}
              </div>
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}
