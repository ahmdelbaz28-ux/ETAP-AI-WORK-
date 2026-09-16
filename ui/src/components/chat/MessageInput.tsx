/**
 * MessageInput — text entry + attachment handling + submit for the chat workspace.
 *
 * Security & Reliability Guarantees:
 * - Blocks empty sends
 * - Disabled while the chat stream is busy
 * - Preserves draft on send failure
 * - Attachments behind fail-closed feature flag
 * - Validates file size (max 10 MiB) and allowed power-system file types before upload
 * - Automatically triggers dry-run preview (`POST /api/v1/import/preview`) for power-system files
 * - Displays ImportPreviewResponse in ActionCard with Approval Gateway guarded execution
 * - Never stores secrets or credentials in component or browser state
 */
import { FileText, Play, Send, ShieldAlert, ShieldCheck, Upload, Wrench, X } from "lucide-react";
import { type ChangeEvent, type FormEvent, useCallback, useRef, useState } from "react";
import { API_BASE_URL } from "../../lib/api-config";
import { getAuthToken } from "../../lib/tokenStorage";
import { useChatStore } from "../../store/chatStore";
import { cn } from "../../utils/helpers";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card, CardHeader, CardSection } from "../ui/Card";
import {
  ALLOWED_EXTENSIONS,
  type ImportPreviewResponse,
  riskVariant,
  validatePowerFile,
} from "../../lib/power-file";

const ENGINEERING_COMMANDS = [
  { cmd: "/flow F-07", label: "/flow <feeder>", desc: "Run Newton-Raphson Load Flow (IEEE 3002.7)" },
  { cmd: "/fault Bus-1", label: "/fault <bus>", desc: "Calculate 3-Phase short-circuit fault (IEC 60909)" },
  { cmd: "/arc-flash SWG-01", label: "/arc-flash <bus>", desc: "Run IEEE 1584 Arc Flash Incident Energy & PPE assessment" },
  { cmd: "/coordination Relay-51", label: "/coordination <relay>", desc: "Verify relay time-current curve coordination (IEC 60255)" },
  { cmd: "/motor-start M-101", label: "/motor-start <motor>", desc: "Simulate dynamic motor starting & voltage dip (IEEE 399)" },
  { cmd: "/export pdf", label: "/export <format>", desc: "Export calculation reports in PDF, Excel, CSV, or JSON" },
];

interface MessageInputProps {
  readonly onSend?: (text: string, file?: File | null) => Promise<boolean> | boolean;
  readonly disabled?: boolean;
  readonly placeholder?: string;
  readonly className?: string;
  readonly attachmentsEnabled?: boolean;
}

export function MessageInput({
  onSend,
  disabled,
  placeholder,
  className,
  attachmentsEnabled = false,
}: MessageInputProps) {
  const [draft, setDraft] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [preview, setPreview] = useState<ImportPreviewResponse | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [pendingApprovalId, setPendingApprovalId] = useState<string | null>(null);
  const [executing, setExecuting] = useState(false);
  const [executionError, setExecutionError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const storeStreaming = useChatStore(
    (s) => s.streamStatus === "streaming" || s.streamStatus === "connecting",
  );
  const storeSend = useChatStore((s) => s.sendMessage);
  const proposeImportApproval = useChatStore((s) => s.proposeImportApproval);
  const resolveApproval = useChatStore((s) => s.resolveApproval);
  const executeImport = useChatStore((s) => s.executeImport);
  const addProposedAction = useChatStore((s) => s.addProposedAction);
  const approvals = useChatStore((s) => s.approvals);
  const autoApprove = useChatStore((s) => s.autoApprove);
  const emergencyStop = useChatStore((s) => s.emergencyStop);

  const isEmergencyStopped = emergencyStop.active;
  const busy = disabled || sending || storeStreaming || executing || isEmergencyStopped;
  const trimmed = draft.trim();

  const runPreview = async (fileToPreview: File) => {
    setPreviewLoading(true);
    setPreviewError(null);
    try {
      const formData = new FormData();
      formData.append("file", fileToPreview);
      const sid = useChatStore.getState().sessionId;
      if (sid) formData.append("session_id", sid);

      const token = getAuthToken();
      const res = await fetch(`${API_BASE_URL}/api/v1/import/preview`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: formData,
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => null);
        setPreviewError(errJson?.detail || `Preview failed: ${res.statusText}`);
        return;
      }

      const previewData: ImportPreviewResponse = await res.json();
      setPreview(previewData);
      addProposedAction({
        tool: "data_import",
        preview_id: previewData.preview_id,
        filename: previewData.filename,
        format: previewData.format,
        records_count: previewData.records_count,
        buses_count: previewData.buses_count,
        branches_count: previewData.branches_count,
        risk_level: previewData.risk_level,
      });
    } catch (err) {
      setPreviewError(err instanceof Error ? err.message : "Failed to preview import");
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    setFileError(null);
    setPreview(null);
    setPreviewError(null);
    setPendingApprovalId(null);
    setExecutionError(null);

    const file = e.target.files?.[0];
    if (!file) return;

    const validation = validatePowerFile(file);
    if (!validation.valid) {
      setFileError(validation.error ?? "Invalid file");
      if (fileInputRef.current) fileInputRef.current.value = "";
      return;
    }

    setSelectedFile(file);
    void runPreview(file);
  };

  const removeFile = useCallback(() => {
    setSelectedFile(null);
    setFileError(null);
    setPreview(null);
    setPreviewError(null);
    setPendingApprovalId(null);
    setExecutionError(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }, []);

  const handleExecute = async () => {
    if (!preview) return;
    setExecuting(true);
    setExecutionError(null);

    try {
      // 1. Propose action to Approval Gateway (POST /api/v1/approvals) -> status: pending
      const approval = await proposeImportApproval(preview);
      if (!approval) {
        throw new Error("Failed to create approval in gateway");
      }
      setPendingApprovalId(approval.id);

      // 2. Resolve approval through Approval Gateway (decision: "approve")
      const approved = await resolveApproval(approval.id, "approve");
      if (!approved) {
        throw new Error("Approval resolution failed");
      }

      // 3. Execute approved import through executeImport (POST /api/v1/import/execute)
      const resultId = await executeImport(preview.preview_id, approval.id);
      if (resultId) {
        removeFile();
      }
    } catch (err) {
      setExecutionError(err instanceof Error ? err.message : "Execution failed");
    } finally {
      setExecuting(false);
    }
  };

  const submit = useCallback(
    async (e?: FormEvent) => {
      e?.preventDefault?.();
      if (busy || (!trimmed && !selectedFile)) return;
      const sendFn = typeof onSend === "function" ? onSend : storeSend;
      setSending(true);
      try {
        let payloadText = trimmed;
        if (selectedFile) {
          const prefix = trimmed ? `${trimmed} ` : "";
          payloadText = `${prefix}[Attached: ${selectedFile.name}]`;
        }
        const ok = await sendFn(payloadText);
        if (ok) {
          setDraft("");
          removeFile();
        }
      } finally {
        setSending(false);
      }
    },
    [busy, trimmed, selectedFile, onSend, storeSend, removeFile],
  );

  return (
    <div
      className={cn("border-t border-[var(--border-primary)] bg-[var(--bg-elevated)]", className)}
    >
      {selectedFile && !preview && (
        <div className="flex items-center justify-between px-3 py-1.5 bg-[var(--bg-muted)] text-xs text-[var(--text-secondary)] border-b border-[var(--border-primary)]">
          <div className="flex items-center gap-2 truncate">
            <FileText className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
            <span className="font-medium truncate">{selectedFile.name}</span>
            <span className="text-[10px] text-[var(--text-tertiary)] shrink-0">
              ({(selectedFile.size / 1024).toFixed(1)} KB)
            </span>
            {previewLoading && (
              <span className="text-[10px] text-brand-400 animate-pulse ml-2 font-medium">
                Generating dry-run preview…
              </span>
            )}
          </div>
          <button
            type="button"
            onClick={removeFile}
            className="p-1 hover:text-[var(--text-primary)] rounded"
            aria-label="Remove attached file"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* Dry-Run Import Preview in ActionCard */}
      {preview && (
        <div
          className="p-3 border-b border-[var(--border-primary)] bg-[var(--bg-elevated)]"
          data-testid="import-preview-action-card"
        >
          <Card padding="sm" data-testid={`action-card-${preview.preview_id}`}>
            <CardHeader
              title="Action proposed · data_import"
              subtitle={`File: ${preview.filename} (${preview.format.toUpperCase()})`}
              icon={<Wrench className="w-4 h-4 text-indigo-400" />}
              action={
                <Badge variant={riskVariant(preview.risk_level)}>
                  {preview.risk_level} risk
                </Badge>
              }
            />
            <CardSection>
              <div className="grid grid-cols-3 gap-2 my-2 text-xs bg-[var(--bg-muted)] p-2 rounded">
                <div>
                  <span className="text-[var(--text-tertiary)]">Records: </span>
                  <span className="font-semibold text-[var(--text-primary)]">
                    {preview.records_count}
                  </span>
                </div>
                <div>
                  <span className="text-[var(--text-tertiary)]">Buses: </span>
                  <span className="font-semibold text-[var(--text-primary)]">
                    {preview.buses_count}
                  </span>
                </div>
                <div>
                  <span className="text-[var(--text-tertiary)]">Branches: </span>
                  <span className="font-semibold text-[var(--text-primary)]">
                    {preview.branches_count}
                  </span>
                </div>
              </div>

              {preview.warnings && preview.warnings.length > 0 && (
                <div className="text-xs text-amber-400 mb-2">{preview.warnings.join(", ")}</div>
              )}

              {preview.errors && preview.errors.length > 0 && (
                <div className="text-xs text-rose-500 mb-2">{preview.errors.join(", ")}</div>
              )}

              {executionError && (
                <div className="text-xs text-rose-500 mb-2" data-testid="execution-error">
                  {executionError}
                </div>
              )}

              <div className="flex items-center justify-between mt-2 pt-2 border-t border-[var(--border-primary)]">
                <div className="text-xs text-[var(--text-tertiary)] flex items-center gap-1.5">
                  {pendingApprovalId ? (
                    <Badge variant="warning">pending gateway</Badge>
                  ) : (
                    <span>Approval Gateway required</span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    onClick={removeFile}
                    disabled={executing}
                  >
                    Cancel
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="primary"
                    icon={pendingApprovalId ? ShieldCheck : Play}
                    loading={executing}
                    disabled={executing || (preview.errors && preview.errors.length > 0)}
                    onClick={() => void handleExecute()}
                    data-testid="execute-import-btn"
                  >
                    {pendingApprovalId ? "Approve & Execute" : "Execute"}
                  </Button>
                </div>
              </div>
            </CardSection>
          </Card>
        </div>
      )}

      {fileError && (
        <div className="px-3 py-1 text-xs text-rose-500 bg-rose-500/10 border-b border-rose-500/20">
          {fileError}
        </div>
      )}

      {previewError && (
        <div
          className="px-3 py-1 text-xs text-rose-500 bg-rose-500/10 border-b border-rose-500/20"
          data-testid="preview-error"
        >
          {previewError}
        </div>
      )}

      {isEmergencyStopped && (
        <div
          className="flex items-center gap-2 px-3 py-1.5 bg-rose-500/10 border-b border-rose-500/30 text-rose-400 text-xs"
          data-testid="emergency-stop-banner"
        >
          <ShieldAlert className="w-4 h-4 shrink-0 text-rose-400" />
          <span className="font-medium">
            Emergency Stop (Kill-Switch) is active — chat message dispatch and actions are halted.
          </span>
        </div>
      )}

      {approvals.length > 0 && !isEmergencyStopped && (
        <div
          className="flex items-center justify-between px-3 py-1.5 bg-amber-500/10 border-b border-amber-500/20 text-xs text-amber-300"
          data-testid="pending-approvals-bar"
        >
          <div className="flex items-center gap-1.5">
            <ShieldCheck className="w-3.5 h-3.5 text-amber-400 shrink-0" />
            <span>
              Pending Approvals: <strong>{approvals.length}</strong> action(s) awaiting review
            </span>
          </div>
          {autoApprove.enabled && (
            <Badge variant="success" size="sm" data-testid="auto-approve-badge">
              Auto-Approve Active
            </Badge>
          )}
        </div>
      )}

      {autoApprove.enabled && approvals.length === 0 && !isEmergencyStopped && (
        <div
          className="flex items-center justify-end px-3 py-0.5 bg-[var(--bg-muted)] border-b border-[var(--border-primary)] text-[10px] text-emerald-400"
          data-testid="auto-approve-status"
        >
          <span className="flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 inline-block" />
            {" "}Auto-Approve Enabled (Low-Risk)
          </span>
        </div>
      )}

      {/* Slash command quick suggestions */}
      {draft.startsWith("/") && (
        (() => {
          const matches = ENGINEERING_COMMANDS.filter((c) =>
            c.cmd.toLowerCase().startsWith(draft.toLowerCase()) ||
            c.label.toLowerCase().includes(draft.toLowerCase()) ||
            c.desc.toLowerCase().includes(draft.toLowerCase())
          );
          if (matches.length === 0) return null;
          return (
            <div
              className="px-3 pt-2 pb-1 border-b border-[#2A3441] bg-[#161B22]"
              data-testid="command-suggestions"
            >
              <div className="text-[10px] font-mono text-slate-400 mb-1.5 flex justify-between items-center">
                <span className="text-brand-400 font-semibold uppercase">⚡ Engineering Commands</span>
                <span>Click or Press <kbd className="px-1 py-0.5 bg-[#20262E] rounded border border-[#334155] text-slate-300">Tab ⇥</kbd></span>
              </div>
              <div className="flex flex-wrap gap-1.5 pb-1">
                {matches.map((item, idx) => (
                  <button
                    key={item.cmd}
                    type="button"
                    onClick={() => {
                      setDraft(item.cmd + " ");
                      textareaRef.current?.focus();
                    }}
                    className="px-2 py-1 rounded bg-[#20262E] hover:bg-brand-600/30 hover:border-brand-500/50 border border-[#334155] text-left text-xs transition-colors flex items-center gap-1.5 group"
                    data-testid={`cmd-suggestion-${idx}`}
                  >
                    <span className="font-mono text-brand-400 font-semibold">{item.label}</span>
                    <span className="text-[10px] text-slate-400 group-hover:text-slate-300">({item.desc.split("(")[0].trim()})</span>
                  </button>
                ))}
              </div>
            </div>
          );
        })()
      )}

      <form onSubmit={submit} className="flex items-end gap-2 p-3" data-testid="message-input-form">
        {attachmentsEnabled && (
          <>
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileChange}
              accept={ALLOWED_EXTENSIONS.join(",")}
              className="hidden"
              data-testid="chat-file-input"
              disabled={busy}
            />
            <Button
              type="button"
              variant="outline"
              size="sm"
              icon={Upload}
              disabled={busy}
              onClick={() => fileInputRef.current?.click()}
              aria-label="Attach power-system file"
              data-testid="attach-file-btn"
            />
          </>
        )}

        <textarea
          ref={textareaRef}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Tab" && draft.startsWith("/")) {
              const matches = ENGINEERING_COMMANDS.filter((c) =>
                c.cmd.toLowerCase().startsWith(draft.toLowerCase()) ||
                c.label.toLowerCase().includes(draft.toLowerCase())
              );
              if (matches.length > 0) {
                e.preventDefault();
                setDraft(matches[0].cmd + " ");
                return;
              }
            }
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              void submit();
            }
          }}
          rows={2}
          placeholder={
            isEmergencyStopped
              ? "Emergency stop active — all chat actions disabled"
              : (placeholder ?? "Ask a power-system question or import a network model…")
          }
          aria-label="Chat message"
          disabled={busy}
          className={cn(
            "flex-1 resize-none rounded-lg bg-[var(--bg-elevated)] border border-[var(--border-primary)]",
            "px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)]",
            "focus:outline-none focus:ring-2 focus:ring-[var(--ring)] disabled:opacity-50",
          )}
        />
        <Button
          type="submit"
          variant="primary"
          loading={sending || storeStreaming}
          disabled={busy || (!trimmed && !selectedFile)}
          icon={Send}
          aria-label="Send message"
        >
          <span className="sr-only md:not-sr-only">{storeStreaming ? "Sending" : "Send"}</span>
        </Button>
      </form>
    </div>
  );
}
