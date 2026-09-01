/**
 * MessageInput — text entry + submit for the chat workspace.
 *
 * - blocks empty sends
 * - disabled while the chat stream is busy
 * - keeps the draft on send failure (the failed send is reported, text preserved)
 * - never stores secrets in component/browser state
 */
import { Send } from "lucide-react";
import { type FormEvent, useCallback, useState } from "react";
import { useChatStore } from "../../store/chatStore";
import { Button } from "../ui/Button";
import { cn } from "../../utils/helpers";

interface MessageInputProps {
  readonly onSend?: (text: string) => Promise<boolean> | boolean;
  readonly disabled?: boolean;
  readonly placeholder?: string;
  readonly className?: string;
}

export function MessageInput({ onSend, disabled, placeholder, className }: MessageInputProps) {
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const storeStreaming = useChatStore((s) => s.streamStatus === "streaming" || s.streamStatus === "connecting");
  const storeSend = useChatStore((s) => s.sendMessage);

  const busy = disabled || sending || storeStreaming;
  const trimmed = draft.trim();

  const submit = useCallback(
    async (e?: FormEvent) => {
      e?.preventDefault?.();
      if (busy || !trimmed) return;
      const sendFn = typeof onSend === "function" ? onSend : storeSend;
      setSending(true);
      try {
        const ok = await sendFn(trimmed);
        if (ok) setDraft("");
        // On failure the draft is intentionally preserved so the user never
        // loses their input; the failure is surfaced by the chat stream error
        // state or the caller's error path.
      } finally {
        setSending(false);
      }
    },
    [busy, trimmed, onSend, storeSend],
  );

  return (
    <form
      onSubmit={submit}
      className={cn("flex items-end gap-2 p-3 border-t border-[var(--border-primary)]", className)}
      data-testid="message-input-form"
    >
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
        placeholder={placeholder ?? "Ask a power-system question…"}
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
        disabled={busy || !trimmed}
        icon={Send}
        aria-label="Send message"
      >
        <span className="sr-only md:not-sr-only">{storeStreaming ? "Sending" : "Send"}</span>
      </Button>
    </form>
  );
}