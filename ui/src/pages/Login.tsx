import { useState, useEffect } from 'react'
import { useNavigate, Link, useSearchParams } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Mail, Lock, ArrowRight, Eye, EyeOff, AlertCircle, ShieldCheck, Globe } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useNotify } from '../context/NotificationContext'
import { useAuth } from '../hooks/useAuth'
import { BrandLogo } from '../components/BrandLogo'
import { LoginBackground } from '../components/LoginBackground'
import { Badge } from '../components/ui'
import { API_BASE_URL } from '../lib/api-config'

/**
 * Login — AhmedETAP professional sign-in page.
 *
 * Features:
 * - Full i18n support (dynamic Arabic and English layouts)
 * - Professional EN/AR selector at the top-right
 * - Elite CAD-style power grid background animation (vector flow simulation)
 * - Safe validation and token-based redirection
 */
export default function Login() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { notify } = useNotify()
  const { login } = useAuth()
  const { t, i18n } = useTranslation()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [authError, setAuthError] = useState<string | null>(null)
  const [forgotOpen, setForgotOpen] = useState(false)
  const [forgotEmail, setForgotEmail] = useState('')
  const [forgotLoading, setForgotLoading] = useState(false)
  const [forgotSent, setForgotSent] = useState(false)

  // Sync html dir and lang attribute on language switch
  useEffect(() => {
    document.documentElement.dir = i18n.language === 'ar' ? 'rtl' : 'ltr'
    document.documentElement.lang = i18n.language
  }, [i18n.language])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!email || !password) {
      notify('error', t('auth.errorMissingFields'))
      return
    }
    setLoading(true)
    setAuthError(null)
    try {
      await login(email, password)
      notify('success', i18n.language === 'ar' ? 'أهلاً بك مجدداً!' : 'Welcome back!')
      const from = searchParams.get('from') || '/dashboard'
      navigate(from, { replace: true })
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown error'
      setAuthError(message)
      notify('error', `${i18n.language === 'ar' ? 'فشل تسجيل الدخول' : 'Login failed'}: ${message}`)
    } finally {
      setLoading(false)
    }
  }

  const handleForgotPassword = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!forgotEmail) return
    setForgotLoading(true)
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/auth/forgot-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: forgotEmail }),
      })
      if (response.ok) {
        setForgotSent(true)
        notify('success', i18n.language === 'ar' ? 'تم إرسال تعليمات إعادة التعيين إن كان البريد مسجلاً' : 'Instructions sent if email is registered')
      } else {
        throw new Error('Request failed')
      }
    } catch {
      setForgotSent(true)
      notify('info', i18n.language === 'ar' ? 'تم إرسال تعليمات إعادة التعيين إن كان البريد مسجلاً' : 'Instructions sent if email is registered')
    } finally {
      setForgotLoading(false)
    }
  }

  const toggleLanguage = () => {
    const nextLang = i18n.language === 'ar' ? 'en' : 'ar'
    i18n.changeLanguage(nextLang)
  }

  const isRtl = i18n.language === 'ar'

  const renderLoginForm = () => (
    <>
      {/* Email Field */}
      <div>
        <label htmlFor="login-email" className="block text-xs font-semibold text-slate-400 mb-1.5">
          {t('auth.emailLabel')}
        </label>
        <div className="relative">
          <Mail className={`absolute ${isRtl ? 'right-3' : 'left-3'} top-1/2 -translate-y-1/2 w-4 h-4 text-slate-600 pointer-events-none`} />
          <input
            id="login-email"
            type="text"
            inputMode="email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            placeholder={t('auth.emailPlaceholder')}
            required
            dir="ltr"
            className={`w-full ${isRtl ? 'pr-9 pl-3' : 'pl-9 pr-3'} py-2.5 bg-slate-950/40 border border-slate-800/80 rounded-xl text-xs text-white placeholder-slate-700 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500/10 transition-all`}
          />
        </div>
      </div>

      {/* Password Field */}
      <div>
        <label htmlFor="login-password" className="block text-xs font-semibold text-slate-400 mb-1.5">
          {t('auth.passwordLabel')}
        </label>
        <div className="relative">
          <Lock className={`absolute ${isRtl ? 'right-3' : 'left-3'} top-1/2 -translate-y-1/2 w-4 h-4 text-slate-600 pointer-events-none`} />
          <input
            id="login-password"
            type={showPassword ? 'text' : 'password'}
            value={password}
            onChange={e => setPassword(e.target.value)}
            placeholder={t('auth.passwordPlaceholder')}
            required
            dir="ltr"
            className={`w-full ${isRtl ? 'pr-9 pl-10' : 'pl-9 pr-10'} py-2.5 bg-slate-950/40 border border-slate-800/80 rounded-xl text-xs text-white placeholder-slate-700 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500/10 transition-all`}
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

      {/* Actions */}
      <div className="flex items-center justify-between text-xs pt-1.5">
        <label className="flex items-center gap-2 text-slate-500 cursor-pointer user-select-none">
          <input
            type="checkbox"
            className="rounded border-slate-800 bg-slate-950 text-blue-600 focus:ring-blue-500/10"
          />
          <span>{t('auth.rememberMe')}</span>
        </label>
        <button
          type="button"
          onClick={() => { setForgotOpen(true); setAuthError(null) }}
          className="text-blue-400 hover:text-blue-300 font-semibold transition-colors"
        >
          {t('auth.forgotPassword')}
        </button>
      </div>

      {/* Submit Button */}
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
            <span>{t('auth.loggingIn')}</span>
          </>
        ) : (
          <>
            <span>{t('auth.loginButton')}</span>
            <ArrowRight className={`w-4 h-4 ${isRtl ? 'rotate-180' : ''}`} />
          </>
        )}
      </motion.button>
    </>
  )

  const renderForgotForm = () => (
    <form onSubmit={handleForgotPassword} className="space-y-3">
      <p className="text-xs font-semibold text-white">{t('auth.resetPasswordTitle')}</p>
      <input
        type="email"
        value={forgotEmail}
        onChange={e => setForgotEmail(e.target.value)}
        placeholder={t('auth.resetEmailPlaceholder')}
        required
        dir="ltr"
        className="w-full px-3 py-2 bg-slate-900/60 border border-slate-800 rounded-lg text-xs text-white focus:outline-none focus:border-blue-500 placeholder-slate-600 transition-colors"
      />
      <div className="flex gap-2 pt-1">
        <button
          type="submit"
          disabled={forgotLoading}
          className="flex-1 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-[11px] font-semibold rounded-md transition-colors disabled:opacity-50"
        >
          {forgotLoading ? t('auth.sending') : t('auth.sendResetLink')}
        </button>
        <button
          type="button"
          onClick={() => setForgotOpen(false)}
          className="px-3 py-1.5 text-slate-400 hover:text-white text-[11px] font-semibold transition-colors"
        >
          {t('auth.cancel')}
        </button>
      </div>
    </form>
  )

  const renderForgotSuccess = () => (
    <div className="text-center py-1">
      <p className="text-xs text-green-400 leading-relaxed mb-4">
        {isRtl ? 'تم إرسال رابط استعادة كلمة المرور إذا كان الحساب مسجلاً لدينا.' : 'Password reset link sent if the email is registered.'}
      </p>
      <button
        onClick={() => { setForgotOpen(false); setForgotSent(false); setForgotEmail('') }}
        className="text-xs font-semibold text-slate-400 hover:text-white transition-colors"
      >
        {t('auth.backToLogin')}
      </button>
    </div>
  )

  return (
    <div className="min-h-screen flex bg-[#070b14] relative overflow-hidden" dir={isRtl ? 'rtl' : 'ltr'}>
      {/* Background with language selector */}
      <LoginBackground isRtl={isRtl} onLanguageToggle={toggleLanguage} />

      {/* FIRST PANEL — Info/Branding */}
      <div className={`hidden lg:flex lg:w-[45%] flex-col justify-between p-12 relative z-10 border-slate-800/40 ${isRtl ? 'border-r' : 'border-l'}`}>
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="flex items-center gap-3.5"
        >
          <BrandLogo size={44} />
          <div>
            <h1 className="text-xl font-bold tracking-tight text-white">AhmedETAP</h1>
            <p className="text-[10px] text-slate-500 tracking-wider uppercase">{t('app.description')}</p>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.1 }}
          className="space-y-6"
        >
          <h2 className="text-3xl xl:text-4xl font-extrabold leading-tight text-white tracking-tight">
            {isRtl ? (
              <>
                تحليل أنظمة الطاقة<br />
                <span className="text-blue-500">بمعايير هندسية متكاملة</span>
              </>
            ) : (
              <>
                Power Systems Analysis<br />
                <span className="text-blue-500">Built for Professionals</span>
              </>
            )}
          </h2>
          <p className="text-sm text-slate-400 leading-relaxed max-w-md">
            {isRtl ? (
              'منصة تشغيل حسابات تدفق الحمل (Load Flow)، تيار القصر (Short Circuit)، الوميض القوسي (Arc Flash)، وتنسيق أجهزة الحماية، متوافقة كلياً مع معايير IEEE و IEC.'
            ) : (
              'Analyze, simulate, and design electrical networks with high-precision engines for load flow, short circuit, protection coordination, and arc flash analysis.'
            )}
          </p>

          <div className="flex flex-wrap gap-2.5 pt-1.5">
            {['IEEE 3002.7', 'IEC 60909', 'IEEE 1584', 'IEC 60255', 'IEEE 519'].map((s) => (
              <BadgeItem key={s} text={s} delay={0.05} />
            ))}
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.4, delay: 0.3 }}
          className="flex items-center gap-2.5 text-[10px] text-slate-600 font-mono"
        >
          <ShieldCheck className="w-4 h-4 text-blue-500" />
          <span>{t('auth.securityBadge')}</span>
        </motion.div>
      </div>

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

          <div className="mb-8">
            <h3 className="text-2xl font-bold text-white tracking-tight">{t('auth.loginTitle')}</h3>
            <p className="text-xs text-slate-500 mt-1.5 leading-relaxed">{t('auth.loginSubtitle')}</p>
          </div>

          {authError && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              className="mb-5 p-3 rounded-lg bg-red-950/20 border border-red-900/40 flex items-start gap-2.5"
            >
              <AlertCircle className="w-4 h-4 text-red-400 mt-0.5 flex-shrink-0" />
              <p className="text-xs text-red-300 leading-normal">{authError}</p>
            </motion.div>
          )}

          {forgotOpen && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              className="mb-5 p-4 rounded-lg bg-slate-950 border border-slate-800"
            >
              {forgotSent ? renderForgotSuccess() : renderForgotForm()}
            </motion.div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            {renderLoginForm()}
          </form>

          <div className="mt-8 pt-5 border-t border-slate-800/40 flex items-center justify-between text-xs">
            <span className="text-slate-500">
              {t('auth.noAccount')}{' '}
              <Link to="/register" className="text-blue-400 hover:text-blue-300 font-semibold transition-colors">
                {t('auth.registerLink')}
              </Link>
            </span>
            <span className="text-[10px] text-slate-700 font-mono">v2.1.0</span>
          </div>
        </motion.div>
      </div>
    </div>
  )
}

// Extracted component to reduce complexity
function BadgeItem({ text, delay }: { text: string; delay: number }) {
  return (
    <motion.span
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.3, delay }}
      className="px-2.5 py-1 text-[10px] font-mono text-slate-400 bg-slate-900/60 border border-slate-800/80 rounded-md"
    >
      {text}
    </motion.span>
  )
}