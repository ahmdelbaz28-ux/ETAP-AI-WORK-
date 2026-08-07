/**
 * MFA Page — Admin/debug UI for the mfa backend module.
 *
 * Wires to all 3 endpoints exposed by api/mfa.py
 * (prefix /api/v1/auth/mfa):
 *   POST /totp/setup    — generate TOTP secret + QR code + backup codes
 *                          (auto-enables MFA on the user record)
 *   POST /totp/verify   — verify a 6-digit TOTP code (brute-force protected)
 *   POST /backup/verify — verify a backup recovery code (SHA-256 hashed)
 *
 * All 3 endpoints require a JWT (F-04 security fix — previously accepted
 * user_id from body, allowing account takeover). The body-supplied
 * user_id field is OPTIONAL and must match the JWT subject; we omit it
 * entirely and let the backend use the JWT subject.
 *
 * The page is operator/dev-oriented: it lets an admin set up MFA for
 * their own account (displaying the QR URI for an authenticator app),
 * verify TOTP codes (useful for debugging authenticator integration),
 * and verify backup codes (for testing the recovery flow).
 *
 * Ref: TASK-9c
 */

import { motion } from "framer-motion";
import {
  CheckCircle2,
  KeyRound,
  Loader2,
  QrCode,
  ShieldAlert,
  ShieldCheck,
  Smartphone,
  XCircle,
} from "lucide-react";
import { QRCodeSVG } from "qrcode.react";
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
// Types — mirror api/mfa.py
// ---------------------------------------------------------------------------

interface SetupResponse {
  success: boolean;
  data?: {
    qr_code_uri?: string;
  };
  errors?: string[];
  trace_id?: string;
  // Error variants (rare — usually 500)
  error?: string;
  message?: string;
}

interface VerifyTotpResponse {
  success: boolean;
  data?: {
    valid: boolean;
  };
  error?: string;
  message?: string;
  trace_id?: string;
}

interface VerifyBackupResponse {
  success: boolean;
  data?: {
    valid: boolean;
  };
  error?: string;
  message?: string;
  trace_id?: string;
}

type TabId = "setup" | "verify-totp" | "verify-backup";

// ---------------------------------------------------------------------------
// Fetch helper
// ---------------------------------------------------------------------------
// Replaced with shared adminFetch from lib/admin-fetch.ts.
// Ref: fix/admin-pages-hardening (#4 + #6)

// ---------------------------------------------------------------------------
// Page component
// ---------------------------------------------------------------------------

export default function MfaPage() {
  const { notify } = useNotify();
  const { t } = useTranslation();
  const [tab, setTab] = useState<TabId>("setup");

  // ─── Setup tab state ────────────────────────────────────────────────
  const [setupResult, setSetupResult] = useState<SetupResponse | null>(null);
  const [setupLoading, setSetupLoading] = useState(false);
  const [setupError, setSetupError] = useState<string | null>(null);

  // ─── Verify TOTP tab state ──────────────────────────────────────────
  const [totpCode, setTotpCode] = useState("");
  const [totpResult, setTotpResult] = useState<VerifyTotpResponse | null>(null);
  const [totpLoading, setTotpLoading] = useState(false);
  const [totpError, setTotpError] = useState<string | null>(null);

  // ─── Verify Backup tab state ────────────────────────────────────────
  const [backupCode, setBackupCode] = useState("");
  const [backupResult, setBackupResult] = useState<VerifyBackupResponse | null>(null);
  const [backupLoading, setBackupLoading] = useState(false);
  const [backupError, setBackupError] = useState<string | null>(null);

  // -------------------------------------------------------------------------
  // Handlers
  // -------------------------------------------------------------------------

  const handleSetup = useCallback(async () => {
    setSetupLoading(true);
    setSetupError(null);
    setSetupResult(null);
    try {
      // No body needed — TOTP secret is generated for the JWT subject.
      // We deliberately omit user_id (F-04: body user_id must match
      // JWT subject or 403; safer to omit entirely).
      const res = await adminFetch<SetupResponse>("/api/v1/auth/mfa/totp/setup", {
        method: "POST",
        body: JSON.stringify({}),
      });
      setSetupResult(res);
      if (res.success) {
        notify("success", t("adminPages.mfa.setup.success"));
      } else {
        notify(
          "error",
          t("adminPages.mfa.setup.failed", {
            error: res.errors?.[0] ?? res.error ?? t("adminPages.common.unknownError"),
          }),
        );
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setSetupError(msg);
      notify("error", `Setup failed: ${msg}`);
    } finally {
      setSetupLoading(false);
    }
  }, [notify, t]);

  const handleVerifyTotp = useCallback(async () => {
    if (!totpCode.trim()) {
      setTotpError("Code is required.");
      return;
    }
    if (!/^\d{4,20}$/.test(totpCode.trim())) {
      setTotpError("Code must be 4-20 digits.");
      return;
    }
    setTotpLoading(true);
    setTotpError(null);
    setTotpResult(null);
    try {
      // Omit user_id — backend uses JWT subject (F-04 fix).
      const res = await adminFetch<VerifyTotpResponse>("/api/v1/auth/mfa/totp/verify", {
        method: "POST",
        body: JSON.stringify({ code: totpCode.trim() }),
      });
      setTotpResult(res);
      if (res.success) {
        notify("success", t("adminPages.mfa.verifyTotp.success"));
      } else {
        notify(
          "error",
          t("adminPages.mfa.verifyTotp.failed", {
            error: res.error ?? t("adminPages.common.unknownError"),
          }),
        );
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setTotpError(msg);
      notify("error", `Verify failed: ${msg}`);
    } finally {
      setTotpLoading(false);
    }
  }, [totpCode, notify, t]);

  const handleVerifyBackup = useCallback(async () => {
    if (!backupCode.trim()) {
      setBackupError("Backup code is required.");
      return;
    }
    if (backupCode.trim().length < 8 || backupCode.trim().length > 16) {
      setBackupError("Backup code must be 8-16 characters.");
      return;
    }
    setBackupLoading(true);
    setBackupError(null);
    setBackupResult(null);
    try {
      // Omit user_id — backend uses JWT subject (F-04 fix).
      const res = await adminFetch<VerifyBackupResponse>("/api/v1/auth/mfa/backup/verify", {
        method: "POST",
        body: JSON.stringify({ code: backupCode.trim() }),
      });
      setBackupResult(res);
      if (res.success) {
        notify("success", t("adminPages.mfa.verifyBackup.success"));
      } else {
        notify(
          "error",
          t("adminPages.mfa.verifyBackup.failed", {
            error: res.error ?? t("adminPages.common.unknownError"),
          }),
        );
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setBackupError(msg);
      notify("error", `Verify failed: ${msg}`);
    } finally {
      setBackupLoading(false);
    }
  }, [backupCode, notify, t]);

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  const tabs: {
    readonly id: string;
    readonly label: string;
    readonly icon: ReactNode;
  }[] = [
    {
      id: "setup",
      label: t("adminPages.mfa.tabs.setup"),
      icon: <QrCode className="w-4 h-4" />,
    },
    {
      id: "verify-totp",
      label: t("adminPages.mfa.tabs.verifyTotp"),
      icon: <Smartphone className="w-4 h-4" />,
    },
    {
      id: "verify-backup",
      label: t("adminPages.mfa.tabs.verifyBackup"),
      icon: <ShieldCheck className="w-4 h-4" />,
    },
  ];

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-6 p-6">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-lg bg-brand-500/10 flex items-center justify-center">
          <KeyRound className="w-5 h-5 text-brand-500" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">
            {t("adminPages.mfa.title")}
          </h1>
          <p className="text-sm text-[var(--text-muted)] mt-0.5">{t("adminPages.mfa.subtitle")}</p>
        </div>
      </div>

      <Tabs tabs={tabs} activeTab={tab} onChange={(id) => setTab(id as TabId)} />

      {tab === "setup" && (
        <SetupTab
          loading={setupLoading}
          error={setupError}
          result={setupResult}
          onSubmit={handleSetup}
        />
      )}
      {tab === "verify-totp" && (
        <VerifyTotpTab
          code={totpCode}
          setCode={setTotpCode}
          loading={totpLoading}
          error={totpError}
          result={totpResult}
          onSubmit={handleVerifyTotp}
        />
      )}
      {tab === "verify-backup" && (
        <VerifyBackupTab
          code={backupCode}
          setCode={setBackupCode}
          loading={backupLoading}
          error={backupError}
          result={backupResult}
          onSubmit={handleVerifyBackup}
        />
      )}
    </motion.div>
  );
}

// ---------------------------------------------------------------------------
// Tab components
// ---------------------------------------------------------------------------

function SetupTab({
  loading,
  error,
  result,
  onSubmit,
}: {
  readonly loading: boolean;
  readonly error: string | null;
  readonly result: SetupResponse | null;
  readonly onSubmit: () => void;
}) {
  const { t } = useTranslation();
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <Card>
        <CardHeader
          title={
            <span className="flex items-center gap-2">
              <QrCode className="w-4 h-4" />
              {t("adminPages.mfa.setup.cardTitle")}
            </span>
          }
          subtitle={t("adminPages.mfa.setup.cardSubtitle")}
        />
        <CardSection className="p-4 space-y-4">
          <p className="text-sm text-zinc-400">{t("adminPages.mfa.setup.description")}</p>
          <p className="text-xs text-amber-400 bg-amber-500/10 border border-amber-500/30 rounded-md p-2">
            <ShieldAlert className="w-3 h-3 inline mr-1" />
            {t("adminPages.mfa.setup.warning")}
          </p>

          {error && <ErrorBanner message={error} />}

          <div className="flex justify-end gap-2">
            <Button data-testid="setup-submit" onClick={onSubmit} disabled={loading}>
              {loading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <QrCode className="w-4 h-4" />
              )}
              {t("adminPages.mfa.setup.submit")}
            </Button>
          </div>
        </CardSection>
      </Card>

      <Card>
        <CardHeader
          title={t("adminPages.common.result")}
          subtitle={t("adminPages.mfa.setup.resultSubtitle")}
        />
        <CardSection className="p-4">
          {(() => {
            if (loading) return <LoadingRow label={t("adminPages.mfa.setup.loading")} />;
            if (result) return <SetupResultCard result={result} />;
            return (
              <EmptyState
                icon={<QrCode className="w-5 h-5 text-zinc-500" />}
                title={t("adminPages.mfa.setup.emptyTitle")}
                description={t("adminPages.mfa.setup.emptyDescription")}
              />
            );
          })()}
        </CardSection>
      </Card>
    </div>
  );
}

function SetupResultCard({ result }: { readonly result: SetupResponse }) {
  const { t } = useTranslation();
  const ok = result.success;
  const qrUri = result.data?.qr_code_uri;
  return (
    <div
      data-testid="setup-result"
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
        {ok && (
          <Badge className="ml-auto" variant="brand">
            {t("adminPages.mfa.setup.mfaEnabledBadge")}
          </Badge>
        )}
      </div>
      {qrUri && (
        <div className="space-y-2 py-2">
          <StatRow
            label={t("adminPages.mfa.setup.qrUri")}
            value={<span className="text-xs break-all">{qrUri}</span>}
          />
          {/*
            Client-side QR renderer (qrcode.react). Previously this sent
            the otpauth:// URI — which contains the TOTP secret in
            plaintext — to https://api.qrserver.com, leaking the user's
            MFA secret to a third party. SVG renderer is purely
            client-side; no network egress. Ref: fix/mfa-qr-leak.
          */}
          <div className="flex justify-center py-3 bg-white rounded-md">
            <QRCodeSVG
              value={qrUri}
              size={200}
              level="M"
              bgColor="#ffffff"
              fgColor="#000000"
              role="img"
              aria-label={t("adminPages.mfa.setup.qrAriaLabel", {
                account:
                  /otpauth:\/\/totp\/([^?]+)/.exec(qrUri)?.[1] ??
                  t("adminPages.mfa.setup.thisAccount"),
              })}
              className="w-48 h-48"
            />
          </div>
          <p className="text-xs text-zinc-500 text-center">{t("adminPages.mfa.setup.scanHelp")}</p>
        </div>
      )}
      {result.errors && result.errors.length > 0 && (
        <StatRow label={t("adminPages.mfa.setup.errors")} value={result.errors.join("; ")} />
      )}
      {result.error && <StatRow label={t("adminPages.common.error")} value={result.error} />}
      {result.message && <StatRow label={t("adminPages.common.message")} value={result.message} />}
      {result.trace_id && (
        <StatRow label={t("adminPages.common.traceId")} value={result.trace_id} />
      )}
    </div>
  );
}

function VerifyTotpTab({
  code,
  setCode,
  loading,
  error,
  result,
  onSubmit,
}: {
  readonly code: string;
  readonly setCode: (v: string) => void;
  readonly loading: boolean;
  readonly error: string | null;
  readonly result: VerifyTotpResponse | null;
  readonly onSubmit: () => void;
}) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <Card>
        <CardHeader
          title={
            <span className="flex items-center gap-2">
              <Smartphone className="w-4 h-4" />
              Verify TOTP Code
            </span>
          }
          subtitle="POST /totp/verify — requires JWT, brute-force protected"
        />
        <CardSection className="p-4 space-y-4">
          <div>
            <label htmlFor="totp-code" className={labelClass}>
              TOTP code
            </label>
            <input
              id="totp-code"
              data-testid="totp-code"
              type="text"
              inputMode="numeric"
              pattern="[0-9]*"
              maxLength={20}
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
              className={`${inputClass} font-mono text-center text-lg tracking-widest`}
              placeholder="123456"
              autoComplete="one-time-code"
            />
            <p className="text-xs text-zinc-500 mt-1">
              6-digit code from your authenticator app. Codes are valid for 30 seconds and can only
              be used once (V-12 replay protection). 5 failed attempts trigger a 15-minute lockout.
            </p>
          </div>

          {error && <ErrorBanner message={error} />}

          <div className="flex justify-end gap-2">
            <Button data-testid="totp-submit" onClick={onSubmit} disabled={loading || !code.trim()}>
              {loading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <ShieldCheck className="w-4 h-4" />
              )}
              Verify Code
            </Button>
          </div>
        </CardSection>
      </Card>

      <Card>
        <CardHeader title="Result" subtitle="Response from POST /totp/verify" />
        <CardSection className="p-4">
          {(() => {
            if (loading) return <LoadingRow label="Verifying TOTP code…" />;
            if (result) return <VerifyResultCard result={result} testId="totp-result" successLabel="Verified" />;
            return (
              <EmptyState
                icon={<Smartphone className="w-5 h-5 text-zinc-500" />}
                title="No verification yet"
                description="Enter a code and submit to verify it."
              />
            );
          })()}
        </CardSection>
      </Card>
    </div>
  );
}

function VerifyBackupTab({
  code,
  setCode,
  loading,
  error,
  result,
  onSubmit,
}: {
  readonly code: string;
  readonly setCode: (v: string) => void;
  readonly loading: boolean;
  readonly error: string | null;
  readonly result: VerifyBackupResponse | null;
  readonly onSubmit: () => void;
}) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <Card>
        <CardHeader
          title={
            <span className="flex items-center gap-2">
              <ShieldCheck className="w-4 h-4" />
              Verify Backup Code
            </span>
          }
          subtitle="POST /backup/verify — requires JWT, recovery flow"
        />
        <CardSection className="p-4 space-y-4">
          <div>
            <label htmlFor="backup-code" className={labelClass}>
              Backup recovery code
            </label>
            <input
              id="backup-code"
              data-testid="backup-code"
              type="text"
              maxLength={16}
              value={code}
              onChange={(e) => setCode(e.target.value)}
              className={`${inputClass} font-mono text-center text-sm tracking-wider`}
              placeholder="ABCD-1234-EFGH"
              autoComplete="off"
            />
            <p className="text-xs text-zinc-500 mt-1">
              8-16 character backup code shown once during TOTP setup. Codes are SHA-256 hashed
              before comparison (V-9). Same brute-force lockout as TOTP applies.
            </p>
          </div>

          {error && <ErrorBanner message={error} />}

          <div className="flex justify-end gap-2">
            <Button
              data-testid="backup-submit"
              onClick={onSubmit}
              disabled={loading || !code.trim()}
              variant="secondary"
            >
              {loading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <ShieldCheck className="w-4 h-4" />
              )}
              Verify Backup Code
            </Button>
          </div>
        </CardSection>
      </Card>

      <Card>
        <CardHeader title="Result" subtitle="Response from POST /backup/verify" />
        <CardSection className="p-4">
          {(() => {
            if (loading) return <LoadingRow label="Verifying backup code…" />;
            if (result) return <VerifyResultCard result={result} testId="backup-result" successLabel="Verified" />;
            return (
              <EmptyState
                icon={<ShieldCheck className="w-5 h-5 text-zinc-500" />}
                title="No verification yet"
                description="Enter a backup code and submit to verify it."
              />
            );
          })()}
        </CardSection>
      </Card>
    </div>
  );
}

function VerifyResultCard({
  result,
  testId,
  successLabel,
}: {
  readonly result: VerifyTotpResponse | VerifyBackupResponse;
  readonly testId: string;
  readonly successLabel: string;
}) {
  const ok = result.success;
  return (
    <div
      data-testid={testId}
      className="rounded-md border border-zinc-800 bg-zinc-900/50 p-4 space-y-1"
    >
      <div className="flex items-center gap-2 mb-3">
        {ok ? (
          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
        ) : (
          <XCircle className="w-4 h-4 text-red-400" />
        )}
        <span className="text-sm font-semibold text-zinc-100">{ok ? successLabel : "Failed"}</span>
        {result.data?.valid !== undefined && (
          <Badge className="ml-auto" variant={result.data.valid ? "success" : "danger"}>
            {result.data.valid ? "valid" : "invalid"}
          </Badge>
        )}
      </div>
      {result.message && <StatRow label="Message" value={result.message} />}
      {result.error && <StatRow label="Error" value={result.error} />}
      {result.trace_id && <StatRow label="Trace ID" value={result.trace_id} />}
    </div>
  );
}
