import type { ReactNode, HTMLAttributes } from 'react';
import { cn } from '../../utils/helpers';

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  variant?: 'default' | 'interactive' | 'bordered' | 'flat' | 'glass';
  padding?: 'none' | 'sm' | 'md' | 'lg';
  hover?: boolean;
}

const variantStyles = {
  default: 'bg-[var(--bg-card)] border border-[var(--border-primary)]',
  interactive: 'card-interactive',
  bordered:
    'bg-[var(--bg-card)] border border-[var(--border-primary)] hover:border-brand-500/50 transition-all',
  flat: 'bg-[var(--bg-elevated)]',
  glass: 'glass border border-white/10',
};

const paddingStyles = {
  none: '',
  sm: 'p-3',
  md: 'p-5',
  lg: 'p-6',
};

export function Card({
  variant = 'default',
  padding = 'md',
  className,
  children,
  ...props
}: CardProps) {
  // NOSONAR — S6759: React props read-only; requires `readonly` refactor across component tree
  return (
    <div
      className={cn(
        'rounded-xl',
        variantStyles[variant],
        paddingStyles[padding],
        variant !== 'flat' && variant !== 'glass' && 'card-hover-lift',
        className,
      )}
      {...props}
    >
      {children}
    </div>
  );
}

interface CardHeaderProps extends Omit<HTMLAttributes<HTMLDivElement>, 'title'> {
  title: ReactNode;
  subtitle?: ReactNode;
  icon?: ReactNode;
  action?: ReactNode;
}

export function CardHeader({
  title,
  subtitle,
  icon,
  action,
  className,
  ...props
}: CardHeaderProps) {
  // NOSONAR — S6759: React props read-only; requires `readonly` refactor across component tree
  return (
    <div className={cn('flex items-center justify-between mb-4', className)} {...props}>
      <div className="flex items-center gap-2.5">
        {icon && <div className="p-1.5 rounded-lg bg-brand-500/10 text-brand-400">{icon}</div>}
        <div>
          <h3 className="text-base font-semibold text-[var(--text-primary)]">{title}</h3>
          {subtitle && <p className="text-xs text-[var(--text-tertiary)] mt-0.5">{subtitle}</p>}
        </div>
      </div>
      {action}
    </div>
  );
}

export function CardSection({ className, children, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        'py-3 border-t border-[var(--border-primary)] first:border-t-0 first:pt-0',
        className,
      )}
      {...props}
    >
      {children}
    </div>
  );
}
