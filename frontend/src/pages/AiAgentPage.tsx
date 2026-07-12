/**
 * AiAgentPage.tsx — AI Engineering Agent (3-column chat)
 *
 * V8.1 Screen 8: Per Stitch-Ready UI Prompt
 * Left: Context & Suggestions | Center: Chat | Right: Tools & History
 *
 * Status: Placeholder — full chat implementation with LLM integration pending.
 * Uses backend POST /api/v1/ai/chat endpoint.
 */
import { BrainCircuit, Send, Paperclip, Mic } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";

const quickActions = [
	"Check NFPA",
	"Calculate battery",
	"Optimize routing",
	"SOLAS review",
	"Generate report",
	"Find violations",
];

const exampleConversation = [
	{
		role: "user",
		text: "Check if my vessel's accommodation detection meets SOLAS",
	},
	{
		role: "agent",
		text: "Analyzing accommodation spaces per SOLAS §9.2.2.2.1...\n\n✓ Smoke detectors mandatory\n✓ Spacing ≤11m from bulkhead\n✓ Spacing ≤22m between detectors\n✓ All 47 rooms compliant\n\nNo violations found. 2 minor recommendations available.",
	},
];

export function AiAgentPage() {
	const [input, setInput] = useState("");

	return (
		<div className="flex-1 flex overflow-hidden">
			{/* Left column — Context & Suggestions */}
			<aside className="w-[280px] border-r border-[#334155] bg-[#1E293B] p-4 overflow-y-auto">
				<div className="mb-6">
					<h3 className="text-caption text-slate-500 mb-3">Current Context</h3>
					<div className="space-y-1 text-sm">
						<div className="flex justify-between">
							<span className="text-slate-400">Project</span>
							<span className="text-white">Office Complex B-12</span>
						</div>
						<div className="flex justify-between">
							<span className="text-slate-400">Standard</span>
							<span className="text-white">NFPA 72-2022</span>
						</div>
						<div className="flex justify-between">
							<span className="text-slate-400">Active Room</span>
							<span className="text-[#38BDF8]">R-205</span>
						</div>
					</div>
				</div>

				<div className="mb-6">
					<h3 className="text-caption text-slate-500 mb-3 flex items-center gap-2">
						<BrainCircuit className="h-3 w-3 text-[#A78BFA]" />
						Proactive Suggestions
					</h3>
					<div className="space-y-2">
						<div className="border-l-2 border-[#E84040] pl-3 py-1">
							<p className="text-xs font-medium text-[#E84040]">CRITICAL</p>
							<p className="text-xs text-slate-300 mt-0.5">Pump room detection non-compliant</p>
							<p className="text-[10px] text-slate-500 mt-1">SOLAS §11.6.3.2 requires flame detectors</p>
						</div>
						<div className="border-l-2 border-[#F59E0B] pl-3 py-1">
							<p className="text-xs font-medium text-[#F59E0B]">WARNING</p>
							<p className="text-xs text-slate-300 mt-0.5">Battery calculation may be incorrect</p>
						</div>
						<div className="border-l-2 border-[#38BDF8] pl-3 py-1">
							<p className="text-xs font-medium text-[#38BDF8]">INFO</p>
							<p className="text-xs text-slate-300 mt-0.5">Cable routing optimization available (18%)</p>
						</div>
					</div>
				</div>
			</aside>

			{/* Center column — Chat */}
			<div className="flex-1 flex flex-col bg-[#0F172A]">
				<div className="flex-1 overflow-y-auto p-6 space-y-4">
					{exampleConversation.map((msg, i) => (
						<div
							key={i}
							className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
						>
							<div
								className={`max-w-[70%] rounded-lg p-3 text-sm whitespace-pre-line ${
									msg.role === "user"
										? "bg-[#A78BFA]/10 border-r-2 border-[#A78BFA] text-white"
										: "bg-[#1E293B] border border-[#334155] text-slate-200"
								}`}
							>
								{msg.text}
							</div>
						</div>
					))}
				</div>

				{/* Quick actions */}
				<div className="px-4 py-2 border-t border-[#334155] flex gap-2 overflow-x-auto">
					{quickActions.map((action) => (
						<button
							key={action}
							onClick={() => setInput(action)}
							className="shrink-0 px-3 py-1 text-xs bg-[#1E293B] border border-[#334155] rounded-full text-slate-300 hover:bg-[#334155] transition-colors"
						>
							{action}
						</button>
					))}
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
							placeholder="Ask BAZspark about NFPA 72, SOLAS, voltage drop, battery sizing..."
							className="flex-1 bg-[#1E293B] border border-[#334155] rounded-md px-3 py-2 text-sm text-white placeholder:text-slate-500 resize-none focus:outline-none focus:border-[#38BDF8]"
							rows={2}
						/>
						<button className="p-2 text-slate-400 hover:text-white">
							<Mic className="h-4 w-4" />
						</button>
						<Button className="bg-[#A78BFA] hover:bg-[#A78BFA]/80 text-white rounded-full p-2 h-10 w-10">
							<Send className="h-4 w-4" />
						</Button>
					</div>
					<p className="text-[10px] text-slate-500 italic mt-2 text-center">
						BAZspark AI may make mistakes. Always verify with licensed FPE.
					</p>
				</div>
			</div>

			{/* Right column — Tools & History */}
			<aside className="w-[260px] border-l border-[#334155] bg-[#1E293B] p-4 overflow-y-auto">
				<h3 className="text-caption text-slate-500 mb-3">Active Tools</h3>
				<div className="space-y-2 mb-6">
					{["NFPA Calculator", "Project Scanner", "Coverage Verifier", "Report Generator", "Cable Router"].map((tool) => (
						<label key={tool} className="flex items-center gap-2 text-sm text-slate-300">
							<input type="checkbox" defaultChecked className="rounded" />
							{tool}
						</label>
					))}
				</div>

				<h3 className="text-caption text-slate-500 mb-3">Session History</h3>
				<div className="space-y-1">
					{["Battery sizing §10.6.7", "SOLAS review VFZ-03", "R-205 violation fix"].map((session) => (
						<button key={session} className="block w-full text-left px-2 py-1.5 text-xs text-slate-400 hover:bg-[#334155] hover:text-white rounded transition-colors">
							{session}
						</button>
					))}
				</div>
			</aside>
		</div>
	);
}
