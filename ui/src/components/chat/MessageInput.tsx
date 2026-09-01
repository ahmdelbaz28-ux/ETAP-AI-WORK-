/**
 * MessageInput — text entry + attachment handling + submit for the chat workspace.
 *
 * Security & Reliability Guarantees:
 * - Blocks empty sends
 * - Disabled while the chat stream is busy
 * - Preserves draft on send failure
 * - Attachments behind fail-closed feature flag
 * - Validates file size (max 10 MiB) and allowed power-system file types before upload
 * - Never stores secrets or credentials in component or browser state
 */
import { Send, Upload, X, FileText } from "lucide-react";
import { type FormEvent, type ChangeEvent, useCallback, useRef, useState } from "react";
import { useChatStore } from "../../store/chatStore";
import { Button } from "../ui/Button";
import { cn } from "../../utils/helpers";

const MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024; // 10 MiB
const ALLOWED_EXTENSIONS = [".json", ".xml", ".cim", ".raw", ".m", ".csv", ".tsv", ".etap"];

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
  const fileInputRef = useRef<HTMLInputElement>(null);

  const storeStreaming = useChatStore((s) => s.streamStatus === "streaming" || s.streamStatus === "connecting");
  const storeSend = useChatStore((s) => s.sendMessage);

  const busy = disabled || sending || storeStreaming;
  const trimmed = draft.trim();

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    setFileError(null);
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.size > MAX_ATTACHMENT_BYTES) {
      setFileError(`File exceeds maximum allowed size of 10 MB (${(file.size / (1024 * 1024)).toFixed(1)} MB)`);
      if (fileInputRef.current) fileInputRef.current.value = "";
      return;
    }

    const lowerName = file.name.toLowerCase();
    const isAllowed = ALLOWED_EXTENSIONS.some((ext) => lowerName.endsWith(ext));
    if (!isAllowed) {
      setFileError(`Unsupported file type. Accepted: ${ALLOWED_EXTENSIONS.join(", ")}`);
      if (fileInputRef.current) fileInputRef.current.value = "";
      return;
    }

    setSelectedFile(file);
  };

  const removeFile = () => {
    setSelectedFile(null);
    setFileError(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const submit = useCallback(
    async (e?: FormEvent) => {
      e?.preventDefault?.();
      if (busy || (!trimmed && !selectedFile)) return;
      const sendFn = typeof onSend === "function" ? onSend : storeSend;
      setSending(true);
      try {
        const payloadText = selectedFile
          ? `${trimmed ? trimmed + " " : ""}[Attached: ${selectedFile.name}]`
          : trimmed;
        const ok = await sendFn(payloadText);
        if (ok) {
          setDraft("");
          setSelectedFile(null);
          setFileError(null);
          if (fileInputRef.current) fileInputRef.current.value = "";
        }
      } finally {
        setSending(false);
      }
    },
    [busy, trimmed, selectedFile, onSend, storeSend],
  );

  return (
    <div className={cn("border-t border-[var(--border-primary)] bg-[var(--bg-elevated)]", className)}>
      {selectedFile && (
        <div className="flex items-center justify-between px-3 py-1.5 bg-[var(--bg-muted)] text-xs text-[var(--text-secondary)] border-b border-[var(--border-primary)]">
          <div className="flex items-center gap-2 truncate">
            <FileText className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
            <span className="font-medium truncate">{selectedFile.name}</span>
            <span className="text-[10px] text-[var(--text-tertiary)] shrink-0">
              ({(selectedFile.size / 1024).toFixed(1)} KB)
            </span>
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

      {fileError && (
        <div className="px-3 py-1 text-xs text-rose-500 bg-rose-500/10 border-b border-rose-500/20">
          {fileError}
        </div>
      )}

      <form
        onSubmit={submit}
        className="flex items-end gap-2 p-3"
        data-testid="message-input-form"
      >
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
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              void submit();
            }
          }}
          rows={2}
          placeholder={placeholder ?? "Ask a power-system question or import a network model…"}
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