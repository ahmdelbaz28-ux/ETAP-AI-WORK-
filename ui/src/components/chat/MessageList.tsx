/**
 * MessageList — renders user/assistant chat messages with Markdown
 * and streaming lifecycle (complete / streaming / error / empty).
 */
import {
  Activity,
  AlertTriangle,
  BarChart3,
  Bot,
  CheckCircle2,
  Flame,
  Loader2,
  ShieldAlert,
  Sparkles,
  Upload,
  User,
  Zap,
} from "lucide-react";
import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { useChatStore, type ChatMessage } from "../../store/chatStore";
import { cn } from "../../utils/helpers";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface MessageListProps {
  readonly messages?: ChatMessage[];
  readonly className?: string;
}

const MarkdownLink = ({ href, children, ...props }: React.ComponentPropsWithoutRef<"a">) => {
  const isSafe = /^https?:\/\//i.test(href || "");
  if (!isSafe) return <span>{children}</span>;
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-brand-400 underline hover:text-brand-300"
      {...props}
    >
      {children}
    </a>
  );
};

const MarkdownImage = ({ alt }: React.ComponentPropsWithoutRef<"img">) => (
  <span className="inline-flex items-center gap-1 text-xs text-[var(--text-muted)] italic">
    🖼️ [{alt || "Image"}]
  </span>
);

const MARKDOWN_COMPONENTS = {
  a: MarkdownLink,
  img: MarkdownImage,
};

interface StructuredFinding {
  category: string;
  severity: "info" | "warning" | "critical" | "pass";
  message: string;
  standard_reference?: string;
}

interface StructuredDutyItem {
  parameter: string;
  calculated_value: number;
  rated_limit: number;
  unit: string;
  duty_percent: number;
  status: string;
  standard_clause?: string;
}

interface StructuredAnswer {
  title?: string;
  summary?: string;
  status?: "complete" | "warning" | "error";
  study_type?: string;
  findings?: StructuredFinding[];
  parameters?: Record<string, unknown>;
  standards_referenced?: string[];
  recommendations?: string[];
  duty_table?: StructuredDutyItem[];
  confidence?: number;
}

function tryParseStructuredAnswer(content: string): StructuredAnswer | null {
  if (!content) return null;
  const trimmed = content.trim();
  if (!trimmed.startsWith("{") || !trimmed.endsWith("}")) return null;
  try {
    const data = JSON.parse(trimmed) as StructuredAnswer;
    if (data && (data.title || data.summary) && (data.findings || data.parameters || data.duty_table)) {
      return data;
    }
  } catch {
    return null;
  }
  return null;
}

function EngineerAnswerCard({ answer }: { readonly answer: StructuredAnswer }) {
  const isPass = answer.status === "complete";
  const isWarn = answer.status === "warning";

  return (
    <div className="flex flex-col gap-3 rounded-xl bg-[var(--bg-secondary)] border border-[var(--border-primary)] p-4 max-w-full text-sm">
      <div className="flex items-center justify-between gap-2 border-b border-[var(--border-secondary)] pb-2">
        <div className="flex items-center gap-2">
          {isPass ? (
            <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
          ) : isWarn ? (
            <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0" />
          ) : (
            <ShieldAlert className="w-5 h-5 text-rose-400 shrink-0" />
          )}
          <span className="font-semibold text-[var(--text-primary)]">{answer.title || "Engineering Analysis"}</span>
        </div>
        {answer.study_type && (
          <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-brand-500/10 text-brand-400 border border-brand-500/20">
            {answer.study_type}
          </span>
        )}
      </div>

      {answer.summary && (
        <p className="text-[var(--text-secondary)] leading-relaxed">{answer.summary}</p>
      )}

      {answer.standards_referenced && answer.standards_referenced.length > 0 && (
        <div className="flex flex-wrap gap-1.5 items-center">
          <span className="text-xs text-[var(--text-muted)]">Standards:</span>
          {answer.standards_referenced.map((std) => (
            <span key={std} className="text-[11px] px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-300 border border-cyan-500/20 font-mono">
              {std}
            </span>
          ))}
        </div>
      )}

      {answer.duty_table && answer.duty_table.length > 0 && (
        <div className="overflow-x-auto my-1">
          <table className="w-full text-xs text-left border-collapse">
            <thead>
              <tr className="border-b border-[var(--border-secondary)] text-[var(--text-muted)]">
                <th className="py-1 px-2">Parameter</th>
                <th className="py-1 px-2">Calculated</th>
                <th className="py-1 px-2">Rated Limit</th>
                <th className="py-1 px-2">% Duty</th>
                <th className="py-1 px-2">Status</th>
              </tr>
            </thead>
            <tbody>
              {answer.duty_table.map((row, idx) => (
                <tr key={idx} className="border-b border-[var(--border-secondary)]/50 hover:bg-white/5">
                  <td className="py-1 px-2 font-medium">{row.parameter}</td>
                  <td className="py-1 px-2">{row.calculated_value} {row.unit}</td>
                  <td className="py-1 px-2">{row.rated_limit} {row.unit}</td>
                  <td className="py-1 px-2 font-mono font-semibold">{row.duty_percent}%</td>
                  <td className="py-1 px-2">
                    <span className={cn(
                      "px-1.5 py-0.5 rounded text-[10px] font-semibold",
                      row.status === "PASS" ? "bg-emerald-500/15 text-emerald-300" : "bg-rose-500/15 text-rose-300"
                    )}>
                      {row.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {answer.findings && answer.findings.length > 0 && (
        <div className="flex flex-col gap-1.5 mt-1">
          <span className="text-xs font-semibold text-[var(--text-muted)]">Findings:</span>
          {answer.findings.map((f, i) => (
            <div key={i} className="flex items-start gap-2 text-xs bg-[var(--bg-elevated)] p-2 rounded border border-[var(--border-secondary)]">
              <span className={cn(
                "px-1.5 py-0.5 rounded text-[10px] uppercase font-bold shrink-0",
                f.severity === "pass" ? "bg-emerald-500/20 text-emerald-400" :
                f.severity === "warning" ? "bg-amber-500/20 text-amber-400" : "bg-rose-500/20 text-rose-400"
              )}>
                {f.severity}
              </span>
              <span className="text-[var(--text-primary)]">{f.message}</span>
              {f.standard_reference && (
                <span className="text-[10px] text-[var(--text-muted)] ml-auto shrink-0 font-mono">[{f.standard_reference}]</span>
              )}
            </div>
          ))}
        </div>
      )}

      {answer.recommendations && answer.recommendations.length > 0 && (
        <div className="flex flex-col gap-1 mt-1 text-xs">
          <span className="font-semibold text-[var(--text-muted)]">Recommendations:</span>
          <ul className="list-disc list-inside space-y-0.5 text-[var(--text-secondary)]">
            {answer.recommendations.map((rec, i) => (
              <li key={i}>{rec}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function MessageBubble({ message }: { readonly message: ChatMessage }) {
  const isUser = message.role === "user";
  const structuredAnswer = !isUser ? tryParseStructuredAnswer(message.content) : null;

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
          ) : structuredAnswer ? (
            <EngineerAnswerCard answer={structuredAnswer} />
          ) : (
            <div className="prose-engineering">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={MARKDOWN_COMPONENTS}
              >
                {message.content || ""}
              </ReactMarkdown>
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
  const { t } = useTranslation();
  const storeMessages = useChatStore((s) => s.messages);
  const sendMessage = useChatStore((s) => s.sendMessage);
  const streamStatus = useChatStore((s) => s.streamStatus);
  const isStreaming = streamStatus === "streaming" || streamStatus === "connecting";

  const list = useMemo(() => {
    const source = Array.isArray(messages) ? messages : storeMessages;
    return [...source].sort((a, b) => a.createdAt - b.createdAt);
  }, [messages, storeMessages]);

  if (list.length === 0) {
    const suggestions = [
      {
        id: "load-flow",
        title: "شغل دراسة سريان الأحمال (Load Flow)",
        subtitle: "تحليل سريان القدرة ومستويات الجهد وفق IEEE 3002.7",
        prompt: "شغل دراسة سريان الأحمال (Load Flow) على الشبكة الحالية وفقاً لمعيار IEEE 3002.7",
        icon: Zap,
        tag: "IEEE 3002.7",
        color: "text-amber-400 bg-amber-500/10 border-amber-500/30",
      },
      {
        id: "arc-flash",
        title: "احسب طاقة الوميض القوسي (Arc Flash)",
        subtitle: "تحديد حدود الأمان ومستويات PPE ومخاطر القوس وفق IEEE 1584",
        prompt: "احسب طاقة الوميض القوسي وحدود الأمان (Arc Flash IEEE 1584) للمشروع",
        icon: Flame,
        tag: "IEEE 1584",
        color: "text-orange-400 bg-orange-500/10 border-orange-500/30",
      },
      {
        id: "short-circuit",
        title: "احسب تيار القصر الأقصى (Short Circuit)",
        subtitle: "حساب سعة القصر ثلاثية الأوجه وفق IEC 60909",
        prompt: "احسب تيار القصر ثلاثي الأوجه (Short Circuit IEC 60909) لكافة قضبان التوزيع",
        icon: Activity,
        tag: "IEC 60909",
        color: "text-rose-400 bg-rose-500/10 border-rose-500/30",
      },
      {
        id: "coordination",
        title: "تنسيق قواطع الحماية (TCC Curves)",
        subtitle: "التحقق من انتقائية القواطع والمرحلات وفق IEC 60255",
        prompt: "تحقق من التنسيق الزمني وقواطع الحماية ومطابقة المنحنيات (TCC) وفق IEC 60255",
        icon: ShieldAlert,
        tag: "IEC 60255",
        color: "text-emerald-400 bg-emerald-500/10 border-emerald-500/30",
      },
      {
        id: "upload-grid",
        title: "ارفع ملف شبكة كهربائية للمعاينة",
        subtitle: "معاينة وتحليل ملف التوزيع الأحادي One-Line Diagram",
        prompt: "معاينة وتحليل ملف شبكة كهربائية ومطابقته",
        icon: Upload,
        tag: "ONE-LINE",
        color: "text-cyan-400 bg-cyan-500/10 border-cyan-500/30",
      },
      {
        id: "summarize-results",
        title: "لخص أحدث نتائج الدراسات والتجاوزات",
        subtitle: "استخراج تقرير الحالات الحرجة وتجاوزات الجهد والحمل",
        prompt: "لخص أحدث نتائج الدراسات المكتملة وتجاوزات الحدود المسموحة",
        icon: BarChart3,
        tag: "SUMMARY",
        color: "text-purple-400 bg-purple-500/10 border-purple-500/30",
      },
    ];

    return (
      <div className="flex-1 flex flex-col items-center justify-center p-6 max-w-4xl mx-auto w-full select-none" data-testid="chat-empty-state">
        <div className="text-center mb-6 space-y-2">
          <div className="w-12 h-12 rounded-2xl bg-brand-500/10 border border-brand-500/30 text-brand-400 flex items-center justify-center mx-auto shadow-lg shadow-brand-500/5">
            <Sparkles className="w-6 h-6 animate-pulse" />
          </div>
          <h2 className="text-base font-semibold text-slate-100">
            {t("chat.workspace", "مساحة العمل الهندسية الذكية — AhmedETAP AI")}
          </h2>
          <p className="text-xs text-slate-400 max-w-md mx-auto">
            {t("chat.suggestionsTitle", "اختر إحدى الدراسات الجاهزة بضغطة واحدة للبدء، أو اكتب سؤالك الهندسي:")}
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 w-full">
          {suggestions.map((card) => {
            const Icon = card.icon;
            return (
              <button
                key={card.id}
                type="button"
                disabled={isStreaming}
                onClick={() => void sendMessage(card.prompt)}
                data-testid={`suggestion-card-${card.id}`}
                className={cn(
                  "flex items-start gap-3 p-3.5 rounded-xl border text-left transition-all group",
                  "bg-[#151A22] border-[#2A3441] hover:border-brand-500/50 hover:bg-[#1B222D]",
                  "active:scale-[0.99] cursor-pointer shadow-sm hover:shadow-md",
                  isStreaming && "opacity-50 cursor-not-allowed"
                )}
              >
                <div className={cn("w-9 h-9 rounded-lg border flex items-center justify-center shrink-0 mt-0.5 transition-transform group-hover:scale-105", card.color)}>
                  <Icon className="w-4 h-4" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2 mb-1">
                    <span className="text-xs font-semibold text-slate-200 group-hover:text-white truncate">
                      {card.title}
                    </span>
                    <span className="text-[9px] px-1.5 py-0.5 rounded bg-[#202734] border border-[#2E3B4D] font-mono text-slate-400 shrink-0">
                      {card.tag}
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-400 group-hover:text-slate-300 leading-relaxed line-clamp-2">
                    {card.subtitle}
                  </p>
                </div>
              </button>
            );
          })}
        </div>
      </div>
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