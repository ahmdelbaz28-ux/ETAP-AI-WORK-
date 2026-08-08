/**
 * AiAgentPage.tsx — AI Engineering Agent (REAL API)
 *
 * V8.1 Screen 8: Connected to REAL backend endpoint:
 *   POST /api/v1/llm/chat  — sends prompt, receives AI response
 *   GET  /api/v1/llm/health — check LLM provider availability
 *
 * No hardcoded conversation — real chat with the backend LLM.
 */
import { BrainCircuit, Loader2, Mic, Paperclip, Send } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { getApiKey } from "@/services/apiKey";

interface ChatMessage {
	role: "user" | "agent";
	text: string;
	timestamp: string;
}

interface LlmHealth {
	success: boolean;
	data: {
		available: boolean;
		primary: {
			name: string;
			available: boolean;
			base_url: string;
			model: string;
		};
		fallback: {
			name: string;
			enabled: boolean;
			available: boolean;
		};
		timeout_s: number;
		max_tokens: number;
	};
}

const API_BASE = "/api/v1";

const quickActions = [
	"Check NFPA 72 spacing for smoke detectors",
	"Calculate battery capacity for 24h standby",
	"Explain voltage drop requirements",
	"SOLAS accommodation detection rules",
	"Find violations in R-205",
];

export function AiAgentPage() {
	const [messages, setMessages] = useState<ChatMessage[]>([]);
	const [input, setInput] = useState("");
	const [loading, setLoading] = useState(false);
	const [health, setHealth] = useState<LlmHealth | null>(null);
	const chatEndRef = useRef<HTMLDivElement>(null);

	const fetchHealth = useCallback(async () => {
		try {
			const headers: Record<string, string> = {};
			const apiKey = getApiKey();
			if (apiKey) headers["X-API-Key"] = apiKey;
			const resp = await fetch(`${API_BASE}/llm/health`, { headers });
			if (resp.ok) {
				const data = await resp.json();
				setHealth(data);
			}
		} catch {
			// Silent — health check is best-effort
		}
	}, []);

	useEffect(() => {
		fetchHealth();
	}, [fetchHealth]);

	useEffect(() => {
		chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
	}, [messages]);

	const sendMessage = async (promptText?: string) => {
		const prompt = promptText || input.trim();
		if (!prompt || loading) return;

		const userMsg: ChatMessage = {
			role: "user",
			text: prompt,
			timestamp: new Date().toISOString(),
		};
		setMessages((prev) => [...prev, userMsg]);
		setInput("");
		setLoading(true);

		try {
			const headers: Record<string, string> = {
				"Content-Type": "application/json",
			};
			const apiKey = getApiKey();
			if (apiKey) headers["X-API-Key"] = apiKey;

			const resp = await fetch(`${API_BASE}/llm/chat`, {
				method: "POST",
				headers,
				body: JSON.stringify({
					prompt,
					system: "You are BAZspark AI, a fire safety engineering assistant. Answer questions about NFPA 72, SOLAS, IMO, NEC standards. Be precise and cite section numbers.",
					temperature: 0.1,
				}),
			});

			if (!resp.ok) {
				const errBody = await resp.json().catch(() => ({}));
				throw new Error(errBody?.detail?.[0]?.msg || `HTTP ${resp.status}`);
			}

			const data = await resp.json();
			const agentText =
				data.response || data.content || data.message || JSON.stringify(data);

			const agentMsg: ChatMessage = {
				role: "agent",
				text: typeof agentText === "string" ? agentText : JSON.stringify(agentText, null, 2),
				timestamp: new Date().toISOString(),
			};
			setMessages((prev) => [...prev, agentMsg]);
		} catch (err) {
			const errMsg: ChatMessage = {
				role: "agent",
				text: `⚠️ Error: ${err instanceof Error ? err.message : "Unknown error"}.\n\nCheck that the LLM provider is configured (ZENMUX_API_KEY env var).`,
				timestamp: new Date().toISOString(),
			};
			setMessages((prev) => [...prev, errMsg]);
			toast.error(`LLM request failed`);
		} finally {
			setLoading(false);
		}
	};

	return (
		<div className="flex-1 flex overflow-hidden">
			{/* Left column — Context & LLM Status */}
			<aside className="w-[280px] border-r border-[#334155] bg-[#1E293B] p-4 overflow-y-auto shrink-0">
				<h3 className="text-caption text-slate-500 mb-3">LLM Provider Status</h3>
				{health ? (
					<div className="space-y-2 mb-6">
						<div className="flex items-center gap-2">
							<span
								className={`h-2 w-2 rounded-full ${
									health.data.available ? "bg-[#22C55E]" : "bg-[#E84040]"
								}`}
							/>
							<span className="text-sm text-white">
								{health.data.available ? "Available" : "Unavailable"}
							</span>
						</div>
						<div className="text-xs text-slate-400 space-y-1">
							<p>Primary: {health.data.primary.name}</p>
							<p>Model: {health.data.primary.model}</p>
							<p>Max tokens: {health.data.max_tokens}</p>
						</div>
					</div>
				) : (
					<p className="text-xs text-slate-500 mb-6">Checking status...</p>
				)}

				<h3 className="text-caption text-slate-500 mb-3 flex items-center gap-2">
					<BrainCircuit className="h-3 w-3 text-[#A78BFA]" />
					Quick Actions
				</h3>
				<div className="space-y-1.5">
					{quickActions.map((action) => (
						<button
							key={action}
							onClick={() => sendMessage(action)}
							disabled={loading}
							className="block w-full text-left px-2 py-1.5 text-xs text-slate-300 hover:bg-[#334155] hover:text-white rounded transition-colors disabled:opacity-50"
						>
							{action}
						</button>
					))}
				</div>
			</aside>

			{/* Center column — Chat */}
			<div className="flex-1 flex flex-col bg-[#0F172A] min-w-0">
				<div className="flex-1 overflow-y-auto p-6 space-y-4">
					{messages.length === 0 ? (
						<div className="flex flex-col items-center justify-center h-full text-center">
							<div className="h-16 w-16 rounded-full bg-[#A78BFA]/10 flex items-center justify-center mb-4 ai-glow">
								<BrainCircuit className="h-8 w-8 text-[#A78BFA]" />
							</div>
							<h2 className="text-white font-semibold text-lg">BAZspark AI</h2>
							<p className="text-sm text-slate-400 mt-1 max-w-md">
								Ask about NFPA 72, SOLAS, IMO, NEC standards. I can help with
								detector spacing, battery sizing, voltage drop, and compliance.
							</p>
						</div>
					) : (
						messages.map((msg, i) => (
							<div
								key={i}
								className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
							>
								<div
									className={`max-w-[70%] rounded-lg p-3 text-sm whitespace-pre-line ${
										msg.role === "user"
											? "bg-[#A78BFA]/10 border-r-2 border-[#A78BFA] text-white"
											: msg.text.startsWith("⚠️")
												? "bg-[#E84040]/10 border border-[#E84040]/30 text-slate-200"
												: "bg-[#1E293B] border border-[#334155] text-slate-200"
									}`}
								>
									{msg.text}
								</div>
							</div>
						))
					)}
					{loading && (
						<div className="flex justify-start">
							<div className="bg-[#1E293B] border border-[#334155] rounded-lg p-3 flex items-center gap-2">
								<Loader2 className="h-4 w-4 text-[#A78BFA] animate-spin" />
								<span className="text-sm text-slate-400">BAZspark AI is thinking...</span>
							</div>
						</div>
					)}
					<div ref={chatEndRef} />
				</div>

				{/* Input area */}
				<div className="p-4 border-t border-[#334155]">
					<div className="flex items-end gap-2">
						<button className="p-2 text-slate-400 hover:text-white">
							<Paperclip className="h-4 w-4" />
						</button>
						<textarea
							value={input}
							onChange={(e) => setInput(e.target.value)}
							onKeyDown={(e) => {
								if (e.key === "Enter" && !e.shiftKey) {
									e.preventDefault();
									sendMessage();
								}
							}}
							placeholder="Ask BAZspark about NFPA 72, SOLAS, voltage drop, battery sizing..."
							className="flex-1 bg-[#1E293B] border border-[#334155] rounded-md px-3 py-2 text-sm text-white placeholder:text-slate-500 resize-none focus:outline-none focus:border-[#A78BFA]"
							rows={2}
							disabled={loading}
						/>
						<button className="p-2 text-slate-400 hover:text-white">
							<Mic className="h-4 w-4" />
						</button>
						<Button
							onClick={() => sendMessage()}
							disabled={loading || !input.trim()}
							className="bg-[#A78BFA] hover:bg-[#A78BFA]/80 text-white rounded-full p-2 h-10 w-10"
						>
							<Send className="h-4 w-4" />
						</Button>
					</div>
					<p className="text-[10px] text-slate-500 italic mt-2 text-center">
						BAZspark AI may make mistakes. Always verify with licensed FPE.
					</p>
				</div>
			</div>
		</div>
	);
}
