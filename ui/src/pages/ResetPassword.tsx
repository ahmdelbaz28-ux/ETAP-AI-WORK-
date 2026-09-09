import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useSearchParams } from "react-router";
import { useNotify } from "../context/NotificationContext";
import { API_BASE_URL } from "../lib/api-config";

export default function ResetPassword() {
  const { i18n } = useTranslation();
  const { notify } = useNotify();
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const isRtl = i18n.language === "ar";

  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!token) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#070b14]" dir={isRtl ? "rtl" : "ltr"}>
        <div className="max-w-md w-full mx-4 p-6 rounded-xl border border-slate-800 bg-slate-900/60 text-center">
          <h1 className="text-lg font-bold text-white mb-2">
            {isRtl ? "رابط غير صالح" : "Invalid link"}
          </h1>
          <p className="text-sm text-slate-400 mb-4">
            {isRtl
              ? "رابط إعادة التعيين ناقص أو غير صالح. اطلب رابطاً جديداً من صفحة الدخول."
              : "This reset link is missing or invalid. Request a new one from the login page."}
          </p>
          <Link to="/login" className="text-blue-400 hover:text-blue-300 text-sm font-semibold">
            {isRtl ? "العودة لصفحة الدخول" : "Back to Login"}
          </Link>
        </div>
      </div>
    );
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (newPassword.length < 8) {
      setError(
        isRtl ? "يجب أن لا تقل كلمة المرور عن 8 خانات" : "Password must be at least 8 characters long",
      );
      return;
    }
    if (newPassword !== confirmPassword) {
      setError(isRtl ? "كلمتا المرور غير متطابقتين" : "Passwords do not match");
      return;
    }
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/auth/reset-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, new_password: newPassword }),
      });
      const data = await response.json().catch(() => null);
      if (response.ok) {
        setDone(true);
        notify("success", isRtl ? "تمت إعادة تعيين كلمة المرور بنجاح" : "Password has been reset successfully");
      } else {
        const detail =
          typeof data?.detail === "string" ? data.detail : isRtl ? "الرابط غير صالح أو منتهي الصلاحية" : "Invalid or expired reset token";
        setError(detail);
      }
    } catch {
      setError(
        isRtl
          ? "تعذر الاتصال بالخادم، تأكد من الاتصال بالشبكة والمحاولة مجدداً"
          : "Network offline or server unreachable. Please check connection and try again.",
      );
    } finally {
      setLoading(false);
    }
  };

  if (done) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#070b14]" dir={isRtl ? "rtl" : "ltr"}>
        <div className="max-w-md w-full mx-4 p-6 rounded-xl border border-slate-800 bg-slate-900/60 text-center" data-testid="reset-success">
          <h1 className="text-lg font-bold text-green-400 mb-2">
            {isRtl ? "تمت إعادة التعيين بنجاح" : "Password reset successful"}
          </h1>
          <p className="text-sm text-slate-400 mb-4">
            {isRtl ? "يمكنك الآن تسجيل الدخول بكلمة المرور الجديدة." : "You can now sign in with your new password."}
          </p>
          <Link to="/login" className="text-blue-400 hover:text-blue-300 text-sm font-semibold">
            {isRtl ? "تسجيل الدخول" : "Sign In"}
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#070b14]" dir={isRtl ? "rtl" : "ltr"}>
      <form
        onSubmit={handleSubmit}
        className="max-w-md w-full mx-4 p-6 rounded-xl border border-slate-800 bg-slate-900/60 space-y-4"
      >
        <h1 className="text-lg font-bold text-white text-center">
          {isRtl ? "إعادة تعيين كلمة المرور" : "Reset Password"}
        </h1>
        {error && (
          <p data-testid="reset-error" className="text-sm text-red-400 text-center">
            {error}
          </p>
        )}
        <div>
          <label htmlFor="reset-new-password" className="block text-xs text-slate-400 mb-1">
            {isRtl ? "كلمة المرور الجديدة" : "New Password"}
          </label>
          <input
            id="reset-new-password"
            data-testid="reset-new-password"
            type="password"
            autoComplete="new-password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500"
          />
        </div>
        <div>
          <label htmlFor="reset-confirm-password" className="block text-xs text-slate-400 mb-1">
            {isRtl ? "تأكيد كلمة المرور" : "Confirm Password"}
          </label>
          <input
            id="reset-confirm-password"
            data-testid="reset-confirm-password"
            type="password"
            autoComplete="new-password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-blue-500"
          />
        </div>
        <button
          type="submit"
          data-testid="reset-submit"
          disabled={loading}
          className="w-full py-2 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-sm font-semibold"
        >
          {loading
            ? isRtl
              ? "جاري الحفظ..."
              : "Saving..."
            : isRtl
              ? "حفظ كلمة المرور الجديدة"
              : "Save New Password"}
        </button>
        <div className="text-center">
          <Link to="/login" className="text-slate-400 hover:text-slate-300 text-xs">
            {isRtl ? "العودة لصفحة الدخول" : "Back to Login"}
          </Link>
        </div>
      </form>
    </div>
  );
}
