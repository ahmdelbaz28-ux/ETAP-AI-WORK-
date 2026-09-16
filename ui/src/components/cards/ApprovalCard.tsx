import { AlertTriangle, Clock, QrCode, ShieldAlert, ShieldCheck, ShieldX, X } from "lucide-react";
import { useEffect, useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import { type PendingApproval, useChatStore } from "../../store/chatStore";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card, CardHeader, CardSection } from "../ui/Card";

export interface ApprovalCardProps {
  readonly approval: PendingApproval;
}

/**
 * Approval card for one PENDING action from the Approval Gateway
 * (`GET /api/v1/approvals/pending`).
 * Includes Dual-Control Maker-Checker protection, live countdown, and QR code verification.
 */
export function ApprovalCard({ approval }: ApprovalCardProps) {
  const resolveApproval = useChatStore((s) => s.resolveApproval);
  const busy = approval.resolving !== undefined;

  const isCritical = approval.risk_class === "critical";
  const [showQrModal, setShowQrModal] = useState(false);

  const getInitialSeconds = () => {
    if (!approval.expires_at) return 300;
    const expiry = new Date(approval.expires_at).getTime();
    const diff = Math.floor((expiry - Date.now()) / 1000);
    return Math.max(0, isNaN(diff) ? 300 : diff);
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
    if (decision === "approve" && isCritical) {
      // Maker-checker policy check: if role is user or maker
      const requesterRole = approval.requested_by_role?.toLowerCase() || "";
      if (requesterRole === "maker" || requesterRole === "engineer" || requesterRole === "user") {
        setMakerCheckerError(
          "MAKER_CHECKER_VIOLATION: Requester cannot self-approve critical modifications. A second certified engineer must authorize.",
        );
        return;
      }
    }
    setMakerCheckerError(null);
    void resolveApproval(approval.id, decision);
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
            {isCritical && (
              <Badge variant="danger" size="sm" data-testid="dual-control-badge">
                <span className="flex items-center gap-1 font-mono text-[10px]">
                  <Clock className="w-3 h-3 text-rose-300 animate-pulse" />
                  pending 2nd approver {formatTimer(secondsRemaining)}
                </span>
              </Badge>
            )}
            <Badge variant={isCritical ? "danger" : "warning"}>{approval.risk_class}</Badge>
          </div>
        }
      />
      <CardSection>
        {/* Dual control warning banner */}
        {isCritical && (
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

      {/* QR Code Modal for Dual-Control */}
      {showQrModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm"
          data-testid="qr-modal"
        >
          <div className="bg-[#181E26] border border-[#334155] rounded-xl p-5 max-w-xs w-full shadow-2xl text-center space-y-4">
            <div className="flex items-center justify-between border-b border-[#2E3846] pb-2">
              <span className="text-xs font-semibold text-slate-100 flex items-center gap-1.5">
                <QrCode className="w-4 h-4 text-brand-400" />
                2nd Approver Dual-Control
              </span>
              <button
                type="button"
                onClick={() => setShowQrModal(false)}
                className="text-slate-400 hover:text-white"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="p-3 bg-white rounded-lg inline-block mx-auto shadow-inner">
              <QRCodeSVG value={qrUri} size={160} level="M" />
            </div>
            <div className="text-[11px] text-slate-300 space-y-1">
              <div className="font-mono text-emerald-400 font-semibold">
                Time remaining: {formatTimer(secondsRemaining)}
              </div>
              <p className="text-slate-400 text-[10px]">
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