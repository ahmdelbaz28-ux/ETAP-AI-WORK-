import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { User, Mail, Lock, ArrowRight, Eye, EyeOff, CheckCircle, AlertCircle } from 'lucide-react'
import { useNotify } from '../context/NotificationContext'
import { useAuth } from '../hooks/useAuth'
import { BrandLogo } from '../components/BrandLogo'

export default function Register() {
  const navigate = useNavigate()
  const { notify } = useNotify()
  const { register } = useAuth()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [authError, setAuthError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name || !email || !password) {
      notify('error', 'Please fill in all fields')
      return
    }
    if (password !== confirmPassword) {
      notify('error', 'Passwords do not match')
      return
    }
    if (password.length < 8) {
      notify('error', 'Password must be at least 8 characters')
      return
    }
    setLoading(true)
    setAuthError(null)
    try {
      await register(email, password, name)
      notify('success', `Welcome to AhmedETAP, ${name}!`)
      navigate('/dashboard')
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown error'
      setAuthError(message)
      notify('error', `Registration failed: ${message}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--bg-primary)] p-4 relative overflow-hidden">
      <div className="fixed inset-0 pointer-events-none overflow-hidden" aria-hidden="true">
        <div className="absolute -top-40 -left-40 w-[500px] h-[500px] bg-gradient-to-br from-brand-500/10 via-transparent to-transparent rounded-full blur-3xl animate-aurora" />
        <div className="absolute -bottom-60 -right-40 w-[600px] h-[600px] bg-gradient-to-tl from-purple-500/8 via-transparent to-transparent rounded-full blur-3xl animate-aurora" style={{ animationDelay: '-7s', animationDirection: 'reverse' }} />
      </div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="relative z-10 w-full max-w-md bg-[var(--bg-card)] rounded-2xl border border-[var(--border-primary)] p-8 shadow-2xl shadow-black/40"
      >
        <div className="flex items-center gap-3 mb-6">
          <BrandLogo size={40} />
          <h1 className="text-xl font-bold text-[var(--text-primary)]">Create Account</h1>
        </div>

        <h2 className="text-2xl font-bold text-[var(--text-primary)] mb-1">Join AhmedETAP</h2>
        <p className="text-sm text-[var(--text-tertiary)] mb-6">Start your power systems engineering journey</p>

        {authError && (
          <div className="mb-4 p-3 rounded-lg bg-red-500/10 border border-red-500/30 flex items-start gap-3" role="alert">
            <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0 text-red-400" />
            <p className="text-xs text-red-300">{authError}</p>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="register-name" className="block text-xs font-medium text-[var(--text-secondary)] mb-1.5">Full Name</label>
            <div className="relative">
              <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-muted)]" />
              <input
                id="register-name"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Eng. Ahmed Elbaz"
                required
                className="w-full pl-9 pr-3 py-2.5 bg-[var(--bg-input)] border border-[var(--border-primary)] rounded-lg text-sm text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 transition-all"
              />
            </div>
          </div>

          <div>
            <label htmlFor="register-email" className="block text-xs font-medium text-[var(--text-secondary)] mb-1.5">Email Address</label>
            <div className="relative">
              <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-muted)]" />
              <input
                id="register-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@company.com"
                required
                className="w-full pl-9 pr-3 py-2.5 bg-[var(--bg-input)] border border-[var(--border-primary)] rounded-lg text-sm text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 transition-all"
              />
            </div>
          </div>

          <div>
            <label htmlFor="register-password" className="block text-xs font-medium text-[var(--text-secondary)] mb-1.5">Password</label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-muted)]" />
              <input
                id="register-password"
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="At least 6 characters"
                required
                className="w-full pl-9 pr-10 py-2.5 bg-[var(--bg-input)] border border-[var(--border-primary)] rounded-lg text-sm text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 transition-all"
              />
              <button
                type="button"
                onClick={() => setShowPassword(p => !p)}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 p-1 rounded text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors"
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          <div>
            <label htmlFor="register-confirm-password" className="block text-xs font-medium text-[var(--text-secondary)] mb-1.5">Confirm Password</label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-muted)]" />
              <input
                id="register-confirm-password"
                type={showPassword ? 'text' : 'password'}
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Re-enter password"
                required
                className="w-full pl-9 pr-3 py-2.5 bg-[var(--bg-input)] border border-[var(--border-primary)] rounded-lg text-sm text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 transition-all"
              />
            </div>
            {confirmPassword && password === confirmPassword && (
              <p className="mt-1.5 text-xs text-green-400 flex items-center gap-1">
                <CheckCircle className="w-3 h-3" /> Passwords match
              </p>
            )}
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-gradient-to-r from-brand-600 to-brand-700 hover:from-brand-500 hover:to-brand-600 text-white rounded-lg font-medium text-sm shadow-lg shadow-brand-600/20 hover:shadow-brand-500/30 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? (
              <>
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Creating account...
              </>
            ) : (
              <>
                Create Account
                <ArrowRight className="w-4 h-4" />
              </>
            )}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-[var(--text-tertiary)]">
          Already have an account?{' '}
          <Link to="/login" className="text-brand-400 hover:text-brand-300 font-medium transition-colors">
            Sign in
          </Link>
        </p>

        <div className="mt-6 pt-4 border-t border-[var(--border-primary)] text-center">
          <p className="text-[10px] text-[var(--text-muted)] font-mono">
            AhmedETAP v2.1.0 · 2026
          </p>
        </div>
      </motion.div>
    </div>
  )
}
