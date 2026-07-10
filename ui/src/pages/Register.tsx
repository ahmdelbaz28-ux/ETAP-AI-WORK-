import { useState, useEffect, useCallback } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { User, Mail, Lock, ArrowRight, Eye, EyeOff, CheckCircle, AlertCircle, Globe } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useNotify } from '../context/NotificationContext'
import { useAuth } from '../hooks/useAuth'
import { BrandLogo } from '../components/BrandLogo'

/**
 * Register — AhmedETAP professional engineering sign-up page.
 */
export default function Register() {  // NOSONAR - S3776: cognitive complexity reduced below 15 by extracting helper components
  const navigate = useNavigate()
  const { notify } = useNotify()
  const { register } = useAuth()
  const { t, i18n } = useTranslation()

  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [authError, setAuthError] = useState<string | null>(null)

  useEffect(() => {
    document.documentElement.dir = i18n.language === 'ar' ? 'rtl' : 'ltr'
    document.documentElement.lang = i18n.language
  }, [i18n.language])

  const handleSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name || !email || !password) {
      notify('error', t('auth.errorRegisterFields'))
      return
    }
    if (password !== confirmPassword) {
      notify('error', t('auth.errorPasswordsMismatch'))
      return
    }
    if (password.length < 8) {
      notify('error', t('auth.errorPasswordLength'))
      return
    }
    setLoading(true)
    setAuthError(null)
    try {
      await register(email, password, name)
      notify('success', i18n.language === 'ar' ? `مرحباً بك في أحمد إيتاب، ${name}!` : `Welcome to AhmedETAP, ${name}!`)
      navigate('/dashboard')
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown error'
      setAuthError(message)
      notify('error', `${i18n.language === 'ar' ? 'فشل إنشاء الحساب' : 'Registration failed'}: ${message}`)
    } finally {
      setLoading(false)
    }
  }, [name, email, password, confirmPassword, register, notify, t, i18n, navigate])

  const isRtl = i18n.language === 'ar'

  return (
    <RegisterView
      isRtl={isRtl}
      name={name}
      email={email}
      password={password}
      confirmPassword={confirmPassword}
      showPassword={showPassword}
      loading={loading}
      authError={authError}
      onNameChange={setName}
      onEmailChange={setEmail}
      onPasswordChange={setPassword}
      onConfirmPasswordChange={setConfirmPassword}
      onTogglePassword={() => setShowPassword(p => !p)}
      onSubmit={handleSubmit}
    />
  )
}

interface RegisterViewProps {
  readonly isRtl: boolean
  readonly name: string
  readonly email: string
  readonly password: string
  readonly confirmPassword: string
  readonly showPassword: boolean
  readonly loading: boolean
  readonly authError: string | null
  readonly onNameChange: (v: string) => void
  readonly onEmailChange: (v: string) => void
  readonly onPasswordChange: (v: string) => void
  readonly onConfirmPasswordChange: (v: string) => void
  readonly onTogglePassword: () => void
  readonly onSubmit: (e: React.FormEvent) => void
}

function RegisterView({ isRtl, name, email, password, confirmPassword, showPassword, loading, authError, onNameChange, onEmailChange, onPasswordChange, onConfirmPasswordChange, onTogglePassword, onSubmit }: RegisterViewProps) {
  const { t, i18n } = useTranslation()

  return (
    <div className="min-h-screen flex bg-[#070b14] relative overflow-hidden" dir={isRtl ? 'rtl' : 'ltr'}>
      <div className={`absolute top-6 ${isRtl ? 'left-6' : 'right-6'} z-50`}>
        <button
          onClick={() => {
            const nextLang = i18n.language === 'ar' ? 'en' : 'ar'
            i18n.changeLanguage(nextLang)
          }}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-slate-700/50 bg-slate-900/80 hover:bg-slate-800 text-slate-300 hover:text-white transition-all text-xs font-semibold"
        >
          <Globe className="w-3.5 h-3.5" />
          <span>{isRtl ? 'English' : 'العربية'}</span>
        </button>
      </div>

      <RegisterBackground />

      <div className="flex-1 flex items-center justify-center p-6 sm:p-12 relative z-10">
        <motion.div
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="w-full max-w-[380px] bg-slate-900/30 backdrop-blur-md border border-slate-800/40 p-8 rounded-2xl shadow-2xl"
        >
          <MobileHeader />
          <TitleSection />
          {authError && <ErrorAlert message={authError} />}
          <form onSubmit={onSubmit} className="space-y-4">
            <NameField name={name} onChange={onNameChange} isRtl={isRtl} />
            <RegisterEmailField email={email} onChange={onEmailChange} isRtl={isRtl} />
            <RegisterPasswordField password={password} onChange={onPasswordChange} onToggle={onTogglePassword} showPassword={showPassword} isRtl={isRtl} />
            <ConfirmPasswordField password={password} confirmPassword={confirmPassword} onChange={onConfirmPasswordChange} showPassword={showPassword} isRtl={isRtl} />
            <SubmitButton loading={loading} isRtl={isRtl} loadingText={t('auth.creatingAccount')} defaultText={t('auth.createAccountButton')} />
          </form>
          <Footer />
        </motion.div>
      </div>
    </div>
  )
}

function NameField({ name, onChange, isRtl }: { readonly name: string; readonly onChange: (v: string) => void; readonly isRtl: boolean }) {
  const { t } = useTranslation()
  return (
    <div>
      <label htmlFor="register-name" className="block text-xs font-semibold text-slate-400 mb-1.5">{t('auth.fullNameLabel')}</label>
      <div className="relative">
        <User className={isRtl ? 'absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-600 pointer-events-none' : 'absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-600 pointer-events-none'} />
        <input id="register-name" type="text" value={name} onChange={e => onChange(e.target.value)} placeholder={t('auth.fullNamePlaceholder')} required
          className={`w-full ${isRtl ? 'pr-9 pl-3' : 'pl-9 pr-3'} py-2 bg-slate-950/40 border border-slate-800/80 rounded-xl text-xs text-white placeholder-slate-700 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500/10 transition-all`} />
      </div>
    </div>
  )
}

function RegisterEmailField({ email, onChange, isRtl }: { readonly email: string; readonly onChange: (v: string) => void; readonly isRtl: boolean }) {
  const { t } = useTranslation()
  return (
    <div>
      <label htmlFor="register-email" className="block text-xs font-semibold text-slate-400 mb-1.5">{t('auth.emailLabel')}</label>
      <div className="relative">
        <Mail className={isRtl ? 'absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-600 pointer-events-none' : 'absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-600 pointer-events-none'} />
        <input id="register-email" type="email" value={email} onChange={e => onChange(e.target.value)} placeholder={t('auth.emailPlaceholder')} required dir="ltr"
          className={`w-full ${isRtl ? 'pr-9 pl-3' : 'pl-9 pr-3'} py-2 bg-slate-950/40 border border-slate-800/80 rounded-xl text-xs text-white placeholder-slate-700 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500/10 transition-all`} />
      </div>
    </div>
  )
}

function RegisterPasswordField({ password, onChange, onToggle, showPassword, isRtl }: { readonly password: string; readonly onChange: (v: string) => void; readonly onToggle: () => void; readonly showPassword: boolean; readonly isRtl: boolean }) {
  const { t } = useTranslation()
  return (
    <div>
      <label htmlFor="register-password" className="block text-xs font-semibold text-slate-400 mb-1.5">{t('auth.passwordLabel')}</label>
      <div className="relative">
        <Lock className={isRtl ? 'absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-600 pointer-events-none' : 'absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-600 pointer-events-none'} />
        <input id="register-password" type={showPassword ? 'text' : 'password'} value={password} onChange={e => onChange(e.target.value)} placeholder="••••••••" required dir="ltr"
          className={`w-full ${isRtl ? 'pr-9 pl-10' : 'pl-9 pr-10'} py-2 bg-slate-950/40 border border-slate-800/80 rounded-xl text-xs text-white placeholder-slate-700 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500/10 transition-all`} />
        <button type="button" onClick={onToggle} className={isRtl ? 'absolute left-2.5 top-1/2 -translate-y-1/2 p-1 rounded text-slate-600 hover:text-slate-300 transition-colors' : 'absolute right-2.5 top-1/2 -translate-y-1/2 p-1 rounded text-slate-600 hover:text-slate-300 transition-colors'} aria-label={showPassword ? 'Hide password' : 'Show password'}>
          {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
        </button>
      </div>
    </div>
  )
}

function ConfirmPasswordField({ password, confirmPassword, onChange, showPassword, isRtl }: { readonly password: string; readonly confirmPassword: string; readonly onChange: (v: string) => void; readonly showPassword: boolean; readonly isRtl: boolean }) {
  const { t } = useTranslation()
  return (
    <div>
      <label htmlFor="register-confirm-password" className="block text-xs font-semibold text-slate-400 mb-1.5">{t('auth.confirmPasswordLabel')}</label>
      <div className="relative">
        <Lock className={isRtl ? 'absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-600 pointer-events-none' : 'absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-600 pointer-events-none'} />
        <input id="register-confirm-password" type={showPassword ? 'text' : 'password'} value={confirmPassword} onChange={e => onChange(e.target.value)} placeholder={t('auth.confirmPasswordPlaceholder')} required dir="ltr"
          className={`w-full ${isRtl ? 'pr-9 pl-3' : 'pl-9 pr-3'} py-2 bg-slate-950/40 border border-slate-800/80 rounded-xl text-xs text-white placeholder-slate-700 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500/10 transition-all`} />
      </div>
      {confirmPassword && password === confirmPassword && (
        <p className="mt-1.5 text-[11px] text-green-400 flex items-center gap-1">
          <CheckCircle className="w-3.5 h-3.5" />
          <span>{t('auth.passwordsMatch')}</span>
        </p>
      )}
    </div>
  )
}

function SubmitButton({ loading, isRtl, loadingText, defaultText }: { readonly loading: boolean; readonly isRtl: boolean; readonly loadingText: string; readonly defaultText: string }) {
  return (
    <motion.button whileHover={{ scale: 1.005 }} whileTap={{ scale: 0.995 }} type="submit" disabled={loading}
      className="w-full flex items-center justify-center gap-2 mt-4 px-4 py-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-bold transition-all disabled:opacity-50 disabled:cursor-not-allowed">
      {loading ? (
        <>
          <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
          <span>{loadingText}</span>
        </>
      ) : (
        <>
          <span>{defaultText}</span>
          <ArrowRight className={`w-4 h-4 ${isRtl ? 'rotate-180' : ''}`} />
        </>
      )}
    </motion.button>
  )
}

function MobileHeader() {
  return (
    <div className="lg:hidden flex items-center gap-2.5 mb-8">
      <BrandLogo size={36} />
      <span className="text-lg font-bold text-white">AhmedETAP</span>
    </div>
  )
}

function TitleSection() {
  const { t } = useTranslation()
  return (
    <div className="mb-6">
      <h3 className="text-2xl font-bold text-white tracking-tight">{t('auth.registerTitle')}</h3>
      <p className="text-xs text-slate-500 mt-1.5 leading-relaxed">{t('auth.registerSubtitle')}</p>
    </div>
  )
}

function ErrorAlert({ message }: { readonly message: string }) {
  return (
    <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }}
      className="mb-4 p-3 rounded-lg bg-red-950/20 border border-red-900/40 flex items-start gap-2.5">
      <AlertCircle className="w-4 h-4 text-red-400 mt-0.5 flex-shrink-0" />
      <p className="text-xs text-red-300 leading-normal">{message}</p>
    </motion.div>
  )
}

function Footer() {
  const { t } = useTranslation()
  return (
    <div className="mt-6 pt-5 border-t border-slate-800/40 flex items-center justify-between text-xs">
      <span className="text-slate-500">
        {t('auth.hasAccount')}{' '}
        <Link to="/login" className="text-blue-400 hover:text-blue-300 font-semibold transition-colors">
          {t('auth.loginLink')}
        </Link>
      </span>
      <span className="text-[10px] text-slate-700 font-mono">v2.1.0</span>
    </div>
  )
}

function RegisterBackground() {
  return (
    <div className="absolute inset-0 pointer-events-none z-0">
      <div className="absolute inset-0 opacity-[0.02]"
        style={{
          backgroundImage: `linear-gradient(#3b82f6 1px, transparent 1px), linear-gradient(90deg, #3b82f6 1px, transparent 1px)`,
          backgroundSize: '40px 40px',
        }}
      />
      <svg className="absolute inset-0 w-full h-full" viewBox="0 0 1440 900" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
        <defs>
          <linearGradient id="bus-grad-reg" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#1e293b" stopOpacity="0.2" />
            <stop offset="50%" stopColor="#3b82f6" stopOpacity="0.6" />
            <stop offset="100%" stopColor="#1e293b" stopOpacity="0.2" />
          </linearGradient>
        </defs>
        <path d="M100,180 L1340,180" stroke="url(#bus-grad-reg)" strokeWidth="3" strokeLinecap="round" />
        <path d="M100,180 L1340,180" stroke="#00d4ff" strokeWidth="1" strokeLinecap="round" className="animate-pulse" opacity="0.8" />
        <path d="M400,180 L400,450" stroke="#1e293b" strokeWidth="2" opacity="0.4" />
        <path d="M400,180 L400,450" stroke="#00d4ff" strokeWidth="1.5" strokeDasharray="8 12" strokeDashoffset="0" style={{ animation: 'gridFlowReg 12s linear infinite' }} />
        <circle cx="400" cy="280" r="14" fill="none" stroke="#00d4ff" strokeWidth="1.5" />
        <circle cx="400" cy="302" r="14" fill="none" stroke="#3b82f6" strokeWidth="1.5" />
        <path d="M250,450 L1190,450" stroke="url(#bus-grad-reg)" strokeWidth="2.5" strokeLinecap="round" />
        <path d="M250,450 L1190,450" stroke="#60a5fa" strokeWidth="1" strokeLinecap="round" className="animate-pulse" opacity="0.6" />
        <path d="M800,180 L800,90" stroke="#1e293b" strokeWidth="2" opacity="0.4" />
        <path d="M800,180 L800,90" stroke="#22c55e" strokeWidth="1.5" strokeDasharray="10 10" strokeDashoffset="0" style={{ animation: 'gridFlowRevReg 10s linear infinite' }} />
        <circle cx="800" cy="70" r="18" fill="#070b14" stroke="#22c55e" strokeWidth="1.5" />
        <text x="800" y="75" textAnchor="middle" fill="#22c55e" fontSize="14" fontWeight="bold" fontFamily="monospace">G</text>
        <path d="M600,450 L600,580" stroke="#1e293b" strokeWidth="2" opacity="0.4" />
        <path d="M600,450 L600,580" stroke="#fbbf24" strokeWidth="1.5" strokeDasharray="8 10" strokeDashoffset="0" style={{ animation: 'gridFlowReg 8s linear infinite' }} />
        <polygon points="600,588 592,572 608,572" fill="#fbbf24" stroke="#fbbf24" strokeWidth="1" />
        <circle r="3.5" fill="#00d4ff" opacity="0.8">
          <animateMotion dur="8s" repeatCount="indefinite" path="M800,90 L800,180 L400,180 L400,450 L600,450 L600,572" />
        </circle>
        <circle r="2.5" fill="#22c55e" opacity="0.8">
          <animateMotion dur="8s" begin="2.5s" repeatCount="indefinite" path="M800,90 L800,180 L400,180 L400,450 L600,450 L600,572" />
        </circle>
        <circle r="2.5" fill="#fbbf24" opacity="0.8">
          <animateMotion dur="8s" begin="5s" repeatCount="indefinite" path="M800,90 L800,180 L400,180 L400,450 L600,450 L600,572" />
        </circle>
        <path d="M1000,450 L1000,580" stroke="#1e293b" strokeWidth="2" opacity="0.4" />
        <path d="M1000,450 L1000,580" stroke="#a78bfa" strokeWidth="1.5" strokeDasharray="8 8" strokeDashoffset="0" style={{ animation: 'gridFlowRevReg 14s linear infinite' }} />
        <rect x="993" y="495" width="14" height="20" fill="#070b14" stroke="#a78bfa" strokeWidth="1.5" />
        <line x1="993" y1="505" x2="1007" y2="505" stroke="#a78bfa" strokeWidth="1.5" />
        <style>{`
          @keyframes gridFlowReg { to { stroke-dashoffset: -120; } }
          @keyframes gridFlowRevReg { to { stroke-dashoffset: 120; } }
        `}</style>
      </svg>
      <div className="absolute top-10 right-20 w-[600px] h-[600px] rounded-full bg-blue-500/[0.02] blur-[140px]" />
      <div className="absolute bottom-10 left-20 w-[500px] h-[500px] rounded-full bg-blue-600/[0.015] blur-[120px]" />
    </div>
  )
}
