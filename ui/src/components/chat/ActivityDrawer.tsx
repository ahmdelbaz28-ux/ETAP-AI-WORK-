/**
 * ActivityDrawer — session activity / progress via SessionStream events.
 *
 * Only reads events already persisted by chatStore (job_progress, approvals,
 * decisions, results). It never alters the SessionStream protocol or payloads.
 */
import {
  Activity,
  Ban,
  CheckCircle2,
  CircleDot,
  Loader2,
  RefreshCw,
  XCircle,
} from "lucide-react";
import type { ComponentType, SVGProps } from "react";
import { useChatStore, type WsConnectionStatus } from "../../store/chatStore";
import { Badge } from "../ui/Badge";
import { Card, CardHeader, CardSection } from "../ui/Card";
import { Progress } from "../ui/Progress";

const WS_META: Record<
  WsConnectionStatus,
  { label: string; variant: "success" | "warning" | "danger" | "info" | "neutral"; icon: ComponentType<SVGProps<SVGSVGElement>> }
> = {
  connecting: { label: "Connecting", variant: "info", icon: CircleDot },
  connected: { label: "Connected", variant: "success", icon: CheckCircle2 },
  reconnecting: { label: "Reconnecting", variant: "warning", icon: RefreshCw },
  disconnected: { label: "Disconnected", variant: "neutral", icon: XCircle },
  completed: { label: "Completed", variant: "success", icon: CheckCircle2 },
  failed: { label: "Failed", variant: "danger", icon: Ban },
};

export function ActivityDrawer() {
  const wsStatus = useChatStore((s) => s.wsStatus);
  const wsError = useChatStore((s) => s.wsError);
  const activity = useChatStore((s) => s.activity);
  const approvals = useChatStore((s) => s.approvals);
  const decisions = useChatStore((s) => s.decisions);
  const results = useChatStore((s) => s.results);

  const meta = WS_META[wsStatus] ?? WS_META.disconnected;
  const Icon = wsStatus === "connecting" || wsStatus === "reconnecting" ? Loader2 : meta.icon;

  return (
    <div className="flex flex-col gap-3" data-testid="activity-drawer">
      <div className="flex items-center gap-2 px-1">
        <Icon
          className={
            wsStatus === "connecting" || wsStatus === "reconnecting"
              ? "w-4 h-4 animate-spin text-[var(--text-secondary)]"
              : "w-4 h-4 text-[var(--text-secondary)]"
          }
          aria-hidden
        />
        <span className="text-sm font-medium text-[var(--text-secondary)]">Session stream</span>
        <Badge variant={meta.variant} dot className="ml-auto">
          {meta.label}
        </Badge>
      </div>
      {wsError && <p className="text-xs text-amber-400 px-1">{wsError}</p>}

      <Card>
        <CardHeader title="Progress" icon={<Activity className="w-4 h-4" />} />
        <CardSection>
          {activity.length === 0 ? (
            <p className="text-xs text-[var(--text-tertiary)]">No active jobs yet.</p>
          ) : (
            <div className="flex flex-col gap-3">
              {activity.map((p) => (
                <div key={p.execution_id ?? `${p.phase}-${p.ts ?? ""}`}>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-medium text-[var(--text-secondary)]">{p.phase}</span>
                    {p.tool && <span className="text-[10px] text-[var(--text-muted)]">{p.tool}</span>}
                  </div>
                  <Progress
                    value={p.pct}
                    variant={p.phase === "failed" ? "danger" : p.phase === "completed" ? "success" : "default"}
                    size="sm"
                    showValue
                  />
                </div>
              ))}
            </div>
          )}
        </CardSection>
      </Card>

      <Card>
        <CardHeader title="Approvals" />
        <CardSection>
          {approvals.length === 0 ? (
            <p className="text-xs text-[var(--text-tertiary)]">No pending approvals.</p>
          ) : (
            <ul className="flex flex-col gap-1.5">
              {approvals.map((a) => (
                <li key={a.id} className="flex items-center gap-2 text-xs">
                  <Badge variant={a.risk_class === "critical" ? "danger" : "warning"} dot>
                    {a.risk_class}
                  </Badge>
                  <span className="text-[var(--text-secondary)] truncate">{a.tool}</span>
                </li>
              ))}
            </ul>
          )}
        </CardSection>
      </Card>

      <Card>
        <CardHeader title="Decisions" />
        <CardSection>
          {decisions.length === 0 ? (
            <p className="text-xs text-[var(--text-tertiary)]">No decision requests yet.</p>
          ) : (
            <ul className="flex flex-col gap-1.5">
              {decisions.map((d) => (
                <li key={d.seq} className="text-xs text-[var(--text-secondary)] truncate">
                  <span className="text-[var(--text-muted)]">#{d.seq}</span>{" "}
                  {typeof d.payload.request === "string" ? d.payload.request : "Decision requested"}
                </li>
              ))}
            </ul>
          )}
        </CardSection>
      </Card>

      <Card>
        <CardHeader title="Results" />
        <CardSection>
          {results.length === 0 ? (
            <p className="text-xs text-[var(--text-tertiary)]">No results yet.</p>
          ) : (
            <ul className="flex flex-col gap-1.5">
              {results.map((r) => (
                <li key={r.resultId} className="text-xs text-[var(--text-secondary)] truncate">
                  {r.tool ? `${r.tool} · ` : ""}
                  <span className="font-mono">{r.resultId.slice(0, 12)}…</span>
                </li>
              ))}
            </ul>
          )}
        </CardSection>
      </Card>
    </div>
  );
}