import { useState, useEffect, useCallback } from 'react'
import { useNavigate, Link, useSearchParams } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Mail, Lock, ArrowRight, Eye, EyeOff, AlertCircle, ShieldCheck, Globe } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { useNotify } from '../context/NotificationContext'
import { useAuth } from '../hooks/useAuth'
import { BrandLogo } from '../components/BrandLogo'
import { LoginBackground } from '../components/LoginBackground'
import { API_BASE_URL } from '../lib/api-config'

/**
 * Login — AhmedETAP professional sign-in page.
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

  useEffect(() => {
    document.documentElement.dir = i18n.language === 'ar' ? 'rtl' : 'ltr'
    document.documentElement.lang = i18n.language
  }, [i18n.language])

  const handleSubmit = useCallback(async (e: React.FormEvent) => {
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
  }, [email, password, login, notify, t, i18n, searchParams, navigate])

  const handleForgotPassword = useCallback(async (e: React.FormEvent) => {
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
  }, [forgotEmail, notify, t, i18n])

  const toggleLanguage = useCallback(() => {
    const nextLang = i18n.language === 'ar' ? 'en' : 'ar'
    i18n.changeLanguage(nextLang)
  }, [i18n])

  const isRtl = i18n.language === 'ar'

  return (
    <LoginView
      isRtl={isRtl}
      email={email}
      password={password}
      showPassword={showPassword}
      loading={loading}
      authError={authError}
      forgotOpen={forgotOpen}
      forgotEmail={forgotEmail}
      forgotLoading={forgotLoading}
      forgotSent={forgotSent}
      onEmailChange={setEmail}
      onPasswordChange={setPassword}
      onTogglePassword={() => setShowPassword(p => !p)}
      onSubmit={handleSubmit}
      onForgotPassword={handleForgotPassword}
      onToggleLanguage={toggleLanguage}
      onForgotOpenChange={setForgotOpen}
      onForgotEmailChange={setForgotEmail}
      onForgotSentChange={setForgotSent}
      navigate={navigate}
    />
  )
}

interface LoginViewProps {
  isRtl: boolean
  email: string
  password: string
  showPassword: boolean
  loading: boolean
  authError: string | null
  forgotOpen: boolean
  forgotEmail: string
  forgotLoading: boolean
  forgotSent: boolean
  onEmailChange: (v: string) => void
  onPasswordChange: (v: string) => void
  onTogglePassword: () => void
  onSubmit: (e: React.FormEvent) => void
  onForgotPassword: (e: React.FormEvent) => void
  onToggleLanguage: () => void
  onForgotOpenChange: (v: boolean) => void
  onForgotEmailChange: (v: string) => void
  onForgotSentChange: (v: boolean) => void
  navigate: (to: string, opts?: { replace: boolean }) => void
}

const RTL_CLASSES = {
  fieldIcon: 'absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-600 pointer-events-none',
  ltrFieldIcon: 'absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-600 pointer-events-none',
  passwordToggle: 'absolute right-2.5 top-1/2 -translate-y-1/2 p-1 rounded text-slate-600 hover:text-slate-300 transition-colors',
  ltrPasswordToggle: 'absolute left-2.5 top-1/2 -translate-y-1/2 p-1 rounded text-slate-600 hover:text-slate-300 transition-colors',
} as const

function LoginView({
  isRtl,
  email,
  password,
  showPassword,
  loading,
  authError,
  forgotOpen,
  forgotEmail,
  forgotLoading,
  forgotSent,
  onEmailChange,
  onPasswordChange,
  onTogglePassword,
  onSubmit,
  onForgotPassword,
  onToggleLanguage,
  onForgotOpenChange,
  onForgotEmailChange,
  onForgotSentChange,
}: LoginViewProps) {
  const { t } = useTranslation()
  const searchParams = useSearchParams()[0]

  return (
    <div className="min-h-screen flex bg-[#070b14] relative overflow-hidden" dir={isRtl ? 'rtl' : 'ltr'}>
      <LoginBackground isRtl={isRtl} onLanguageToggle={onToggleLanguage} />

      <div className={`hidden lg:flex lg:w-[45%] flex-col justify-between p-12 relative z-10 border-slate-800/40 ${isRtl ? 'border-r' : 'border-l'}`}>
        <BrandLogoSection isRtl={isRtl} />
        <EngineeringTitles isRtl={isRtl} />
        <SecurityBadge />
      </div>

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
          {forgotOpen && (
            <ForgotPasswordSection
              forgotSent={forgotSent}
              forgotEmail={forgotEmail}
              forgotLoading={forgotLoading}
              isRtl={isRtl}
              onEmailChange={onForgotEmailChange}
              onSubmit={onForgotPassword}
              onClose={() => { onForgotOpenChange(false); onForgotSentChange(false); onForgotEmailChange('') }}
            />
          )}
          <form onSubmit={onSubmit} className="space-y-4">
            <EmailField email={email} onChange={onEmailChange} isRtl={isRtl} />
            <PasswordField password={password} onChange={onPasswordChange} onToggle={onTogglePassword} showPassword={showPassword} isRtl={isRtl} />
            <ActionRow onForgot={() => { onForgotOpenChange(true) }} />
            <SubmitButton loading={loading} isRtl={isRtl} loadingText={t('auth.loggingIn')} defaultText={t('auth.loginButton')} />
          </form>
          <Footer />
        </motion.div>
      </div>
    </div>
  )
}

function EmailField({ email, onChange, isRtl }: { email: string; onChange: (v: string) => void; isRtl: boolean }) {
  const { t } = useTranslation()
  return (
    <div>
      <label htmlFor="login-email" className="block text-xs font-semibold text-slate-400 mb-1.5">{t('auth.emailLabel')}</label>
      <div className="relative">
        <Mail className={isRtl ? RTL_CLASSES.fieldIcon : RTL_CLASSES.ltrFieldIcon} />
        <input
          id="login-email"
          type="text"
          inputMode="email"
          value={email}
          onChange={e => onChange(e.target.value)}
          placeholder={t('auth.emailPlaceholder')}
          required
          dir="ltr"
          className={`w-full ${isRtl ? 'pr-9 pl-3' : 'pl-9 pr-3'} py-2.5 bg-slate-950/40 border border-slate-800/80 rounded-xl text-xs text-white placeholder-slate-700 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500/10 transition-all`}
        />
      </div>
    </div>
  )
}

function PasswordField({ password, onChange, onToggle, showPassword, isRtl }: { password: string; onChange: (v: string) => void; onToggle: () => void; showPassword: boolean; isRtl: boolean }) {
  const { t } = useTranslation()
  return (
    <div>
      <label htmlFor="login-password" className="block text-xs font-semibold text-slate-400 mb-1.5">{t('auth.passwordLabel')}</label>
      <div className="relative">
        <Lock className={isRtl ? RTL_CLASSES.fieldIcon : RTL_CLASSES.ltrFieldIcon} />
        <input
          id="login-password"
          type={showPassword ? 'text' : 'password'}
          value={password}
          onChange={e => onChange(e.target.value)}
          placeholder={t('auth.passwordPlaceholder')}
          required
          dir="ltr"
          className={`w-full ${isRtl ? 'pr-9 pl-10' : 'pl-9 pr-10'} py-2.5 bg-slate-950/40 border border-slate-800/80 rounded-xl text-xs text-white placeholder-slate-700 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500/10 transition-all`}
        />
        <button type="button" onClick={onToggle} className={isRtl ? RTL_CLASSES.passwordToggle : RTL_CLASSES.ltrPasswordToggle} aria-label={showPassword ? 'Hide password' : 'Show password'}>
          {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
        </button>
      </div>
    </div>
  )
}

function ActionRow({ onForgot }: { onForgot: () => void }) {
  const { t } = useTranslation()
  return (
    <div className="flex items-center justify-between text-xs pt-1.5">
      <label className="flex items-center gap-2 text-slate-500 cursor-pointer user-select-none">
        <input type="checkbox" className="rounded border-slate-800 bg-slate-950 text-blue-600 focus:ring-blue-500/10" />
        <span>{t('auth.rememberMe')}</span>
      </label>
      <button type="button" onClick={onForgot} className="text-blue-400 hover:text-blue-300 font-semibold transition-colors">
        {t('auth.forgotPassword')}
      </button>
    </div>
  )
}

function SubmitButton({ loading, isRtl, loadingText, defaultText }: { loading: boolean; isRtl: boolean; loadingText: string; defaultText: string }) {
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

function ForgotPasswordSection({ forgotSent, forgotEmail, forgotLoading, isRtl, onEmailChange, onSubmit, onClose }: { forgotSent: boolean; forgotEmail: string; forgotLoading: boolean; isRtl: boolean; onEmailChange: (v: string) => void; onSubmit: (e: React.FormEvent) => void; onClose: () => void }) {
  const { t } = useTranslation()
  return (
    <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} className="mb-5 p-4 rounded-lg bg-slate-950 border border-slate-800">
      {forgotSent ? (
        <div className="text-center py-1">
          <p className="text-xs text-green-400 leading-relaxed mb-4">
            {isRtl ? 'تم إرسال رابط استعادة كلمة المرور إذا كان الحساب مسجلاً لدينا.' : 'Password reset link sent if the email is registered.'}
          </p>
          <button onClick={onClose} className="text-xs font-semibold text-slate-400 hover:text-white transition-colors">
            {t('auth.backToLogin')}
          </button>
        </div>
      ) : (
        <form onSubmit={onSubmit} className="space-y-3">
          <p className="text-xs font-semibold text-white">{t('auth.resetPasswordTitle')}</p>
          <input
            type="email"
            value={forgotEmail}
            onChange={e => onEmailChange(e.target.value)}
            placeholder={t('auth.resetEmailPlaceholder')}
            required
            dir="ltr"
            className="w-full px-3 py-2 bg-slate-900/60 border border-slate-800 rounded-lg text-xs text-white focus:outline-none focus:border-blue-500 placeholder-slate-600 transition-colors"
          />
          <div className="flex gap-2 pt-1">
            <button type="submit" disabled={forgotLoading}
              className="flex-1 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-[11px] font-semibold rounded-md transition-colors disabled:opacity-50">
              {forgotLoading ? t('auth.sending') : t('auth.sendResetLink')}
            </button>
            <button type="button" onClick={onClose}
              className="px-3 py-1.5 text-slate-400 hover:text-white text-[11px] font-semibold transition-colors">
              {t('auth.cancel')}
            </button>
          </div>
        </form>
      )}
    </motion.div>
  )
}

function ErrorAlert({ message }: { message: string }) {
  return (
    <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }}
      className="mb-5 p-3 rounded-lg bg-red-950/20 border border-red-900/40 flex items-start gap-2.5">
      <AlertCircle className="w-4 h-4 text-red-400 mt-0.5 flex-shrink-0" />
      <p className="text-xs text-red-300 leading-normal">{message}</p>
    </motion.div>
  )
}

function BrandLogoSection({ isRtl }: { isRtl: boolean }) {
  const { t } = useTranslation()
  return (
    <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}
      className="flex items-center gap-3.5">
      <BrandLogo size={44} />
      <div>
        <h1 className="text-xl font-bold tracking-tight text-white">AhmedETAP</h1>
        <p className="text-[10px] text-slate-500 tracking-wider uppercase">{t('app.description')}</p>
      </div>
    </motion.div>
  )
}

const AR_TITLES = (
  <>
    تحليل أنظمة الطاقة<br />
    <span className="text-blue-500">بمعايير هندسية متكاملة</span>
  </>
)

const EN_TITLES = (
  <>
    Power Systems Analysis<br />
    <span className="text-blue-500">Built for Professionals</span>
  </>
)

const AR_DESC = 'منصة تشغيل حسابات تدفق الحمل (Load Flow)، تيار القصر (Short Circuit)، الوميض القوسي (Arc Flash)، وتنسيق أجهزة الحماية، متوافقة كلياً مع معايير IEEE و IEC.'

const EN_DESC = 'Analyze, simulate, and design electrical networks with high-precision engines for load flow, short circuit, protection coordination, and arc flash analysis.'

const STANDARDS = ['IEEE 3002.7', 'IEC 60909', 'IEEE 1584', 'IEC 60255', 'IEEE 519']

function EngineeringTitles({ isRtl }: { isRtl: boolean }) {
  const { t } = useTranslation()
  return (
    <motion.div initial={{ opacity: 0, y: 15 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.1 }} className="space-y-6">
      <h2 className="text-3xl xl:text-4xl font-extrabold leading-tight text-white tracking-tight">
        {isRtl ? AR_TITLES : EN_TITLES}
      </h2>
      <p className="text-sm text-slate-400 leading-relaxed max-w-md">
        {isRtl ? AR_DESC : EN_DESC}
      </p>
      <div className="flex flex-wrap gap-2.5 pt-1.5">
        {STANDARDS.map((s, i) => (
          <BadgeItem key={s} text={s} delay={0.05 + i * 0.05} />
        ))}
      </div>
    </motion.div>
  )
}

function SecurityBadge() {
  const { t } = useTranslation()
  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.4, delay: 0.3 }}
      className="flex items-center gap-2.5 text-[10px] text-slate-600 font-mono">
      <ShieldCheck className="w-4 h-4 text-blue-500" />
      <span>{t('auth.securityBadge')}</span>
    </motion.div>
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
    <div className="mb-8">
      <h3 className="text-2xl font-bold text-white tracking-tight">{t('auth.loginTitle')}</h3>
      <p className="text-xs text-slate-500 mt-1.5 leading-relaxed">{t('auth.loginSubtitle')}</p>
    </div>
  )
}

function Footer() {
  const { t } = useTranslation()
  return (
    <div className="mt-8 pt-5 border-t border-slate-800/40 flex items-center justify-between text-xs">
      <span className="text-slate-500">
        {t('auth.noAccount')}{' '}
        <Link to="/register" className="text-blue-400 hover:text-blue-300 font-semibold transition-colors">
          {t('auth.registerLink')}
        </Link>
      </span>
      <span className="text-[10px] text-slate-700 font-mono">v2.1.0</span>
    </div>
  )
}

function BadgeItem({ text, delay }: { text: string; delay: number }) {
  return (
    <motion.span initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.3, delay }}
      className="px-2.5 py-1 text-[10px] font-mono text-slate-400 bg-slate-900/60 border border-slate-800/80 rounded-md">
      {text}
    </motion.span>
  )
}
