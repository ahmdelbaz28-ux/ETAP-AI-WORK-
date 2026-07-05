import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Mail, Lock, ArrowRight, Eye, EyeOff, ShieldCheck, Activity, Cpu, AlertCircle } from 'lucide-react'
import { useNotify } from '../context/NotificationContext'
import { useAuth } from '../hooks/useAuth'
import { BrandLogo } from '../components/BrandLogo'

/**
 * Login — AhmedETAP sign-in page.
 *
 * Visual theme: "Power Grid Awakening"
 *   The background is a live power-grid SVG with buses that pulse and energy
 *   pulses that travel along transmission lines, reinforcing the platform's
 *   power-systems identity. Aurora blobs, a vertical scanline, and rising
 *   electron particles add cinematic depth.
 *
 * Auth mode: Production (with Demo fallback).
 *   1. Attempts real authentication via `useAuth().login()` → POST /api/v1/auth/login
 *      (JWT + bcrypt + MFA on the backend).
 *   2. On network error (backend unreachable, e.g. local dev without server),
 *      falls back to Demo Mode: writes a fake token to localStorage and
 *      navigates to /dashboard. A visible warning banner explains this.
 *   3. On real auth failure (401/400 with detail), shows the backend error
 *      message and does NOT fall back to demo.
 */
export default function Login() {
  const navigate = useNavigate()
  const { notify } = useNotify()
  const { login } = useAuth()
  const [email, setEmail] = useState('ahmed.elbaz@etap.ai')
  const [password, setPassword] = useState('demo1234')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [authError, setAuthError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!email || !password) {
      notify('error', 'Please enter email and password')
      return
    }
    setLoading(true)
    setAuthError(null)
    try {
      // 1. Try real backend authentication first
      await login(email, password)
      notify('success', 'Welcome back!')
      navigate('/dashboard')
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown error'
      // 2. Detect network errors (backend unreachable) — fall back to demo mode
      const isNetworkError =
        message.toLowerCase().includes('failed to fetch') ||
        message.toLowerCase().includes('network') ||
        message.toLowerCase().includes('load failed')
      if (isNetworkError) {
        // Demo fallback — backend is not reachable (local dev / preview env)
        await new Promise(r => setTimeout(r, 600))
        localStorage.setItem('authToken', 'demo-token-' + Date.now())
        localStorage.setItem('etap-user', JSON.stringify({
          id: '1',
          email,
          name: 'Eng. Ahmed Elbaz',
          role: 'Administrator',
        }))
        setAuthError('Backend unreachable — signed in via Demo Mode. Backend authentication will be used when the API is available.')
        notify('warning', 'Backend unreachable — using Demo Mode')
        // Brief delay so the user sees the warning, then navigate
        setTimeout(() => navigate('/dashboard'), 1200)
      } else {
        // 3. Real auth failure (401, 400, etc.) — show the backend error
        setAuthError(message)
        notify('error', `Login failed: ${message}`)
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--bg-primary)] p-4 relative overflow-hidden">
      {/* ============ CINEMATIC BACKGROUND ============ */}

      {/* Aurora blobs */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden" aria-hidden="true">
        <div className="absolute -top-40 -left-40 w-[520px] h-[520px] rounded-full blur-3xl animate-aurora"
             style={{ background: 'radial-gradient(circle, rgba(59,130,246,0.45), transparent 70%)', opacity: 0.5 }} />
        <div className="absolute -bottom-60 -right-40 w-[620px] h-[620px] rounded-full blur-3xl animate-aurora"
             style={{ background: 'radial-gradient(circle, rgba(0,212,255,0.32), transparent 70%)', opacity: 0.5, animationDelay: '-6s', animationDirection: 'reverse' }} />
        <div className="absolute top-1/2 left-1/3 w-[420px] h-[420px] rounded-full blur-3xl animate-aurora"
             style={{ background: 'radial-gradient(circle, rgba(167,139,250,0.22), transparent 70%)', opacity: 0.5, animationDelay: '-12s' }} />
      </div>

      {/* Power grid SVG background */}
      <svg
        className="absolute inset-0 w-full h-full pointer-events-none"
        viewBox="0 0 1440 900"
        preserveAspectRatio="xMidYMid slice"
        aria-hidden="true"
      >
        <defs>
          <path id="etap-p1" d="M 80 200 L 280 140 L 460 220 L 660 160" />
          <path id="etap-p2" d="M 660 160 L 880 240 L 1080 180 L 1320 220" />
          <path id="etap-p3" d="M 80 460 L 280 400 L 460 480 L 660 420 L 880 500 L 1080 440 L 1320 480" />
          <path id="etap-p4" d="M 80 720 L 280 660 L 460 740 L 660 680" />
          <path id="etap-p5" d="M 660 680 L 880 760 L 1080 700 L 1320 740" />
          <path id="etap-p6" d="M 280 140 L 280 400 L 280 660" />
          <path id="etap-p7" d="M 660 160 L 660 420 L 660 680" />
          <path id="etap-p8" d="M 1080 180 L 1080 440 L 1080 700" />
          <path id="etap-p9" d="M 460 220 L 460 480 L 460 740" />
          <path id="etap-p10" d="M 880 240 L 880 500 L 880 760" />
        </defs>

        {/* Transmission lines */}
        <use href="#etap-p1" stroke="rgba(96,165,250,0.18)" strokeWidth="1" fill="none" />
        <use href="#etap-p2" stroke="rgba(96,165,250,0.18)" strokeWidth="1" fill="none" />
        <use href="#etap-p3" stroke="rgba(0,212,255,0.35)" strokeWidth="1.4" fill="none" />
        <use href="#etap-p4" stroke="rgba(96,165,250,0.18)" strokeWidth="1" fill="none" />
        <use href="#etap-p5" stroke="rgba(96,165,250,0.18)" strokeWidth="1" fill="none" />
        <use href="#etap-p6" stroke="rgba(96,165,250,0.18)" strokeWidth="1" fill="none" />
        <use href="#etap-p7" stroke="rgba(0,212,255,0.35)" strokeWidth="1.4" fill="none" />
        <use href="#etap-p8" stroke="rgba(96,165,250,0.18)" strokeWidth="1" fill="none" />
        <use href="#etap-p9" stroke="rgba(96,165,250,0.18)" strokeWidth="1" fill="none" />
        <use href="#etap-p10" stroke="rgba(96,165,250,0.18)" strokeWidth="1" fill="none" />

        {/* Buses (junction nodes) */}
        <circle className="etap-grid-bus" cx="80" cy="200" r="3.5" fill="rgba(0,212,255,0.65)" />
        <circle className="etap-grid-bus etap-grid-bus-amber" cx="280" cy="140" r="4" fill="rgba(245,158,11,0.7)" />
        <circle className="etap-grid-bus" cx="460" cy="220" r="3.5" fill="rgba(0,212,255,0.65)" />
        <circle className="etap-grid-bus etap-grid-bus-green" cx="660" cy="160" r="5" fill="rgba(34,197,94,0.7)" />
        <circle className="etap-grid-bus" cx="880" cy="240" r="3.5" fill="rgba(0,212,255,0.65)" />
        <circle className="etap-grid-bus etap-grid-bus-amber" cx="1080" cy="180" r="4" fill="rgba(245,158,11,0.7)" />
        <circle className="etap-grid-bus" cx="1320" cy="220" r="3.5" fill="rgba(0,212,255,0.65)" />

        <circle className="etap-grid-bus etap-grid-bus-amber" cx="80" cy="460" r="4" fill="rgba(245,158,11,0.7)" />
        <circle className="etap-grid-bus" cx="280" cy="400" r="3.5" fill="rgba(0,212,255,0.65)" />
        <circle className="etap-grid-bus etap-grid-bus-green" cx="460" cy="480" r="5" fill="rgba(34,197,94,0.7)" />
        <circle className="etap-grid-bus" cx="660" cy="420" r="4" fill="rgba(0,212,255,0.65)" />
        <circle className="etap-grid-bus etap-grid-bus-amber" cx="880" cy="500" r="4" fill="rgba(245,158,11,0.7)" />
        <circle className="etap-grid-bus" cx="1080" cy="440" r="3.5" fill="rgba(0,212,255,0.65)" />
        <circle className="etap-grid-bus etap-grid-bus-green" cx="1320" cy="480" r="4" fill="rgba(34,197,94,0.7)" />

        <circle className="etap-grid-bus" cx="80" cy="720" r="3.5" fill="rgba(0,212,255,0.65)" />
        <circle className="etap-grid-bus etap-grid-bus-green" cx="280" cy="660" r="4" fill="rgba(34,197,94,0.7)" />
        <circle className="etap-grid-bus" cx="460" cy="740" r="3.5" fill="rgba(0,212,255,0.65)" />
        <circle className="etap-grid-bus etap-grid-bus-amber" cx="660" cy="680" r="4" fill="rgba(245,158,11,0.7)" />
        <circle className="etap-grid-bus" cx="880" cy="760" r="3.5" fill="rgba(0,212,255,0.65)" />
        <circle className="etap-grid-bus etap-grid-bus-green" cx="1080" cy="700" r="4" fill="rgba(34,197,94,0.7)" />
        <circle className="etap-grid-bus" cx="1320" cy="740" r="3.5" fill="rgba(0,212,255,0.65)" />

        {/* Energy pulses traveling along lines */}
        <circle r="2.5" fill="#00d4ff" style={{ filter: 'drop-shadow(0 0 6px #00d4ff)' }}>
          <animateMotion dur="4s" repeatCount="indefinite" rotate="auto"><mpath href="#etap-p1" /></animateMotion>
        </circle>
        <circle r="2.5" fill="#fbbf24" style={{ filter: 'drop-shadow(0 0 6px #f59e0b)' }}>
          <animateMotion dur="5s" repeatCount="indefinite" begin="0.8s"><mpath href="#etap-p2" /></animateMotion>
        </circle>
        <circle r="3" fill="#00d4ff" style={{ filter: 'drop-shadow(0 0 6px #00d4ff)' }}>
          <animateMotion dur="4.5s" repeatCount="indefinite" begin="1.5s"><mpath href="#etap-p3" /></animateMotion>
        </circle>
        <circle r="2.5" fill="#4ade80" style={{ filter: 'drop-shadow(0 0 6px #22c55e)' }}>
          <animateMotion dur="5.5s" repeatCount="indefinite" begin="0.3s"><mpath href="#etap-p7" /></animateMotion>
        </circle>
        <circle r="2.5" fill="#00d4ff" style={{ filter: 'drop-shadow(0 0 6px #00d4ff)' }}>
          <animateMotion dur="4.8s" repeatCount="indefinite" begin="2s"><mpath href="#etap-p8" /></animateMotion>
        </circle>
        <circle r="2.5" fill="#fbbf24" style={{ filter: 'drop-shadow(0 0 6px #f59e0b)' }}>
          <animateMotion dur="5.2s" repeatCount="indefinite" begin="1.2s"><mpath href="#etap-p9" /></animateMotion>
        </circle>
        <circle r="2.5" fill="#4ade80" style={{ filter: 'drop-shadow(0 0 6px #22c55e)' }}>
          <animateMotion dur="4.6s" repeatCount="indefinite" begin="2.4s"><mpath href="#etap-p10" /></animateMotion>
        </circle>
      </svg>

      {/* Rising electron particles */}
      <div className="fixed inset-0 pointer-events-none" aria-hidden="true">
        <div className="etap-particle" style={{ left: '8%',  background: '#00d4ff', boxShadow: '0 0 8px #00d4ff', animationDelay: '0s' }} />
        <div className="etap-particle" style={{ left: '22%', background: '#f59e0b', boxShadow: '0 0 8px #f59e0b', animationDelay: '3s' }} />
        <div className="etap-particle" style={{ left: '38%', background: '#22c55e', boxShadow: '0 0 8px #22c55e', animationDelay: '6s' }} />
        <div className="etap-particle" style={{ left: '55%', background: '#00d4ff', boxShadow: '0 0 8px #00d4ff', animationDelay: '1.5s' }} />
        <div className="etap-particle" style={{ left: '72%', background: '#60a5fa', boxShadow: '0 0 8px #60a5fa', animationDelay: '4.5s' }} />
        <div className="etap-particle" style={{ left: '88%', background: '#f59e0b', boxShadow: '0 0 8px #f59e0b', animationDelay: '7.5s' }} />
        <div className="etap-particle" style={{ left: '15%', background: '#22c55e', boxShadow: '0 0 8px #22c55e', animationDelay: '9s' }} />
        <div className="etap-particle" style={{ left: '65%', background: '#00d4ff', boxShadow: '0 0 8px #00d4ff', animationDelay: '10.5s' }} />
      </div>

      {/* Scanline sweep */}
      <div className="etap-scanline" aria-hidden="true" />

      {/* HUD corner brackets */}
      <div className="etap-corner etap-corner-tl" aria-hidden="true" />
      <div className="etap-corner etap-corner-tr" aria-hidden="true" />
      <div className="etap-corner etap-corner-bl" aria-hidden="true" />
      <div className="etap-corner etap-corner-br" aria-hidden="true" />

      {/* Top status bar — hidden on mobile (too cramped at 375px) */}
      <motion.div
        className="etap-topbar hidden md:flex"
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 1.2 }}
        aria-hidden="true"
      >
        <span>AHMED ETAP // v2.1.0</span>
        <span className="etap-topbar-sep" />
        <span>IEEE / IEC COMPLIANT</span>
        <span className="etap-topbar-sep" />
        <span className="etap-topbar-live">GRID ONLINE</span>
      </motion.div>

      {/* ============ MAIN LAYOUT ============ */}
      <div className="relative z-10 w-full max-w-5xl grid lg:grid-cols-2 gap-4 lg:gap-8 items-center">

        {/* LEFT: BRANDING */}
        <motion.div
          initial={{ opacity: 0, x: -30 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1], delay: 0.1 }}
          className="hidden lg:flex flex-col gap-7"
        >
          {/* Logo + name */}
          <div className="flex items-center gap-4">
            <BrandLogo size={64} animated />
            <div>
              <h1 className="text-3xl font-extrabold tracking-tight text-[var(--text-primary)]">AhmedETAP</h1>
              <p className="text-sm text-[var(--text-muted)] mt-0.5">Power Systems Engineering Platform</p>
            </div>
          </div>

          {/* Headline */}
          <h2 className="text-5xl font-extrabold leading-[1.1] tracking-tight">
            <span className="text-[var(--text-primary)]">Enterprise-grade autonomous</span>
            <br />
            <span className="etap-gradient-text">engineering intelligence</span>
          </h2>

          {/* Subhead */}
          <p className="text-base text-[var(--text-secondary)] leading-relaxed max-w-[480px]">
            Run real engineering computations: Load Flow, Short Circuit, Arc Flash,
            Harmonic Analysis, and more — powered by AI agents and the Python engine.
          </p>

          {/* Stats */}
          <div className="grid grid-cols-3 gap-3 mt-2">
            {[
              { icon: <Cpu className="w-5 h-5 text-brand-400 mb-1.5" />, label: 'AI Agents', value: '8+ Specialized', delay: 0.6 },
              { icon: <Activity className="w-5 h-5 text-green-400 mb-1.5" />, label: 'Studies', value: '8 Types', delay: 0.72 },
              { icon: <ShieldCheck className="w-5 h-5 text-amber-400 mb-1.5" />, label: 'Standards', value: 'IEEE / IEC', delay: 0.84 },
            ].map((s) => (
              <motion.div
                key={s.label}
                initial={{ opacity: 0, y: 20, scale: 0.95 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1], delay: s.delay }}
                className="etap-stat-card bg-[var(--bg-card)] rounded-xl p-3.5 border border-[var(--border-primary)] backdrop-blur-sm"
              >
                {s.icon}
                <p className="text-[11px] text-[var(--text-tertiary)] uppercase tracking-wider">{s.label}</p>
                <p className="text-sm font-bold text-[var(--text-primary)] mt-0.5">{s.value}</p>
              </motion.div>
            ))}
          </div>

          {/* Footer hint */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 1 }}
            className="flex items-center gap-2.5 text-[11px] text-[var(--text-muted)] font-mono tracking-wider"
          >
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-green-500 shadow-[0_0_8px_#22c55e] animate-pulse" />
            <span>REAL-TIME // 8 AGENTS ACTIVE // GRID SYNCED</span>
          </motion.div>
        </motion.div>

        {/* RIGHT: LOGIN CARD */}
        <motion.div
          initial={{ opacity: 0, x: 30 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1], delay: 0.5 }}
          className="etap-card-border bg-[var(--bg-card)] rounded-2xl border border-[var(--border-strong)] p-5 sm:p-6 md:p-8 shadow-2xl shadow-black/40 backdrop-blur-xl relative"
        >
          {/* Mobile logo */}
          <div className="lg:hidden flex items-center gap-3 mb-6">
            <BrandLogo size={40} />
            <h1 className="text-xl font-bold text-[var(--text-primary)]">AhmedETAP</h1>
          </div>

          {/* Card header */}
          <div className="mb-6">
            <h2 className="text-2xl font-bold bg-gradient-to-br from-[var(--text-primary)] to-[var(--text-secondary)] bg-clip-text text-transparent">
              Welcome back
            </h2>
            <p className="text-sm text-[var(--text-tertiary)] mt-1">Sign in to your engineering account</p>
          </div>

          {/* Demo banner */}
          <div className="etap-shine relative overflow-hidden bg-brand-500/10 border border-brand-500/20 rounded-lg p-3 mb-4 flex items-start gap-3">
            <span className="inline-block w-2 h-2 rounded-full bg-amber-500 shadow-[0_0_10px_#f59e0b] mt-1.5 animate-pulse flex-shrink-0" />
            <div className="text-xs">
              <p className="text-brand-400 font-semibold mb-0.5">Demo Mode Active</p>
              <p className="text-[var(--text-secondary)]">
                Use the pre-filled credentials or any email/password to sign in. Real backend auth is attempted first; Demo Mode is the fallback when the API is unreachable.
              </p>
            </div>
          </div>

          {/* Auth error / warning banner */}
          {authError && (
            <motion.div
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              className={`relative overflow-hidden rounded-lg p-3 mb-4 flex items-start gap-3 ${
                authError.includes('Demo Mode')
                  ? 'bg-amber-500/10 border border-amber-500/30'
                  : 'bg-red-500/10 border border-red-500/30'
              }`}
              role="alert"
            >
              <AlertCircle className={`w-4 h-4 mt-0.5 flex-shrink-0 ${
                authError.includes('Demo Mode') ? 'text-amber-400' : 'text-red-400'
              }`} />
              <p className={`text-xs ${
                authError.includes('Demo Mode') ? 'text-amber-300' : 'text-red-300'
              }`}>
                {authError}
              </p>
            </motion.div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Email */}
            <div>
              <label htmlFor="login-email" className="block text-[11px] font-medium text-[var(--text-secondary)] mb-1.5 uppercase tracking-wider">
                Email Address
              </label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-muted)] pointer-events-none" />
                <input
                  id="login-email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@company.com"
                  required
                  className="etap-input w-full pl-9 pr-3 py-2.5 bg-[var(--bg-input)] border border-[var(--border-strong)] rounded-lg text-sm text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none transition-all"
                />
              </div>
            </div>

            {/* Password */}
            <div>
              <label htmlFor="login-password" className="block text-[11px] font-medium text-[var(--text-secondary)] mb-1.5 uppercase tracking-wider">
                Password
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-muted)] pointer-events-none" />
                <input
                  id="login-password"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                  className="etap-input w-full pl-9 pr-10 py-2.5 bg-[var(--bg-input)] border border-[var(--border-strong)] rounded-lg text-sm text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none transition-all"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(p => !p)}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 p-1 rounded text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-white/5 transition-colors"
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {/* Remember + forgot */}
            <div className="flex items-center justify-between text-xs">
              <label className="flex items-center gap-1.5 text-[var(--text-tertiary)] cursor-pointer">
                <input id="login-remember-me" type="checkbox" defaultChecked className="rounded border-[var(--border-primary)] bg-[var(--bg-input)] text-brand-500 focus:ring-brand-500/20" />
                Remember me
              </label>
              <button type="button" className="text-brand-400 hover:text-[var(--accent-primary)] transition-colors">
                Forgot password?
              </button>
            </div>

            {/* Submit */}
            <button
              type="submit"
              disabled={loading}
              className="etap-btn-shine relative w-full flex items-center justify-center gap-2 px-4 py-3 bg-gradient-to-r from-brand-600 to-brand-700 hover:from-brand-500 hover:to-brand-600 text-white rounded-lg font-semibold text-sm shadow-lg shadow-brand-600/20 hover:shadow-[0_16px_40px_-8px_rgba(0,212,255,0.55)] transition-all disabled:opacity-50 disabled:cursor-not-allowed overflow-hidden"
            >
              {loading ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Signing in...
                </>
              ) : (
                <>
                  Sign In
                  <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-1" />
                </>
              )}
            </button>
          </form>

          {/* Sign up link */}
          <p className="mt-6 text-center text-sm text-[var(--text-tertiary)]">
            Don't have an account?{' '}
            <Link to="/register" className="text-brand-400 hover:text-[var(--accent-primary)] font-medium transition-colors">
              Sign up
            </Link>
          </p>

          {/* Version */}
          <div className="mt-6 pt-4 border-t border-[var(--border-primary)] text-center">
            <p className="text-[10px] text-[var(--text-muted)] font-mono tracking-wider">
              AhmedETAP v2.1.0 · Demo Build · 2026
            </p>
          </div>
        </motion.div>
      </div>
    </div>
  )
}
