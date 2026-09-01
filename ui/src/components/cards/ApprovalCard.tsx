import { ShieldCheck, ShieldX } from "lucide-react";
import { useChatStore, type PendingApproval } from "../../store/chatStore";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card, CardHeader, CardSection } from "../ui/Card";

export interface ApprovalCardProps {
  readonly approval: PendingApproval;
}

/**
 * Approval card for one PENDING action from the Approval Gateway
 * (`GET /api/v1/approvals/pending`). Approve/Reject always go through
 * `POST /api/v1/approvals/{id}/resolve` — no client-side bypass exists.
 */
export function ApprovalCard({ approval }: ApprovalCardProps) {
  const resolveApproval = useChatStore((s) => s.resolveApproval);
  const busy = approval.resolving !== undefined;

  const decide = (decision: "approve" | "reject") => {
    void resolveApproval(approval.id, decision);
  };

  return (
    <Card padding="sm" data-testid={`approval-card-${approval.id}`}>
      <CardHeader
        title={approval.tool}
        subtitle={`Requested by ${approval.requested_by_role ?? "user"}`}
        action={<Badge variant={approval.risk_class === "critical" ? "danger" : "warning"}>{approval.risk_class}</Badge>}
      />
      <CardSection>
        {approval.error && <p className="text-xs text-red-400 mb-2">{approval.error}</p>}
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
    </Card>
  );
}