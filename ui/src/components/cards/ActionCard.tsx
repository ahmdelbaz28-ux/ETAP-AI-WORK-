import { Wrench } from "lucide-react";
import type { ProposedActionEntry } from "../../store/chatStore";
import { Badge } from "../ui/Badge";
import { Card, CardHeader, CardSection } from "../ui/Card";

export interface ActionCardProps {
  readonly action: ProposedActionEntry;
}

/**
 * Display-only card for an `action_proposed` SessionStream event.
 * The client NEVER executes an action itself — approval flows through the
 * backend Approval Gateway (ApprovalCard / resolve endpoints).
 */
export function ActionCard({ action }: ActionCardProps) {
  const tool = typeof action.payload.tool === "string" ? action.payload.tool : "unknown";
  const requestedTool = typeof action.payload.requested_tool === "string" ? action.payload.requested_tool : undefined;
  const planId = typeof action.payload.plan_id === "string" ? action.payload.plan_id : undefined;

  return (
    <Card padding="sm" data-testid={`action-card-${action.seq}`}>
      <CardHeader
        title={`Action proposed · ${tool}`}
        subtitle={requestedTool && requestedTool !== tool ? `requested as ${requestedTool}` : undefined}
        icon={<Wrench className="w-4 h-4" />}
        action={<Badge variant="warning">proposed</Badge>}
      />
      <CardSection>
        <p className="text-xs text-[var(--text-secondary)]">
          {planId ? (
            <>
              Plan <span className="font-mono">{planId}</span>
            </>
          ) : (
            "Awaiting the backend approval gateway decision."
          )}
        </p>
      </CardSection>
    </Card>
  );
}