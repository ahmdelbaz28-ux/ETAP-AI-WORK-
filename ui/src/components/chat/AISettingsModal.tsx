import { Bot, Cpu, KeyRound, RefreshCw, X } from "lucide-react";
import { useState } from "react";
import { useChatStore } from "../../store/chatStore";
import { refreshSettingsCache } from "../../lib/settings-cache";
import { AgentsTab } from "../../pages/settings/AgentsTab";
import ProvidersTab from "../../pages/settings/ProvidersTab";
import { cn } from "../../utils/helpers";
import { Button } from "../ui/Button";

interface AISettingsModalProps {
  readonly open: boolean;
  readonly onClose: () => void;
}

export function AISettingsModal({ open, onClose }: AISettingsModalProps) {
  const [activeTab, setActiveTab] = useState<"providers" | "agents">("providers");
  const [refreshing, setRefreshing] = useState(false);
  const connectSession = useChatStore((s) => s.connectSession);

  if (!open) return null;

  const handleApplyAndReconnect = async () => {
    setRefreshing(true);
    try {
      await refreshSettingsCache();
      connectSession();
      onClose();
    } catch (err) {
      console.error("[AISettingsModal] Failed to refresh settings:", err);
      onClose();
    } finally {
      setRefreshing(false);
    }
  };

  return (
    <dialog
      open
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-md animate-in fade-in-50 border-0 w-full h-full max-w-none max-h-none m-0"
      data-testid="ai-settings-modal"
      aria-modal="true"
    >
      <div className="bg-[var(--bg-card)] border border-[var(--border-primary)] rounded-xl w-full max-w-4xl h-[85vh] flex flex-col shadow-2xl overflow-hidden font-sans">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-[var(--border-primary)] bg-[var(--bg-elevated)] shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-brand-500/10 border border-brand-500/20 text-brand-400 flex items-center justify-center">
              <Bot className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-[var(--text-primary)] flex items-center gap-2">
                <span>AI Engine & Agents Configuration</span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  Live Sync
                </span>
              </h2>
              <p className="text-[11px] text-[var(--text-tertiary)]">
                Configure provider credentials, model selection, and active power-system specialist agents without restarting the session.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-[var(--text-tertiary)] hover:text-[var(--text-primary)] p-1.5 rounded-lg hover:bg-[var(--bg-hover)] transition-colors cursor-pointer"
            data-testid="ai-settings-modal-close"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tab Navigation */}
        <div className="flex items-center gap-2 px-5 py-2.5 border-b border-[var(--border-primary)] bg-[var(--bg-elevated)] shrink-0">
          <button
            type="button"
            onClick={() => setActiveTab("providers")}
            className={cn(
              "flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer",
              activeTab === "providers"
                ? "bg-brand-600 text-white shadow-sm"
                : "text-[var(--text-tertiary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)]",
            )}
            data-testid="ai-tab-providers"
          >
            <KeyRound className="w-3.5 h-3.5" />
            Providers & API Keys
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("agents")}
            className={cn(
              "flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer",
              activeTab === "agents"
                ? "bg-brand-600 text-white shadow-sm"
                : "text-[var(--text-tertiary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)]",
            )}
            data-testid="ai-tab-agents"
          >
            <Cpu className="w-3.5 h-3.5" />
            Engineering Specialist Agents
          </button>
        </div>

        {/* Content Panel */}
        <div className="flex-1 overflow-y-auto p-5 bg-[var(--bg-input)]">
          {activeTab === "providers" && <ProvidersTab />}
          {activeTab === "agents" && <AgentsTab />}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-5 py-3 border-t border-[var(--border-primary)] bg-[var(--bg-elevated)] shrink-0">
          <div className="text-[11px] text-[var(--text-tertiary)] flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span>Keys and agents sync automatically with the backend stream.</span>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={onClose}>
              Cancel
            </Button>
            <Button
              variant="primary"
              size="sm"
              icon={RefreshCw}
              loading={refreshing}
              onClick={handleApplyAndReconnect}
              data-testid="apply-ai-settings-btn"
            >
              Apply & Sync
            </Button>
          </div>
        </div>
      </div>
    </dialog>
  );
}

export default AISettingsModal;
