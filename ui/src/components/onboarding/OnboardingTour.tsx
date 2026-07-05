import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { X, ChevronRight, ChevronLeft, Zap, LayoutDashboard, FolderPlus, HelpCircle, Activity, CheckCircle } from 'lucide-react'
import { cn } from '../../utils/helpers'

const ONBOARDING_KEY = 'etap-ai-onboarding-completed'

interface TourStep {
  id: string
  title: string
  description: string
  icon: React.ElementType
  target?: string
  action?: () => void
  position: 'top' | 'bottom' | 'left' | 'right'
}

export function OnboardingTour() {
  const [show, setShow] = useState(false)
  const [currentStep, setCurrentStep] = useState(0)
  const [completed, setCompleted] = useState(false)
  const navigate = useNavigate()

  const steps: TourStep[] = [
    {
      id: 'welcome',
      title: 'Welcome to Ahmed etap Platform',
      description: 'Enterprise-grade autonomous engineering intelligence for power systems. This tour will guide you through the key features.',
      icon: Zap,
      position: 'bottom',
    },
    {
      id: 'sidebar',
      title: 'Navigation Sidebar',
      description: 'Access all modules from the sidebar. It\'s organized into sections: main navigation, engineering, integration, and system tools. You can collapse it for more workspace.',
      icon: LayoutDashboard,
      target: 'sidebar',
      position: 'right',
    },
    {
      id: 'projects',
      title: 'Project Management',
      description: 'Create and manage power system projects. Each project stores your system configuration, study results, and reports in one place.',
      icon: FolderPlus,
      action: () => navigate('/projects'),
      position: 'bottom',
    },
    {
      id: 'studies',
      title: 'Engineering Studies',
      description: 'Run real engineering computations: Load Flow, Short Circuit, Arc Flash, Harmonic Analysis, and more. Select a study type and configure parameters.',
      icon: Zap,
      action: () => navigate('/studies'),
      position: 'bottom',
    },
    {
      id: 'help',
      title: 'Smart Help',
      description: 'Press F1 anytime to open contextual help. When errors occur, the help system maps them to relevant troubleshooting guides.',
      icon: HelpCircle,
      position: 'bottom',
    },
    {
      id: 'status',
      title: 'Backend Status',
      description: 'Monitor the connection to the engineering service. The status indicator in the sidebar shows real-time connectivity.',
      icon: Activity,
      action: () => navigate('/diagnostics'),
      position: 'bottom',
    },
    {
      id: 'complete',
      title: 'You\'re All Set!',
      description: 'You\'re ready to start using Ahmed etap. Press Ctrl+K anytime to open the command palette for quick navigation.',
      icon: CheckCircle,
      position: 'bottom',
    },
  ]

  useEffect(() => {
    const hasCompleted = localStorage.getItem(ONBOARDING_KEY)
    if (!hasCompleted) {
      const timer = setTimeout(() => setShow(true), 1000)
      return () => clearTimeout(timer)
    }
    return undefined  // QUALITY v2.1.1: explicit return for TS7030 (strict mode)
  }, [])

  const handleNext = () => {
    if (currentStep < steps.length - 1) {
      const nextStep = steps[currentStep + 1]
      if (nextStep.action) nextStep.action()
      setCurrentStep(currentStep + 1)
    } else {
      handleComplete()
    }
  }

  const handlePrev = () => {
    if (currentStep > 0) setCurrentStep(currentStep - 1)
  }

  const handleComplete = () => {
    localStorage.setItem(ONBOARDING_KEY, 'true')
    setCompleted(true)
    setTimeout(() => setShow(false), 300)
  }

  // handleSkip is intentionally identical to handleComplete — both dismiss
  // the tour and mark it as seen. Kept as a separate name for call-site
  // readability (Skip vs Complete convey different user intents).
  const handleSkip = handleComplete

  const handleRestart = () => {
    localStorage.removeItem(ONBOARDING_KEY)
    setCurrentStep(0)
    setCompleted(false)
    setShow(true)
  }

  // Expose restart function globally
  useEffect(() => {
    const w = globalThis as unknown as Record<string, unknown>
    w.__restartOnboarding = handleRestart
    return () => { delete (w as Record<string, unknown>).__restartOnboarding }
  }, [])

  // Keyboard shortcuts: Esc = skip, Enter = next, Backspace = prev
  useEffect(() => {
    if (!show) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        handleSkip()
      } else if (e.key === 'Enter') {
        e.preventDefault()
        handleNext()
      } else if (e.key === 'Backspace' && currentStep > 0) {
        e.preventDefault()
        handlePrev()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [show, currentStep])

  if (!show) return null

  const step = steps[currentStep]
  const StepIcon = step.icon
  const isLast = currentStep === steps.length - 1

  return (
    <div
      className="fixed inset-0 z-[200] flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="onboarding-title"
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/80 backdrop-blur-md"
        onClick={handleSkip}
        onKeyDown={(e) => { if (e.key === 'Escape' || e.key === 'Enter') handleSkip() }}  // SonarCloud S1082: a11y — keyboard listener for click handler
        role="button"
        tabIndex={0}
        aria-label="Skip onboarding"
      />

      {/* Modal card */}
      <div
        className={cn(
          'relative z-[201] w-full max-w-[520px]',
          'bg-[var(--bg-secondary)] border border-[var(--border-secondary)]',
          'rounded-2xl overflow-hidden',
          'shadow-[0_24px_80px_-12px_rgba(0,0,0,0.7)]',
          'ring-1 ring-white/5',
          'transition-all duration-300 ease-out',
          completed ? 'opacity-0 scale-95 translate-y-2' : 'opacity-100 scale-100 translate-y-0'
        )}
      >
        {/* Decorative top accent gradient */}
        <div
          className={cn(
            'absolute top-0 left-0 right-0 h-[3px]',
            isLast
              ? 'bg-gradient-to-r from-emerald-500 via-green-400 to-emerald-500'
              : 'bg-gradient-to-r from-[var(--accent-primary)] via-cyan-400 to-[var(--accent-primary)]'
          )}
          aria-hidden="true"
        />

        {/* Subtle glow halo behind icon area */}
        <div
          className="absolute -top-20 -left-20 w-64 h-64 rounded-full opacity-20 blur-3xl pointer-events-none"
          style={{ background: isLast ? '#22c55e' : 'var(--accent-primary)' }}
          aria-hidden="true"
        />

        {/* Header: step indicator + close */}
        <div className="relative flex items-center justify-between px-7 pt-6 pb-2">
          <div className="flex items-center gap-2.5">
            {/* Step counter pill */}
            <span className={cn(
              'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold tracking-wide uppercase',
              isLast
                ? 'bg-green-500/15 text-green-400'
                : 'bg-[var(--accent-glow)] text-[var(--accent-primary)]'
            )}>
              <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse" />
              Step {currentStep + 1} / {steps.length}
            </span>
          </div>
          <button
            onClick={handleSkip}
            aria-label="Close tour"
            className="p-1.5 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-elevated)] transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Progress bar — discrete segments, not thin bars */}
        <div className="relative px-7 pb-1">
          <div className="flex gap-1.5">
            {steps.map((s, i) => (
              <div
                key={s.id}
                className={cn(
                  'h-1 flex-1 rounded-full transition-all duration-500',
                  i < currentStep && 'bg-[var(--accent-primary)]',
                  i === currentStep && (isLast ? 'bg-green-400' : 'bg-[var(--accent-primary)]'),
                  i > currentStep && 'bg-[var(--border-primary)]'
                )}
              />
            ))}
          </div>
        </div>

        {/* Body: icon + content */}
        <div className="relative px-7 pt-6 pb-5">
          <div className="flex items-start gap-5">
            {/* Icon tile */}
            <div className={cn(
              'shrink-0 w-16 h-16 rounded-2xl flex items-center justify-center',
              'ring-1 ring-inset transition-colors',
              isLast
                ? 'bg-green-500/10 text-green-400 ring-green-500/20'
                : 'bg-[var(--accent-glow)] text-[var(--accent-primary)] ring-[var(--accent-primary)]/20'
            )}>
              <StepIcon className="w-8 h-8" strokeWidth={1.75} />
            </div>

            {/* Title + description */}
            <div className="flex-1 min-w-0 pt-1">
              <h3
                id="onboarding-title"
                className="text-xl font-semibold text-[var(--text-primary)] leading-tight mb-2 tracking-tight"
              >
                {step.title}
              </h3>
              <p className="text-[13.5px] text-[var(--text-secondary)] leading-relaxed">
                {step.description}
              </p>
            </div>
          </div>
        </div>

        {/* Footer: actions */}
        <div className="relative flex items-center justify-between px-7 py-4 border-t border-[var(--border-primary)] bg-[var(--bg-tertiary)]/40">
          <button
            onClick={handleSkip}
            className="text-xs font-medium text-[var(--text-muted)] hover:text-[var(--text-secondary)] transition-colors px-2 py-1.5 -ml-2"
          >
            Skip tour
          </button>

          <div className="flex items-center gap-2">
            {currentStep > 0 && (
              <button
                onClick={handlePrev}
                className="flex items-center gap-1 px-3.5 py-2 text-xs font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-elevated)] rounded-lg transition-colors"
              >
                <ChevronLeft className="w-3.5 h-3.5" strokeWidth={2.5} />
                Back
              </button>
            )}
            <button
              onClick={handleNext}
              className={cn(
                'flex items-center gap-1.5 px-5 py-2 text-[13px] font-semibold rounded-lg transition-all',
                'shadow-lg active:scale-95',
                isLast
                  ? 'bg-green-600 hover:bg-green-500 text-white shadow-green-900/30'
                  : 'bg-[var(--accent-primary)] hover:brightness-110 text-black shadow-cyan-900/30'
              )}
            >
              {isLast ? 'Get Started' : 'Next'}
              {isLast
                ? <CheckCircle className="w-4 h-4" strokeWidth={2.5} />
                : <ChevronRight className="w-4 h-4" strokeWidth={2.5} />
              }
            </button>
          </div>
        </div>

        {/* Keyboard hint */}
        <div className="relative px-7 pb-3 -mt-1 text-[10px] text-[var(--text-muted)] text-center">
          Press <kbd className="px-1.5 py-0.5 rounded bg-[var(--bg-elevated)] border border-[var(--border-primary)] font-mono text-[10px]">Esc</kbd> to skip · <kbd className="px-1.5 py-0.5 rounded bg-[var(--bg-elevated)] border border-[var(--border-primary)] font-mono text-[10px]">↵</kbd> to continue
        </div>
      </div>
    </div>
  )
}
