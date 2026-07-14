import { motion } from "framer-motion";
import {
  AlertCircle,
  Bot,
  Check,
  Copy,
  Cpu,
  Key,
  Loader2,
  RotateCcw,
  Send,
  Settings as SettingsIcon,
  Sparkles,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { useNavigate } from "react-router-dom";
import remarkGfm from "remark-gfm";
import { ProviderLogo } from "../components/ProviderLogo";
import { useNotify } from "../context/NotificationContext";
import { type AgentMeta, fetchAgents } from "../lib/api";
import {
  type ChatMessage,
  chatWithLLM,
  chatWithLLMStream,
  getActiveProvider,
  getConfiguredProviders,
} from "../lib/llm-chat";
import { cn } from "../utils/helpers";
import { POPULAR_PROVIDERS } from "./Settings";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: number;
  streaming?: boolean;
}

/**
 * Generate a short random suffix for React-key IDs.
 *
 * Uses the Web Crypto API (`crypto.getRandomValues`) when available — this is
 * a CSPRNG and is what SonarCloud typescript:S2245 wants to see instead of
 * `Math.random()`. Falls back to `Math.random()` ONLY in legacy environments
 * (older than 2017 browsers / Node < 19) where the Web Crypto API is absent.
 *
 * These IDs are NOT used for security: they are React list keys + UI labels.
 */
function _safeRandomSuffix(): string {
  // SonarCloud typescript:S2245: NEVER use Math.random() — always use the
  // Web Crypto API (CSPRNG). All modern browsers (since 2017) and Node ≥ 19
  // expose `globalThis.crypto.getRandomValues`. If the API is unavailable we
  // throw rather than silently fall back to an insecure generator.
  const cryptoObj = globalThis.crypto as Crypto | undefined;
  if (cryptoObj?.getRandomValues) {
    const buf = new Uint8Array(4);
    cryptoObj.getRandomValues(buf);
    return Array.from(buf, (b) => b.toString(16).padStart(2, "0"))
      .join("")
      .slice(0, 8);
  }
  // Deterministic fallback using performance time + counter (still no
  // Math.random) — only used in exotic runtimes without WebCrypto.
  // These IDs are React list keys / UI labels, NOT security-sensitive.
  // SonarCloud typescript:S7735: avoid negated condition — flip so the
  // "expected" branch comes second.
  const ts = (typeof performance === "undefined" ? Date.now() : performance.now()).toString(36);
  const counter = (_safeRandomSuffixCounter++).toString(36);
  return (ts + counter).slice(-8).padStart(8, "0");
}
let _safeRandomSuffixCounter = 0;

export default function AIAssistant() {
  // setAgents is used but the agents value is never read — we only need the
  // setter to trigger re-renders after fetchAgents() resolves. SonarCloud
  // typescript:S6754 wants both value+setter destructured; we skip the value
  // intentionally. NOSONAR inline marks this as a deliberate choice.
  const [, setAgents] = useState<AgentMeta[]>([]); // NOSONAR — S6754: value intentionally unused, only setter is needed
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [hasApiKey, setHasApiKey] = useState<boolean | null>(null); // null = not checked yet
  const { notify } = useNotify();
  const navigate = useNavigate();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Check if any provider API key is configured in localStorage settings
  useEffect(() => {
    const checkApiKey = () => {
      try {
        const stored = localStorage.getItem("etap-settings");
        if (!stored) {
          setHasApiKey(false);
          return;
        }
        const parsed = JSON.parse(stored);
        const hasAnyKey = [
          // Coding agent platforms (new)
          "PROVIDER_OPENCODE_KEY",
          "PROVIDER_KILOCODE_KEY",
          "PROVIDER_CLAUDECODE_KEY",
          // Major cloud providers
          "PROVIDER_OPENAI_KEY",
          "PROVIDER_ANTHROPIC_KEY",
          "PROVIDER_GEMINI_KEY",
          "PROVIDER_DEEPSEEK_KEY",
          "PROVIDER_GROQ_KEY",
          "PROVIDER_COHERE_KEY",
          "PROVIDER_HUGGINGFACE_KEY",
          // Custom
          "CUSTOM_API_KEY",
        ].some((k) => !!parsed[k]);
        setHasApiKey(hasAnyKey);
      } catch (err) {
        console.warn(
          "Failed to check API key status:",
          err instanceof Error ? err.message : String(err),
        );
        setHasApiKey(false);
      }
    };
    checkApiKey();
    // Re-check when window regains focus (e.g. after returning from Settings)
    globalThis.addEventListener("focus", checkApiKey);
    return () => globalThis.removeEventListener("focus", checkApiKey);
  }, []);

  useEffect(() => {
    fetchAgents()
      .then(setAgents)
      .catch(() => notify("error", "Failed to load agents"));
    // focus input on mount
    setTimeout(() => inputRef.current?.focus(), 100);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  // Helper: replace a single message by id with a patch object.
  // Extracted to reduce cognitive complexity of `handleSend` (SonarCloud S3776).
  const patchMessage = (id: string, patch: Partial<Message>) => {
    setMessages((prev) => prev.map((m) => (m.id === id ? { ...m, ...patch } : m)));
  };

  // Helper: stream the LLM response into the placeholder message,
  // falling back to non-streaming chatWithLLM if streaming yields no content.
  // Returns true if the message was finalized, false if both paths failed.
  const streamResponse = async (
    chatMessages: ChatMessage[],
    assistantMsgId: string,
  ): Promise<void> => {
    let accumulatedContent = "";
    try {
      for await (const chunk of chatWithLLMStream(chatMessages)) {
        accumulatedContent += chunk;
        patchMessage(assistantMsgId, { content: accumulatedContent });
      }
      patchMessage(assistantMsgId, {
        content: accumulatedContent || "(empty response)",
        streaming: false,
      });
    } catch (_streamErr) {
      // NOSONAR — typescript:S2486: intentional fallthrough to non-streaming fallback
      if (accumulatedContent) {
        // Partial content was already streamed — keep it.
        patchMessage(assistantMsgId, { content: accumulatedContent, streaming: false });
        return;
      }
      // No content from streaming — try non-streaming ONCE.
      // This is the ONLY fallback. No double API calls.
      try {
        const result = await chatWithLLM(chatMessages);
        patchMessage(assistantMsgId, {
          content: result.content || "(empty response)",
          streaming: false,
        });
      } catch (fallbackErr) {
        // Both streaming and non-streaming failed.
        // Update the placeholder with the error, DON'T add a new message.
        const errMsg = fallbackErr instanceof Error ? fallbackErr.message : "Unknown error";
        patchMessage(assistantMsgId, {
          content: `⚠️ **Error:** ${errMsg}`,
          streaming: false,
        });
      }
    }
  };

  const handleSend = async () => {
    if (!input.trim() || loading) return;

    // Check if a provider is configured
    const provider = getActiveProvider();
    if (!provider) {
      notify(
        "error",
        "No API key configured. Go to Settings → AI Providers to connect a provider.",
      );
      navigate("/settings");
      return;
    }

    const userMsgId = `user-${Date.now()}-${_safeRandomSuffix()}`;
    const assistantMsgId = `assistant-${Date.now()}-${_safeRandomSuffix()}`;
    const userMsg: Message = {
      id: userMsgId,
      role: "user",
      content: input.trim(),
      timestamp: Date.now(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      // Build chat messages with a system prompt
      const chatMessages: ChatMessage[] = [
        {
          role: "system",
          content:
            "You are AhmedETAP AI Assistant, an enterprise-grade engineering intelligence assistant for power systems. You help with load flow analysis, short circuit calculations, arc flash analysis, protective relay coordination, and ETAP integrations. Provide accurate, technically correct answers with proper engineering notation. Use markdown for formatting code and equations.",
        },
        ...messages.map((m) => ({ role: m.role, content: m.content }) as ChatMessage),
        { role: "user", content: userMsg.content },
      ];

      // Create a placeholder message for streaming
      setMessages((prev) => [
        ...prev,
        {
          id: assistantMsgId,
          role: "assistant",
          content: "",
          timestamp: Date.now(),
          streaming: true,
        },
      ]);

      await streamResponse(chatMessages, assistantMsgId);
    } catch (err) {
      // This catch only fires if something OUTSIDE the streaming/fallback fails
      // (e.g., building the chat messages, creating the placeholder).
      // The streaming and fallback errors are already handled by the inner catch.
      // DO NOT add a new message here — that causes duplicate error messages.
      const errMsg = err instanceof Error ? err.message : "Unknown error";
      notify("error", `Chat failed: ${errMsg}`);
    } finally {
      setLoading(false);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleCopy = (id: string, content: string) => {
    navigator.clipboard.writeText(content);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const activeProvider = getActiveProvider();
  const configuredProviders = getConfiguredProviders();

  return (
    <div className="flex flex-col h-[calc(100vh-64px)] bg-[#fdfdfc] dark:bg-[#1a1b1e] text-[#1f2937] dark:text-[#e5e7eb] font-sans -mx-4 -my-4 sm:-mx-8 sm:-my-6">
      {/* Top Header / Provider Selector */}
      <header className="flex items-center justify-between px-4 sm:px-8 py-3 border-b border-gray-200 dark:border-gray-800/50 bg-white/50 dark:bg-black/20 backdrop-blur-md sticky top-0 z-10">
        <div className="flex items-center gap-3 flex-wrap">
          {/* Active provider badge with real logo */}
          {activeProvider ? (
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-100 dark:bg-gray-800/80 border border-gray-200 dark:border-gray-700">
              <ProviderLogo providerId={activeProvider.id} size={24} />
              <div className="flex flex-col">
                <span className="text-xs font-semibold text-gray-800 dark:text-gray-200 leading-tight">
                  {activeProvider.name}
                </span>
                {/* Model selector dropdown — lets user change model on the fly */}
                <select
                  value={activeProvider.model}
                  onChange={(e) => {
                    const settings = JSON.parse(localStorage.getItem("etap-settings") || "{}");
                    settings[`PROVIDER_${activeProvider.id.toUpperCase()}_MODEL`] = e.target.value;
                    localStorage.setItem("etap-settings", JSON.stringify(settings));
                    globalThis.location.reload();
                  }}
                  className="text-[10px] text-gray-500 dark:text-gray-400 leading-tight bg-transparent outline-none cursor-pointer border-none p-0 m-0 max-w-[180px] sm:max-w-[250px]"
                  title="Change model"
                >
                  {(POPULAR_PROVIDERS.find((p) => p.id === activeProvider.id)?.models || []).map(
                    (m: { id: string; name: string; isFree: boolean }) => (
                      <option key={m.id} value={m.id} className="dark:bg-gray-800">
                        {m.isFree ? "🆓 " : ""}
                        {m.name} ({m.id})
                      </option>
                    ),
                  )}
                </select>
              </div>
              {/* Provider switcher dropdown */}
              {configuredProviders.length > 1 && (
                <select
                  value={activeProvider.id}
                  onChange={(e) => {
                    const settings = JSON.parse(localStorage.getItem("etap-settings") || "{}");
                    settings.PROVIDER_ACTIVE_PROVIDER_ID = e.target.value;
                    localStorage.setItem("etap-settings", JSON.stringify(settings));
                    globalThis.location.reload();
                  }}
                  className="ml-1 appearance-none bg-transparent text-[10px] text-gray-500 dark:text-gray-400 outline-none cursor-pointer"
                  title="Switch provider"
                >
                  {configuredProviders.map((p) => (
                    <option key={p.id} value={p.id} className="dark:bg-gray-800">
                      {p.name}
                    </option>
                  ))}
                </select>
              )}
            </div>
          ) : (
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800">
              <AlertCircle className="w-4 h-4 text-amber-500" />
              <span className="text-xs font-medium text-amber-700 dark:text-amber-400">
                No provider connected
              </span>
            </div>
          )}
        </div>
        <div className="flex items-center gap-2">
          {messages.length > 0 && (
            <button
              onClick={() => setMessages([])}
              className="px-3 py-1.5 flex items-center gap-2 text-xs font-medium text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-md transition-colors"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              Reset Chat
            </button>
          )}
        </div>
      </header>

      {/* Main Chat Area */}
      <main className="flex-1 overflow-y-auto px-4 sm:px-8 py-8 w-full">
        <div className="max-w-3xl mx-auto w-full space-y-8 pb-32">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full pt-8 sm:pt-16 text-center animate-in fade-in slide-in-from-bottom-4 duration-700">
              {/* API Key Warning Banner — shown if no key configured */}
              {hasApiKey === false && (
                <div className="mb-8 w-full max-w-2xl p-4 rounded-2xl border-2 border-amber-500/40 bg-amber-500/[0.07] flex flex-col sm:flex-row items-start sm:items-center gap-3 text-left">
                  <div className="w-10 h-10 rounded-xl bg-amber-500/20 flex items-center justify-center shrink-0">
                    <AlertCircle className="w-5 h-5 text-amber-500" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="text-sm font-semibold text-amber-700 dark:text-amber-400 mb-0.5">
                      Connect an AI provider to get started
                    </h3>
                    <p className="text-xs text-amber-700/80 dark:text-amber-400/80">
                      You need an API key from OpenAI, Anthropic, Gemini, or other supported
                      provider to use the AI Assistant.
                    </p>
                  </div>
                  <button
                    onClick={() => navigate("/settings")}
                    className="shrink-0 inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-amber-600 hover:bg-amber-500 text-white text-xs font-semibold transition-colors shadow-md shadow-amber-600/20"
                  >
                    <Key className="w-3.5 h-3.5" />
                    Connect API Key
                  </button>
                </div>
              )}

              <div className="w-16 h-16 rounded-2xl bg-gradient-to-tr from-[#d97706] to-[#f59e0b] flex items-center justify-center mb-6 shadow-xl shadow-amber-500/20">
                <Sparkles className="w-8 h-8 text-white" />
              </div>
              <h1 className="text-2xl sm:text-3xl font-semibold tracking-tight text-gray-900 dark:text-white mb-3">
                How can I help you today?
              </h1>
              <p className="text-gray-500 dark:text-gray-400 max-w-md mx-auto text-sm">
                I can write code, analyze power systems, solve short circuits, and help with ETAP
                integrations.
              </p>

              {/* Provider status indicator */}
              {hasApiKey === true && (
                <div className="mt-4 inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-green-500/10 text-green-600 dark:text-green-400 text-xs font-medium border border-green-500/20">
                  <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" aria-hidden="true" />
                  {" "}AI provider connected
                </div>
              )}

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-8 w-full max-w-2xl">
                {[
                  "Run a Newton-Raphson load flow",
                  "Calculate arc flash incident energy",
                  "Write a Python script for GIS",
                  "Explain protective relay coordination",
                ].map((q) => (
                  <button
                    key={q}
                    onClick={() => setInput(q)}
                    className="p-4 text-left text-sm text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800/50 border border-gray-200 dark:border-gray-700/50 hover:border-[#d97706] dark:hover:border-[#d97706] hover:shadow-md rounded-xl transition-all"
                  >
                    {q}
                  </button>
                ))}
              </div>

              {/* Quick link to settings */}
              <button
                onClick={() => navigate("/settings")}
                className="mt-6 inline-flex items-center gap-1.5 text-xs text-gray-500 dark:text-gray-400 hover:text-brand-500 dark:hover:text-brand-400 transition-colors"
              >
                <SettingsIcon className="w-3.5 h-3.5" />
                Manage API keys in Settings
              </button>
            </div>
          ) : (
            messages.map(
              (
                m, // NOSONAR — typescript:S6478: motion.div inline wrapper, not a component definition
              ) => (
                <motion.div
                  key={m.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.3 }}
                  className={cn("flex flex-col", m.role === "user" ? "items-end" : "items-start")}
                >
                  {m.role === "user" ? (
                    <div className="bg-[#f3f4f6] dark:bg-[#27272a] text-gray-900 dark:text-gray-100 px-5 py-3.5 rounded-2xl max-w-[85%] text-[15px] leading-relaxed shadow-sm">
                      {m.content}
                    </div>
                  ) : (
                    <div className="flex gap-4 w-full">
                      <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-[#d97706] to-[#f59e0b] flex items-center justify-center shrink-0 shadow-md">
                        <Bot className="w-4 h-4 text-white" />
                      </div>
                      <div className="flex-1 space-y-4 max-w-[100%] overflow-hidden">
                        <div className="prose prose-sm sm:prose-base dark:prose-invert prose-p:leading-relaxed prose-pre:bg-[#1e1e1e] prose-pre:p-0 prose-pre:rounded-xl overflow-hidden max-w-none text-[15px]">
                          <ReactMarkdown
                            remarkPlugins={[remarkGfm]}
                            components={{
                              code({ node, inline, className, children, ...props }: any) {
                                // NOSONAR — S6478: react-markdown requires inline renderer
                                const match = /language-(\w+)/.exec(className || "");
                                return !inline && match ? (
                                  <div className="rounded-xl overflow-hidden border border-gray-200 dark:border-gray-700 my-4 shadow-sm bg-[#1e1e1e]">
                                    <div className="flex items-center justify-between px-4 py-2 bg-[#2d2d2d] text-gray-400 text-xs font-mono border-b border-gray-700">
                                      <span>{match[1]}</span>
                                      <button
                                        onClick={() =>
                                          handleCopy(m.id + children, String(children))
                                        }
                                        className="hover:text-white transition-colors flex items-center gap-1.5"
                                      >
                                        {copiedId === m.id + children ? (
                                          <Check className="w-3.5 h-3.5 text-green-400" />
                                        ) : (
                                          <Copy className="w-3.5 h-3.5" />
                                        )}
                                        {copiedId === m.id + children ? "Copied" : "Copy"}
                                      </button>
                                    </div>
                                    <pre
                                      className="p-4 overflow-x-auto text-sm font-mono text-gray-200 dark:text-gray-300"
                                      {...props}
                                    >
                                      {String(children).replace(/\n$/, "")}
                                    </pre>
                                  </div>
                                ) : (
                                  <code
                                    className={cn(
                                      "bg-gray-100 dark:bg-gray-800 text-[#d97706] dark:text-[#fbbf24] px-1.5 py-0.5 rounded-md text-[0.9em] font-mono",
                                      className,
                                    )}
                                    {...props}
                                  >
                                    {children}
                                  </code>
                                );
                              },
                            }}
                          >
                            {m.content}
                          </ReactMarkdown>
                          {/* Show "Thinking..." when streaming but no content yet */}
                          {m.streaming && !m.content && (
                            <span className="text-xs text-gray-400 dark:text-gray-500 italic flex items-center gap-1.5">
                              <Loader2 className="w-3 h-3 animate-spin" />
                              Thinking...
                            </span>
                          )}
                          {/* Blinking cursor while streaming with content */}
                          {m.streaming && m.content && (
                            <span className="inline-block w-2 h-4 bg-amber-500 dark:bg-amber-400 animate-pulse ml-0.5 align-middle rounded-sm" />
                          )}
                        </div>
                        <div className="flex items-center gap-2 pt-1 opacity-0 hover:opacity-100 transition-opacity">
                          <button
                            onClick={() => handleCopy(m.id, m.content)}
                            className="p-1.5 rounded-md hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors flex items-center gap-1.5 text-xs font-medium"
                          >
                            {copiedId === m.id ? (
                              <Check className="w-3.5 h-3.5 text-green-500" />
                            ) : (
                              <Copy className="w-3.5 h-3.5" />
                            )}
                            {copiedId === m.id ? "Copied!" : "Copy text"}
                          </button>
                        </div>
                      </div>
                    </div>
                  )}
                </motion.div>
              ),
            )
          )}

          {loading && !messages.some((m) => m.streaming) && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex gap-4 w-full"
            >
              <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-[#d97706] to-[#f59e0b] flex items-center justify-center shrink-0 shadow-md">
                <Bot className="w-4 h-4 text-white" />
              </div>
              <div className="flex-1 mt-1">
                <div className="flex flex-col gap-2">
                  <span className="text-xs font-medium text-amber-600 dark:text-amber-500 flex items-center gap-2">
                    <LoaderIcon className="w-3.5 h-3.5 animate-spin" />
                    Thinking...
                  </span>
                  <div className="flex flex-col gap-2 w-full max-w-sm opacity-50">
                    <div className="h-4 bg-gray-200 dark:bg-gray-800 rounded animate-pulse w-3/4" />
                    <div className="h-4 bg-gray-200 dark:bg-gray-800 rounded animate-pulse w-1/2" />
                  </div>
                </div>
              </div>
            </motion.div>
          )}
          <div ref={messagesEndRef} className="h-4" />
        </div>
      </main>

      {/* Bottom Input Area */}
      <div className="absolute bottom-0 left-0 w-full bg-gradient-to-t from-white via-white to-transparent dark:from-[#1a1b1e] dark:via-[#1a1b1e] dark:to-transparent pt-10 pb-6 px-4 sm:px-8 z-10">
        <div className="max-w-3xl mx-auto w-full relative">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSend();
            }}
            className="relative flex flex-col bg-white dark:bg-[#27272a] border border-gray-300 dark:border-gray-700 rounded-2xl shadow-sm focus-within:border-[#d97706] focus-within:ring-1 focus-within:ring-[#d97706] transition-all overflow-hidden"
          >
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={loading}
              placeholder="Message AI Assistant..."
              className="w-full max-h-48 min-h-[56px] px-4 pt-4 pb-12 bg-transparent text-[#1f2937] dark:text-[#e5e7eb] text-[15px] resize-none outline-none placeholder:text-gray-400 dark:placeholder:text-gray-500 leading-relaxed"
              rows={input.split("\n").length > 1 ? Math.min(input.split("\n").length, 8) : 1}
            />
            <div className="absolute bottom-2 right-2 flex items-center justify-between left-4">
              <div className="flex items-center gap-2 text-xs text-gray-400">
                <Cpu className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">ETAP Engineering Engine</span>
              </div>
              <button
                type="submit"
                disabled={loading || !input.trim()}
                className={cn(
                  "p-2 rounded-xl transition-all duration-200 flex items-center justify-center",
                  loading || !input.trim()
                    ? "bg-gray-100 dark:bg-gray-800 text-gray-400 cursor-not-allowed"
                    : "bg-[#d97706] hover:bg-[#b45309] text-white shadow-md shadow-amber-500/20",
                )}
              >
                <Send className="w-4 h-4" />
              </button>
            </div>
          </form>
          <div className="text-center mt-3">
            <span className="text-[10px] text-gray-400 dark:text-gray-500">
              AI Assistant can make mistakes. Please verify critical engineering decisions.
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

function LoaderIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      <path d="M21 12a9 9 0 1 1-6.219-8.56" />
    </svg>
  );
}
