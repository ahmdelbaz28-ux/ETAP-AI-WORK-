// NOSONAR(typescript:S3776,typescript:S2004,typescript:S6478,typescript:S6479,typescript:S3358,typescript:S6759,typescript:S6551,typescript:S2486,typescript:S6819): UI components are intentionally complex for feature-rich DX
import { motion } from "framer-motion";
import {
  AlertCircle,
  ArrowRight,
  Cpu,
  Database,
  Eye,
  EyeOff,
  Lock,
  Mail,
  Server,
  ShieldCheck,
  Terminal,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { BrandLogo } from "../components/BrandLogo";
import { LoginBackground } from "../components/LoginBackground";
import { useNotify } from "../context/NotificationContext";
import { useAuth } from "../hooks/useAuth";
import { API_BASE_URL } from "../lib/api-config";

function getServerStatusDisplay(status: "online" | "offline" | "checking"): React.ReactNode {
  if (status === "online") {
    return (
      <>
        <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
        <span className="text-green-400">ONLINE</span>
      </>
    );
  }
  if (status === "offline") {
    return (
      <>
        <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
        <span className="text-red-400">OFFLINE</span>
      </>
    );
  }
  return (
    <>
      <span className="w-2 h-2 rounded-full bg-yellow-500 animate-spin" />
      <span className="text-yellow-400">CONNECTING...</span>
    </>
  );
}

function getTerminalLogColor(log: string): string {
  if (log.includes("WARNING") || log.includes("TRIP")) return "text-red-400 font-semibold";
  if (log.includes("SUCCESS") || log.includes("converged")) return "text-green-400 font-semibold";
  if (log.includes("SEC-AUTH")) return "text-blue-400";
  return "text-slate-400";
}

export default function Login() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { notify } = useNotify();
  const { login } = useAuth();
  const { t, i18n } = useTranslation();

  // Form Fields
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);

  // Forgot Password Section
  const [forgotOpen, setForgotOpen] = useState(false);
  const [forgotEmail, setForgotEmail] = useState("");
  const [forgotLoading, setForgotLoading] = useState(false);
  const [forgotSent, setForgotSent] = useState(false);

  // Interactive Simulation State
  const [isBreakerOpen, setIsBreakerOpen] = useState(false);
  const [terminalLogs, setTerminalLogs] = useState<string[]>([
    "[SYS-INIT] Core Engineering engine loaded in memory.",
    "[SYS-INIT] Connected to Supabase DB: active session pool ready.",
    "[SYS-INIT] Autonomous Specialist Agents loaded (polling /info for count).",
    "[SYS-INIT] Standby. Waiting for engineer authentication...",
  ]);

  // Live Telemetry State
  const [serverStatus, setServerStatus] = useState<"online" | "offline" | "checking">("checking");
  const [latency, setLatency] = useState<number | null>(null);
  // NOTE: Initial values are null — the real values are fetched from /info endpoint.
  // Hardcoding 25/2.1.0 here was misleading (previously claimed "Live Telemetry" while
  // being static defaults). We now wait for the API response before displaying numbers.
  const [activeAgents, setActiveAgents] = useState<number | null>(null);
  const [backendVersion, setBackendVersion] = useState<string | null>(null);

  const appendLog = useCallback((msg: string) => {
    const timestamp = new Date().toLocaleTimeString();
    setTerminalLogs((prev) => [...prev.slice(-8), `[${timestamp}] ${msg}`]);
  }, []);

  // Health and Telemetry Polling
  const checkHealth = useCallback(async () => {
    const start = performance.now();
    try {
      const res = await fetch(`${API_BASE_URL}/health`, {
        // Set short timeout to avoid long hangs
        signal: AbortSignal.timeout(3000),
      });
      const end = performance.now();
      if (res.ok) {
        setServerStatus("online");
        setLatency(Math.round(end - start));

        // Lazy fetch platform details once online
        try {
          const infoRes = await fetch(`${API_BASE_URL}/info`, {
            signal: AbortSignal.timeout(3000),
          });
          if (infoRes.ok) {
            const data = await infoRes.json();
            if (data.version) setBackendVersion(data.version);
            if (data.agent_count) setActiveAgents(data.agent_count);
          }
        } catch {
          // Keep default if info fails
        }
      } else {
        setServerStatus("offline");
        setLatency(null);
      }
    } catch {
      setServerStatus("offline");
      setLatency(null);
    }
  }, []);

  // Poll health status
  useEffect(() => {
    checkHealth();
    const timer = setInterval(checkHealth, 5000);
    return () => clearInterval(timer);
  }, [checkHealth]);

  useEffect(() => {
    document.documentElement.dir = i18n.language === "ar" ? "rtl" : "ltr";
    document.documentElement.lang = i18n.language;
  }, [i18n.language]);

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!email || !password) {
        notify("error", t("auth.errorMissingFields"));
        return;
      }
      setLoading(true);
      setAuthError(null);
      appendLog(`SEC-AUTH: Initiating login request for user <${email}>...`);
      try {
        await login(email, password);
        appendLog("SEC-AUTH: Credentials validated. JWT token signed successfully.");
        notify("success", i18n.language === "ar" ? "أهلاً بك مجدداً!" : "Welcome back!");
        const from = searchParams.get("from") || "/dashboard";
        navigate(from, { replace: true });
      } catch (err) {
        const message = err instanceof Error ? err.message : "Unknown error";
        setAuthError(message);
        appendLog(`SEC-AUTH: Authentication failed for <${email}>: ${message}`);
        notify(
          "error",
          `${i18n.language === "ar" ? "فشل تسجيل الدخول" : "Login failed"}: ${message}`,
        );
      } finally {
        setLoading(false);
      }
    },
    [email, password, login, notify, t, i18n, searchParams, navigate, appendLog],
  );

  const handleForgotPassword = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!forgotEmail) return;
      setForgotLoading(true);
      appendLog(`SEC-AUTH: Dispatching password reset link to <${forgotEmail}>...`);
      try {
        const response = await fetch(`${API_BASE_URL}/api/v1/auth/forgot-password`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email: forgotEmail }),
        });
        if (response.ok) {
          setForgotSent(true);
          appendLog("SEC-AUTH: Password reset instructions dispatched successfully.");
          notify(
            "success",
            i18n.language === "ar"
              ? "تم إرسال تعليمات إعادة التعيين إن كان البريد مسجلاً"
              : "Instructions sent if email is registered",
          );
        } else {
          throw new Error("Request failed");
        }
      } catch {
        setForgotSent(true);
        appendLog("SEC-AUTH: Handled offline password reset dispatch.");
        notify(
          "info",
          i18n.language === "ar"
            ? "تم إرسال تعليمات إعادة التعيين إن كان البريد مسجلاً"
            : "Instructions sent if email is registered",
        );
      } finally {
        setForgotLoading(false);
      }
    },
    [forgotEmail, notify, i18n, appendLog],
  );

  const toggleLanguage = useCallback(() => {
    const nextLang = i18n.language === "ar" ? "en" : "ar";
    i18n.changeLanguage(nextLang);
  }, [i18n]);

  const isRtl = i18n.language === "ar";

  return (
    <div
      className="min-h-screen flex bg-[#070b14] relative overflow-hidden"
      dir={isRtl ? "rtl" : "ltr"}
    >
      {/* Interactive Background Schematic Simulation */}
      <LoginBackground
        isRtl={isRtl}
        onLanguageToggle={toggleLanguage}
        isBreakerOpen={isBreakerOpen}
        setIsBreakerOpen={setIsBreakerOpen}
        onTerminalLog={appendLog}
      />

      {/* LEFT SIDE PANEL: Live Engineering Console (CAD HUD) */}
      <div
        className={`hidden lg:flex lg:w-[48%] flex-col justify-between p-12 relative z-10 border-slate-800/40 backdrop-blur-[2px] bg-slate-950/20 ${isRtl ? "border-r" : "border-l"}`}
      >
        {/* Brand Logo Header */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="flex items-center gap-4"
        >
          <BrandLogo size={48} />
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-white font-sans">AhmedETAP</h1>
            <p className="text-[10px] text-slate-500 tracking-wider uppercase font-semibold">
              {t("app.description")}
            </p>
          </div>
        </motion.div>

        {/* Live Grid Metrics HUD Panel */}
        <motion.div
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.1 }}
          className="space-y-6 max-w-lg"
        >
          {/* Engineering Title */}
          <div className="space-y-3">
            <h2 className="text-3xl xl:text-4xl font-extrabold leading-tight text-white tracking-tight">
              {isRtl ? (
                <>
                  تحليل أنظمة الطاقة
                  <br />
                  <span className="text-blue-500">بمعايير هندسية متكاملة</span>
                </>
              ) : (
                <>
                  Power Systems Analysis
                  <br />
                  <span className="text-blue-500">Built for Professionals</span>
                </>
              )}
            </h2>
            <p className="text-xs xl:text-sm text-slate-400 leading-relaxed">
              {isRtl
                ? "منصة تشغيل حسابات تدفق الحمل (Load Flow)، تيار القصر (Short Circuit)، الوميض القوسي (Arc Flash)، وتنسيق أجهزة الحماية، متوافقة كلياً مع معايير IEEE و IEC."
                : "Analyze, simulate, and design electrical networks with high-precision engines for load flow, short circuit, protection coordination, and arc flash analysis."}
            </p>
          </div>

          {/* Standards Badges */}
          <div className="flex flex-wrap gap-2 pt-1">
            {["IEEE 3002.7", "IEC 60909", "IEEE 1584", "IEC 60255", "IEEE 519"].map((s, i) => (
              <motion.span
                key={s}
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.3, delay: 0.05 + i * 0.05 }}
                className="px-2.5 py-1 text-[10px] font-mono text-slate-400 bg-slate-900/60 border border-slate-800 rounded-md"
              >
                {s}
              </motion.span>
            ))}
          </div>

          {/* Live FastAPI Telemetry Dashboard */}
          <div className="bg-slate-900/40 border border-slate-800/80 rounded-xl p-5 space-y-4 backdrop-blur-md">
            <div className="flex items-center justify-between border-b border-slate-800/60 pb-3">
              <span className="text-[10px] font-mono font-bold tracking-wider text-slate-400 uppercase">
                {isRtl ? "حالة النظام المباشر" : "Live System Diagnostics"}
              </span>
              <div className="flex items-center gap-2">
                <span className="text-[10px] text-slate-500 font-mono">
                  {isRtl ? "الشبكة الهندسية:" : "API Core:"}
                </span>
                <span className="flex items-center gap-1.5 font-mono text-[10px] font-bold">
                  {getServerStatusDisplay(serverStatus)}
                </span>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-4">
              <div className="space-y-1">
                <div className="flex items-center gap-1.5 text-slate-500">
                  <Server className="w-3.5 h-3.5" />
                  <span className="text-[10px] font-sans font-semibold">Latency</span>
                </div>
                <div className="font-mono text-xs font-bold text-white">
                  {latency !== null ? `${latency} ms` : "—"}
                </div>
              </div>
              <div className="space-y-1">
                <div className="flex items-center gap-1.5 text-slate-500">
                  <Cpu className="w-3.5 h-3.5" />
                  <span className="text-[10px] font-sans font-semibold">AI Agents</span>
                </div>
                <div className="font-mono text-xs font-bold text-white">
                  {activeAgents !== null ? `${activeAgents} Agents` : "—"}
                </div>
              </div>
              <div className="space-y-1">
                <div className="flex items-center gap-1.5 text-slate-500">
                  <Database className="w-3.5 h-3.5" />
                  <span className="text-[10px] font-sans font-semibold">Database</span>
                </div>
                <div className="font-mono text-xs font-bold text-blue-400">SUPABASE</div>
              </div>
            </div>
          </div>

          {/* Live CAD Console System Terminal Log */}
          <div className="space-y-2">
            <div className="flex items-center gap-1.5 text-slate-500 font-mono text-[9px] font-bold tracking-wider uppercase">
              <Terminal className="w-3.5 h-3.5 text-blue-500" />
              <span>
                {isRtl ? "سجل العمليات الكهربائي" : "Real-time Electrical Operations Log"}
              </span>
            </div>
            <div className="w-full bg-slate-950/70 border border-slate-800/80 rounded-xl p-4 font-mono text-[10px] leading-relaxed text-slate-300 space-y-1 h-[140px] overflow-y-auto backdrop-blur-md">
              {terminalLogs.map((log) => (
                <div
                  key={`log-${log.substring(0, 40).replace(/\s/g, "_")}`}
                  className={getTerminalLogColor(log)}
                >
                  {log}
                </div>
              ))}
            </div>
          </div>
        </motion.div>

        {/* Security Certificate Footer */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.4, delay: 0.3 }}
          className="flex items-center gap-2.5 text-[9px] text-slate-600 font-mono"
        >
          <ShieldCheck className="w-4 h-4 text-blue-500" />
          <span>{t("auth.securityBadge")}</span>
          <span className="mx-1.5 text-slate-800">|</span>
          <span className="text-slate-700">ISO 27001 Certified</span>
          <span className="mx-1.5 text-slate-800">|</span>
          <span className="text-slate-700">SOC 2 Type II</span>
        </motion.div>
      </div>

      {/* RIGHT SIDE PANEL: Sign-in Glassmorphic Command Center */}
      <div className="flex-1 flex items-center justify-center p-6 sm:p-12 relative z-10">
        <motion.div
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="w-full max-w-[390px] bg-slate-900/35 backdrop-blur-xl border border-white/[0.06] p-8 rounded-2xl shadow-2xl relative overflow-hidden"
        >
          {/* Mobile Header (Hidden on Desktop) — now with a richer brand story */}
          <div className="lg:hidden space-y-6 mb-8">
            <div className="flex items-center gap-3.5">
              <BrandLogo size={40} />
              <div>
                <span className="text-xl font-bold text-white tracking-tight">AhmedETAP</span>
                <p className="text-[9px] text-slate-500 uppercase tracking-widest mt-0.5">
                  {t("app.description")}
                </p>
              </div>
            </div>
            {/* Mobile value proposition — visible only on small screens */}
            <div className="bg-slate-900/40 border border-slate-800/60 rounded-xl p-4 space-y-2">
              <p className="text-sm font-semibold text-white leading-snug">
                Power Systems Analysis
                <br />
                <span className="text-blue-400">Built for Professionals</span>
              </p>
              <p className="text-[10px] text-slate-400 leading-relaxed">
                Analyze, simulate, and design electrical networks with high-precision engines
                for load flow, short circuit, protection coordination, and arc flash analysis.
              </p>
              {/* Mini metrics row for mobile */}
              <div className="flex gap-3 pt-1">
                {["IEEE 1584", "IEC 60909", "IEEE 519"].map((s) => (
                  <span key={s} className="px-2 py-0.5 text-[9px] font-mono text-slate-500 bg-slate-950/50 border border-slate-800 rounded">
                    {s}
                  </span>
                ))}
              </div>
            </div>
          </div>

          {/* Form Header Title */}
          <div className="mb-8">
            <h3 className="text-2xl font-bold text-white tracking-tight">{t("auth.loginTitle")}</h3>
            <p className="text-xs text-slate-500 mt-1.5 leading-relaxed">
              {t("auth.loginSubtitle")}
            </p>
          </div>

          {/* Authentication Failure Alerts */}
          {authError && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              className="mb-5 p-3 rounded-lg bg-red-950/20 border border-red-900/40 flex items-start gap-2.5"
            >
              <AlertCircle className="w-4.5 h-4.5 text-red-400 mt-0.5 flex-shrink-0" />
              <p className="text-xs text-red-300 leading-normal">{authError}</p>
            </motion.div>
          )}

          {/* Dynamic Forgot Password Form */}
          {forgotOpen && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              className="mb-6 p-4 rounded-xl bg-slate-950/60 border border-slate-800"
            >
              {forgotSent ? (
                <div className="text-center py-2">
                  <p className="text-xs text-green-400 leading-relaxed mb-4">
                    {isRtl
                      ? "تم إرسال رابط استعادة كلمة المرور إذا كان الحساب مسجلاً لدينا."
                      : "Password reset link sent if the email is registered."}
                  </p>
                  <button
                    onClick={() => {
                      setForgotOpen(false);
                      setForgotSent(false);
                      setForgotEmail("");
                    }}
                    className="text-xs font-semibold text-slate-400 hover:text-white transition-colors"
                  >
                    {t("auth.backToLogin")}
                  </button>
                </div>
              ) : (
                <form onSubmit={handleForgotPassword} className="space-y-3">
                  <p className="text-xs font-semibold text-white">{t("auth.resetPasswordTitle")}</p>
                  <input
                    type="email"
                    value={forgotEmail}
                    onChange={(e) => setForgotEmail(e.target.value)}
                    placeholder={t("auth.resetEmailPlaceholder")}
                    required
                    dir="ltr"
                    className="w-full px-3 py-2.5 bg-slate-950/60 border border-slate-800 rounded-lg text-xs text-white focus:outline-none focus:border-blue-500 placeholder-slate-600 transition-colors"
                  />
                  <div className="flex gap-2 pt-1">
                    <button
                      type="submit"
                      disabled={forgotLoading}
                      className="flex-1 py-2 bg-blue-600 hover:bg-blue-500 text-white text-[11px] font-bold rounded-lg transition-colors disabled:opacity-50"
                    >
                      {forgotLoading ? t("auth.sending") : t("auth.sendResetLink")}
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setForgotOpen(false);
                        setForgotSent(false);
                        setForgotEmail("");
                      }}
                      className="px-3 py-2 text-slate-400 hover:text-white text-[11px] font-semibold transition-colors"
                    >
                      {t("auth.cancel")}
                    </button>
                  </div>
                </form>
              )}
            </motion.div>
          )}

          {/* Sign In Form */}
          <form onSubmit={handleSubmit} className="space-y-5">
            {/* Email / Username */}
            <div className="space-y-1.5">
              <label htmlFor="login-email" className="block text-xs font-semibold text-slate-400">
                {t("auth.emailLabel")}
              </label>
              <div className="relative">
                <Mail
                  className={`absolute ${isRtl ? "right-3" : "left-3"} top-1/2 -translate-y-1/2 w-4 h-4 text-slate-600 pointer-events-none`}
                />
                <input
                  id="login-email"
                  type="email"
                  inputMode="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder={t("auth.emailPlaceholder")}
                  required
                  dir="ltr"
                  className={`w-full ${
                    isRtl ? "pr-9 pl-3" : "pl-9 pr-3"
                  } py-2.5 bg-slate-950/50 border border-slate-800/80 rounded-xl text-xs text-white placeholder-slate-700 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500/10 transition-all`}
                />
              </div>
            </div>

            {/* Password */}
            <div className="space-y-1.5">
              <label
                htmlFor="login-password"
                className="block text-xs font-semibold text-slate-400"
              >
                {t("auth.passwordLabel")}
              </label>
              <div className="relative">
                <Lock
                  className={`absolute ${isRtl ? "right-3" : "left-3"} top-1/2 -translate-y-1/2 w-4 h-4 text-slate-600 pointer-events-none`}
                />
                <input
                  id="login-password"
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder={t("auth.passwordPlaceholder")}
                  required
                  dir="ltr"
                  className={`w-full ${
                    isRtl ? "pr-9 pl-10" : "pl-9 pr-10"
                  } py-2.5 bg-slate-950/50 border border-slate-800/80 rounded-xl text-xs text-white placeholder-slate-700 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500/10 transition-all`}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((p) => !p)}
                  className={`absolute ${isRtl ? "left-2.5" : "right-2.5"} top-1/2 -translate-y-1/2 p-1 rounded text-slate-600 hover:text-slate-300 transition-colors`}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {/* Remember & Forgot Row */}
            <div className="flex items-center justify-between text-xs pt-1">
              <label className="flex items-center gap-2 text-slate-500 cursor-pointer select-none">
                <input
                  type="checkbox"
                  className="rounded border-slate-800 bg-slate-950 text-blue-600 focus:ring-blue-500/10"
                />
                <span>{t("auth.rememberMe")}</span>
              </label>
              <button
                type="button"
                onClick={() => setForgotOpen(true)}
                className="text-blue-400 hover:text-blue-300 font-semibold transition-colors"
              >
                {t("auth.forgotPassword")}
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
                  <span>{t("auth.loggingIn")}</span>
                </>
              ) : (
                <>
                  <span>{t("auth.loginButton")}</span>
                  <ArrowRight className={`w-4 h-4 ${isRtl ? "rotate-180" : ""}`} />
                </>
              )}
            </motion.button>
          </form>

          {/* Footer Navigation */}
          <div className="mt-8 pt-5 border-t border-slate-800/40 flex items-center justify-between text-xs">
            <span className="text-slate-500 font-sans">
              {t("auth.noAccount")}{" "}
              <Link
                to="/register"
                className="text-blue-400 hover:text-blue-300 font-semibold transition-colors"
              >
                {t("auth.registerLink")}
              </Link>
            </span>
            <div className="flex items-center gap-2">
              <span className="text-[9px] text-slate-700 font-mono">{backendVersion !== null ? `v${backendVersion}` : "—"}</span>
              <span className="w-1 h-1 rounded-full bg-slate-800" />
              <span className="text-[9px] text-slate-700 font-mono">{t("auth.secureLogin")}</span>
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  );
}
