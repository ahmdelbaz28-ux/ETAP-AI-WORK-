import { GitPullRequest } from "lucide-react";
import type { DecisionEntry } from "../../store/chatStore";
import { Badge } from "../ui/Badge";
import { Card, CardHeader, CardSection } from "../ui/Card";

export interface DecisionCardProps {
  readonly decision: DecisionEntry;
}

/**
 * Display-only card for a `decision_request` SessionStream event.
 *
 * The backend wire payload for `decision_request` is not produced by any
 * emitter at the P5 baseline (verified: only constants/documentation mention
 * the event type), so this card renders whatever the backend actually sent
 * without inventing fields or executing any action.
 */
export function DecisionCard({ decision }: DecisionCardProps) {
  const requestText = typeof decision.payload.request === "string" ? decision.payload.request : undefined;
  const requestedTool = typeof decision.payload.tool === "string" ? decision.payload.tool : undefined;

  return (
    <Card padding="sm" data-testid={`decision-card-${decision.seq}`}>
      <CardHeader
        title={`Decision requested${requestedTool ? ` · ${requestedTool}` : ""}`}
        icon={<GitPullRequest className="w-4 h-4" />}
        action={<Badge variant="info">pending</Badge>}
      />
      <CardSection>
        <p className="text-xs text-[var(--text-secondary)]">
          {requestText ?? "A decision was requested by the backend session."}
        </p>
      </CardSection>
    </Card>
  );
}