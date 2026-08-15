// DualControl.tsx — Life-safety 4-eyes approval workflow UI
//
// Implements the operator/approver flow for dual-control requests on
// life-safety operations (breaker switching, protection setting changes,
// SCADA commands, etc.). All 5 backend endpoints require admin/engineer
// role and derive identity from JWT — see api.ts for the full contract.
//
// Coverage:
//   - List pending approval requests (auto-refresh every 5s)
//   - Create a new approval request (modal form)
//   - Approve a pending request (with optional QR 2FA secret)
//   - Reject a pending request (with mandatory reason)
//   - Show QR secret for mobile-approval fallback
//   - Visual countdown of the 5-minute auto-reject timer
//   - Status badges (pending / approved / rejected / expired)
//
// Backend endpoints (all in hf-space/app.py, all auth'd via Task 5):
//   POST /api/v1/dual-control/request
//   POST /api/v1/dual-control/approve/{request_id}
//   POST /api/v1/dual-control/reject/{request_id}
//   GET  /api/v1/dual-control/pending
//   GET  /api/v1/dual-control/qr/{request_id}

import { motion } from "framer-motion";
import {
  AlertCircle,
  Check,
  Clock,
  Eye,
  EyeOff,
  Loader2,
  Plus,
  QrCode,
  RefreshCw,
  ShieldCheck,
  Timer,
  X,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ModalBackdrop from "../components/ModalBackdrop";
import ModalHeader from "../components/ModalHeader";
import { ContextHelpButton } from "../components/help/ContextHelpButton";
import { Badge, Button, Card, CardSection, EmptyState } from "../components/ui";
import { useNotify } from "../context/NotificationContext";
import { useAuth } from "../hooks/useAuth";
import {
  type DualControlAction,
  type DualControlRequest,
  approveDualControlRequest,
  createDualControlRequest,
  getDualControlQrSecret,
  listPendingDualControlRequests,
  rejectDualControlRequest,
} from "../lib/api";

// Auto-refresh interval for the pending list (5s — matches CuaMonitor pattern).
const REFRESH_INTERVAL_MS = 5000;

// Auto-reject timeout enforced server-side (must match AUTO_REJECT_SECONDS
// in api/dual_control.py:38). Used purely for the visual countdown.
const AUTO_REJECT_SECONDS = 300;

interface NewRequestFormState {
  actionType: string;
  target: string;
  description: string;
}

const EMPTY_FORM: NewRequestFormState = {
  actionType: "",
  target: "",
  description: "",
};

// Common life-safety action types — populated as <select> options to
// encourage consistent naming and prevent free-form typos that would
// make audit trails hard to search.
const ACTION_TYPES: ReadonlyArray<{ value: string; label: string }> = [
  { value: "breaker_switch", label: "Breaker Switch" },
  { value: "protection_setting", label: "Protection Setting Change" },
  { value: "scada_command", label: "SCADA Command" },
  { value: "earth_grid_test", label: "Earth Grid Test" },
  { value: "arc_flash_clear", label: "Arc Flash Clear" },
  { value: "isolation_repair", label: "Isolation for Repair" },
  { value: "other", label: "Other (specify in description)" },
];

function statusBadgeVariant(
  status: DualControlRequest["status"],
): "default" | "success" | "warning" | "danger" | "info" {
  switch (status) {
    case "approved":
      return "success";
    case "pending":
      return "warning";
    case "rejected":
      return "danger";
    case "expired":
      return "default";
    default:
      return "info";
  }
}

function formatTimeRemaining(expiresAt: number, now: number): string {
  const remaining = Math.max(0, expiresAt - now / 1000);
  const minutes = Math.floor(remaining / 60);
  const seconds = Math.floor(remaining % 60);
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

function isExpired(req: DualControlRequest, now: number = Date.now()): boolean {
  return req.status === "expired" || (req.status === "pending" && req.expires_at != null && now / 1000 > Number(req.expires_at));
}

export default function DualControl() {
  const { user } = useAuth();
  const { notify } = useNotify();

  const [pending, setPending] = useState<DualControlRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [form, setForm] = useState<NewRequestFormState>(EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [actionInProgress, setActionInProgress] = useState<string | null>(null);
  const [qrForRequestId, setQrForRequestId] = useState<string | null>(null);
  const [qrSecret, setQrSecret] = useState<string | null>(null);
  const [qrLoading, setQrLoading] = useState(false);
  const [showQrSecret, setShowQrSecret] = useState(false);
  const [rejectingRequestId, setRejectingRequestId] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState("");
  const [approveSecretInput, setApproveSecretInput] = useState<Record<string, string>>({});
  // Tick `now` every second so the countdown timer updates smoothly.
  // Without this, the timer only updates every 5s (on auto-refresh), making
  // it appear to jump in 5-second increments instead of counting down 1-by-1.
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  // Ref mirror of qrForRequestId so async QR-fetch handlers can detect if
  // the user closed the modal while the fetch was in-flight (prevents stale
  // state from leaking into the next modal open).
  const qrForRequestIdRef = useRef<string | null>(null);
  useEffect(() => {
    qrForRequestIdRef.current = qrForRequestId;
  }, [qrForRequestId]);

  const fetchPending = useCallback(async () => {
    try {
      const data = await listPendingDualControlRequests();
      const requests = data.data ?? [];
      // Mark expired ones locally (server may not have swept them yet).
      const normalized = requests.map((r: DualControlRequest) =>
        isExpired(r) ? { ...r, status: "expired" as const } : r,
      );
      setPending(normalized);
      setError(null);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      setError(msg);
      setPending([]);
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial fetch + auto-refresh.
  // Pause auto-refresh when ANY modal is open — prevents the request the
  // user is acting on from disappearing mid-action (e.g., another admin
  // approves it in the 5s window, the list refreshes, the request vanishes,
  // and the user's approve/reject call returns 404 on a now-stale request_id).
  const anyModalOpen = showCreateModal || qrForRequestId !== null || rejectingRequestId !== null;
  useEffect(() => {
    if (anyModalOpen) return; // don't start the interval while a modal is open
    fetchPending();
    const id = setInterval(fetchPending, REFRESH_INTERVAL_MS);
    return () => clearInterval(id);
  }, [fetchPending, anyModalOpen]);

  const handleCreate = useCallback(async () => {
    if (!form.actionType.trim()) {
      notify("error", "Action type is required");
      return;
    }
    setSubmitting(true);
    try {
      const action: DualControlAction = form.actionType.trim() as DualControlAction;
      const target = form.target.trim();
      const description = form.description.trim();
      const result = await createDualControlRequest(action, target, description);
      notify(
        "success",
        `Dual-control request ${result.data.request_id} created. A second engineer must approve within 5 minutes.`,
      );
      setShowCreateModal(false);
      setForm(EMPTY_FORM);
      await fetchPending();
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      notify("error", `Failed to create request: ${msg}`);
    } finally {
      setSubmitting(false);
    }
  }, [form, notify, fetchPending]);

  const handleApprove = useCallback(
    async (req: DualControlRequest) => {
      // Prevent self-approval — the same user cannot approve their own request.
      // This is a client-side guard; the server SHOULD also enforce it but
      // currently does not (noted as a follow-up in the worklog).
      //
      // NOTE: backend uses `user.user_id` (JWT claim) but frontend User type
      // exposes `id`. These map to the same value — backend sets user_id = id
      // in the JWT payload. See api/auth.py:_create_token().
      if (user && req.requested_by === user.id) {
        notify(
          "error",
          "You cannot approve your own dual-control request. Ask another admin/engineer.",
        );
        return;
      }
      const secret = approveSecretInput[req.request_id]?.trim();
      setActionInProgress(req.request_id);
      try {
        const result = await approveDualControlRequest(req.request_id, secret || undefined);
        if (result.success === false) {
          notify("error", `Approval rejected by server: ${result.error ?? "unknown"}`);
        } else {
          notify("success", `Request ${req.request_id} approved`);
        }
        await fetchPending();
      } catch (e) {
        const msg = e instanceof Error ? e.message : "Unknown error";
        notify("error", `Failed to approve: ${msg}`);
      } finally {
        setActionInProgress(null);
      }
    },
    [approveSecretInput, notify, fetchPending, user],
  );

  const handleReject = useCallback(
    async (req: DualControlRequest) => {
      if (!rejectReason.trim()) {
        notify("error", "A rejection reason is required for audit trail");
        return;
      }
      setActionInProgress(req.request_id);
      try {
        const result = await rejectDualControlRequest(req.request_id, rejectReason.trim());
        if (result.success === false) {
          notify("error", `Rejection failed: ${result.error ?? "unknown"}`);
        } else {
          notify("success", `Request ${req.request_id} rejected`);
        }
        setRejectingRequestId(null);
        setRejectReason("");
        await fetchPending();
      } catch (e) {
        const msg = e instanceof Error ? e.message : "Unknown error";
        notify("error", `Failed to reject: ${msg}`);
      } finally {
        setActionInProgress(null);
      }
    },
    [rejectReason, notify, fetchPending],
  );

  const handleShowQr = useCallback(
    async (req: DualControlRequest) => {
      setQrForRequestId(req.request_id);
      setQrSecret(null);
      setShowQrSecret(false);
      setQrLoading(true);
      try {
        const result = await getDualControlQrSecret(req.request_id);
        // Guard: if the user closed the modal while the fetch was in-flight,
        // don't update state (prevents a stale secret from leaking into the
        // next time the modal opens).
        if (qrForRequestIdRef.current !== req.request_id) return;
        setQrSecret(result.data.qr_secret);
      } catch (e) {
        if (qrForRequestIdRef.current !== req.request_id) return;
        const msg = e instanceof Error ? e.message : "Unknown error";
        notify("error", `Failed to fetch QR secret: ${msg}`);
        setQrForRequestId(null);
      } finally {
        if (qrForRequestIdRef.current === req.request_id) {
          setQrLoading(false);
        }
      }
    },
    [notify],
  );

  const pendingCount = useMemo(
    () => pending.filter((r) => r.status === "pending").length,
    [pending],
  );
  const approvedCount = useMemo(
    () => pending.filter((r) => r.status === "approved").length,
    [pending],
  );
  const rejectedCount = useMemo(
    () => pending.filter((r) => r.status === "rejected").length,
    [pending],
  );

  const formatDate = (iso: string): string => {
    try {
      return new Date(iso).toLocaleString();
    } catch {
      return iso;
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between"
      >
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-brand-500/10 border border-brand-500/20">
            <ShieldCheck className="w-5 h-5 text-brand-400" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-[var(--text-primary)]">
              Dual-Control Approvals
            </h2>
            <div className="flex items-center gap-2">
              <p className="text-sm text-[var(--text-tertiary)]">
                {pendingCount} pending · {approvedCount} approved · {rejectedCount} rejected
              </p>
              <ContextHelpButton contextId="dual-control.manage" />
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            icon={RefreshCw}
            onClick={fetchPending}
            disabled={loading}
          >
            Refresh
          </Button>
          <Button variant="primary" size="sm" icon={Plus} onClick={() => setShowCreateModal(true)}>
            New Request
          </Button>
        </div>
      </motion.div>

      {/* Life-safety warning banner */}
      <Card padding="md" variant="bordered">
        <div className="flex items-start gap-3 text-amber-300">
          <AlertCircle className="w-5 h-5 mt-0.5 flex-shrink-0" />
          <div className="text-xs">
            <p className="font-medium mb-1">Life-safety workflow</p>
            <p className="text-[var(--text-muted)]">
              Dual-control enforces the 4-eyes principle on critical operations (breaker switching,
              protection changes, SCADA commands). Each request auto-expires after 5 minutes. A
              second admin/engineer must approve — you cannot approve your own request. All actions
              are logged with operator + approver identity for audit.
            </p>
          </div>
        </div>
      </Card>

      {/* Loading state */}
      {loading && (
        <Card padding="lg">
          <div className="flex items-center justify-center py-12 text-[var(--text-muted)]">
            <Loader2 className="w-5 h-5 animate-spin mr-2" />
            Loading pending approvals...
          </div>
        </Card>
      )}

      {/* Error state */}
      {error && !loading && (
        <Card padding="lg">
          <div className="flex items-start gap-3 text-red-400">
            <AlertCircle className="w-5 h-5 mt-0.5 flex-shrink-0" />
            <div>
              <p className="text-sm font-medium">Failed to load pending approvals</p>
              <p className="text-xs text-[var(--text-muted)] mt-1 font-mono">{error}</p>
              <Button variant="ghost" size="sm" className="mt-3" onClick={fetchPending}>
                Retry
              </Button>
            </div>
          </div>
        </Card>
      )}

      {/* Empty state */}
      {!loading && !error && pending.length === 0 && (
        <Card padding="lg">
          <EmptyState
            icon={<ShieldCheck className="w-12 h-12" />}
            title="No dual-control requests"
            description="There are no pending or recently-decided approval requests. Create a new request to initiate a 4-eyes approval flow on a life-safety operation."
            action={
              <Button
                variant="primary"
                size="sm"
                icon={Plus}
                onClick={() => setShowCreateModal(true)}
              >
                New Request
              </Button>
            }
          />
        </Card>
      )}

      {/* Request list */}
      {!loading && !error && pending.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {pending.map((req, i) => {
            const expired = isExpired(req, now);
            const isOwn = user != null && req.requested_by === user.id;
            return (
              <motion.div
                key={req.request_id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.05 * i }}
              >
                <Card variant="bordered" padding="md">
                  {/* Header row: action type + status badge */}
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-3">
                      <div className="p-2 rounded-lg bg-brand-500/10">
                        <ShieldCheck className="w-5 h-5 text-brand-400" />
                      </div>
                      <div>
                        <h3 className="text-sm font-semibold text-[var(--text-primary)]">
                          {req.action.type}
                          {req.action.target ? ` → ${req.action.target}` : ""}
                        </h3>
                        <p className="text-xs text-[var(--text-muted)] font-mono">
                          {req.request_id}
                        </p>
                      </div>
                    </div>
                    <Badge variant={statusBadgeVariant(req.status)} dot size="sm">
                      {req.status}
                    </Badge>
                  </div>

                  {/* Body: description + meta */}
                  <CardSection>
                    {req.action.description && (
                      <p className="text-xs text-[var(--text-secondary)] mb-2">
                        {req.action.description}
                      </p>
                    )}
                    <div className="grid grid-cols-2 gap-2 text-xs text-[var(--text-muted)] mb-3">
                      <div>
                        <span className="text-[var(--text-tertiary)]">Operator:</span>{" "}
                        <span className="font-mono">{req.requested_by}</span>
                        {isOwn && (
                          <Badge variant="info" size="sm" className="ml-2">
                            you
                          </Badge>
                        )}
                      </div>
                      <div>
                        <span className="text-[var(--text-tertiary)]">Created:</span>{" "}
                        {formatDate(req.created_at)}
                      </div>
                      {req.approved_by && (
                        <div>
                          <span className="text-[var(--text-tertiary)]">Approver:</span>{" "}
                          <span className="font-mono">{req.approved_by}</span>
                        </div>
                      )}
                      {req.approved_at && (
                        <div>
                          <span className="text-[var(--text-tertiary)]">Approved:</span>{" "}
                          {formatDate(req.approved_at)}
                        </div>
                      )}
                      {req.rejected_by && (
                        <div>
                          <span className="text-[var(--text-tertiary)]">Rejector:</span>{" "}
                          <span className="font-mono">{req.rejected_by}</span>
                        </div>
                      )}
                      {req.rejected_reason && (
                        <div className="col-span-2">
                          <span className="text-[var(--text-tertiary)]">Reason:</span>{" "}
                          {req.rejected_reason}
                        </div>
                      )}
                    </div>

                    {/* Countdown timer for pending requests */}
                    {req.status === "pending" && !expired && (
                      <div className="flex items-center gap-2 text-xs text-amber-300 mb-3 font-mono">
                        <Timer className="w-3.5 h-3.5" />
                        <span>Auto-reject in {formatTimeRemaining(req.expires_at, now)}</span>
                      </div>
                    )}

                    {/* Action buttons */}
                    {req.status === "pending" && !expired && (
                      <div className="space-y-2">
                        {/* Optional QR secret input for mobile 2FA approval */}
                        <div className="flex items-center gap-2">
                          <input
                            type="text"
                            placeholder="QR secret (optional, for mobile 2FA)"
                            value={approveSecretInput[req.request_id] ?? ""}
                            onChange={(e) =>
                              setApproveSecretInput((m) => ({
                                ...m,
                                [req.request_id]: e.target.value,
                              }))
                            }
                            disabled={actionInProgress === req.request_id || isOwn}
                            className="flex-1 px-2 py-1 text-xs bg-[var(--bg-input)] border border-[var(--border-primary)] rounded text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:border-brand-500 focus:ring-1 focus:ring-brand-500/20 outline-none disabled:opacity-50 font-mono"
                          />
                          <button
                            type="button"
                            onClick={() => handleShowQr(req)}
                            disabled={actionInProgress === req.request_id}
                            title="Show QR secret for mobile approval"
                            className="p-1.5 rounded text-[var(--text-muted)] hover:text-brand-400 hover:bg-brand-400/10 disabled:opacity-50 transition-colors"
                          >
                            <QrCode className="w-3.5 h-3.5" />
                          </button>
                        </div>

                        <div className="flex items-center gap-2">
                          <Button
                            variant="success"
                            size="sm"
                            icon={actionInProgress === req.request_id ? Loader2 : Check}
                            onClick={() => handleApprove(req)}
                            disabled={actionInProgress === req.request_id || isOwn}
                            className={actionInProgress === req.request_id ? "animate-pulse" : ""}
                          >
                            Approve
                          </Button>
                          <Button
                            variant="danger"
                            size="sm"
                            icon={X}
                            onClick={() => {
                              setRejectingRequestId(req.request_id);
                              setRejectReason("");
                            }}
                            disabled={actionInProgress === req.request_id}
                          >
                            Reject
                          </Button>
                          {isOwn && (
                            <span className="text-xs text-[var(--text-muted)] ml-auto">
                              Cannot approve own request
                            </span>
                          )}
                        </div>
                      </div>
                    )}
                  </CardSection>
                </Card>
              </motion.div>
            );
          })}
        </div>
      )}

      {/* Create Request Modal */}
      {showCreateModal && (
        <ModalBackdrop onClose={() => setShowCreateModal(false)} disabled={submitting}>
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            onClick={(e) => e.stopPropagation()}
            className="bg-[var(--bg-elevated)] border border-[var(--border-primary)] rounded-xl w-full max-w-md p-6 shadow-2xl"
          >
            <ModalHeader
              title="New Dual-Control Request"
              onClose={() => setShowCreateModal(false)}
              disabled={submitting}
              icon={ShieldCheck}
            />
            <div className="space-y-4">
              <div>
                <label
                  htmlFor="dc-action-type"
                  className="block text-xs font-medium text-[var(--text-secondary)] mb-1.5"
                >
                  Action Type <span className="text-red-400">*</span>
                </label>
                <select
                  id="dc-action-type"
                  aria-label="Action Type"
                  value={form.actionType}
                  onChange={(e) => setForm((f) => ({ ...f, actionType: e.target.value }))}
                  disabled={submitting}
                  className="w-full px-3 py-2 bg-[var(--bg-input)] border border-[var(--border-primary)] rounded-lg text-sm text-[var(--text-primary)] focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 outline-none transition-all disabled:opacity-50"
                >
                  <option value="">Select an action type...</option>
                  {ACTION_TYPES.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label
                  htmlFor="dc-target"
                  className="block text-xs font-medium text-[var(--text-secondary)] mb-1.5"
                >
                  Target Asset / Device
                </label>
                <input
                  id="dc-target"
                  type="text"
                  aria-label="Target Asset"
                  value={form.target}
                  onChange={(e) => setForm((f) => ({ ...f, target: e.target.value }))}
                  placeholder="e.g., BRK-13800-MAIN, protection-relay-3"
                  disabled={submitting}
                  className="w-full px-3 py-2 bg-[var(--bg-input)] border border-[var(--border-primary)] rounded-lg text-sm text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 outline-none transition-all disabled:opacity-50 font-mono"
                />
              </div>
              <div>
                <label
                  htmlFor="dc-description"
                  className="block text-xs font-medium text-[var(--text-secondary)] mb-1.5"
                >
                  Description / Justification
                </label>
                <textarea
                  id="dc-description"
                  aria-label="Description"
                  value={form.description}
                  onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                  placeholder="e.g., Open main breaker for scheduled maintenance on T1 transformer — see work order WO-2026-0142"
                  rows={3}
                  disabled={submitting}
                  className="w-full px-3 py-2 bg-[var(--bg-input)] border border-[var(--border-primary)] rounded-lg text-sm text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 outline-none transition-all disabled:opacity-50 resize-none"
                />
              </div>
              <div className="flex items-start gap-2 text-xs text-amber-300 bg-amber-400/5 border border-amber-400/20 rounded-lg p-2.5">
                <Clock className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
                <span>
                  Once created, this request will auto-reject in {AUTO_REJECT_SECONDS / 60} minutes
                  unless a second admin/engineer approves it.
                </span>
              </div>
            </div>
            <div className="flex items-center justify-end gap-2 mt-6">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowCreateModal(false)}
                disabled={submitting}
              >
                Cancel
              </Button>
              <Button
                variant="primary"
                size="sm"
                icon={submitting ? Loader2 : Plus}
                onClick={handleCreate}
                disabled={submitting || !form.actionType.trim()}
                className={submitting ? "animate-pulse" : ""}
              >
                {submitting ? "Creating..." : "Create Request"}
              </Button>
            </div>
          </motion.div>
        </ModalBackdrop>
      )}

      {/* QR Secret Modal */}
      {qrForRequestId && (
        <ModalBackdrop
          onClose={() => {
            setQrForRequestId(null);
            setQrSecret(null);
            setShowQrSecret(false);
          }}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            onClick={(e) => e.stopPropagation()}
            className="bg-[var(--bg-elevated)] border border-[var(--border-primary)] rounded-xl w-full max-w-md p-6 shadow-2xl"
          >
            <ModalHeader
              title="QR Secret for Mobile Approval"
              onClose={() => {
                setQrForRequestId(null);
                setQrSecret(null);
                setShowQrSecret(false);
              }}
              icon={QrCode}
            />
            <div className="space-y-3">
              <p className="text-xs text-[var(--text-secondary)]">
                Request{" "}
                <span className="font-mono text-[var(--text-primary)]">{qrForRequestId}</span>
              </p>
              <p className="text-xs text-[var(--text-muted)]">
                Share this secret with the second engineer out-of-band (e.g., in person or via a
                secure channel). They can enter it in the approval form's "QR secret" field to
                satisfy the mobile 2FA factor.
              </p>
              {qrLoading ? (
                <div className="flex items-center justify-center py-6">
                  <Loader2 className="w-5 h-5 animate-spin text-[var(--text-muted)]" />
                </div>
              ) : qrSecret ? (
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <code className="flex-1 px-3 py-2 bg-[var(--bg-input)] border border-[var(--border-primary)] rounded-lg text-xs text-[var(--text-primary)] font-mono break-all">
                      {showQrSecret ? qrSecret : "•".repeat(Math.min(qrSecret.length, 32))}
                    </code>
                    <button
                      type="button"
                      onClick={() => setShowQrSecret((v) => !v)}
                      title={showQrSecret ? "Hide secret" : "Reveal secret"}
                      className="p-2 rounded text-[var(--text-muted)] hover:text-brand-400 hover:bg-brand-400/10 transition-colors"
                    >
                      {showQrSecret ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      navigator.clipboard.writeText(qrSecret);
                      notify("success", "QR secret copied to clipboard");
                    }}
                    className="text-xs text-brand-400 hover:text-brand-300 transition-colors"
                  >
                    Copy to clipboard
                  </button>
                </div>
              ) : (
                <p className="text-xs text-red-400">Failed to load QR secret.</p>
              )}
            </div>
          </motion.div>
        </ModalBackdrop>
      )}

      {/* Reject Reason Modal */}
      {rejectingRequestId && (
        <ModalBackdrop
          onClose={() => {
            setRejectingRequestId(null);
            setRejectReason("");
          }}
          disabled={actionInProgress === rejectingRequestId}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            onClick={(e) => e.stopPropagation()}
            className="bg-[var(--bg-elevated)] border border-[var(--border-primary)] rounded-xl w-full max-w-md p-6 shadow-2xl"
          >
            <ModalHeader
              title="Reject Dual-Control Request"
              onClose={() => {
                setRejectingRequestId(null);
                setRejectReason("");
              }}
              disabled={actionInProgress === rejectingRequestId}
              icon={X}
            />
            <div className="space-y-3">
              <p className="text-xs text-[var(--text-secondary)]">
                Request{" "}
                <span className="font-mono text-[var(--text-primary)]">{rejectingRequestId}</span>
              </p>
              <div>
                <label
                  htmlFor="dc-reject-reason"
                  className="block text-xs font-medium text-[var(--text-secondary)] mb-1.5"
                >
                  Reason <span className="text-red-400">*</span>
                </label>
                <textarea
                  id="dc-reject-reason"
                  aria-label="Rejection reason"
                  value={rejectReason}
                  onChange={(e) => setRejectReason(e.target.value)}
                  placeholder="e.g., Target asset is still energized — verify isolation procedure first"
                  rows={3}
                  disabled={actionInProgress === rejectingRequestId}
                  className="w-full px-3 py-2 bg-[var(--bg-input)] border border-[var(--border-primary)] rounded-lg text-sm text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 outline-none transition-all disabled:opacity-50 resize-none"
                />
              </div>
            </div>
            <div className="flex items-center justify-end gap-2 mt-6">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setRejectingRequestId(null);
                  setRejectReason("");
                }}
                disabled={actionInProgress === rejectingRequestId}
              >
                Cancel
              </Button>
              <Button
                variant="danger"
                size="sm"
                icon={actionInProgress === rejectingRequestId ? Loader2 : X}
                onClick={() => {
                  const req = pending.find((r) => r.request_id === rejectingRequestId);
                  if (req) handleReject(req);
                }}
                disabled={actionInProgress === rejectingRequestId || !rejectReason.trim()}
                className={actionInProgress === rejectingRequestId ? "animate-pulse" : ""}
              >
                {actionInProgress === rejectingRequestId ? "Rejecting..." : "Confirm Reject"}
              </Button>
            </div>
          </motion.div>
        </ModalBackdrop>
      )}
    </div>
  );
}
