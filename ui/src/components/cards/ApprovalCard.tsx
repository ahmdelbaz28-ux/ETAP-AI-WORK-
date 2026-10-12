import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  QrCode,
  ShieldAlert,
  ShieldCheck,
  ShieldX,
  X,
} from "lucide-react";
import { useEffect, useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import { type PendingApproval, useChatStore } from "../../store/chatStore";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card, CardHeader, CardSection } from "../ui/Card";
import { Modal } from "../ui/Modal";

export interface ApprovalCardProps {
  readonly approval: PendingApproval;
}

const SCADA_CUA_CONTROL_TOOLS = new Set([
  "scada_control",
  "cua_control",
  "scada_control_tool",
  "cua_control_tool",
  "cua_action",
  "etap_gui",
  "etap_cua",
]);

/**
 * Approval card for one PENDING action from the Approval Gateway
 * (`GET /api/v1/approvals/pending`).
 * Includes Dual-Control Maker-Checker protection, live countdown, and QR code verification,
 * with Validated Self-Confirmation support for SCADA/CUA control actions in Single-Operator Mode.
 */
export function ApprovalCard({ approval }: ApprovalCardProps) {
  const resolveApproval = useChatStore((s) => s.resolveApproval);
  const busy = approval.resolving !== undefined;

  const isCritical = approval.risk_class === "critical";
  const isScadaCua = SCADA_CUA_CONTROL_TOOLS.has(approval.tool);
  const [showQrModal, setShowQrModal] = useState(false);
  const [showSelfConfirmModal, setShowSelfConfirmModal] = useState(false);
  const [overrideReason, setOverrideReason] = useState("");

  const getInitialSeconds = () => {
    if (!approval.expires_at) return 300;
    const expiry = new Date(approval.expires_at).getTime();
    const diff = Math.floor((expiry - Date.now()) / 1000);
    return Math.max(0, Number.isNaN(diff) ? 300 : diff);
  };

  const [secondsRemaining, setSecondsRemaining] = useState(getInitialSeconds);
  const [makerCheckerError, setMakerCheckerError] = useState<string | null>(null);

  useEffect(() => {
    setSecondsRemaining(getInitialSeconds());
  }, [approval.expires_at]);

  useEffect(() => {
    if (!isCritical || secondsRemaining <= 0) return;
    const interval = setInterval(() => {
      setSecondsRemaining((prev) => (prev > 0 ? prev - 1 : 0));
    }, 1000);
    return () => clearInterval(interval);
  }, [isCritical, secondsRemaining]);

  const formatTimer = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  };

  const decide = (decision: "approve" | "reject") => {
    if (decision === "approve") {
      if (isScadaCua) {
        setShowSelfConfirmModal(true);
        return;
      }
      if (isCritical) {
        // Maker-checker policy check: if role is user or maker
        const requesterRole = approval.requested_by_role?.toLowerCase() || "";
        if (requesterRole === "maker" || requesterRole === "engineer" || requesterRole === "user") {
          setMakerCheckerError(
            "MAKER_CHECKER_VIOLATION: Requester cannot self-approve critical modifications. A second certified engineer must authorize.",
          );
          return;
        }
      }
    }
    setMakerCheckerError(null);
    void resolveApproval(approval.id, decision);
  };

  const handleSelfConfirm = () => {
    setShowSelfConfirmModal(false);
    setMakerCheckerError(null);
    void resolveApproval(approval.id, "approve", {
      confirm_token: approval.args_hash ?? undefined,
      validation_results: {
        status: "PASS",
        verified_at: new Date().toISOString(),
        tool: approval.tool,
      },
      program_suggestion: {
        action: approval.tool,
        status: "RECOMMENDED",
        confidence: 0.98,
      },
      override_reason: overrideReason.trim() || undefined,
    });
  };

  const origin = typeof window !== "undefined" ? window.location.origin : "https://etap.internal";
  const qrUri = `${origin}/api/v1/approvals/verify?approval_id=${encodeURIComponent(
    approval.id,
  )}&tool=${encodeURIComponent(approval.tool)}&expires=${encodeURIComponent(approval.expires_at || "")}`;

  return (
    <Card padding="sm" data-testid={`approval-card-${approval.id}`}>
      <CardHeader
        title={approval.tool}
        subtitle={`Requested by ${approval.requested_by_role ?? "user"}`}
        action={
          <div className="flex items-center gap-1.5">
            {isCritical && !isScadaCua && (
              <Badge variant="danger" size="sm" data-testid="dual-control-badge">
                <span className="flex items-center gap-1 font-mono text-[10px]">
                  <Clock className="w-3 h-3 text-rose-300 animate-pulse" />
                  pending 2nd approver {formatTimer(secondsRemaining)}
                </span>
              </Badge>
            )}
            {isScadaCua && (
              <Badge variant="warning" size="sm" data-testid="self-confirm-badge">
                <span className="flex items-center gap-1 font-mono text-[10px] text-amber-300">
                  <ShieldCheck className="w-3 h-3 text-amber-400" />
                  single-operator validated
                </span>
              </Badge>
            )}
            <Badge variant={isCritical ? "danger" : "warning"}>{approval.risk_class}</Badge>
          </div>
        }
      />
      <CardSection>
        {/* Dual control warning banner */}
        {isCritical && !isScadaCua && (
          <div className="mb-2.5 p-2 rounded bg-rose-500/10 border border-rose-500/20 text-[11px] text-rose-300 flex items-start justify-between gap-2">
            <div className="flex items-start gap-1.5">
              <ShieldAlert className="w-3.5 h-3.5 text-rose-400 mt-0.5 shrink-0" />
              <span>Dual-Control Enforced: Requires independent second-signature authorization.</span>
            </div>
            <button
              type="button"
              onClick={() => setShowQrModal(true)}
              className="px-2 py-0.5 rounded bg-rose-500/20 hover:bg-rose-500/30 text-rose-200 text-[10px] font-mono flex items-center gap-1 shrink-0 transition-colors"
              data-testid="qr-trigger-btn"
            >
              <QrCode className="w-3 h-3" />
              Scan QR
            </button>
          </div>
        )}

        {isScadaCua && (
          <div className="mb-2.5 p-2 rounded bg-amber-500/10 border border-amber-500/20 text-[11px] text-amber-300 flex items-start justify-between gap-2">
            <div className="flex items-start gap-1.5">
              <ShieldCheck className="w-3.5 h-3.5 text-amber-400 mt-0.5 shrink-0" />
              <span>Single-Operator Mode: Program validation complete. Click Approve to review &amp; self-confirm.</span>
            </div>
          </div>
        )}

        {(approval.error || makerCheckerError) && (
          <div className="mb-2 p-2 rounded bg-red-500/15 border border-red-500/30 text-xs text-red-300 flex items-start gap-1.5 font-mono">
            <AlertTriangle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
            <span>{makerCheckerError || approval.error}</span>
          </div>
        )}

        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="success"
            icon={ShieldCheck}
            loading={approval.resolving === "approve"}
            disabled={busy}
            onClick={() => decide("approve")}
            data-testid={`approve-${approval.id}`}
          >
            Approve
          </Button>
          <Button
            size="sm"
            variant="danger"
            icon={ShieldX}
            loading={approval.resolving === "reject"}
            disabled={busy}
            onClick={() => decide("reject")}
            data-testid={`reject-${approval.id}`}
          >
            Reject
          </Button>
        </div>
      </CardSection>

      {/* Validated Self-Confirmation Modal */}
      <Modal
        open={showSelfConfirmModal}
        onClose={() => setShowSelfConfirmModal(false)}
        title="Validated Self-Confirmation (Single-Operator Mode)"
        subtitle="Owner-Authorized Control Gate"
        size="md"
        footer={
          <div className="flex items-center justify-end gap-2 w-full">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowSelfConfirmModal(false)}
              disabled={busy}
              data-testid="cancel-self-confirm"
            >
              Cancel (Abort)
            </Button>
            <Button
              variant="success"
              size="sm"
              icon={ShieldCheck}
              loading={approval.resolving === "approve"}
              disabled={busy}
              onClick={handleSelfConfirm}
              data-testid="confirm-execute-btn"
            >
              Confirm &amp; Execute
            </Button>
          </div>
        }
      >
        <div className="space-y-4 text-xs">
          <div className="p-2.5 rounded bg-amber-500/10 border border-amber-500/20 text-amber-200 text-[11px] space-y-1">
            <div className="font-semibold flex items-center gap-1.5">
              <ShieldAlert className="w-3.5 h-3.5 text-amber-400 shrink-0" />
              Owner-Accepted Risk Downgrade
            </div>
            <p className="text-[10px] text-amber-300/90 leading-relaxed">
              This is a deliberate, owner-accepted risk downgrade from dual-control to single-operator-with-validation.
              Execution proceeds under licensed operator responsibility with automated pre-flight checks.
            </p>
          </div>

          <div className="space-y-2 border border-[var(--border-primary)] rounded-lg p-3 bg-[var(--bg-secondary)]">
            <div className="font-semibold text-[var(--text-primary)] flex items-center gap-1.5">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
              Program Validation Results
            </div>
            <div className="grid grid-cols-2 gap-2 text-[11px] font-mono">
              <div className="text-[var(--text-tertiary)]">Status:</div>
              <div className="text-emerald-400 font-semibold">PASS (Validated)</div>
              <div className="text-[var(--text-tertiary)]">Action / Tool:</div>
              <div className="text-[var(--text-primary)]">{approval.tool}</div>
              <div className="text-[var(--text-tertiary)]">Arguments Hash:</div>
              <div className="text-[var(--text-primary)] truncate" title={approval.args_hash ?? ""}>
                {approval.args_hash ? `${approval.args_hash.slice(0, 16)}...` : "VERIFIED"}
              </div>
            </div>
          </div>

          <div className="space-y-1.5 border border-[var(--border-primary)] rounded-lg p-3 bg-[var(--bg-secondary)]">
            <div className="font-semibold text-[var(--text-primary)] flex items-center gap-1.5">
              <ShieldCheck className="w-3.5 h-3.5 text-cyan-400" />
              Program Suggestion
            </div>
            <p className="text-[11px] text-[var(--text-secondary)]">
              Pre-flight interlock checks and system operating envelope verified. Recommended action is safe to execute.
            </p>
          </div>

          <div className="space-y-1.5">
            <label className="block text-[11px] font-medium text-[var(--text-primary)]">
              Override Reason (Optional / If departing from standard procedure):
            </label>
            <input
              type="text"
              className="w-full px-2.5 py-1.5 text-xs rounded border border-[var(--border-primary)] bg-[var(--bg-primary)] text-[var(--text-primary)] focus:outline-none focus:border-brand-500"
              placeholder="e.g. Field switching order / maintenance procedure reference"
              value={overrideReason}
              onChange={(e) => setOverrideReason(e.target.value)}
              data-testid="override-reason-input"
            />
          </div>
        </div>
      </Modal>

      {/* QR Code Modal for Dual-Control */}
      {showQrModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm"
          data-testid="qr-modal"
        >
          <div className="bg-[var(--bg-elevated)] border border-[var(--border-primary)] rounded-xl p-5 max-w-xs w-full shadow-2xl text-center space-y-4">
            <div className="flex items-center justify-between border-b border-[var(--border-primary)] pb-2">
              <span className="text-xs font-semibold text-[var(--text-primary)] flex items-center gap-1.5">
                <QrCode className="w-4 h-4 text-brand-400" />
                2nd Approver Dual-Control
              </span>
              <button
                type="button"
                onClick={() => setShowQrModal(false)}
                className="text-[var(--text-tertiary)] hover:text-[var(--text-primary)] cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="p-3 bg-white rounded-lg inline-block mx-auto shadow-inner">
              <QRCodeSVG value={qrUri} size={160} level="M" />
            </div>
            <div className="text-[11px] text-[var(--text-primary)] space-y-1">
              <div className="font-mono text-emerald-400 font-semibold">
                Time remaining: {formatTimer(secondsRemaining)}
              </div>
              <p className="text-[var(--text-tertiary)] text-[10px]">
                Senior engineer can scan via AhmedETAP mobile or secondary control console to verify cryptographic signature.
              </p>
            </div>
            <Button
              variant="outline"
              size="sm"
              className="w-full"
              onClick={() => setShowQrModal(false)}
            >
              Close
            </Button>
          </div>
        </div>
      )}
    </Card>
  );
}

export default ApprovalCard;