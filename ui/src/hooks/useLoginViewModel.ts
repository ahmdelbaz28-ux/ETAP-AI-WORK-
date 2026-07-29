import { useCallback, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useNotify } from "../context/NotificationContext";
import { useAuth } from "../hooks/useAuth";
import { API_BASE_URL } from "../lib/api-config";

export function useLoginViewModel() {
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

  const appendLog = useCallback((msg: string) => {
    const timestamp = new Date().toLocaleTimeString();
    setTerminalLogs((prev) => [...prev.slice(-8), `[${timestamp}] ${msg}`]);
  }, []);

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

  return {
    email,
    setEmail,
    password,
    setPassword,
    showPassword,
    setShowPassword,
    loading,
    authError,
    forgotOpen,
    setForgotOpen,
    forgotEmail,
    setForgotEmail,
    forgotLoading,
    forgotSent,
    setForgotSent,
    isBreakerOpen,
    setIsBreakerOpen,
    terminalLogs,
    handleSubmit,
    handleForgotPassword,
    t,
    i18n,
  };
}
