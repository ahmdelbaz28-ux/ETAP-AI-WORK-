/**
 * Email OTP Page — Admin/debug UI for the email-otp backend module.
 *
 * Wires to all 3 endpoints exposed by api/email_otp.py
 * (prefix /api/v1/auth/email-otp):
 *   POST /send        — send a 6-digit OTP to an email address
 *   POST /verify      — verify an OTP code (one-shot consume)
 *   POST /invalidate  — force-invalidate a pending OTP (query params)
 *
 * The page is operator/dev-oriented: it lets an admin trigger an OTP send
 * for any email/purpose combination, verify a code without round-tripping
 * through the email inbox (useful for debugging), and invalidate a
 * pending OTP for logout/admin flows. All three endpoints are public
 * (no JWT required) — they're exercised with mock responses in tests.
 *
 * Ref: TASK-8
 */

import { motion } from "framer-motion";
import {
	AlertTriangle,
	Ban,
	CheckCircle2,
	KeyRound,
	Loader2,
	RefreshCw,
	Send,
	ShieldCheck,
	XCircle,
} from "lucide-react";
import { type ReactNode, useCallback, useState } from "react";
import {
	Badge,
	Button,
	Card,
	CardHeader,
	CardSection,
	EmptyState,
	Tabs,
} from "../components/ui";
import { useNotify } from "../context/NotificationContext";
import { API_BASE_URL } from "../lib/api-config";
import { getAuthToken } from "../lib/tokenStorage";

// ---------------------------------------------------------------------------
// Types — mirror api/email_otp.py
// ---------------------------------------------------------------------------

type OtpPurpose =
	| "signup"
	| "login"
	| "password_reset"
	| "mfa"
	| "sensitive_action";

interface SendOtpRequest {
	email: string;
	purpose: OtpPurpose;
	user_name?: string;
}

interface SendOtpResponse {
	success: boolean;
	expires_in_seconds?: number;
	cooldown_seconds?: number;
	message?: string;
	trace_id?: string;
	// Test-mode only
	test_code?: string;
	test_mode?: boolean;
	// Error variants
	error?: string;
	retry_after_seconds?: number;
	resend_error?: string;
}

interface VerifyOtpRequest {
	email: string;
	purpose: OtpPurpose;
	code: string;
}

interface VerifyOtpResponse {
	success: boolean;
	message?: string;
	verified_email?: string;
	purpose?: string;
	action_token?: string | null;
	action_token_expires_in?: number | null;
	trace_id?: string;
	test_mode?: boolean;
	// Error variants
	error?: string;
	retry_after_seconds?: number | null;
}

interface InvalidateResponse {
	success: boolean;
	message?: string;
	trace_id?: string;
}

type TabId = "send" | "verify" | "invalidate";

// ---------------------------------------------------------------------------
// Fetch helper
// ---------------------------------------------------------------------------

function authHeaders(
	extra: Record<string, string> = {},
): Record<string, string> {
	const token = getAuthToken();
	return { ...(token ? { Authorization: `Bearer ${token}` } : {}), ...extra };
}

async function otpFetch<T>(path: string, init?: RequestInit): Promise<T> {
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

function StatRow({
	label,
	value,
}: { readonly label: string; readonly value: ReactNode }) {
	return (
		<div className="flex items-center justify-between py-2 border-b border-[var(--border-primary)] last:border-0 gap-3">
			<span className="text-xs uppercase tracking-wider text-zinc-400 font-semibold shrink-0">
				{label}
			</span>
			<span className="text-sm text-zinc-100 font-mono text-right break-all">
				{value}
			</span>
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

const PURPOSE_OPTIONS: {
	readonly value: OtpPurpose;
	readonly label: string;
}[] = [
	{ value: "login", label: "Login (passwordless)" },
	{ value: "signup", label: "Signup verification" },
	{ value: "password_reset", label: "Password reset" },
	{ value: "mfa", label: "MFA alternative" },
	{ value: "sensitive_action", label: "Sensitive action (5min token)" },
];

const inputClass =
	"w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:ring-2 focus:ring-brand-500/50";
const labelClass =
	"block text-xs uppercase tracking-wider text-zinc-400 font-semibold mb-1";

// ---------------------------------------------------------------------------
// Page component
// ---------------------------------------------------------------------------

export default function EmailOtpPage() {
	const { notify } = useNotify();
	const [tab, setTab] = useState<TabId>("send");

	// ─── Send tab state ──────────────────────────────────────────────────
	const [sendEmail, setSendEmail] = useState("");
	const [sendPurpose, setSendPurpose] = useState<OtpPurpose>("login");
	const [sendName, setSendName] = useState("");
	const [sendResult, setSendResult] = useState<SendOtpResponse | null>(null);
	const [sendLoading, setSendLoading] = useState(false);
	const [sendError, setSendError] = useState<string | null>(null);

	// ─── Verify tab state ────────────────────────────────────────────────
	const [verifyEmail, setVerifyEmail] = useState("");
	const [verifyPurpose, setVerifyPurpose] = useState<OtpPurpose>("login");
	const [verifyCode, setVerifyCode] = useState("");
	const [verifyResult, setVerifyResult] = useState<VerifyOtpResponse | null>(
		null,
	);
	const [verifyLoading, setVerifyLoading] = useState(false);
	const [verifyError, setVerifyError] = useState<string | null>(null);

	// ─── Invalidate tab state ────────────────────────────────────────────
	const [invEmail, setInvEmail] = useState("");
	const [invPurpose, setInvPurpose] = useState<OtpPurpose>("login");
	const [invResult, setInvResult] = useState<InvalidateResponse | null>(null);
	const [invLoading, setInvLoading] = useState(false);
	const [invError, setInvError] = useState<string | null>(null);

	// -------------------------------------------------------------------------
	// Handlers
	// -------------------------------------------------------------------------

	const handleSend = useCallback(async () => {
		if (!sendEmail.trim()) {
			setSendError("Email is required.");
			return;
		}
		setSendLoading(true);
		setSendError(null);
		setSendResult(null);
		try {
			const body: SendOtpRequest = {
				email: sendEmail.trim(),
				purpose: sendPurpose,
				...(sendName.trim() ? { user_name: sendName.trim() } : {}),
			};
			const res = await otpFetch<SendOtpResponse>(
				"/api/v1/auth/email-otp/send",
				{
					method: "POST",
					body: JSON.stringify(body),
				},
			);
			setSendResult(res);
			if (res.success) {
				const codeNote = res.test_code ? ` (test code: ${res.test_code})` : "";
				notify("success", `OTP sent to ${sendEmail.trim()}.${codeNote}`);
			} else {
				notify("error", `Send failed: ${res.error ?? "unknown error"}`);
			}
		} catch (err) {
			const msg = err instanceof Error ? err.message : String(err);
			setSendError(msg);
			notify("error", `Send failed: ${msg}`);
		} finally {
			setSendLoading(false);
		}
	}, [sendEmail, sendPurpose, sendName, notify]);

	const handleVerify = useCallback(async () => {
		if (!verifyEmail.trim()) {
			setVerifyError("Email is required.");
			return;
		}
		if (!verifyCode.trim()) {
			setVerifyError("Code is required.");
			return;
		}
		setVerifyLoading(true);
		setVerifyError(null);
		setVerifyResult(null);
		try {
			const body: VerifyOtpRequest = {
				email: verifyEmail.trim(),
				purpose: verifyPurpose,
				code: verifyCode.trim(),
			};
			const res = await otpFetch<VerifyOtpResponse>(
				"/api/v1/auth/email-otp/verify",
				{
					method: "POST",
					body: JSON.stringify(body),
				},
			);
			setVerifyResult(res);
			if (res.success) {
				notify("success", `OTP verified for ${verifyEmail.trim()}.`);
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
	}, [verifyEmail, verifyPurpose, verifyCode, notify]);

	const handleInvalidate = useCallback(async () => {
		if (!invEmail.trim()) {
			setInvError("Email is required.");
			return;
		}
		setInvLoading(true);
		setInvError(null);
		setInvResult(null);
		try {
			// Invalidate uses query params (email, purpose) per the backend.
			const qs = new URLSearchParams({
				email: invEmail.trim(),
				purpose: invPurpose,
			});
			const res = await otpFetch<InvalidateResponse>(
				`/api/v1/auth/email-otp/invalidate?${qs.toString()}`,
				{ method: "POST" },
			);
			setInvResult(res);
			if (res.success) {
				notify(
					"success",
					`OTP invalidated for ${invEmail.trim()} (${invPurpose}).`,
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
	}, [invEmail, invPurpose, notify]);

	// -------------------------------------------------------------------------
	// Render
	// -------------------------------------------------------------------------

	const tabs = [
		{ id: "send", label: "Send OTP", icon: <Send className="w-4 h-4" /> },
		{
			id: "verify",
			label: "Verify",
			icon: <ShieldCheck className="w-4 h-4" />,
		},
		{
			id: "invalidate",
			label: "Invalidate",
			icon: <Ban className="w-4 h-4" />,
		},
	];

	return (
		<motion.div
			initial={{ opacity: 0 }}
			animate={{ opacity: 1 }}
			className="space-y-6 p-6 max-w-7xl mx-auto"
		>
			{/* ─── Header ─────────────────────────────────────────────────────── */}
			<div className="flex items-start justify-between gap-4">
				<div className="min-w-0">
					<h1 className="text-2xl font-bold text-[var(--text-primary)] flex items-center gap-2">
						<KeyRound className="w-6 h-6 text-brand-500" />
						Email OTP
					</h1>
					<p className="text-sm text-[var(--text-muted)] mt-1">
						Admin &amp; debug tools for the email one-time-passcode flow. Send a
						code to any email/purpose, verify it without round-tripping through
						the inbox, or invalidate a pending OTP for logout/admin flows.
					</p>
				</div>
				<Button
					variant="secondary"
					size="sm"
					onClick={() => {
						setSendResult(null);
						setVerifyResult(null);
						setInvResult(null);
					}}
					icon={RefreshCw}
				>
					Clear Results
				</Button>
			</div>

			<Tabs
				tabs={tabs}
				activeTab={tab}
				onChange={(id) => setTab(id as TabId)}
			/>

			{/* ─── Send tab ───────────────────────────────────────────────────── */}
			{tab === "send" && (
				<div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
					{/* Form card */}
					<Card>
						<CardHeader
							title={
								<span className="flex items-center gap-2">
									<Send className="w-4 h-4" />
									Send OTP
								</span>
							}
							subtitle="Trigger POST /send — rate-limited per (email, purpose)"
						/>
						<CardSection className="p-4 space-y-4">
							<div>
								<label htmlFor="send-email" className={labelClass}>
									Recipient email
								</label>
								<input
									id="send-email"
									type="email"
									value={sendEmail}
									onChange={(e) => setSendEmail(e.target.value)}
									placeholder="user@example.com"
									className={inputClass}
									data-testid="send-email"
								/>
							</div>
							<div>
								<label htmlFor="send-purpose" className={labelClass}>
									Purpose
								</label>
								<select
									id="send-purpose"
									value={sendPurpose}
									onChange={(e) => setSendPurpose(e.target.value as OtpPurpose)}
									className={inputClass}
									data-testid="send-purpose"
								>
									{PURPOSE_OPTIONS.map((p) => (
										<option key={p.value} value={p.value}>
											{p.label}
										</option>
									))}
								</select>
							</div>
							<div>
								<label htmlFor="send-name" className={labelClass}>
									Display name (optional)
								</label>
								<input
									id="send-name"
									type="text"
									maxLength={120}
									value={sendName}
									onChange={(e) => setSendName(e.target.value)}
									placeholder="Ahmed"
									className={inputClass}
									data-testid="send-name"
								/>
							</div>
							{sendError && <ErrorBanner message={sendError} />}
							<div className="flex justify-end">
								<Button
									variant="primary"
									onClick={handleSend}
									loading={sendLoading}
									icon={Send}
									disabled={!sendEmail.trim()}
									data-testid="send-submit"
								>
									{sendLoading ? "Sending…" : "Send OTP"}
								</Button>
							</div>
						</CardSection>
					</Card>

					{/* Result card */}
					<Card>
						<CardHeader
							title="Result"
							subtitle="Backend response from POST /send"
						/>
						<CardSection className="p-4">
							{!sendResult && !sendLoading && (
								<EmptyState
									icon={<Send className="w-8 h-8" />}
									title="No result yet"
									description="Fill the form and click Send OTP to see the backend response here."
								/>
							)}
							{sendLoading && <LoadingRow label="Sending OTP…" />}
							{sendResult && (
								<div data-testid="send-result" className="space-y-2">
									<div className="flex items-center gap-2">
										{sendResult.success ? (
											<CheckCircle2 className="w-4 h-4 text-green-400" />
										) : (
											<XCircle className="w-4 h-4 text-red-400" />
										)}
										<span className="text-sm font-semibold text-zinc-200">
											{sendResult.success ? "Success" : "Failed"}
										</span>
										{sendResult.test_mode && (
											<Badge className="bg-amber-500/10 text-amber-300 border border-amber-500/30">
												test mode
											</Badge>
										)}
									</div>
									{sendResult.message && (
										<p className="text-xs text-zinc-400">
											{sendResult.message}
										</p>
									)}
									{sendResult.error && (
										<div className="rounded-md border border-red-500/30 bg-red-500/10 p-2 text-xs text-red-300 font-mono break-all">
											{sendResult.error}
										</div>
									)}
									{sendResult.expires_in_seconds !== undefined && (
										<StatRow
											label="Expires in"
											value={`${sendResult.expires_in_seconds}s`}
										/>
									)}
									{sendResult.cooldown_seconds !== undefined && (
										<StatRow
											label="Cooldown"
											value={`${sendResult.cooldown_seconds}s`}
										/>
									)}
									{sendResult.retry_after_seconds !== undefined && (
										<StatRow
											label="Retry after"
											value={`${sendResult.retry_after_seconds}s`}
										/>
									)}
									{sendResult.test_code && (
										<StatRow label="Test code" value={sendResult.test_code} />
									)}
									{sendResult.trace_id && (
										<StatRow label="Trace ID" value={sendResult.trace_id} />
									)}
								</div>
							)}
						</CardSection>
					</Card>
				</div>
			)}

			{/* ─── Verify tab ─────────────────────────────────────────────────── */}
			{tab === "verify" && (
				<div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
					<Card>
						<CardHeader
							title={
								<span className="flex items-center gap-2">
									<ShieldCheck className="w-4 h-4" />
									Verify OTP
								</span>
							}
							subtitle="Trigger POST /verify — code is consumed on success (one-shot)"
						/>
						<CardSection className="p-4 space-y-4">
							<div>
								<label htmlFor="verify-email" className={labelClass}>
									Email
								</label>
								<input
									id="verify-email"
									type="email"
									value={verifyEmail}
									onChange={(e) => setVerifyEmail(e.target.value)}
									placeholder="user@example.com"
									className={inputClass}
									data-testid="verify-email"
								/>
							</div>
							<div>
								<label htmlFor="verify-purpose" className={labelClass}>
									Purpose
								</label>
								<select
									id="verify-purpose"
									value={verifyPurpose}
									onChange={(e) =>
										setVerifyPurpose(e.target.value as OtpPurpose)
									}
									className={inputClass}
									data-testid="verify-purpose"
								>
									{PURPOSE_OPTIONS.map((p) => (
										<option key={p.value} value={p.value}>
											{p.label}
										</option>
									))}
								</select>
							</div>
							<div>
								<label htmlFor="verify-code" className={labelClass}>
									Code (6 digits)
								</label>
								<input
									id="verify-code"
									type="text"
									inputMode="numeric"
									maxLength={6}
									value={verifyCode}
									onChange={(e) => setVerifyCode(e.target.value)}
									placeholder="123456"
									className={inputClass}
									data-testid="verify-code"
								/>
							</div>
							{verifyError && <ErrorBanner message={verifyError} />}
							<div className="flex justify-end">
								<Button
									variant="primary"
									onClick={handleVerify}
									loading={verifyLoading}
									icon={ShieldCheck}
									disabled={!verifyEmail.trim() || !verifyCode.trim()}
									data-testid="verify-submit"
								>
									{verifyLoading ? "Verifying…" : "Verify"}
								</Button>
							</div>
						</CardSection>
					</Card>

					<Card>
						<CardHeader
							title="Result"
							subtitle="Backend response from POST /verify"
						/>
						<CardSection className="p-4">
							{!verifyResult && !verifyLoading && (
								<EmptyState
									icon={<ShieldCheck className="w-8 h-8" />}
									title="No result yet"
									description="Fill the form and click Verify to see the backend response here."
								/>
							)}
							{verifyLoading && <LoadingRow label="Verifying OTP…" />}
							{verifyResult && (
								<div data-testid="verify-result" className="space-y-2">
									<div className="flex items-center gap-2">
										{verifyResult.success ? (
											<CheckCircle2 className="w-4 h-4 text-green-400" />
										) : (
											<XCircle className="w-4 h-4 text-red-400" />
										)}
										<span className="text-sm font-semibold text-zinc-200">
											{verifyResult.success ? "Verified" : "Failed"}
										</span>
										{verifyResult.test_mode && (
											<Badge className="bg-amber-500/10 text-amber-300 border border-amber-500/30">
												test mode
											</Badge>
										)}
									</div>
									{verifyResult.message && (
										<p className="text-xs text-zinc-400">
											{verifyResult.message}
										</p>
									)}
									{verifyResult.error && (
										<div className="rounded-md border border-red-500/30 bg-red-500/10 p-2 text-xs text-red-300 font-mono break-all">
											{verifyResult.error}
										</div>
									)}
									{verifyResult.verified_email && (
										<StatRow
											label="Verified email"
											value={verifyResult.verified_email}
										/>
									)}
									{verifyResult.purpose && (
										<StatRow label="Purpose" value={verifyResult.purpose} />
									)}
									{verifyResult.action_token && (
										<StatRow
											label="Action token"
											value={verifyResult.action_token}
										/>
									)}
									{verifyResult.action_token_expires_in !== null &&
										verifyResult.action_token_expires_in !== undefined && (
											<StatRow
												label="Token TTL"
												value={`${verifyResult.action_token_expires_in}s`}
											/>
										)}
									{verifyResult.retry_after_seconds !== null &&
										verifyResult.retry_after_seconds !== undefined && (
											<StatRow
												label="Retry after"
												value={`${verifyResult.retry_after_seconds}s`}
											/>
										)}
									{verifyResult.trace_id && (
										<StatRow label="Trace ID" value={verifyResult.trace_id} />
									)}
								</div>
							)}
						</CardSection>
					</Card>
				</div>
			)}

			{/* ─── Invalidate tab ─────────────────────────────────────────────── */}
			{tab === "invalidate" && (
				<div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
					<Card>
						<CardHeader
							title={
								<span className="flex items-center gap-2">
									<Ban className="w-4 h-4" />
									Invalidate OTP
								</span>
							}
							subtitle="Trigger POST /invalidate — force-clear a pending OTP (query params)"
						/>
						<CardSection className="p-4 space-y-4">
							<p className="text-sm text-zinc-400">
								Force-invalidate a pending OTP for the given email/purpose.
								Useful for logout flows or admin operations. The endpoint
								accepts{" "}
								<code className="text-xs font-mono text-zinc-300">email</code>{" "}
								and{" "}
								<code className="text-xs font-mono text-zinc-300">purpose</code>{" "}
								as query parameters.
							</p>
							<div>
								<label htmlFor="inv-email" className={labelClass}>
									Email
								</label>
								<input
									id="inv-email"
									type="email"
									value={invEmail}
									onChange={(e) => setInvEmail(e.target.value)}
									placeholder="user@example.com"
									className={inputClass}
									data-testid="inv-email"
								/>
							</div>
							<div>
								<label htmlFor="inv-purpose" className={labelClass}>
									Purpose
								</label>
								<select
									id="inv-purpose"
									value={invPurpose}
									onChange={(e) => setInvPurpose(e.target.value as OtpPurpose)}
									className={inputClass}
									data-testid="inv-purpose"
								>
									{PURPOSE_OPTIONS.map((p) => (
										<option key={p.value} value={p.value}>
											{p.label}
										</option>
									))}
								</select>
							</div>
							{invError && <ErrorBanner message={invError} />}
							<div className="flex justify-end">
								<Button
									variant="primary"
									onClick={handleInvalidate}
									loading={invLoading}
									icon={Ban}
									disabled={!invEmail.trim()}
									data-testid="inv-submit"
								>
									{invLoading ? "Invalidating…" : "Invalidate"}
								</Button>
							</div>
						</CardSection>
					</Card>

					<Card>
						<CardHeader
							title="Result"
							subtitle="Backend response from POST /invalidate"
						/>
						<CardSection className="p-4">
							{!invResult && !invLoading && (
								<EmptyState
									icon={<Ban className="w-8 h-8" />}
									title="No result yet"
									description="Fill the form and click Invalidate to see the backend response here."
								/>
							)}
							{invLoading && <LoadingRow label="Invalidating OTP…" />}
							{invResult && (
								<div data-testid="inv-result" className="space-y-2">
									<div className="flex items-center gap-2">
										{invResult.success ? (
											<CheckCircle2 className="w-4 h-4 text-green-400" />
										) : (
											<XCircle className="w-4 h-4 text-red-400" />
										)}
										<span className="text-sm font-semibold text-zinc-200">
											{invResult.success ? "Success" : "Failed"}
										</span>
									</div>
									{invResult.message && (
										<p className="text-xs text-zinc-400">{invResult.message}</p>
									)}
									{invResult.trace_id && (
										<StatRow label="Trace ID" value={invResult.trace_id} />
									)}
								</div>
							)}
						</CardSection>
					</Card>
				</div>
			)}
		</motion.div>
	);
}
