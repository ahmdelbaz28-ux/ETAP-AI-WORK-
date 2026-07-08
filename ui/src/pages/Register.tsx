import { useState, useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { User, Mail, Lock, ArrowRight, Eye, EyeOff, CheckCircle, AlertCircle, Globe, ShieldCheck } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useNotify } from '../context/NotificationContext'
import { useAuth } from '../hooks/useAuth'
import { BrandLogo } from '../components/BrandLogo'

/**
 * Register — AhmedETAP professional engineering sign-up page.
 *
 * Features:
 * - Full i18n support (dynamic Arabic and English layouts)
 * - Professional EN/AR selector at the top-right
 * - Elite CAD-style power grid background animation (vector flow simulation)
 */
export default function Register() {
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

  // Sync html dir and lang attribute on language switch
  useEffect(() => {
    document.documentElement.dir = i18n.language === 'ar' ? 'rtl' : 'ltr'
    document.documentElement.lang = i18n.language
  }, [i18n.language])

  const handleSubmit = async (e: React.FormEvent) => {
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
  }

  const isRtl = i18n.language === 'ar'

  const renderRegisterForm = () => (
    <>
      {/* Name Field */}
      <div>
        <label htmlFor="register-name" className="block text-xs font-semibold text-slate-400 mb-1.5">
          {t('auth.fullNameLabel')}
        </label>
        <div className="relative">
          <User className={`absolute ${isRtl ? 'right-3' : 'left-3'} top-1/2 -translate-y-1/2 w-4 h-4 text-slate-600 pointer-events-none`} />
          <input
            id="register-name"
            type="text"
            value={name}
            onChange={e => setName(e.target.value)}
            placeholder={t('auth.fullNamePlaceholder')}
            required
            className={`w-full ${isRtl ? 'pr-9 pl-3' : 'pl-9 pr-3'} py-2 bg-slate-950/40 border border-slate-800/80 rounded-xl text-xs text-white placeholder-slate-700 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500/10 transition-all`}
          />
        </div>
      </div>

      {/* Email Field */}
      <div>
        <label htmlFor="register-email" className="block text-xs font-semibold text-slate-400 mb-1.5">
          {t('auth.emailLabel')}
        </label>
        <div className="relative">
          <Mail className={`absolute ${isRtl ? 'right-3' : 'left-3'} top-1/2 -translate-y-1/2 w-4 h-4 text-slate-600 pointer-events-none`} />
          <input
            id="register-email"
            type="email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            placeholder={t('auth.emailPlaceholder')}
            required
            dir="ltr"
            className={`w-full ${isRtl ? 'pr-9 pl-3' : 'pl-9 pr-3'} py-2 bg-slate-950/40 border border-slate-800/80 rounded-xl text-xs text-white placeholder-slate-700 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500/10 transition-all`}
          />
        </div>
      </div>

      {/* Password Field */}
      <div>
        <label htmlFor="register-password" className="block text-xs font-semibold text-slate-400 mb-1.5">
          {t('auth.passwordLabel')}
        </label>
        <div className="relative">
          <Lock className={`absolute ${isRtl ? 'right-3' : 'left-3'} top-1/2 -translate-y-1/2 w-4 h-4 text-slate-600 pointer-events-none`} />
          <input
            id="register-password"
            type={showPassword ? 'text' : 'password'}
            value={password}
            onChange={e => setPassword(e.target.value)}
            placeholder="••••••••"
            required
            dir="ltr"
            className={`w-full ${isRtl ? 'pr-9 pl-10' : 'pl-9 pr-10'} py-2 bg-slate-950/40 border border-slate-800/80 rounded-xl text-xs text-white placeholder-slate-700 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500/10 transition-all`}
          />
          <button
            type="button"
            onClick={() => setShowPassword(p => !p)}
            className={`absolute ${isRtl ? 'left-2.5' : 'right-2.5'} top-1/2 -translate-y-1/2 p-1 rounded text-slate-600 hover:text-slate-300 transition-colors`}
            aria-label={showPassword ? 'Hide password' : 'Show password'}
          >
            {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Confirm Password Field */}
      <div>
        <label htmlFor="register-confirm-password" className="block text-xs font-semibold text-slate-400 mb-1.5">
          {t('auth.confirmPasswordLabel')}
        </label>
        <div className="relative">
          <Lock className={`absolute ${isRtl ? 'right-3' : 'left-3'} top-1/2 -translate-y-1/2 w-4 h-4 text-slate-600 pointer-events-none`} />
          <input
            id="register-confirm-password"
            type={showPassword ? 'text' : 'password'}
            value={confirmPassword}
            onChange={e => setConfirmPassword(e.target.value)}
            placeholder={t('auth.confirmPasswordPlaceholder')}
            required
            dir="ltr"
            className={`w-full ${isRtl ? 'pr-9 pl-3' : 'pl-9 pr-3'} py-2 bg-slate-950/40 border border-slate-800/80 rounded-xl text-xs text-white placeholder-slate-700 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500/10 transition-all`}
          />
        </div>
        {confirmPassword && password === confirmPassword && (
          <p className="mt-1.5 text-[11px] text-green-400 flex items-center gap-1">
            <CheckCircle className="w-3.5 h-3.5" />
            <span>{t('auth.passwordsMatch')}</span>
          </p>
        )}
      </div>
    </>
  )

  return (
    <div className="min-h-screen flex bg-[#070b14] relative overflow-hidden" dir={isRtl ? 'rtl' : 'ltr'}>
      {/* Lang Selector */}
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

      {/* Background */}
      <RegisterBackground isRtl={isRtl} />

      {/* SECOND PANEL — Form */}
      <div className="flex-1 flex items-center justify-center p-6 sm:p-12 relative z-10">
        <motion.div
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="w-full max-w-[380px] bg-slate-900/30 backdrop-blur-md border border-slate-800/40 p-8 rounded-2xl shadow-2xl"
        >
          <div className="lg:hidden flex items-center gap-2.5 mb-8">
            <BrandLogo size={36} />
            <span className="text-lg font-bold text-white">AhmedETAP</span>
          </div>

          <div className="mb-6">
            <h3 className="text-2xl font-bold text-white tracking-tight">{t('auth.registerTitle')}</h3>
            <p className="text-xs text-slate-500 mt-1.5 leading-relaxed">{t('auth.registerSubtitle')}</p>
          </div>

          {authError && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              className="mb-4 p-3 rounded-lg bg-red-950/20 border border-red-900/40 flex items-start gap-2.5"
            >
              <AlertCircle className="w-4 h-4 text-red-400 mt-0.5 flex-shrink-0" />
              <p className="text-xs text-red-300 leading-normal">{authError}</p>
            </motion.div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            {renderRegisterForm()}
            <motion.button
              whileHover={{ scale: 1.005 }}
              whileTap={{ scale: 0.995 }}
              type="submit"
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 mt-4 px-4 py-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-bold transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  <span>{t('auth.creatingAccount')}</span>
                </>
              ) : (
                <>
                  <span>{t('auth.createAccountButton')}</span>
                  <ArrowRight className={`w-4 h-4 ${isRtl ? 'rotate-180' : ''}`} />
                </>
              )}
            </motion.button>
          </form>

          <div className="mt-6 pt-5 border-t border-slate-800/40 flex items-center justify-between text-xs">
            <span className="text-slate-500">
              {t('auth.hasAccount')}{' '}
              <Link to="/login" className="text-blue-400 hover:text-blue-300 font-semibold transition-colors">
                {t('auth.loginLink')}
              </Link>
            </span>
            <span className="text-[10px] text-slate-700 font-mono">v2.1.0</span>
          </div>
        </motion.div>
      </div>
    </div>
  )
}

function RegisterBackground({ isRtl }: { isRtl: boolean }) {
  return (
    <div className="absolute inset-0 pointer-events-none z-0">
      {/* Fine grid */}
      <div
        className="absolute inset-0 opacity-[0.02]"
        style={{
          backgroundImage: `linear-gradient(#3b82f6 1px, transparent 1px), linear-gradient(90deg, #3b82f6 1px, transparent 1px)`,
          backgroundSize: '40px 40px',
        }}
      />

      {/* Dynamic single-line schematic flow simulation */}
      <svg className="absolute inset-0 w-full h-full" viewBox="0 0 1440 900" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
        <defs>
          <linearGradient id="bus-grad-reg" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#1e293b" stopOpacity="0.2" />
            <stop offset="50%" stopColor="#3b82f6" stopOpacity="0.6" />
            <stop offset="100%" stopColor="#1e293b" stopOpacity="0.2" />
          </linearGradient>
        </defs>

        {/* High voltage main bus bar */}
        <path d="M100,180 L1340,180" stroke="url(#bus-grad-reg)" strokeWidth="3" strokeLinecap="round" />
        <path d="M100,180 L1340,180" stroke="#00d4ff" strokeWidth="1" strokeLinecap="round" className="animate-pulse" opacity="0.8" />

        {/* Other paths omitted for brevity - same as Login.tsx but with different IDs */}
        <path d="M400,180 L400,450" stroke="#1e293b" strokeWidth="2" opacity="0.4" />
        <path d="M400,180 L400,450" stroke="#00d4ff" strokeWidth="1.5" strokeDasharray="8 12" strokeDashoffset="0" style={{ animation: 'gridFlowReg 12s linear infinite' }} />
        <circle cx="400" cy="280" r="14" fill="none" stroke="#00d4ff" strokeWidth="1.5" />
        <circle cx="400" cy="302" r="14" fill="none" stroke="#3b82f6" strokeWidth="1.5" />
        <path d="M250,450 L1190,450" stroke="url(#bus-grad-reg)" strokeWidth="2.5" strokeLinecap="round" />
        <circle cx="800" cy="70" r="18" fill="#070b14" stroke="#22c55e" strokeWidth="1.5" />
        <text x="800" y="75" textAnchor="middle" fill="#22c55e" fontSize="14" fontWeight="bold" fontFamily="monospace">G</text>

        <style>{`
          @keyframes gridFlowReg { to { stroke-dashoffset: -120; } }
        `}</style>
      </svg>

      {/* Ambient background aura */}
      <div className="absolute top-10 right-20 w-[600px] h-[600px] rounded-full bg-blue-500/[0.02] blur-[140px]" />
      <div className="absolute bottom-10 left-20 w-[500px] h-[500px] rounded-full bg-blue-600/[0.015] blur-[120px]" />
    </div>
  )
}