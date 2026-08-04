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
  AlertTriangle,
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
import { Badge, Button, Card, CardHeader, CardSection, EmptyState, Tabs } from "../components/ui";
import { useNotify } from "../context/NotificationContext";
import { API_BASE_URL } from "../lib/api-config";
import { getAuthToken } from "../lib/tokenStorage";

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
// Fetch helper
// ---------------------------------------------------------------------------

function authHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const token = getAuthToken();
  return { ...(token ? { Authorization: `Bearer ${token}` } : {}), ...extra };
}

async function magicFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const callerHeaders = init?.headers;
  const mergedHeaders: Record<string, string> = {
    "Content-Type": "application/json",
    ...authHeaders(),
  };
  if (callerHeaders instanceof Headers) {
    callerHeaders.forEach((v, k) => {
      mergedHeaders[k] = v;
    });
  } else if (Array.isArray(callerHeaders)) {
    for (const [k, v] of callerHeaders) {
      mergedHeaders[k] = v;
    }
  } else if (callerHeaders && typeof callerHeaders === "object") {
    Object.assign(mergedHeaders, callerHeaders as Record<string, string>);
  }

  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: mergedHeaders,
  });
  const text = await res.text().catch(() => "");
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const parsed = JSON.parse(text);
      if (parsed?.detail) detail = `${detail}: ${parsed.detail}`;
      else if (parsed?.message) detail = `${detail}: ${parsed.message}`;
      else if (parsed?.error) detail = `${detail}: ${parsed.error}`;
    } catch {
      if (text) detail = `${detail}: ${text.slice(0, 200)}`;
    }
    throw new Error(detail);
  }
  try {
    return JSON.parse(text) as T;
  } catch {
    return text as unknown as T;
  }
}

// ---------------------------------------------------------------------------
// Small UI primitives (local — kept here to avoid bloating shared ui/)
// ---------------------------------------------------------------------------

function StatRow({ label, value }: { readonly label: string; readonly value: ReactNode }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-[var(--border-primary)] last:border-0 gap-3">
      <span className="text-xs uppercase tracking-wider text-zinc-400 font-semibold shrink-0">
        {label}
      </span>
      <span className="text-sm text-zinc-100 font-mono text-right break-all">{value}</span>
    </div>
  );
}

function ErrorBanner({ message }: { readonly message: string }) {
  return (
    <div
      role="alert"
      className="flex items-start gap-2 rounded-md border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300"
    >
      <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
      <span className="break-words">{message}</span>
    </div>
  );
}

function LoadingRow({ label }: { readonly label: string }) {
  return (
    <div className="flex items-center gap-2 py-2 text-sm text-zinc-400">
      <Loader2 className="w-4 h-4 animate-spin" />
      <span>{label}</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const inputClass =
  "w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:ring-2 focus:ring-brand-500/50";
const labelClass = "block text-xs uppercase tracking-wider text-zinc-400 font-semibold mb-1";

// ---------------------------------------------------------------------------
// Page component
// ---------------------------------------------------------------------------

export default function MagicLinksPage() {
  const { notify } = useNotify();
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
      const res = await magicFetch<RequestResponse>("/api/v1/auth/magic-link/request", {
        method: "POST",
        body: JSON.stringify({ email: reqEmail.trim() }),
      });
      setReqResult(res);
      if (res.success) {
        const tokenNote = res.test_token ? ` (test token: ${res.test_token.slice(0, 8)}…)` : "";
        notify("success", `Magic link requested for ${reqEmail.trim()}.${tokenNote}`);
      } else {
        notify("error", `Request failed: ${res.error ?? "unknown error"}`);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setReqError(msg);
      notify("error", `Request failed: ${msg}`);
    } finally {
      setReqLoading(false);
    }
  }, [reqEmail, notify]);

  const handleVerify = useCallback(async () => {
    if (!verifyToken.trim()) {
      setVerifyError("Token is required.");
      return;
    }
    setVerifyLoading(true);
    setVerifyError(null);
    setVerifyResult(null);
    try {
      const res = await magicFetch<VerifyResponse>("/api/v1/auth/magic-link/verify", {
        method: "POST",
        body: JSON.stringify({ token: verifyToken.trim() }),
      });
      setVerifyResult(res);
      if (res.success) {
        notify("success", `Magic link verified for ${res.user?.email ?? "user"}.`);
      } else {
        notify("error", `Verify failed: ${res.error ?? "unknown error"}`);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setVerifyError(msg);
      notify("error", `Verify failed: ${msg}`);
    } finally {
      setVerifyLoading(false);
    }
  }, [verifyToken, notify]);

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
      const res = await magicFetch<InvalidateResponse>("/api/v1/auth/magic-link/invalidate", {
        method: "POST",
        body: JSON.stringify({ email: invEmail.trim() }),
      });
      setInvResult(res);
      if (res.success) {
        notify(
          "success",
          `Invalidated ${res.invalidated ?? 0} pending magic link(s) for ${invEmail.trim()}.`,
        );
      } else {
        notify("error", `Invalidate failed: ${res.message ?? "unknown error"}`);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setInvError(msg);
      notify("error", `Invalidate failed: ${msg}`);
    } finally {
      setInvLoading(false);
    }
  }, [invEmail, notify]);

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  const tabs: {
    readonly id: string;
    readonly label: string;
    readonly icon: ReactNode;
  }[] = [
    { id: "request", label: "Request", icon: <Send className="w-4 h-4" /> },
    {
      id: "verify",
      label: "Verify",
      icon: <LogIn className="w-4 h-4" />,
    },
    {
      id: "invalidate",
      label: "Invalidate",
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
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">Magic Links</h1>
          <p className="text-sm text-[var(--text-muted)] mt-0.5">
            Passwordless authentication via one-time-use email links (public request/verify ·
            admin-only invalidate)
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
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <Card>
        <CardHeader
          title={
            <span className="flex items-center gap-2">
              <Send className="w-4 h-4" />
              Request Magic Link
            </span>
          }
          subtitle="POST /request — public, always returns 200 (no enumeration)"
        />
        <CardSection className="p-4 space-y-4">
          <div>
            <label htmlFor="req-email" className={labelClass}>
              Email address
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
            <p className="text-xs text-zinc-500 mt-1">
              If the email exists, a magic link will be sent. Always returns 200 to prevent user
              enumeration.
            </p>
          </div>

          {error && <ErrorBanner message={error} />}

          <div className="flex justify-end gap-2">
            <Button data-testid="req-submit" onClick={onSubmit} disabled={loading || !email.trim()}>
              {loading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Send className="w-4 h-4" />
              )}
              Request Magic Link
            </Button>
          </div>
        </CardSection>
      </Card>

      <Card>
        <CardHeader title="Result" subtitle="Response from POST /request" />
        <CardSection className="p-4">
          {loading ? (
            <LoadingRow label="Sending magic link…" />
          ) : result ? (
            <RequestResultCard result={result} />
          ) : (
            <EmptyState
              icon={<Mail className="w-5 h-5 text-zinc-500" />}
              title="No request yet"
              description="Fill the email and submit to request a magic link."
            />
          )}
        </CardSection>
      </Card>
    </div>
  );
}

function RequestResultCard({ result }: { readonly result: RequestResponse }) {
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
        <span className="text-sm font-semibold text-zinc-100">{ok ? "Success" : "Failed"}</span>
        {result.test_mode && (
          <Badge className="ml-auto" variant="brand">
            test mode
          </Badge>
        )}
      </div>
      {result.message && <StatRow label="Message" value={result.message} />}
      {result.expires_in_seconds !== undefined && (
        <StatRow label="Expires in" value={`${result.expires_in_seconds}s`} />
      )}
      {result.test_token && (
        <StatRow
          label="Test token"
          value={<span title={result.test_token}>{result.test_token.slice(0, 16)}…</span>}
        />
      )}
      {result.retry_after_seconds !== undefined && (
        <StatRow label="Retry after" value={`${result.retry_after_seconds}s`} />
      )}
      {result.error && <StatRow label="Error" value={result.error} />}
      {result.trace_id && <StatRow label="Trace ID" value={result.trace_id} />}
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
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <Card>
        <CardHeader
          title={
            <span className="flex items-center gap-2">
              <LogIn className="w-4 h-4" />
              Verify Magic Link
            </span>
          }
          subtitle="POST /verify — public, mints JWT on success"
        />
        <CardSection className="p-4 space-y-4">
          <div>
            <label htmlFor="verify-token" className={labelClass}>
              Magic-link token
            </label>
            <textarea
              id="verify-token"
              data-testid="verify-token"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              className={`${inputClass} font-mono text-xs`}
              placeholder="Paste the token from the magic-link URL (e.g. ?token=…)"
              rows={4}
            />
            <p className="text-xs text-zinc-500 mt-1">
              Tokens are 32-byte URL-safe random strings, valid for 15 minutes, single-use.
            </p>
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
              Verify Token
            </Button>
          </div>
        </CardSection>
      </Card>

      <Card>
        <CardHeader title="Result" subtitle="Response from POST /verify" />
        <CardSection className="p-4">
          {loading ? (
            <LoadingRow label="Verifying magic link…" />
          ) : result ? (
            <VerifyResultCard result={result} />
          ) : (
            <EmptyState
              icon={<ShieldCheck className="w-5 h-5 text-zinc-500" />}
              title="No verification yet"
              description="Paste a token and submit to verify it."
            />
          )}
        </CardSection>
      </Card>
    </div>
  );
}

function VerifyResultCard({ result }: { readonly result: VerifyResponse }) {
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
        <span className="text-sm font-semibold text-zinc-100">{ok ? "Verified" : "Failed"}</span>
        {result.token_type && (
          <Badge className="ml-auto" variant="brand">
            {result.token_type}
          </Badge>
        )}
      </div>
      {result.message && <StatRow label="Message" value={result.message} />}
      {result.access_token && (
        <StatRow
          label="Access token"
          value={<span title={result.access_token}>{result.access_token.slice(0, 16)}…</span>}
        />
      )}
      {result.refresh_token && (
        <StatRow
          label="Refresh token"
          value={<span title={result.refresh_token}>{result.refresh_token.slice(0, 16)}…</span>}
        />
      )}
      {result.user && (
        <>
          <StatRow label="User ID" value={result.user.id} />
          <StatRow label="Email" value={result.user.email} />
          <StatRow label="Username" value={result.user.username} />
          <StatRow label="Role" value={result.user.role} />
        </>
      )}
      {result.error && <StatRow label="Error" value={result.error} />}
      {result.trace_id && <StatRow label="Trace ID" value={result.trace_id} />}
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
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <Card>
        <CardHeader
          title={
            <span className="flex items-center gap-2">
              <Ban className="w-4 h-4" />
              Invalidate Pending Links
            </span>
          }
          subtitle="POST /invalidate — requires JWT"
        />
        <CardSection className="p-4 space-y-4">
          <div>
            <label htmlFor="inv-email" className={labelClass}>
              Email address
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
              Requires JWT. All unused (pending) magic links for this email will be invalidated.
              Used links are unaffected.
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
              Invalidate Pending Links
            </Button>
          </div>
        </CardSection>
      </Card>

      <Card>
        <CardHeader title="Result" subtitle="Response from POST /invalidate" />
        <CardSection className="p-4">
          {loading ? (
            <LoadingRow label="Invalidating…" />
          ) : result ? (
            <InvalidateResultCard result={result} />
          ) : (
            <EmptyState
              icon={<Ban className="w-5 h-5 text-zinc-500" />}
              title="No invalidation yet"
              description="Enter an email and submit to invalidate its pending links."
            />
          )}
        </CardSection>
      </Card>
    </div>
  );
}

function InvalidateResultCard({ result }: { readonly result: InvalidateResponse }) {
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
        <span className="text-sm font-semibold text-zinc-100">{ok ? "Success" : "Failed"}</span>
      </div>
      {result.invalidated !== undefined && (
        <StatRow label="Invalidated" value={String(result.invalidated)} />
      )}
      {result.email && <StatRow label="Email" value={result.email} />}
      {result.message && <StatRow label="Message" value={result.message} />}
      {result.trace_id && <StatRow label="Trace ID" value={result.trace_id} />}
    </div>
  );
}
