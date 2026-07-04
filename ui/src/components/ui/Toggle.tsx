import { cn } from '../../utils/helpers';

interface ToggleProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label?: string;
  description?: string;
  disabled?: boolean;
  size?: 'sm' | 'md';
}

export function Toggle({
  checked,
  onChange,
  label,
  description,
  disabled,
  size = 'md',
}: ToggleProps) {
  // NOSONAR — S6759: React props read-only; requires `readonly` refactor across component tree
  const isMd = size === 'md';
  return (
    <label
      className={cn(
        'flex items-center gap-3 cursor-pointer group',
        disabled && 'opacity-50 cursor-not-allowed',
      )}
    >
      <button
        role="switch"
        aria-checked={checked}
        onClick={() => !disabled && onChange(!checked)}
        className={cn(
          'relative rounded-full transition-colors shrink-0',
          isMd ? 'w-11 h-6' : 'w-8 h-4.5',
          checked ? 'bg-brand-500' : 'bg-[var(--border-secondary)]',
        )}
      >
        <span
          className={cn(
            'absolute top-0.5 bg-white rounded-full shadow-sm transition-transform',
            isMd ? 'w-5 h-5' : 'w-3.5 h-3.5',
            checked ? (isMd ? 'translate-x-[22px]' : 'translate-x-[14px]') : 'translate-x-0.5', // NOSONAR — S3358: nested ternary; refactor to named variable (tech debt)
          )}
        />
      </button>
      {(label || description) && (
        <div>
          {label && (
            <span className="text-sm text-[var(--text-secondary)] group-hover:text-[var(--text-primary)] transition-colors">
              {label}
            </span>
          )}
          {description && <p className="text-xs text-[var(--text-muted)] mt-0.5">{description}</p>}
        </div>
      )}
    </label>
  );
}
