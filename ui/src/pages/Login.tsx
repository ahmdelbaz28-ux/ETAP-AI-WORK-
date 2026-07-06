import { useState } from 'react'
import { useNavigate, Link, useSearchParams } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Mail, Lock, ArrowRight, Eye, EyeOff, AlertCircle, ShieldCheck } from 'lucide-react'
import { useNotify } from '../context/NotificationContext'
import { useAuth } from '../hooks/useAuth'
import { BrandLogo } from '../components/BrandLogo'
import { API_BASE_URL } from '../lib/api-config'

/**
 * Login — AhmedETAP professional sign-in page.
 *
 * Auth: REAL backend only via useAuth().login().
 * Forgot password: REAL backend via POST /api/v1/auth/forgot-password.
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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!email || !password) {
      notify('error', 'Please enter email and password')
      return
    }
    setLoading(true)
    setAuthError(null)
    try {
      await login(email, password)
      notify('success', 'Welcome back!')
      const from = searchParams.get('from') || '/dashboard'
      navigate(from, { replace: true })
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown error'
      setAuthError(message)
      notify('error', `Login failed: ${message}`)
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
        notify('success', 'If the email exists, a reset token has been sent')
      } else {
        throw new Error('Request failed')
      }
    } catch {
      setForgotSent(true)
      notify('info', 'If the email exists, a reset token has been sent')
    } finally {
      setForgotLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex bg-[#0a0e1a]">
      {/* ============ LEFT PANEL — Brand ============ */}
      <div className="hidden lg:flex lg:w-[45%] xl:w-[40%] flex-col justify-between p-12 relative overflow-hidden border-r border-[#1e2a4a]">
        {/* Subtle grid background */}
        <div
          className="absolute inset-0 opacity-[0.03]"
          style={{
            backgroundImage: `linear-gradient(#60a5fa 1px, transparent 1px), linear-gradient(90deg, #60a5fa 1px, transparent 1px)`,
            backgroundSize: '40px 40px',
          }}
        />

        {/* Top: Logo + name */}
        <div className="relative z-10 flex items-center gap-3">
          <BrandLogo size={44} />
          <div>
            <h1 className="text-xl font-bold tracking-tight text-white">AhmedETAP</h1>
            <p className="text-[11px] text-slate-500 tracking-wide uppercase">Power Systems Engineering</p>
          </div>
        </div>

        {/* Middle: Headline */}
        <div className="relative z-10 space-y-6">
          <h2 className="text-3xl xl:text-4xl font-bold leading-tight text-white">
            Power System Analysis<br />
            <span className="text-blue-400">Built for Engineers</span>
          </h2>
          <p className="text-sm text-slate-400 leading-relaxed max-w-md">
            Load Flow, Short Circuit, Arc Flash, Protection Coordination,
            Harmonics, and more — compliant with IEEE and IEC standards.
          </p>

          {/* Standards badges */}
          <div className="flex flex-wrap gap-2 pt-2">
            {['IEEE 3002.7', 'IEC 60909', 'IEEE 1584', 'IEC 60255', 'IEEE 519'].map(s => (
              <span key={s} className="px-2.5 py-1 text-[10px] font-mono text-slate-400 bg-slate-800/50 border border-slate-700/50 rounded">
                {s}
              </span>
            ))}
          </div>
        </div>

        {/* Bottom: Security note */}
        <div className="relative z-10 flex items-center gap-2 text-[11px] text-slate-600">
          <ShieldCheck className="w-3.5 h-3.5" />
          <span>JWT + bcrypt • End-to-end encrypted • SOC2-ready audit logging</span>
        </div>
      </div>

      {/* ============ RIGHT PANEL — Login Form ============ */}
      <div className="flex-1 flex items-center justify-center p-6 sm:p-8">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
          className="w-full max-w-sm"
        >
          {/* Mobile logo */}
          <div className="lg:hidden flex items-center gap-2.5 mb-8">
            <BrandLogo size={36} />
            <span className="text-lg font-bold text-white">AhmedETAP</span>
          </div>

          {/* Header */}
          <div className="mb-8">
            <h2 className="text-2xl font-bold text-white mb-1">Sign in</h2>
            <p className="text-sm text-slate-500">Enter your credentials to continue</p>
          </div>

          {/* Error banner */}
          {authError && (
            <div className="mb-4 p-3 rounded-md bg-red-950/40 border border-red-800/50 flex items-start gap-2.5">
              <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0 text-red-400" />
              <p className="text-xs text-red-300">{authError}</p>
            </div>
          )}

          {/* Forgot password modal */}
          {forgotOpen && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              className="mb-4 p-4 rounded-md bg-slate-900/60 border border-slate-700/50"
            >
              {forgotSent ? (
                <div className="text-center py-2">
                  <p className="text-sm text-green-400 mb-3">
                    If the email exists, a reset token has been sent.
                  </p>
                  <button
                    onClick={() => { setForgotOpen(false); setForgotSent(false); setForgotEmail('') }}
                    className="text-xs text-slate-400 hover:text-white transition-colors"
                  >
                    Back to sign in
                  </button>
                </div>
              ) : (
                <form onSubmit={handleForgotPassword}>
                  <p className="text-sm text-white mb-3">Reset your password</p>
                  <input
                    type="email"
                    value={forgotEmail}
                    onChange={e => setForgotEmail(e.target.value)}
                    placeholder="your@email.com"
                    required
                    className="w-full px-3 py-2 mb-3 bg-slate-950 border border-slate-700 rounded text-sm text-white placeholder-slate-600 focus:outline-none focus:border-blue-500 transition-colors"
                  />
                  <div className="flex gap-2">
                    <button
                      type="submit"
                      disabled={forgotLoading}
                      className="flex-1 py-2 bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium rounded transition-colors disabled:opacity-50"
                    >
                      {forgotLoading ? 'Sending...' : 'Send reset token'}
                    </button>
                    <button
                      type="button"
                      onClick={() => setForgotOpen(false)}
                      className="px-4 py-2 text-slate-400 hover:text-white text-xs transition-colors"
                    >
                      Cancel
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
                Email
              </label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-600 pointer-events-none" />
                <input
                  id="login-email"
                  type="email"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  placeholder="you@company.com"
                  required
                  className="w-full pl-9 pr-3 py-2.5 bg-slate-950 border border-slate-700/50 rounded text-sm text-white placeholder-slate-600 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500/20 transition-all"
                />
              </div>
            </div>

            <div>
              <label htmlFor="login-password" className="block text-xs font-medium text-slate-400 mb-1.5">
                Password
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-600 pointer-events-none" />
                <input
                  id="login-password"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                  className="w-full pl-9 pr-10 py-2.5 bg-slate-950 border border-slate-700/50 rounded text-sm text-white placeholder-slate-600 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500/20 transition-all"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(p => !p)}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 p-1 rounded text-slate-600 hover:text-slate-300 transition-colors"
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <div className="flex items-center justify-between text-xs">
              <label className="flex items-center gap-1.5 text-slate-500 cursor-pointer">
                <input type="checkbox" className="rounded border-slate-700 bg-slate-950 text-blue-600 focus:ring-blue-500/20" />
                Remember me
              </label>
              <button
                type="button"
                onClick={() => { setForgotOpen(true); setAuthError(null) }}
                className="text-blue-400 hover:text-blue-300 font-medium transition-colors"
              >
                Forgot password?
              </button>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded text-sm font-semibold transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Signing in...
                </>
              ) : (
                <>
                  Sign in
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>

          {/* Footer */}
          <div className="mt-8 pt-6 border-t border-slate-800/50 flex items-center justify-between">
            <p className="text-xs text-slate-600">
              No account?{' '}
              <Link to="/register" className="text-blue-400 hover:text-blue-300 font-medium transition-colors">
                Create one
              </Link>
            </p>
            <p className="text-[10px] text-slate-700 font-mono">v2.1.0</p>
          </div>
        </motion.div>
      </div>
    </div>
  )
}
