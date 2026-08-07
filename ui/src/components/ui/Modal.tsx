<<<<<<< HEAD
import { X } from "lucide-react";
import { type ReactNode, useEffect, useRef } from "react";
import { cn } from "../../utils/helpers";

interface ModalProps {
  readonly open: boolean;
  readonly onClose: () => void;
  readonly title?: string;
  readonly subtitle?: string;
  readonly size?: "sm" | "md" | "lg" | "xl" | "full";
  readonly children: ReactNode;
  readonly footer?: ReactNode;
  readonly closeOnOverlay?: boolean;
}

const sizeStyles = {
  sm: "max-w-sm",
  md: "max-w-lg",
  lg: "max-w-2xl",
  xl: "max-w-4xl",
  full: "max-w-[90vw]",
};

export function Modal({
  open,
  onClose,
  title,
  subtitle,
  size = "md",
  children,
  footer,
  closeOnOverlay = true,
}: ModalProps) {
  // NOSONAR — S6759: React props read-only; requires `readonly` refactor across component tree
  const previouslyOpen = useRef(open);

  useEffect(() => {
    previouslyOpen.current = open;
    if (open) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape" && open) onClose();
    };
    globalThis.addEventListener("keydown", handleEsc);
    return () => globalThis.removeEventListener("keydown", handleEsc);
  }, [open, onClose]);

  if (!open) return null;
=======
import { useEffect, type ReactNode, useRef } from 'react'
import { cn } from '../../utils/helpers'
import { X } from 'lucide-react'

interface ModalProps {
  open: boolean
  onClose: () => void
  title?: string
  subtitle?: string
  size?: 'sm' | 'md' | 'lg' | 'xl' | 'full'
  children: ReactNode
  footer?: ReactNode
  closeOnOverlay?: boolean
}

const sizeStyles = {
  sm: 'max-w-sm',
  md: 'max-w-lg',
  lg: 'max-w-2xl',
  xl: 'max-w-4xl',
  full: 'max-w-[90vw]',
}

export function Modal({ open, onClose, title, subtitle, size = 'md', children, footer, closeOnOverlay = true }: ModalProps) {
  const previouslyOpen = useRef(open)

  useEffect(() => {
    previouslyOpen.current = open
    if (open) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
    return () => { document.body.style.overflow = '' }
  }, [open])

  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && open) onClose()
    }
    window.addEventListener('keydown', handleEsc)
    return () => window.removeEventListener('keydown', handleEsc)
  }, [open, onClose])

  if (!open) return null
>>>>>>> origin/fix/scenario-tests-properly

  return (
    <div
      className={cn(
<<<<<<< HEAD
        "fixed inset-0 z-[var(--z-modal-backdrop)] flex items-center justify-center p-4",
        "transition-all duration-200",
        open ? "opacity-100" : "opacity-0 pointer-events-none",
      )}
    >
      {/* Backdrop */}
      <div // NOSONAR — S6848: non-interactive DOM role; intentional
=======
        'fixed inset-0 z-[var(--z-modal-backdrop)] flex items-center justify-center p-4',
        'transition-all duration-200',
        open ? 'opacity-100' : 'opacity-0 pointer-events-none'
      )}
    >
      {/* Backdrop */}
      <div
>>>>>>> origin/fix/scenario-tests-properly
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={closeOnOverlay ? onClose : undefined}
      />

      {/* Content */}
      <div
        className={cn(
<<<<<<< HEAD
          "relative z-[var(--z-modal)] w-full rounded-xl",
          "bg-[var(--bg-secondary)] border border-[var(--border-primary)]",
          "shadow-[var(--shadow-modal)]",
          "transition-all duration-200",
          sizeStyles[size],
          open ? "scale-100 translate-y-0" : "scale-95 translate-y-4",
=======
          'relative z-[var(--z-modal)] w-full rounded-xl',
          'bg-[var(--bg-secondary)] border border-[var(--border-primary)]',
          'shadow-[var(--shadow-modal)]',
          'transition-all duration-200',
          sizeStyles[size],
          open ? 'scale-100 translate-y-0' : 'scale-95 translate-y-4'
>>>>>>> origin/fix/scenario-tests-properly
        )}
      >
        {/* Header */}
        {(title || subtitle) && (
          <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--border-primary)]">
            <div>
<<<<<<< HEAD
              {title && (
                <h2 className="text-lg font-semibold text-[var(--text-primary)]">{title}</h2>
              )}
=======
              {title && <h2 className="text-lg font-semibold text-[var(--text-primary)]">{title}</h2>}
>>>>>>> origin/fix/scenario-tests-properly
              {subtitle && <p className="text-sm text-[var(--text-tertiary)] mt-0.5">{subtitle}</p>}
            </div>
            <button
              onClick={onClose}
<<<<<<< HEAD
              className="p-2 rounded-lg hover:bg-[var(--bg-elevated)] text-[var(--text-tertiary)] hover:text-[var(--text-primary)] transition-colors focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
              aria-label="Close"
              type="button"
            >
              <X className="w-5 h-5" />
=======
              className="p-1.5 rounded-lg hover:bg-[var(--bg-elevated)] text-[var(--text-tertiary)] hover:text-[var(--text-primary)] transition-colors"
            >
              <X className="w-4 h-4" />
>>>>>>> origin/fix/scenario-tests-properly
            </button>
          </div>
        )}

        {/* Body */}
<<<<<<< HEAD
        <div className="px-6 py-4 max-h-[70vh] overflow-y-auto">{children}</div>
=======
        <div className="px-6 py-4 max-h-[70vh] overflow-y-auto">
          {children}
        </div>
>>>>>>> origin/fix/scenario-tests-properly

        {/* Footer */}
        {footer && (
          <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-[var(--border-primary)]">
            {footer}
          </div>
        )}
      </div>
    </div>
<<<<<<< HEAD
  );
=======
  )
>>>>>>> origin/fix/scenario-tests-properly
}
