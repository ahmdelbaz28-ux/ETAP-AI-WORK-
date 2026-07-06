import { useState, useEffect } from 'react'
import { useNavigate, Link, useSearchParams } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Mail, Lock, ArrowRight, Eye, EyeOff, AlertCircle, ShieldCheck } from 'lucide-react'
import { useNotify } from '../context/NotificationContext'
import { useAuth } from '../hooks/useAuth'
import { BrandLogo } from '../components/BrandLogo'
import { API_BASE_URL } from '../lib/api-config'

/**
 * Login — AhmedETAP professional sign-in page (Arabic + animated).
 *
 * Features:
 * - Arabic UI (RTL)
 * - Animated power-grid background (SVG one-line diagram with flowing energy pulses)
 * - Forgot password is REAL (POST /api/v1/auth/forgot-password)
 * - No demo, no fake data
 */
export default function Login() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { notify } = useNotify()
  const { login } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [authError, setAuthError] = useState<string | null>(null)
  const [forgotOpen, setForgotOpen] = useState(false)
  const [forgotEmail, setForgotEmail] = useState('')
  const [forgotLoading, setForgotLoading] = useState(false)
  const [forgotSent, setForgotSent] = useState(false)

  // Set RTL + Arabic on mount
  useEffect(() => {
    document.documentElement.dir = 'rtl'
    document.documentElement.lang = 'ar'
    return () => {
      document.documentElement.dir = 'ltr'
      document.documentElement.lang = 'en'
    }
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!email || !password) {
      notify('error', 'يرجى إدخال البريد الإلكتروني وكلمة المرور')
      return
    }
    setLoading(true)
    setAuthError(null)
    try {
      await login(email, password)
      notify('success', 'مرحباً بعودتك!')
      const from = searchParams.get('from') || '/dashboard'
      navigate(from, { replace: true })
    } catch (err) {
      const message = err instanceof Error ? err.message : 'خطأ غير معروف'
      setAuthError(message)
      notify('error', `فشل تسجيل الدخول: ${message}`)
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
        notify('success', 'إذا كان البريد موجوداً، تم إرسال رمز إعادة التعيين')
      } else {
        throw new Error('Request failed')
      }
    } catch {
      setForgotSent(true)
      notify('info', 'إذا كان البريد موجوداً، تم إرسال رمز إعادة التعيين')
    } finally {
      setForgotLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex bg-[#070b14] relative overflow-hidden">
      {/* ============ ANIMATED BACKGROUND ============ */}
      <div className="absolute inset-0 pointer-events-none">
        {/* Subtle grid */}
        <div
          className="absolute inset-0 opacity-[0.025]"
          style={{
            backgroundImage: `linear-gradient(#3b82f6 1px, transparent 1px), linear-gradient(90deg, #3b82f6 1px, transparent 1px)`,
            backgroundSize: '50px 50px',
          }}
        />

        {/* Animated power-line SVG — one-line diagram with flowing pulses */}
        <svg
          className="absolute inset-0 w-full h-full"
          viewBox="0 0 1440 900"
          preserveAspectRatio="xMidYMid slice"
          aria-hidden="true"
        >
          <defs>
            <linearGradient id="line-grad" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#1e3a5f" stopOpacity="0.3" />
              <stop offset="50%" stopColor="#3b82f6" stopOpacity="0.5" />
              <stop offset="100%" stopColor="#1e3a5f" stopOpacity="0.3" />
            </linearGradient>
          </defs>

          {/* Horizontal bus lines */}
          <line x1="0" y1="200" x2="1440" y2="200" stroke="url(#line-grad)" strokeWidth="1" />
          <line x1="0" y1="450" x2="1440" y2="450" stroke="url(#line-grad)" strokeWidth="1.5" />
          <line x1="0" y1="700" x2="1440" y2="700" stroke="url(#line-grad)" strokeWidth="1" />

          {/* Vertical connector lines */}
          <line x1="200" y1="200" x2="200" y2="450" stroke="#1e3a5f" strokeWidth="0.8" opacity="0.4" />
          <line x1="500" y1="200" x2="500" y2="450" stroke="#1e3a5f" strokeWidth="0.8" opacity="0.4" />
          <line x1="800" y1="200" x2="800" y2="450" stroke="#1e3a5f" strokeWidth="0.8" opacity="0.4" />
          <line x1="1100" y1="200" x2="1100" y2="450" stroke="#1e3a5f" strokeWidth="0.8" opacity="0.4" />
          <line x1="300" y1="450" x2="300" y2="700" stroke="#1e3a5f" strokeWidth="0.8" opacity="0.4" />
          <line x1="700" y1="450" x2="700" y2="700" stroke="#1e3a5f" strokeWidth="0.8" opacity="0.4" />
          <line x1="1050" y1="450" x2="1050" y2="700" stroke="#1e3a5f" strokeWidth="0.8" opacity="0.4" />

          {/* Bus junction nodes (pulsing) */}
          {[
            { cx: 200, cy: 200, delay: 0 },
            { cx: 500, cy: 200, delay: 0.5 },
            { cx: 800, cy: 200, delay: 1 },
            { cx: 1100, cy: 200, delay: 1.5 },
            { cx: 300, cy: 450, delay: 0.3 },
            { cx: 700, cy: 450, delay: 0.8 },
            { cx: 1050, cy: 450, delay: 1.3 },
            { cx: 300, cy: 700, delay: 0.6 },
            { cx: 700, cy: 700, delay: 1.1 },
            { cx: 1050, cy: 700, delay: 1.6 },
          ].map((n, i) => (
            <motion.circle
              key={i}
              cx={n.cx}
              cy={n.cy}
              r="3"
              fill="#3b82f6"
              initial={{ opacity: 0.2 }}
              animate={{ opacity: [0.2, 0.8, 0.2] }}
              transition={{ duration: 3, repeat: Infinity, delay: n.delay, ease: 'easeInOut' }}
            />
          ))}

          {/* Energy pulses traveling along bus lines */}
          <motion.circle
            r="2"
            fill="#60a5fa"
            initial={{ cx: 0, cy: 200 }}
            animate={{ cx: [0, 1440] }}
            transition={{ duration: 8, repeat: Infinity, ease: 'linear' }}
          />
          <motion.circle
            r="2.5"
            fill="#3b82f6"
            initial={{ cx: 0, cy: 450 }}
            animate={{ cx: [0, 1440] }}
            transition={{ duration: 6, repeat: Infinity, ease: 'linear', delay: 2 }}
          />
          <motion.circle
            r="2"
            fill="#60a5fa"
            initial={{ cx: 1440, cy: 700 }}
            animate={{ cx: [1440, 0] }}
            transition={{ duration: 7, repeat: Infinity, ease: 'linear', delay: 1 }}
          />
        </svg>

        {/* Ambient glow blobs */}
        <motion.div
          className="absolute top-1/4 right-1/4 w-[500px] h-[500px] rounded-full"
          style={{ background: 'radial-gradient(circle, rgba(59,130,246,0.06), transparent 70%)' }}
          animate={{ scale: [1, 1.15, 1], opacity: [0.5, 0.7, 0.5] }}
          transition={{ duration: 10, repeat: Infinity, ease: 'easeInOut' }}
        />
        <motion.div
          className="absolute bottom-1/4 left-1/4 w-[400px] h-[400px] rounded-full"
          style={{ background: 'radial-gradient(circle, rgba(245,158,11,0.04), transparent 70%)' }}
          animate={{ scale: [1.1, 1, 1.1], opacity: [0.4, 0.6, 0.4] }}
          transition={{ duration: 12, repeat: Infinity, ease: 'easeInOut', delay: 2 }}
        />
      </div>

      {/* ============ RIGHT PANEL — Brand (RTL: right = first) ============ */}
      <div className="hidden lg:flex lg:w-[42%] flex-col justify-between p-12 relative z-10 border-l border-[#1e2a4a]/50">
        {/* Top: Logo */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="flex items-center gap-3"
        >
          <BrandLogo size={48} />
          <div>
            <h1 className="text-xl font-bold tracking-tight text-white">AhmedETAP</h1>
            <p className="text-[11px] text-slate-500 tracking-wide">منصة هندسة أنظمة الطاقة</p>
          </div>
        </motion.div>

        {/* Middle: Headline */}
        <motion.div
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.15 }}
          className="space-y-5"
        >
          <h2 className="text-3xl xl:text-4xl font-bold leading-tight text-white">
            تحليل أنظمة الطاقة<br />
            <span className="text-blue-400">بُنية للمهندسين</span>
          </h2>
          <p className="text-sm text-slate-400 leading-relaxed max-w-md">
            تدفق الحمل، الدائرة القصيرة، القوس الكهربائي، تنسيق الحماية،
            التوافقيات، والمزيد — متوافق مع معايير IEEE و IEC.
          </p>

          {/* Standards badges */}
          <div className="flex flex-wrap gap-2 pt-1">
            {['IEEE 3002.7', 'IEC 60909', 'IEEE 1584', 'IEC 60255', 'IEEE 519'].map((s, i) => (
              <motion.span
                key={s}
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.3, delay: 0.3 + i * 0.08 }}
                className="px-2.5 py-1 text-[10px] font-mono text-slate-400 bg-slate-900/40 border border-slate-700/40 rounded"
              >
                {s}
              </motion.span>
            ))}
          </div>
        </motion.div>

        {/* Bottom: Security note */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.5, delay: 0.5 }}
          className="flex items-center gap-2 text-[11px] text-slate-600"
        >
          <ShieldCheck className="w-3.5 h-3.5" />
          <span>JWT + bcrypt • تشفير شامل • سجل تدقيق جاهز لـ SOC2</span>
        </motion.div>
      </div>

      {/* ============ LEFT PANEL — Login Form (RTL: left = form) ============ */}
      <div className="flex-1 flex items-center justify-center p-6 sm:p-8 relative z-10">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.1 }}
          className="w-full max-w-sm"
        >
          {/* Mobile logo */}
          <div className="lg:hidden flex items-center gap-2.5 mb-8">
            <BrandLogo size={36} />
            <span className="text-lg font-bold text-white">AhmedETAP</span>
          </div>

          {/* Header */}
          <div className="mb-8">
            <h2 className="text-2xl font-bold text-white mb-1">تسجيل الدخول</h2>
            <p className="text-sm text-slate-500">أدخل بياناتك للمتابعة</p>
          </div>

          {/* Error banner */}
          {authError && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              className="mb-4 p-3 rounded-md bg-red-950/40 border border-red-800/50 flex items-start gap-2.5"
            >
              <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0 text-red-400" />
              <p className="text-xs text-red-300">{authError}</p>
            </motion.div>
          )}

          {/* Forgot password form */}
          {forgotOpen && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              className="mb-4 p-4 rounded-md bg-slate-900/60 border border-slate-700/50"
            >
              {forgotSent ? (
                <div className="text-center py-2">
                  <p className="text-sm text-green-400 mb-3">
                    إذا كان البريد موجوداً، تم إرسال رمز إعادة التعيين.
                  </p>
                  <button
                    onClick={() => { setForgotOpen(false); setForgotSent(false); setForgotEmail('') }}
                    className="text-xs text-slate-400 hover:text-white transition-colors"
                  >
                    العودة لتسجيل الدخول
                  </button>
                </div>
              ) : (
                <form onSubmit={handleForgotPassword}>
                  <p className="text-sm text-white mb-3">إعادة تعيين كلمة المرور</p>
                  <input
                    type="email"
                    value={forgotEmail}
                    onChange={e => setForgotEmail(e.target.value)}
                    placeholder="your@email.com"
                    required
                    className="w-full px-3 py-2 mb-3 bg-slate-950 border border-slate-700 rounded text-sm text-white placeholder-slate-600 focus:outline-none focus:border-blue-500 transition-colors"
                    dir="ltr"
                  />
                  <div className="flex gap-2">
                    <button
                      type="submit"
                      disabled={forgotLoading}
                      className="flex-1 py-2 bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium rounded transition-colors disabled:opacity-50"
                    >
                      {forgotLoading ? 'جارٍ الإرسال...' : 'إرسال رمز التعيين'}
                    </button>
                    <button
                      type="button"
                      onClick={() => setForgotOpen(false)}
                      className="px-4 py-2 text-slate-400 hover:text-white text-xs transition-colors"
                    >
                      إلغاء
                    </button>
                  </div>
                </form>
              )}
            </motion.div>
          )}

          {/* Login form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="login-email" className="block text-xs font-medium text-slate-400 mb-1.5">
                البريد الإلكتروني
              </label>
              <div className="relative">
                <Mail className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-600 pointer-events-none" />
                <input
                  id="login-email"
                  type="email"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  placeholder="you@company.com"
                  required
                  dir="ltr"
                  className="w-full pr-9 pl-3 py-2.5 bg-slate-950/80 border border-slate-700/50 rounded text-sm text-white placeholder-slate-600 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500/20 transition-all"
                />
              </div>
            </div>

            <div>
              <label htmlFor="login-password" className="block text-xs font-medium text-slate-400 mb-1.5">
                كلمة المرور
              </label>
              <div className="relative">
                <Lock className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-600 pointer-events-none" />
                <input
                  id="login-password"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                  dir="ltr"
                  className="w-full pr-9 pl-10 py-2.5 bg-slate-950/80 border border-slate-700/50 rounded text-sm text-white placeholder-slate-600 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500/20 transition-all"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(p => !p)}
                  className="absolute left-2.5 top-1/2 -translate-y-1/2 p-1 rounded text-slate-600 hover:text-slate-300 transition-colors"
                  aria-label={showPassword ? 'إخفاء كلمة المرور' : 'إظهار كلمة المرور'}
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <div className="flex items-center justify-between text-xs">
              <label className="flex items-center gap-1.5 text-slate-500 cursor-pointer">
                <input type="checkbox" className="rounded border-slate-700 bg-slate-950 text-blue-600 focus:ring-blue-500/20" />
                تذكرني
              </label>
              <button
                type="button"
                onClick={() => { setForgotOpen(true); setAuthError(null) }}
                className="text-blue-400 hover:text-blue-300 font-medium transition-colors"
              >
                نسيت كلمة المرور؟
              </button>
            </div>

            <motion.button
              whileHover={{ scale: 1.01 }}
              whileTap={{ scale: 0.99 }}
              type="submit"
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded text-sm font-semibold transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  جارٍ تسجيل الدخول...
                </>
              ) : (
                <>
                  دخول
                  <ArrowRight className="w-4 h-4 rotate-180" />
                </>
              )}
            </motion.button>
          </form>

          {/* Footer */}
          <div className="mt-8 pt-6 border-t border-slate-800/50 flex items-center justify-between">
            <p className="text-xs text-slate-600">
              ليس لديك حساب؟{' '}
              <Link to="/register" className="text-blue-400 hover:text-blue-300 font-medium transition-colors">
                أنشئ واحداً
              </Link>
            </p>
            <p className="text-[10px] text-slate-700 font-mono">v2.1.0</p>
          </div>
        </motion.div>
      </div>
    </div>
  )
}
