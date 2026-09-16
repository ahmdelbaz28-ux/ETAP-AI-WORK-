import { ArrowLeft, Bot, Settings as CogIcon, Sliders } from "lucide-react";
import { useEffect, useState } from "react";
import { ActivityDrawer } from "../components/chat/ActivityDrawer";
import { AutoApproveToggle } from "../components/chat/AutoApproveToggle";
import { EmergencyStopButton } from "../components/chat/EmergencyStopButton";
import { MessageInput } from "../components/chat/MessageInput";
import { MessageList } from "../components/chat/MessageList";
import { ProjectSelector } from "../components/chat/ProjectSelector";
import { ParametersDrawer } from "../components/chat/ParametersDrawer";
import { IntegrationStatusPills } from "../components/chat/IntegrationStatusPills";
import { AISettingsModal } from "../components/chat/AISettingsModal";
import { AutoViewPanel } from "../components/chat/AutoViewPanel";
import { ActionCard } from "../components/cards/ActionCard";
import { ApprovalCard } from "../components/cards/ApprovalCard";
import { DecisionCard } from "../components/cards/DecisionCard";
import { ResultCard } from "../components/cards/ResultCard";
import { ResultViewer } from "../components/viewer/ResultViewer";
import { ErrorBoundary } from "../components/ErrorBoundary";
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
      {approvalResults.map((ar) => (
        <div
          key={`${ar.seq}-${ar.ts}`}
          className="p-2 rounded bg-[var(--bg-elevated)] border border-[var(--border-primary)] text-xs font-mono"
          data-testid="approval-result-item"
        >
          <div className="flex items-center justify-between">
            <span className="font-semibold text-[var(--text-primary)]">
              Approval {ar.decision}
            </span>
            <Badge variant={ar.decision === "approve" ? "success" : "danger"}>
              {ar.decision}
            </Badge>
          </div>
          {typeof ar.tool === "string" && (
            <p className="text-[var(--text-secondary)] mt-1">{ar.tool}</p>
          )}
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
  const projectId = useChatStore((s) => s.projectId);
  const sessionId = useChatStore((s) => s.sessionId);

  const [paramsOpen, setParamsOpen] = useState(false);
  const [aiModalOpen, setAiModalOpen] = useState(false);

  const selectedResult = selectedResultId ? results.find((r) => r.resultId === selectedResultId) ?? null : null;

  useEffect(() => {
    connectSession();
    return () => disconnectSession();
  }, [connectSession, disconnectSession]);

  return (
    <div className="h-screen flex flex-col bg-[var(--bg-primary)]" data-testid="chat-workspace">
      {/* Top Header */}
      <header className="flex items-center gap-3 px-4 h-14 border-b border-[var(--border-primary)] shrink-0 bg-[#161B22]" data-testid="chat-header">
        <div className="flex items-center gap-2 shrink-0">
          <span className="w-7 h-7 rounded-lg bg-brand-600 text-white flex items-center justify-center shadow-md">
            <Bot className="w-4 h-4" />
          </span>
          <div>
            <h1 className="text-sm font-semibold text-[var(--text-primary)] leading-tight">Chat Workspace</h1>
            <p className="text-[10px] text-[var(--text-tertiary)] leading-none">
              MV Protection & Studies • {results[0]?.version ? `Rev: ${results[0].version}` : "Rev: —"}
            </p>
          </div>
        </div>

        {/* Project Selector */}
        <div className="shrink-0">
          <ProjectSelector />
        </div>

        {/* Integration Telemetry Pills */}
        <div className="hidden lg:flex items-center shrink-0">
          <IntegrationStatusPills />
        </div>

        {/* Header Action Controls */}
        <div className="ml-auto flex items-center gap-2.5">
          <Button
            variant="outline"
            size="sm"
            icon={Sliders}
            onClick={() => setParamsOpen(true)}
            data-testid="parameters-drawer-trigger"
          >
            Parameters
          </Button>

          <Button
            variant="outline"
            size="sm"
            icon={CogIcon}
            onClick={() => setAiModalOpen(true)}
            data-testid="ai-settings-trigger"
          >
            AI Engine
          </Button>

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

      {/* Engineering Title Block Signature Strip */}
      <div
        className="flex items-center justify-between px-4 py-1 bg-[#12161D] border-b border-[#2A3441] text-[10px] font-mono text-slate-400 shrink-0 select-none"
        data-testid="title-block-strip"
      >
        <div className="flex items-center gap-3">
          <div>
            <span className="text-slate-500">PROJECT:</span>{" "}
            <span className="text-slate-200 font-semibold">{projectId || "UNASSIGNED"}</span>
          </div>
          <div className="h-3 w-px bg-slate-700" />
          <div>
            <span className="text-slate-500">REV:</span>{" "}
            <span className="text-slate-300">
              {results.length > 0 ? `Rev ${results[0].resultId.slice(0, 6)}` : "Rev 01"} (PROD)
            </span>
          </div>
          <div className="h-3 w-px bg-slate-700" />
          <div>
            <span className="text-slate-500">STANDARD:</span>{" "}
            <span className="text-emerald-400">IEC 60909 / IEEE 1584 / IEEE 3002.7</span>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div>
            <span className="text-slate-500">GATEWAY:</span>{" "}
            <span className="text-cyan-400">DUAL-CONTROL ENFORCED</span>
          </div>
          <div className="h-3 w-px bg-slate-700" />
          <div>
            <span className="text-slate-500">SESSION:</span>{" "}
            <span className="text-slate-300">{sessionId ? sessionId.slice(0, 10) : "N/A"}…</span>
          </div>
        </div>
      </div>

      <div className="flex flex-1 min-h-0">
        <section className="flex flex-col flex-1 min-w-0">
          <MessageList className="flex-1" />
          <div className="px-4 pb-1 text-[10px] text-[var(--text-tertiary)]">
            Stream: <span data-testid="stream-status-label">{streamStatus}</span>
          </div>
          <MessageInput attachmentsEnabled={true} />
        </section>

        {/* AutoViewPanel for SCADA, GIS, or SLD Grid Viewer */}
        <ErrorBoundary>
          <AutoViewPanel />
        </ErrorBoundary>

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

      {/* Modal & Drawer Overlays */}
      <ParametersDrawer open={paramsOpen} onClose={() => setParamsOpen(false)} />
      <AISettingsModal open={aiModalOpen} onClose={() => setAiModalOpen(false)} />
      <ErrorBoundary>
        <ResultViewer result={selectedResult} onClose={() => selectResult(null)} />
      </ErrorBoundary>
    </div>
  );
}

export default ChatWorkspace;