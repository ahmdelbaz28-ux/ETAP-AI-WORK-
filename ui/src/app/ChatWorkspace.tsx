import { ArrowLeft, Bot } from "lucide-react";
import { useEffect } from "react";
import { ActivityDrawer } from "../components/chat/ActivityDrawer";
import { AutoApproveToggle } from "../components/chat/AutoApproveToggle";
import { EmergencyStopButton } from "../components/chat/EmergencyStopButton";
import { MessageInput } from "../components/chat/MessageInput";
import { MessageList } from "../components/chat/MessageList";
import { ActionCard } from "../components/cards/ActionCard";
import { ApprovalCard } from "../components/cards/ApprovalCard";
import { DecisionCard } from "../components/cards/DecisionCard";
import { ResultCard } from "../components/cards/ResultCard";
import { ResultViewer } from "../components/viewer/ResultViewer";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { useChatStore } from "../store/chatStore";

export interface ChatWorkspaceProps {
  readonly onExitToLegacy?: () => void;
}

function SessionFeed() {
  const proposedActions = useChatStore((s) => s.proposedActions);
  const approvals = useChatStore((s) => s.approvals);
  const decisions = useChatStore((s) => s.decisions);
  const results = useChatStore((s) => s.results);
  const approvalResults = useChatStore((s) => s.approvalResults);

  const isEmpty =
    proposedActions.length +
      approvals.length +
      decisions.length +
      results.length +
      approvalResults.length ===
    0;

  if (isEmpty) {
    return (
      <p className="text-xs text-[var(--text-tertiary)] px-1" data-testid="session-feed-empty">
        Session feed is empty. Ask the assistant to get started.
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-3" data-testid="session-feed">
      {proposedActions.map((action) => (
        <ActionCard key={action.seq} action={action} />
      ))}
      {approvals.map((approval) => (
        <ApprovalCard key={approval.id} approval={approval} />
      ))}
      {decisions.map((decision) => (
        <DecisionCard key={decision.seq} decision={decision} />
      ))}
      {results.map((result) => (
        <ResultCard key={result.resultId} result={result} />
      ))}
      {approvalResults.map((entry) => (
        <div
          key={entry.seq}
          className="text-xs px-1 flex items-center gap-2"
          data-testid={`approval-result-${entry.seq}`}
        >
          <span className="text-[var(--text-secondary)]">{entry.tool ?? "action"}</span>
          <Badge
            variant={
              entry.decision === "approved" || entry.decision === "auto_approved" ? "success" : "danger"
            }
          >
            {entry.decision}
          </Badge>
          {entry.reason && <span className="text-[var(--text-tertiary)] truncate">{entry.reason}</span>}
        </div>
      ))}
    </div>
  );
}

/**
 * ChatWorkspace — P6 chat-first UI.
 *
 * Rendered only when the `chat_first_ui` feature flag is ON (see
 * `lib/chat-first-ui.ts`). Streams the chat via the existing SSE contract,
 * mirrors session events via SessionStream, and reflects backend gateways
 * (Approvals / auto-approve / kill-switch / ResultStore) without acting on
 * the user's behalf.
 */
export function ChatWorkspace({ onExitToLegacy }: ChatWorkspaceProps) {
  const connectSession = useChatStore((s) => s.connectSession);
  const disconnectSession = useChatStore((s) => s.disconnectSession);
  const selectResult = useChatStore((s) => s.selectResult);
  const streamStatus = useChatStore((s) => s.streamStatus);
  const selectedResultId = useChatStore((s) => s.selectedResultId);
  const results = useChatStore((s) => s.results);

  const selectedResult = selectedResultId ? results.find((r) => r.resultId === selectedResultId) ?? null : null;

  useEffect(() => {
    connectSession();
    return () => disconnectSession();
  }, [connectSession, disconnectSession]);

  return (
    <div className="h-screen flex flex-col bg-[var(--bg-primary)]" data-testid="chat-workspace">
      <header className="flex items-center gap-3 px-4 h-14 border-b border-[var(--border-primary)] shrink-0">
        <div className="flex items-center gap-2">
          <span className="w-7 h-7 rounded-lg bg-brand-600 text-white flex items-center justify-center">
            <Bot className="w-4 h-4" />
          </span>
          <div>
            <h1 className="text-sm font-semibold text-[var(--text-primary)]">Chat Workspace</h1>
            <p className="text-[10px] text-[var(--text-tertiary)]">chat-first UI</p>
          </div>
        </div>
        <div className="ml-auto flex items-center gap-4">
          <AutoApproveToggle />
          <EmergencyStopButton />
          {onExitToLegacy && (
            <Button
              variant="ghost"
              size="sm"
              icon={ArrowLeft}
              onClick={onExitToLegacy}
              data-testid="exit-to-legacy"
            >
              Legacy UI
            </Button>
          )}
        </div>
      </header>

      <div className="flex flex-1 min-h-0">
        <section className="flex flex-col flex-1 min-w-0">
          <MessageList className="flex-1" />
          <div className="px-4 pb-1 text-[10px] text-[var(--text-tertiary)]">
            Stream: <span data-testid="stream-status-label">{streamStatus}</span>
          </div>
          <MessageInput />
        </section>
        <aside className="w-72 border-l border-[var(--border-primary)] overflow-y-auto p-3 space-y-3 shrink-0">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
            Session activity
          </h2>
          <SessionFeed />
        </aside>
        <aside className="w-80 border-l border-[var(--border-primary)] overflow-y-auto p-3 shrink-0">
          <ActivityDrawer />
        </aside>
      </div>

      <ResultViewer result={selectedResult} onClose={() => selectResult(null)} />
    </div>
  );
}