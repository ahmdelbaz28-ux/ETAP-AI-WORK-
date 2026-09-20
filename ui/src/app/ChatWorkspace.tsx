import {
  Activity,
  ArrowLeft,
  Bot,
  Download,
  History,
  Plus,
  Settings as CogIcon,
  Sliders,
  X,
} from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { ActionCard } from "../components/cards/ActionCard";
import { ApprovalCard } from "../components/cards/ApprovalCard";
import { DecisionCard } from "../components/cards/DecisionCard";
import { ResultCard } from "../components/cards/ResultCard";
import { AISettingsModal } from "../components/chat/AISettingsModal";
import { ActivityDrawer } from "../components/chat/ActivityDrawer";
import { AutoApproveToggle } from "../components/chat/AutoApproveToggle";
import { AutoViewPanel } from "../components/chat/AutoViewPanel";
import { EmergencyStopButton } from "../components/chat/EmergencyStopButton";
import { IntegrationStatusPills } from "../components/chat/IntegrationStatusPills";
import { MessageInput } from "../components/chat/MessageInput";
import { MessageList } from "../components/chat/MessageList";
import { ParametersDrawer } from "../components/chat/ParametersDrawer";
import { ProjectSelector } from "../components/chat/ProjectSelector";
import { QuickActionsBar } from "../components/chat/QuickActionsBar";
import { TokenBudgetIndicator } from "../components/chat/TokenBudgetIndicator";
import { ErrorBoundary } from "../components/ErrorBoundary";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { ResultViewer } from "../components/viewer/ResultViewer";
import { useChatStore } from "../store/chatStore";
import { cn } from "../utils/helpers";

export interface ChatWorkspaceProps {
  readonly onExitToLegacy?: () => void;
}

function SessionFeed() {
  const { t } = useTranslation();
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
        {t("chat.sessionFeedEmpty", "Session feed is empty. Ask the assistant to get started.")}
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
  const { t, i18n } = useTranslation();
  const isRtl = i18n.language === "ar";

  const connectSession = useChatStore((s) => s.connectSession);
  const disconnectSession = useChatStore((s) => s.disconnectSession);
  const selectResult = useChatStore((s) => s.selectResult);
  const streamStatus = useChatStore((s) => s.streamStatus);
  const selectedResultId = useChatStore((s) => s.selectedResultId);
  const results = useChatStore((s) => s.results);
  const activity = useChatStore((s) => s.activity);
  const projectId = useChatStore((s) => s.projectId);
  const sessionId = useChatStore((s) => s.sessionId);
  const startNewSession = useChatStore((s) => s.startNewSession);
  const exportSessionMarkdown = useChatStore((s) => s.exportSessionMarkdown);

  const [paramsOpen, setParamsOpen] = useState(false);
  const [aiModalOpen, setAiModalOpen] = useState(false);
  const [mobileActivityOpen, setMobileActivityOpen] = useState(false);
  const [mobileFeedOpen, setMobileFeedOpen] = useState(false);

  const selectedResult = selectedResultId ? results.find((r) => r.resultId === selectedResultId) ?? null : null;

  useEffect(() => {
    connectSession();
    return () => disconnectSession();
  }, [connectSession, disconnectSession]);

  const handleExportChat = () => {
    const md = exportSessionMarkdown();
    const blob = new Blob([md], { type: "text/markdown;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", `etap-chat-${sessionId || "session"}.md`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const activeJobCount = activity.filter((a) => a.phase !== "completed" && a.phase !== "failed").length;

  return (
    <div
      className={cn("h-screen flex flex-col bg-[var(--bg-primary)] text-slate-100 overflow-hidden", isRtl && "font-sans")}
      dir={isRtl ? "rtl" : "ltr"}
      data-testid="chat-workspace"
    >
      {/* Top Header */}
      <header
        className="flex items-center gap-2 sm:gap-3 px-3 sm:px-4 h-14 border-b border-[var(--border-primary)] shrink-0 bg-[#161B22]"
        data-testid="chat-header"
      >
        <div className="flex items-center gap-2 shrink-0">
          <span className="w-7 h-7 rounded-lg bg-brand-600 text-white flex items-center justify-center shadow-md">
            <Bot className="w-4 h-4" />
          </span>
          <div className="hidden sm:block">
            <h1 className="text-sm font-semibold text-[var(--text-primary)] leading-tight">
              {t("chat.workspace", "Chat Workspace")}
            </h1>
            <p className="text-[10px] text-[var(--text-tertiary)] leading-none">
              {t("chat.subtitle", "MV Protection & Studies")} • Rev: —
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

        {/* Token Budget Indicator */}
        <div className="hidden md:flex items-center shrink-0">
          <TokenBudgetIndicator />
        </div>

        {/* Header Action Controls */}
        <div className="ml-auto flex items-center gap-1.5 sm:gap-2">
          {/* New Session Button */}
          <Button
            variant="ghost"
            size="sm"
            icon={Plus}
            onClick={startNewSession}
            data-testid="new-session-btn"
            title={t("chat.newSession", "New Session")}
          >
            <span className="hidden xl:inline">{t("chat.newSession", "New")}</span>
          </Button>

          {/* Export Chat Button */}
          <Button
            variant="ghost"
            size="sm"
            icon={Download}
            onClick={handleExportChat}
            data-testid="export-chat-btn"
            title={t("chat.exportChat", "Export Chat")}
          >
            <span className="hidden xl:inline">{t("chat.exportChat", "Export")}</span>
          </Button>

          {/* Parameters Drawer Trigger */}
          <Button
            variant="outline"
            size="sm"
            icon={Sliders}
            onClick={() => setParamsOpen(true)}
            data-testid="parameters-drawer-trigger"
          >
            <span className="hidden lg:inline">{t("chat.parameters", "Parameters")}</span>
          </Button>

          {/* AI Settings Trigger */}
          <Button
            variant="outline"
            size="sm"
            icon={CogIcon}
            onClick={() => setAiModalOpen(true)}
            data-testid="ai-settings-trigger"
          >
            <span className="hidden lg:inline">{t("chat.aiEngine", "AI Engine")}</span>
          </Button>

          <AutoApproveToggle />
          <EmergencyStopButton />

          {/* Responsive Drawer Toggles for <1500px */}
          <button
            type="button"
            onClick={() => setMobileFeedOpen((prev) => !prev)}
            className="2xl:hidden p-1.5 rounded-lg border border-[#334155] bg-[#1E2530] text-slate-300 hover:text-white relative cursor-pointer"
            data-testid="toggle-feed-drawer"
            title={t("chat.sessionHistory", "Session History")}
          >
            <History className="w-4 h-4" />
          </button>

          <button
            type="button"
            onClick={() => setMobileActivityOpen((prev) => !prev)}
            className="2xl:hidden p-1.5 rounded-lg border border-[#334155] bg-[#1E2530] text-slate-300 hover:text-white relative cursor-pointer"
            data-testid="toggle-activity-drawer"
            title={t("chat.sessionActivity", "Session Activity")}
          >
            <Activity className="w-4 h-4" />
            {activeJobCount > 0 && (
              <span className="absolute -top-1 -right-1 w-3.5 h-3.5 rounded-full bg-emerald-500 text-[9px] font-bold text-black flex items-center justify-center animate-pulse">
                {activeJobCount}
              </span>
            )}
          </button>

          {onExitToLegacy && (
            <Button
              variant="ghost"
              size="sm"
              icon={ArrowLeft}
              onClick={onExitToLegacy}
              data-testid="exit-to-legacy"
            >
              <span className="hidden sm:inline">{t("chat.legacyUi", "Legacy UI")}</span>
            </Button>
          )}
        </div>
      </header>

      {/* Engineering Title Block Signature Strip */}
      <div
        className="flex items-center justify-between px-4 py-1 bg-[#12161D] border-b border-[#2A3441] text-[10px] font-mono text-slate-400 shrink-0 select-none overflow-x-auto no-scrollbar"
        data-testid="title-block-strip"
      >
        <div className="flex items-center gap-3 shrink-0">
          <div>
            <span className="text-slate-500">{t("chat.project", "PROJECT")}:</span>{" "}
            <span className="text-slate-200 font-semibold">{projectId || t("chat.unassigned", "UNASSIGNED")}</span>
          </div>
          <div className="h-3 w-px bg-slate-700" />
          <div>
            <span className="text-slate-500">REV:</span>{" "}
            <span className="text-slate-300">—</span>
          </div>
          <div className="h-3 w-px bg-slate-700" />
          <div>
            <span className="text-slate-500">STANDARD:</span>{" "}
            <span className="text-emerald-400">IEC 60909 / IEEE 1584 / IEEE 3002.7</span>
          </div>
        </div>
        <div className="flex items-center gap-3 shrink-0 ml-4">
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

      {/* Main Workspace Layout */}
      <div className="flex flex-1 min-h-0 relative overflow-hidden">
        {/* Chat Conversation Column (Highest Priority) */}
        <section className="flex flex-col flex-1 min-w-0 h-full relative">
          <MessageList className="flex-1" />
          <div className="px-4 pb-1 text-[10px] text-[var(--text-tertiary)] flex items-center justify-between">
            <div>
              Stream: <span data-testid="stream-status-label" className="font-mono">{streamStatus}</span>
            </div>
            {streamStatus === "streaming" && (
              <span className="text-emerald-400 animate-pulse text-[10px] font-mono">
                ● Live Streaming Response…
              </span>
            )}
          </div>

          {/* Quick Actions Bar directly above MessageInput */}
          <QuickActionsBar />

          {/* Unified Input */}
          <MessageInput attachmentsEnabled={true} />
        </section>

        {/* AutoViewPanel for SCADA, GIS, or SLD Grid Viewer */}
        <ErrorBoundary>
          <AutoViewPanel />
        </ErrorBoundary>

        {/* Static Sidebars for 2xl (>1500px) */}
        <aside className="hidden 2xl:flex flex-col w-72 border-l border-[var(--border-primary)] overflow-y-auto p-3 space-y-3 shrink-0 bg-[#14181F]">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">
            {t("chat.sessionActivity", "Session Activity")}
          </h2>
          <SessionFeed />
        </aside>
        <aside className="hidden 2xl:flex flex-col w-80 border-l border-[var(--border-primary)] overflow-y-auto p-3 shrink-0 bg-[#14181F]">
          <ActivityDrawer />
        </aside>

        {/* Floating / Responsive Drawers for <1500px */}
        {mobileFeedOpen && (
          <div
            className="2xl:hidden fixed inset-0 z-40 flex justify-end bg-black/50 backdrop-blur-xs animate-in fade-in"
            onClick={() => setMobileFeedOpen(false)}
          >
            <div
              className="w-80 h-full bg-[#161B22] border-l border-[#334155] p-4 overflow-y-auto shadow-2xl animate-in slide-in-from-right"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center justify-between pb-3 mb-3 border-b border-[#334155]">
                <h3 className="text-xs font-semibold uppercase text-slate-300">
                  {t("chat.sessionActivity", "Session Activity")}
                </h3>
                <button
                  type="button"
                  onClick={() => setMobileFeedOpen(false)}
                  className="p-1 rounded text-slate-400 hover:text-white"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
              <SessionFeed />
            </div>
          </div>
        )}

        {mobileActivityOpen && (
          <div
            className="2xl:hidden fixed inset-0 z-40 flex justify-end bg-black/50 backdrop-blur-xs animate-in fade-in"
            onClick={() => setMobileActivityOpen(false)}
          >
            <div
              className="w-80 h-full bg-[#161B22] border-l border-[#334155] p-4 overflow-y-auto shadow-2xl animate-in slide-in-from-right"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center justify-between pb-3 mb-3 border-b border-[#334155]">
                <h3 className="text-xs font-semibold uppercase text-slate-300">
                  {t("chat.sessionStream", "Session Stream & Progress")}
                </h3>
                <button
                  type="button"
                  onClick={() => setMobileActivityOpen(false)}
                  className="p-1 rounded text-slate-400 hover:text-white"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
              <ActivityDrawer />
            </div>
          </div>
        )}
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