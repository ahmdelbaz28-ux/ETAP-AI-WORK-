import { forwardRef, type ButtonHTMLAttributes } from 'react'
import { cn } from '../../utils/helpers'
import { Loader2 } from 'lucide-react'

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'success' | 'outline'
type ButtonSize = 'sm' | 'md' | 'lg' | 'icon'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: ButtonSize
  loading?: boolean
  icon?: React.ElementType
}

const variantStyles: Record<ButtonVariant, string> = {
  primary: 'bg-brand-600 hover:bg-brand-500 text-white shadow-sm shadow-brand-600/20 hover:shadow-brand-500/30 active:bg-brand-700',
  secondary: 'bg-[var(--bg-elevated)] hover:bg-[var(--border-primary)] text-[var(--text-secondary)] border border-[var(--border-primary)] active:bg-[var(--border-secondary)]',
  ghost: 'hover:bg-[var(--bg-elevated)] text-[var(--text-secondary)] active:bg-[var(--border-primary)]',
  danger: 'bg-red-600 hover:bg-red-500 text-white shadow-sm active:bg-red-700',
  success: 'bg-green-600 hover:bg-green-500 text-white shadow-sm active:bg-green-700',
  outline: 'border border-brand-500/50 text-brand-400 hover:bg-brand-500/10 active:bg-brand-500/20',
}

const sizeStyles: Record<ButtonSize, string> = {
  sm: 'px-3 py-1.5 text-xs gap-1.5',
  md: 'px-4 py-2 text-sm gap-2',
  lg: 'px-6 py-3 text-base gap-2.5',
  icon: 'p-2 aspect-square',
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = 'primary', size = 'md', loading, icon: Icon, className, children, disabled, ...props }, ref) => {
    return (
      <button
        ref={ref}
        disabled={disabled || loading}
        className={cn(
          'inline-flex items-center justify-center font-medium rounded-lg transition-all duration-150 select-none',
          'disabled:opacity-50 disabled:cursor-not-allowed',
          'btn-press relative',
          variantStyles[variant],
          sizeStyles[size],
          className
        )}
        {...props}
      >
        {loading ? (
          <Loader2 className={cn('animate-spin', size === 'sm' ? 'w-3.5 h-3.5' : 'w-4 h-4')} />
        ) : Icon ? (  // NOSONAR — S3358: nested ternary; refactor to named variable (tech debt)
          <Icon className={cn(size === 'sm' ? 'w-3.5 h-3.5' : 'w-4 h-4')} />
        ) : null}
        {children}
      </button>
    )
  }
)

Button.displayName = 'Button'
