import { useState, useEffect } from 'react'
import { useNavigate, Link, useSearchParams } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Mail, Lock, ArrowRight, Eye, EyeOff, AlertCircle, ShieldCheck, Globe } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useNotify } from '../context/NotificationContext'
import { useAuth } from '../hooks/useAuth'
import { BrandLogo } from '../components/BrandLogo'
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

  return (
    <div className="min-h-screen flex bg-[#070b14] relative overflow-hidden" dir={isRtl ? 'rtl' : 'ltr'}>
      {/* ============ LANG SELECTOR ============ */}
      <div className={`absolute top-6 ${isRtl ? 'left-6' : 'right-6'} z-50`}>
        <button
          onClick={toggleLanguage}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-slate-700/50 bg-slate-900/80 hover:bg-slate-800 text-slate-300 hover:text-white transition-all text-xs font-semibold"
        >
          <Globe className="w-3.5 h-3.5" />
          <span>{isRtl ? 'English' : 'العربية'}</span>
        </button>
      </div>

      {/* ============ ELITE CAD BACKGROUND (POWER DIAGRAM ANIMATION) ============ */}
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
        <svg
          className="absolute inset-0 w-full h-full"
          viewBox="0 0 1440 900"
          preserveAspectRatio="xMidYMid slice"
          aria-hidden="true"
        >
          <defs>
            <linearGradient id="bus-grad" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#1e293b" stopOpacity="0.2" />
              <stop offset="50%" stopColor="#3b82f6" stopOpacity="0.6" />
              <stop offset="100%" stopColor="#1e293b" stopOpacity="0.2" />
            </linearGradient>
          </defs>

          {/* High voltage main bus bar */}
          <path d="M100,180 L1340,180" stroke="url(#bus-grad)" strokeWidth="3" strokeLinecap="round" />
          <path d="M100,180 L1340,180" stroke="#00d4ff" strokeWidth="1" strokeLinecap="round" className="animate-pulse" opacity="0.8" />

          {/* Transformer circuit branch */}
          <path d="M400,180 L400,450" stroke="#1e293b" strokeWidth="2" opacity="0.4" />
          <path d="M400,180 L400,450" stroke="#00d4ff" strokeWidth="1.5" strokeDasharray="8 12" strokeDashoffset="0" style={{ animation: 'gridFlow 12s linear infinite' }} />

          {/* Transformer windings symbol */}
          <circle cx="400" cy="280" r="14" fill="none" stroke="#00d4ff" strokeWidth="1.5" />
          <circle cx="400" cy="302" r="14" fill="none" stroke="#3b82f6" strokeWidth="1.5" />

          {/* Lower distribution bus bar */}
          <path d="M250,450 L1190,450" stroke="url(#bus-grad)" strokeWidth="2.5" strokeLinecap="round" />
          <path d="M250,450 L1190,450" stroke="#60a5fa" strokeWidth="1" strokeLinecap="round" className="animate-pulse" opacity="0.6" />

          {/* Generator branch */}
          <path d="M800,180 L800,90" stroke="#1e293b" strokeWidth="2" opacity="0.4" />
          <path d="M800,180 L800,90" stroke="#22c55e" strokeWidth="1.5" strokeDasharray="10 10" strokeDashoffset="0" style={{ animation: 'gridFlowRev 10s linear infinite' }} />
          <circle cx="800" cy="70" r="18" fill="#070b14" stroke="#22c55e" strokeWidth="1.5" />
          <text x="800" y="75" textAnchor="middle" fill="#22c55e" fontSize="14" fontWeight="bold" fontFamily="monospace">G</text>

          {/* Feeder load circuit */}
          <path d="M600,450 L600,580" stroke="#1e293b" strokeWidth="2" opacity="0.4" />
          <path d="M600,450 L600,580" stroke="#fbbf24" strokeWidth="1.5" strokeDasharray="8 10" strokeDashoffset="0" style={{ animation: 'gridFlow 8s linear infinite' }} />
          <polygon points="600,588 592,572 608,572" fill="#fbbf24" stroke="#fbbf24" strokeWidth="1" />

          {/* Network dynamic particle paths */}
          <circle r="3.5" fill="#00d4ff" opacity="0.8">
            <animateMotion dur="8s" repeatCount="indefinite" path="M800,90 L800,180 L400,180 L400,450 L600,450 L600,572" />
          </circle>
          <circle r="2.5" fill="#22c55e" opacity="0.8">
            <animateMotion dur="8s" begin="2.5s" repeatCount="indefinite" path="M800,90 L800,180 L400,180 L400,450 L600,450 L600,572" />
          </circle>
          <circle r="2.5" fill="#fbbf24" opacity="0.8">
            <animateMotion dur="8s" begin="5s" repeatCount="indefinite" path="M800,90 L800,180 L400,180 L400,450 L600,450 L600,572" />
          </circle>

          {/* Circuit breaker branch */}
          <path d="M1000,450 L1000,580" stroke="#1e293b" strokeWidth="2" opacity="0.4" />
          <path d="M1000,450 L1000,580" stroke="#a78bfa" strokeWidth="1.5" strokeDasharray="8 8" strokeDashoffset="0" style={{ animation: 'gridFlow 14s linear infinite' }} />
          <rect x="993" y="495" width="14" height="20" fill="#070b14" stroke="#a78bfa" strokeWidth="1.5" />
          <line x1="993" y1="505" x2="1007" y2="505" stroke="#a78bfa" strokeWidth="1.5" />

          <style>{`
            @keyframes gridFlow {
              to { stroke-dashoffset: -120; }
            }
            @keyframes gridFlowRev {
              to { stroke-dashoffset: 120; }
            }
          `}</style>
        </svg>

        {/* Ambient background aura (very subtle) */}
        <div className="absolute top-10 right-20 w-[600px] h-[600px] rounded-full bg-blue-500/[0.02] blur-[140px]" />
        <div className="absolute bottom-10 left-20 w-[500px] h-[500px] rounded-full bg-blue-600/[0.015] blur-[120px]" />
      </div>

      {/* ============ FIRST PANEL — Info/Branding ============ */}
      <div className={`hidden lg:flex lg:w-[45%] flex-col justify-between p-12 relative z-10 border-slate-800/40 ${isRtl ? 'border-r' : 'border-l'}`}>
        {/* Top brand logo */}
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

        {/* Engineering titles */}
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

          {/* Standards list */}
          <div className="flex flex-wrap gap-2.5 pt-1.5">
            {['IEEE 3002.7', 'IEC 60909', 'IEEE 1584', 'IEC 60255', 'IEEE 519'].map((s, i) => (
              <motion.span
                key={s}
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.3, delay: 0.2 + i * 0.05 }}
                className="px-2.5 py-1 text-[10px] font-mono text-slate-400 bg-slate-900/60 border border-slate-800/80 rounded-md"
              >
                {s}
              </motion.span>
            ))}
          </div>
        </motion.div>

        {/* Security badge at bottom */}
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

      {/* ============ SECOND PANEL — Form ============ */}
      <div className="flex-1 flex items-center justify-center p-6 sm:p-12 relative z-10">
        <motion.div
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="w-full max-w-[380px] bg-slate-900/30 backdrop-blur-md border border-slate-800/40 p-8 rounded-2xl shadow-2xl"
        >
          {/* Mobile brand header */}
          <div className="lg:hidden flex items-center gap-2.5 mb-8">
            <BrandLogo size={36} />
            <span className="text-lg font-bold text-white">AhmedETAP</span>
          </div>

          <div className="mb-8">
            <h3 className="text-2xl font-bold text-white tracking-tight">{t('auth.loginTitle')}</h3>
            <p className="text-xs text-slate-500 mt-1.5 leading-relaxed">{t('auth.loginSubtitle')}</p>
          </div>

          {/* Form alert error */}
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

          {/* Forgot Password toggle menu */}
          {forgotOpen && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              className="mb-5 p-4 rounded-lg bg-slate-950 border border-slate-800"
            >
              {forgotSent ? (
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
              ) : (
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
              )}
            </motion.div>
          )}

          {/* SignIn main form */}
          <form onSubmit={handleSubmit} className="space-y-4">
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
          </form>

          {/* Footer register link */}
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
