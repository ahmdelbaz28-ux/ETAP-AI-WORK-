/**
 * Magic Links Page — Admin/debug UI for the magic_links backend module.
 *
 * Wires to all 3 endpoints exposed by api/magic_links.py
 * (prefix /api/v1/auth/magic-link):
 *   POST /request     — send a magic-link email to a user (public, no JWT)
 *   POST /verify      — verify a magic-link token and receive JWT (public, no JWT)
 *   POST /invalidate  — invalidate all pending magic links for an email
 *                        (requires JWT — admin/debug endpoint)
 *
 * The page is operator/dev-oriented: it lets an admin trigger a magic-link
 * request for any email, paste/verify a token (without round-tripping
 * through the email inbox — useful for debugging), and invalidate pending
 * links for a given email (admin cleanup / DoS-prevention).
 *
 * /request and /verify are public endpoints; /invalidate requires a JWT,
 * which we attach from tokenStorage when present.
 *
 * Ref: TASK-9a
 */

import { motion } from "framer-motion";
import {
  Ban,
  CheckCircle2,
  Link2,
  Loader2,
  LogIn,
  Mail,
  Send,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import { type ReactNode, useCallback, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  ErrorBanner,
  LoadingRow,
  StatRow,
  inputClass,
  labelClass,
} from "../components/admin-primitives";
import { Badge, Button, Card, CardHeader, CardSection, EmptyState, Tabs } from "../components/ui";
import { useNotify } from "../context/NotificationContext";
import { adminFetch } from "../lib/admin-fetch";

// ---------------------------------------------------------------------------
// Types — mirror api/magic_links.py
// ---------------------------------------------------------------------------

interface MagicLinkUser {
  id: string;
  email: string;
  username: string;
  role: string;
}

interface RequestResponse {
  success: boolean;
  message?: string;
  expires_in_seconds?: number;
  trace_id?: string;
  // Test-mode only
  test_token?: string;
  test_mode?: boolean;
  // Error variants
  error?: string;
  retry_after_seconds?: number;
}

interface VerifyResponse {
  success: boolean;
  message?: string;
  access_token?: string;
  refresh_token?: string;
  token_type?: string;
  user?: MagicLinkUser;
  trace_id?: string;
  // Error variants
  error?: string;
}

interface InvalidateResponse {
  success: boolean;
  invalidated?: number;
  email?: string | null;
  message?: string;
  trace_id?: string;
}

type TabId = "request" | "verify" | "invalidate";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

// Re-exported from admin-primitives for backward compat with the
// per-page inputClass / labelClass references below.

// ---------------------------------------------------------------------------
// Page component
// ---------------------------------------------------------------------------

export default function MagicLinksPage() {
  const { notify } = useNotify();
  const { t } = useTranslation();
  const [tab, setTab] = useState<TabId>("request");

  // ─── Request tab state ──────────────────────────────────────────────
  const [reqEmail, setReqEmail] = useState("");
  const [reqResult, setReqResult] = useState<RequestResponse | null>(null);
  const [reqLoading, setReqLoading] = useState(false);
  const [reqError, setReqError] = useState<string | null>(null);

  // ─── Verify tab state ───────────────────────────────────────────────
  const [verifyToken, setVerifyToken] = useState("");
  const [verifyResult, setVerifyResult] = useState<VerifyResponse | null>(null);
  const [verifyLoading, setVerifyLoading] = useState(false);
  const [verifyError, setVerifyError] = useState<string | null>(null);

  // ─── Invalidate tab state ───────────────────────────────────────────
  const [invEmail, setInvEmail] = useState("");
  const [invResult, setInvResult] = useState<InvalidateResponse | null>(null);
  const [invLoading, setInvLoading] = useState(false);
  const [invError, setInvError] = useState<string | null>(null);

  // -------------------------------------------------------------------------
  // Handlers
  // -------------------------------------------------------------------------

  const handleRequest = useCallback(async () => {
    if (!reqEmail.trim()) {
      setReqError("Email is required.");
      return;
    }
    setReqLoading(true);
    setReqError(null);
    setReqResult(null);
    try {
      const res = await adminFetch<RequestResponse>("/api/v1/auth/magic-link/request", {
        method: "POST",
        body: JSON.stringify({ email: reqEmail.trim() }),
      });
      setReqResult(res);
      if (res.success) {
        // SECURITY: only reveal the test token in the toast when
        // running in dev (import.meta.env.DEV). In production builds
        // the token must never appear in the DOM or toast history,
        // even if the backend accidentally has test_mode enabled.
        // Ref: fix/admin-pages-hardening (#3)
        const tokenNote =
          import.meta.env.DEV && res.test_token
            ? ` (test token: ${res.test_token.slice(0, 8)}…)`
            : "";
        notify(
          "success",
          t("adminPages.magicLinks.request.success", { email: reqEmail.trim(), note: tokenNote }),
        );
      } else {
        notify(
          "error",
          t("adminPages.magicLinks.request.failed", {
            error: res.error ?? t("adminPages.common.unknownError"),
          }),
        );
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setReqError(msg);
      notify("error", t("adminPages.magicLinks.request.failed", { error: msg }));
    } finally {
      setReqLoading(false);
    }
  }, [reqEmail, notify, t]);

  const handleVerify = useCallback(async () => {
    if (!verifyToken.trim()) {
      setVerifyError("Token is required.");
      return;
    }
    setVerifyLoading(true);
    setVerifyError(null);
    setVerifyResult(null);
    try {
      const res = await adminFetch<VerifyResponse>("/api/v1/auth/magic-link/verify", {
        method: "POST",
        body: JSON.stringify({ token: verifyToken.trim() }),
      });
      setVerifyResult(res);
      if (res.success) {
        notify(
          "success",
          t("adminPages.magicLinks.verify.success", {
            email: res.user?.email ?? t("adminPages.common.user"),
          }),
        );
      } else {
        notify(
          "error",
          t("adminPages.magicLinks.verify.failed", {
            error: res.error ?? t("adminPages.common.unknownError"),
          }),
        );
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setVerifyError(msg);
      notify("error", t("adminPages.magicLinks.verify.failed", { error: msg }));
    } finally {
      setVerifyLoading(false);
    }
  }, [verifyToken, notify, t]);

  const handleInvalidate = useCallback(async () => {
    if (!invEmail.trim()) {
      setInvError("Email is required.");
      return;
    }
    setInvLoading(true);
    setInvError(null);
    setInvResult(null);
    try {
      // Invalidate accepts email via JSON body (preferred over query
      // param to avoid leaking it in URL logs).
      const res = await adminFetch<InvalidateResponse>("/api/v1/auth/magic-link/invalidate", {
        method: "POST",
        body: JSON.stringify({ email: invEmail.trim() }),
      });
      setInvResult(res);
      if (res.success) {
        notify(
          "success",
          t("adminPages.magicLinks.invalidate.success", {
            count: res.invalidated ?? 0,
            email: invEmail.trim(),
          }),
        );
      } else {
        notify(
          "error",
          t("adminPages.magicLinks.invalidate.failed", {
            error: res.message ?? t("adminPages.common.unknownError"),
          }),
        );
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setInvError(msg);
      notify("error", t("adminPages.magicLinks.invalidate.failed", { error: msg }));
    } finally {
      setInvLoading(false);
    }
  }, [invEmail, notify, t]);

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  const tabs: {
    readonly id: string;
    readonly label: string;
    readonly icon: ReactNode;
  }[] = [
    {
      id: "request",
      label: t("adminPages.magicLinks.tabs.request"),
      icon: <Send className="w-4 h-4" />,
    },
    {
      id: "verify",
      label: t("adminPages.magicLinks.tabs.verify"),
      icon: <LogIn className="w-4 h-4" />,
    },
    {
      id: "invalidate",
      label: t("adminPages.magicLinks.tabs.invalidate"),
      icon: <Ban className="w-4 h-4" />,
    },
  ];

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-6 p-6">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-lg bg-brand-500/10 flex items-center justify-center">
          <Link2 className="w-5 h-5 text-brand-500" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">
            {t("adminPages.magicLinks.title")}
          </h1>
          <p className="text-sm text-[var(--text-muted)] mt-0.5">
            {t("adminPages.magicLinks.subtitle")}
          </p>
        </div>
      </div>

      <Tabs tabs={tabs} activeTab={tab} onChange={(id) => setTab(id as TabId)} />

      {tab === "request" && (
        <RequestTab
          email={reqEmail}
          setEmail={setReqEmail}
          loading={reqLoading}
          error={reqError}
          result={reqResult}
          onSubmit={handleRequest}
        />
      )}
      {tab === "verify" && (
        <VerifyTab
          token={verifyToken}
          setToken={setVerifyToken}
          loading={verifyLoading}
          error={verifyError}
          result={verifyResult}
          onSubmit={handleVerify}
        />
      )}
      {tab === "invalidate" && (
        <InvalidateTab
          email={invEmail}
          setEmail={setInvEmail}
          loading={invLoading}
          error={invError}
          result={invResult}
          onSubmit={handleInvalidate}
        />
      )}
    </motion.div>
  );
}

// ---------------------------------------------------------------------------
// Tab components
// ---------------------------------------------------------------------------

function RequestTab({
  email,
  setEmail,
  loading,
  error,
  result,
  onSubmit,
}: {
  readonly email: string;
  readonly setEmail: (v: string) => void;
  readonly loading: boolean;
  readonly error: string | null;
  readonly result: RequestResponse | null;
  readonly onSubmit: () => void;
}) {
  const { t } = useTranslation();
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <Card>
        <CardHeader
          title={
            <span className="flex items-center gap-2">
              <Send className="w-4 h-4" />
              {t("adminPages.magicLinks.request.cardTitle")}
            </span>
          }
          subtitle={t("adminPages.magicLinks.request.cardSubtitle")}
        />
        <CardSection className="p-4 space-y-4">
          <div>
            <label htmlFor="req-email" className={labelClass}>
              {t("adminPages.common.emailAddress")}
            </label>
            <input
              id="req-email"
              data-testid="req-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className={inputClass}
              placeholder="user@example.com"
              autoComplete="email"
            />
            <p className="text-xs text-zinc-500 mt-1">{t("adminPages.magicLinks.request.help")}</p>
          </div>

          {error && <ErrorBanner message={error} />}

          <div className="flex justify-end gap-2">
            <Button data-testid="req-submit" onClick={onSubmit} disabled={loading || !email.trim()}>
              {loading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Send className="w-4 h-4" />
              )}
              {t("adminPages.magicLinks.request.submit")}
            </Button>
          </div>
        </CardSection>
      </Card>

      <Card>
        <CardHeader
          title={t("adminPages.common.result")}
          subtitle={t("adminPages.magicLinks.request.resultSubtitle")}
        />
        <CardSection className="p-4">
          {loading ? (
            <LoadingRow label={t("adminPages.magicLinks.request.loading")} />
          ) : result ? (
            <RequestResultCard result={result} />
          ) : (
            <EmptyState
              icon={<Mail className="w-5 h-5 text-zinc-500" />}
              title={t("adminPages.magicLinks.request.emptyTitle")}
              description={t("adminPages.magicLinks.request.emptyDescription")}
            />
          )}
        </CardSection>
      </Card>
    </div>
  );
}

function RequestResultCard({ result }: { readonly result: RequestResponse }) {
  const { t } = useTranslation();
  const ok = result.success;
  return (
    <div
      data-testid="req-result"
      className="rounded-md border border-zinc-800 bg-zinc-900/50 p-4 space-y-1"
    >
      <div className="flex items-center gap-2 mb-3">
        {ok ? (
          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
        ) : (
          <XCircle className="w-4 h-4 text-red-400" />
        )}
        <span className="text-sm font-semibold text-zinc-100">
          {ok ? t("adminPages.common.success") : t("adminPages.common.failed")}
        </span>
        {/* SECURITY: test_mode badge is dev-only. In production we
            must not advertise that test mode is active, even if the
            backend accidentally has it enabled — doing so would
            signal to an attacker that tokens are predictable.
            Ref: fix/admin-pages-hardening (#3) */}
        {import.meta.env.DEV && result.test_mode && (
          <Badge className="ml-auto" variant="brand">
            {t("adminPages.common.testMode")}
          </Badge>
        )}
      </div>
      {result.message && <StatRow label={t("adminPages.common.message")} value={result.message} />}
      {result.expires_in_seconds !== undefined && (
        <StatRow label={t("adminPages.common.expiresIn")} value={`${result.expires_in_seconds}s`} />
      )}
      {/* SECURITY: test_token is dev-only. Ref: fix/admin-pages-hardening (#3) */}
      {import.meta.env.DEV && result.test_token && (
        <StatRow
          label={t("adminPages.common.testToken")}
          value={<span title={result.test_token}>{result.test_token.slice(0, 16)}…</span>}
        />
      )}
      {result.retry_after_seconds !== undefined && (
        <StatRow
          label={t("adminPages.common.retryAfter")}
          value={`${result.retry_after_seconds}s`}
        />
      )}
      {result.error && <StatRow label={t("adminPages.common.error")} value={result.error} />}
      {result.trace_id && (
        <StatRow label={t("adminPages.common.traceId")} value={result.trace_id} />
      )}
    </div>
  );
}

function VerifyTab({
  token,
  setToken,
  loading,
  error,
  result,
  onSubmit,
}: {
  readonly token: string;
  readonly setToken: (v: string) => void;
  readonly loading: boolean;
  readonly error: string | null;
  readonly result: VerifyResponse | null;
  readonly onSubmit: () => void;
}) {
  const { t } = useTranslation();
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <Card>
        <CardHeader
          title={
            <span className="flex items-center gap-2">
              <LogIn className="w-4 h-4" />
              {t("adminPages.magicLinks.verify.cardTitle")}
            </span>
          }
          subtitle={t("adminPages.magicLinks.verify.cardSubtitle")}
        />
        <CardSection className="p-4 space-y-4">
          <div>
            <label htmlFor="verify-token" className={labelClass}>
              {t("adminPages.magicLinks.verify.tokenLabel")}
            </label>
            <textarea
              id="verify-token"
              data-testid="verify-token"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              className={`${inputClass} font-mono text-xs`}
              placeholder={t("adminPages.magicLinks.verify.tokenPlaceholder")}
              rows={4}
            />
            <p className="text-xs text-zinc-500 mt-1">{t("adminPages.magicLinks.verify.help")}</p>
          </div>

          {error && <ErrorBanner message={error} />}

          <div className="flex justify-end gap-2">
            <Button
              data-testid="verify-submit"
              onClick={onSubmit}
              disabled={loading || !token.trim()}
            >
              {loading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <LogIn className="w-4 h-4" />
              )}
              {t("adminPages.magicLinks.verify.submit")}
            </Button>
          </div>
        </CardSection>
      </Card>

      <Card>
        <CardHeader
          title={t("adminPages.common.result")}
          subtitle={t("adminPages.magicLinks.verify.resultSubtitle")}
        />
        <CardSection className="p-4">
          {loading ? (
            <LoadingRow label={t("adminPages.magicLinks.verify.loading")} />
          ) : result ? (
            <VerifyResultCard result={result} />
          ) : (
            <EmptyState
              icon={<ShieldCheck className="w-5 h-5 text-zinc-500" />}
              title={t("adminPages.magicLinks.verify.emptyTitle")}
              description={t("adminPages.magicLinks.verify.emptyDescription")}
            />
          )}
        </CardSection>
      </Card>
    </div>
  );
}

function VerifyResultCard({ result }: { readonly result: VerifyResponse }) {
  const { t } = useTranslation();
  const ok = result.success;
  return (
    <div
      data-testid="verify-result"
      className="rounded-md border border-zinc-800 bg-zinc-900/50 p-4 space-y-1"
    >
      <div className="flex items-center gap-2 mb-3">
        {ok ? (
          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
        ) : (
          <XCircle className="w-4 h-4 text-red-400" />
        )}
        <span className="text-sm font-semibold text-zinc-100">
          {ok ? t("adminPages.common.verified") : t("adminPages.common.failed")}
        </span>
        {result.token_type && (
          <Badge className="ml-auto" variant="brand">
            {result.token_type}
          </Badge>
        )}
      </div>
      {result.message && <StatRow label={t("adminPages.common.message")} value={result.message} />}
      {result.access_token && (
        <StatRow
          label={t("adminPages.common.accessToken")}
          value={<span title={result.access_token}>{result.access_token.slice(0, 16)}…</span>}
        />
      )}
      {result.refresh_token && (
        <StatRow
          label={t("adminPages.common.refreshToken")}
          value={<span title={result.refresh_token}>{result.refresh_token.slice(0, 16)}…</span>}
        />
      )}
      {result.user && (
        <>
          <StatRow label={t("adminPages.common.userId")} value={result.user.id} />
          <StatRow label={t("adminPages.common.emailAddress")} value={result.user.email} />
          <StatRow label={t("adminPages.common.username")} value={result.user.username} />
          <StatRow label={t("adminPages.common.role")} value={result.user.role} />
        </>
      )}
      {result.error && <StatRow label={t("adminPages.common.error")} value={result.error} />}
      {result.trace_id && (
        <StatRow label={t("adminPages.common.traceId")} value={result.trace_id} />
      )}
    </div>
  );
}

function InvalidateTab({
  email,
  setEmail,
  loading,
  error,
  result,
  onSubmit,
}: {
  readonly email: string;
  readonly setEmail: (v: string) => void;
  readonly loading: boolean;
  readonly error: string | null;
  readonly result: InvalidateResponse | null;
  readonly onSubmit: () => void;
}) {
  const { t } = useTranslation();
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <Card>
        <CardHeader
          title={
            <span className="flex items-center gap-2">
              <Ban className="w-4 h-4" />
              {t("adminPages.magicLinks.invalidate.cardTitle")}
            </span>
          }
          subtitle={t("adminPages.magicLinks.invalidate.cardSubtitle")}
        />
        <CardSection className="p-4 space-y-4">
          <div>
            <label htmlFor="inv-email" className={labelClass}>
              {t("adminPages.common.emailAddress")}
            </label>
            <input
              id="inv-email"
              data-testid="inv-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className={inputClass}
              placeholder="user@example.com"
              autoComplete="email"
            />
            <p className="text-xs text-zinc-500 mt-1">
              {t("adminPages.magicLinks.invalidate.help")}
            </p>
          </div>

          {error && <ErrorBanner message={error} />}

          <div className="flex justify-end gap-2">
            <Button
              data-testid="inv-submit"
              onClick={onSubmit}
              disabled={loading || !email.trim()}
              variant="danger"
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Ban className="w-4 h-4" />}
              {t("adminPages.magicLinks.invalidate.submit")}
            </Button>
          </div>
        </CardSection>
      </Card>

      <Card>
        <CardHeader
          title={t("adminPages.common.result")}
          subtitle={t("adminPages.magicLinks.invalidate.resultSubtitle")}
        />
        <CardSection className="p-4">
          {loading ? (
            <LoadingRow label={t("adminPages.magicLinks.invalidate.loading")} />
          ) : result ? (
            <InvalidateResultCard result={result} />
          ) : (
            <EmptyState
              icon={<Ban className="w-5 h-5 text-zinc-500" />}
              title={t("adminPages.magicLinks.invalidate.emptyTitle")}
              description={t("adminPages.magicLinks.invalidate.emptyDescription")}
            />
          )}
        </CardSection>
      </Card>
    </div>
  );
}

function InvalidateResultCard({ result }: { readonly result: InvalidateResponse }) {
  const { t } = useTranslation();
  const ok = result.success;
  return (
    <div
      data-testid="inv-result"
      className="rounded-md border border-zinc-800 bg-zinc-900/50 p-4 space-y-1"
    >
      <div className="flex items-center gap-2 mb-3">
        {ok ? (
          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
        ) : (
          <XCircle className="w-4 h-4 text-red-400" />
        )}
        <span className="text-sm font-semibold text-zinc-100">
          {ok ? t("adminPages.common.success") : t("adminPages.common.failed")}
        </span>
      </div>
      {result.invalidated !== undefined && (
        <StatRow label={t("adminPages.common.invalidated")} value={String(result.invalidated)} />
      )}
      {result.email && <StatRow label={t("adminPages.common.emailAddress")} value={result.email} />}
      {result.message && <StatRow label={t("adminPages.common.message")} value={result.message} />}
      {result.trace_id && (
        <StatRow label={t("adminPages.common.traceId")} value={result.trace_id} />
      )}
    </div>
  );
}
