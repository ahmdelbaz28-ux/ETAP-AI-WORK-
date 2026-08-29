/**
 * MessageList — renders user/assistant chat messages with Markdown
 * and streaming lifecycle (complete / streaming / error / empty).
 */
import { Bot, Loader2, MessageSquare, User } from "lucide-react";
import { useMemo } from "react";
import { useChatStore, type ChatMessage } from "../../store/chatStore";
import { cn } from "../../utils/helpers";
import { EmptyState } from "../ui/EmptyState";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface MessageListProps {
  readonly messages?: ChatMessage[];
  readonly className?: string;
}

function MessageBubble({ message }: { readonly message: ChatMessage }) {
  const isUser = message.role === "user";
  return (
    <div
      className={cn(
        "flex gap-3 items-start",
        isUser ? "flex-row-reverse" : "flex-row",
      )}
    >
      <div
        className={cn(
          "w-8 h-8 rounded-lg flex items-center justify-center shrink-0 border mt-0.5",
          isUser
            ? "bg-brand-500/15 border-brand-500/20 text-brand-400"
            : "bg-[var(--bg-elevated)] border-[var(--border-primary)] text-[var(--text-secondary)]",
        )}
        aria-hidden
      >
        {isUser ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
      </div>

      <div className={cn("max-w-[80%] flex flex-col gap-1", isUser ? "items-end" : "items-start")}>
        <div
          className={cn(
            "px-4 py-3 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap",
            isUser
              ? "bg-brand-600 text-white rounded-tr-sm"
              : "bg-[var(--bg-elevated)] border border-[var(--border-primary)] text-[var(--text-primary)] rounded-tl-sm",
            message.status === "error" && "border-red-500/40 text-red-300",
          )}
        >
          {isUser ? (
            message.content
          ) : (
            <div className="prose-engineering">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content || ""}</ReactMarkdown>
            </div>
          )}
        </div>

        <div className="flex items-center gap-2 px-1">
          {message.status === "streaming" && (
            <span className="text-[10px] text-[var(--text-muted)] inline-flex items-center gap-1">
              <Loader2 className="w-3 h-3 animate-spin" />
              generating…
            </span>
          )}
          {message.error && (
            <span className="text-[10px] text-red-400">
              ⚠ {message.error}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

export function MessageList({ messages, className }: MessageListProps) {
  const storeMessages = useChatStore((s) => s.messages);
  const list = useMemo(() => {
    const source = Array.isArray(messages) ? messages : storeMessages;
    return [...source].sort((a, b) => a.createdAt - b.createdAt);
  }, [messages, storeMessages]);

  if (list.length === 0) {
    return (
      <EmptyState
        icon={<MessageSquare className="w-8 h-8" />}
        title="No messages yet"
        description="Ask about load flow, short circuit, arc flash, coordination, or any power-system study."
        className="h-full"
      />
    );
  }

  return (
    <div
      className={cn("flex flex-col gap-4 overflow-y-auto p-4", className)}
      data-testid="message-list"
      aria-live="polite"
    >
      {list.map((message) => (
        <MessageBubble key={message.id} message={message} />
      ))}
    </div>
  );
}