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

  const handleSkip = () => {
    localStorage.setItem(ONBOARDING_KEY, 'true')
    setCompleted(true)
    setTimeout(() => setShow(false), 300)
  }

  const handleRestart = () => {
    localStorage.removeItem(ONBOARDING_KEY)
    setCurrentStep(0)
    setCompleted(false)
    setShow(true)
  }

  // Expose restart function globally
  useEffect(() => {
    const w = window as unknown as Record<string, unknown>
    w.__restartOnboarding = handleRestart
    return () => { delete (w as Record<string, unknown>).__restartOnboarding }
  }, [])

  if (!show) return null

  const step = steps[currentStep]
  const StepIcon = step.icon
  const isLast = currentStep === steps.length - 1

  return (
    <div className="fixed inset-0 z-[200] flex items-center justify-center">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={handleSkip} />

      <div className={cn(
        'relative z-[201] w-full max-w-md mx-4',
        'bg-[var(--bg-secondary)] border border-[var(--border-secondary)] rounded-2xl',
        'shadow-2xl shadow-black/50',
        'transition-all duration-300',
        completed ? 'opacity-0 scale-95' : 'opacity-100 scale-100'
      )}>
        {/* Progress */}
        <div className="flex gap-1 px-6 pt-5">
          {steps.map((_, i) => (
            <div
              key={i}
              className={cn(
                'h-1 flex-1 rounded-full transition-all duration-300',
                i <= currentStep ? 'bg-[var(--accent-primary)]' : 'bg-[var(--border-primary)]'
              )}
            />
          ))}
        </div>

        {/* Close button */}
        <button
          onClick={handleSkip}
          className="absolute top-4 right-4 p-1.5 rounded-lg hover:bg-[var(--bg-elevated)] text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors"
        >
          <X className="w-4 h-4" />
        </button>

        {/* Content */}
        <div className="px-6 py-6">
          <div className={cn(
            'w-14 h-14 rounded-2xl flex items-center justify-center mb-4',
            isLast
              ? 'bg-green-500/10 text-green-400'
              : 'bg-[var(--accent-glow)] text-[var(--accent-primary)]'
          )}>
            <StepIcon className="w-7 h-7" />
          </div>

          <h3 className="text-lg font-semibold text-[var(--text-primary)] mb-2">
            {step.title}
          </h3>
          <p className="text-sm text-[var(--text-secondary)] leading-relaxed">
            {step.description}
          </p>
        </div>

        {/* Navigation */}
        <div className="flex items-center justify-between px-6 pb-5">
          <button
            onClick={handleSkip}
            className="text-xs text-[var(--text-muted)] hover:text-[var(--text-secondary)] transition-colors"
          >
            Skip tour
          </button>

          <div className="flex items-center gap-2">
            {currentStep > 0 && (
              <button
                onClick={handlePrev}
                className="flex items-center gap-1 px-3 py-1.5 text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] rounded-lg transition-colors"
              >
                <ChevronLeft className="w-3.5 h-3.5" />
                Back
              </button>
            )}
            <button
              onClick={handleNext}
              className={cn(
                'flex items-center gap-1.5 px-4 py-2 text-sm font-medium rounded-lg transition-all',
                isLast
                  ? 'bg-green-600 hover:bg-green-500 text-white'
                  : 'bg-[var(--accent-primary)] hover:opacity-90 text-black'
              )}
            >
              {isLast ? 'Get Started' : 'Next'}
              {!isLast && <ChevronRight className="w-3.5 h-3.5" />}
            </button>
          </div>
        </div>

        {/* Step counter */}
        <div className="text-center pb-4 text-[10px] text-[var(--text-muted)]">
          {currentStep + 1} of {steps.length}
        </div>
      </div>
    </div>
  )
}
