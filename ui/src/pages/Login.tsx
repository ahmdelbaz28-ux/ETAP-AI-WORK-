import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Zap, Mail, Lock, ArrowRight, Eye, EyeOff, ShieldCheck, Activity, Cpu } from 'lucide-react';
import { useNotify } from '../context/NotificationContext';

export default function Login() {
  const navigate = useNavigate();
  const { notify } = useNotify();
  const [email, setEmail] = useState('ahmed.elbaz@etap.ai');
  const [password, setPassword] = useState('demo1234');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) {
      notify('error', 'Please enter email and password');
      return;
    }
    setLoading(true);
    // Demo mode: accept any credentials
    await new Promise((r) => setTimeout(r, 800));
    localStorage.setItem('authToken', `demo-token-${Date.now()}`);
    localStorage.setItem(
      'etap-user',
      JSON.stringify({
        id: '1',
        email,
        name: 'Eng. Ahmed Elbaz',
        role: 'Administrator',
      }),
    );
    notify('success', 'Welcome back, Eng. Ahmed!');
    navigate('/dashboard');
    setLoading(false);
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--bg-primary)] p-4 relative overflow-hidden">
      {/* Animated background */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden" aria-hidden="true">
        <div className="absolute -top-40 -left-40 w-[500px] h-[500px] bg-gradient-to-br from-brand-500/10 via-transparent to-transparent rounded-full blur-3xl animate-aurora" />
        <div
          className="absolute -bottom-60 -right-40 w-[600px] h-[600px] bg-gradient-to-tl from-purple-500/8 via-transparent to-transparent rounded-full blur-3xl animate-aurora"
          style={{ animationDelay: '-7s', animationDirection: 'reverse' }}
        />
        <div
          className="absolute top-1/2 left-1/3 w-[400px] h-[400px] bg-gradient-to-r from-cyan-500/6 via-transparent to-transparent rounded-full blur-3xl animate-aurora"
          style={{ animationDelay: '-14s' }}
        />
      </div>

      <div className="relative z-10 w-full max-w-5xl grid lg:grid-cols-2 gap-8 items-center">
        {/* Left side — Branding */}
        <motion.div
          initial={{ opacity: 0, x: -30 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.6 }}
          className="hidden lg:flex flex-col gap-6"
        >
          <div className="flex items-center gap-3">
            <div className="w-14 h-14 bg-gradient-to-br from-brand-500 to-brand-700 rounded-2xl flex items-center justify-center shadow-2xl shadow-brand-500/30">
              <Zap className="w-7 h-7 text-white" />
            </div>
            <div>
              <h1 className="text-3xl font-bold text-[var(--text-primary)]">AhmedETAP</h1>
              <p className="text-sm text-[var(--text-muted)]">Power Systems Engineering Platform</p>
            </div>
          </div>

          <h2 className="text-4xl font-bold text-[var(--text-primary)] leading-tight">
            Enterprise-grade autonomous
            <br />
            <span className="bg-gradient-to-r from-brand-400 to-cyan-400 bg-clip-text text-transparent">
              engineering intelligence
            </span>
          </h2>
          <p className="text-base text-[var(--text-secondary)] leading-relaxed">
            Run real engineering computations: Load Flow, Short Circuit, Arc Flash, Harmonic
            Analysis, and more — powered by AI agents and the Python engine.
          </p>

          <div className="grid grid-cols-3 gap-3 mt-4">
            <div className="bg-[var(--bg-card)] rounded-xl p-3 border border-[var(--border-primary)]">
              <Cpu className="w-5 h-5 text-brand-400 mb-1.5" />
              <p className="text-xs text-[var(--text-tertiary)]">AI Agents</p>
              <p className="text-sm font-bold text-[var(--text-primary)]">8+ Specialized</p>
            </div>
            <div className="bg-[var(--bg-card)] rounded-xl p-3 border border-[var(--border-primary)]">
              <Activity className="w-5 h-5 text-green-400 mb-1.5" />
              <p className="text-xs text-[var(--text-tertiary)]">Studies</p>
              <p className="text-sm font-bold text-[var(--text-primary)]">8 Types</p>
            </div>
            <div className="bg-[var(--bg-card)] rounded-xl p-3 border border-[var(--border-primary)]">
              <ShieldCheck className="w-5 h-5 text-amber-400 mb-1.5" />
              <p className="text-xs text-[var(--text-tertiary)]">Standards</p>
              <p className="text-sm font-bold text-[var(--text-primary)]">IEEE / IEC</p>
            </div>
          </div>
        </motion.div>

        {/* Right side — Login form */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.1 }}
          className="bg-[var(--bg-card)] rounded-2xl border border-[var(--border-primary)] p-8 shadow-2xl shadow-black/40"
        >
          <div className="lg:hidden flex items-center gap-3 mb-6">
            <div className="w-10 h-10 bg-gradient-to-br from-brand-500 to-brand-700 rounded-xl flex items-center justify-center">
              <Zap className="w-5 h-5 text-white" />
            </div>
            <h1 className="text-xl font-bold text-[var(--text-primary)]">AhmedETAP</h1>
          </div>

          <h2 className="text-2xl font-bold text-[var(--text-primary)] mb-1">Welcome back</h2>
          <p className="text-sm text-[var(--text-tertiary)] mb-6">
            Sign in to your engineering account
          </p>

          <div className="bg-brand-500/10 border border-brand-500/20 rounded-lg p-3 mb-6">
            <p className="text-xs text-brand-400 font-medium mb-1">Demo Mode Active</p>
            <p className="text-xs text-[var(--text-secondary)]">
              Use the pre-filled credentials or any email/password to sign in. No backend required.
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label
                htmlFor="login-email"
                className="block text-xs font-medium text-[var(--text-secondary)] mb-1.5"
              >
                Email Address
              </label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-muted)]" />
                <input
                  id="login-email"
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
              <label
                htmlFor="login-password"
                className="block text-xs font-medium text-[var(--text-secondary)] mb-1.5"
              >
                Password
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-muted)]" />
                <input
                  id="login-password"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                  className="w-full pl-9 pr-10 py-2.5 bg-[var(--bg-input)] border border-[var(--border-primary)] rounded-lg text-sm text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 transition-all"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((p) => !p)}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 p-1 rounded text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors"
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <div className="flex items-center justify-between text-xs">
              <label className="flex items-center gap-1.5 text-[var(--text-tertiary)] cursor-pointer">
                <input
                  id="login-remember-me"
                  type="checkbox"
                  defaultChecked
                  className="rounded border-[var(--border-primary)] bg-[var(--bg-input)] text-brand-500 focus:ring-brand-500/20"
                />
                Remember me
              </label>
              <button
                type="button"
                className="text-brand-400 hover:text-brand-300 transition-colors"
              >
                Forgot password?
              </button>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-gradient-to-r from-brand-600 to-brand-700 hover:from-brand-500 hover:to-brand-600 text-white rounded-lg font-medium text-sm shadow-lg shadow-brand-600/20 hover:shadow-brand-500/30 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Signing in...
                </>
              ) : (
                <>
                  Sign In
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-[var(--text-tertiary)]">
            Don't have an account?{' '}
            <Link
              to="/register"
              className="text-brand-400 hover:text-brand-300 font-medium transition-colors"
            >
              Sign up
            </Link>
          </p>

          <div className="mt-6 pt-4 border-t border-[var(--border-primary)] text-center">
            <p className="text-[10px] text-[var(--text-muted)] font-mono">
              AhmedETAP v2.1.0 · Demo Build · 2026
            </p>
          </div>
        </motion.div>
      </div>
    </div>
  );
}
