/**
 * AuditLogPage.tsx — Audit Log & SHA-256 Chain
 *
 * V8.1 Screen 13 (part 1): Per Stitch-Ready UI Prompt
 * SHA-256 chain verification, filterable event table, export with integrity seal.
 */
import { ShieldCheck, Download, Search } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";

interface AuditEntry {
	timestamp: string;
	event: string;
	rule: string;
	room: string;
	severity: "PASS" | "FAIL" | "WARN";
	hash: string;
}

const sampleEntries: AuditEntry[] = [
	{ timestamp: "2026-07-12 14:32:15", event: "Spacing verified", rule: "NFPA §17.7.3.2.1", room: "R-101", severity: "PASS", hash: "a3f2b9c1d4e5" },
	{ timestamp: "2026-07-12 14:31:42", event: "Wall violation", rule: "NFPA §17.6.3.1.1", room: "R-205", severity: "FAIL", hash: "b4e3c8d2f1a6" },
	{ timestamp: "2026-07-12 14:30:18", event: "Battery sized", rule: "NFPA §10.6.7.1.1", room: "R-101", severity: "PASS", hash: "c5f4d9e3a2b7" },
	{ timestamp: "2026-07-12 14:29:55", event: "Coverage gap", rule: "NFPA §17.6.4.1", room: "R-312", severity: "WARN", hash: "d6a5e0f4b3c8" },
];

const severityColors = {
	PASS: "bg-[#22C55E]/10 text-[#22C55E]",
	FAIL: "bg-[#E84040]/10 text-[#E84040]",
	WARN: "bg-[#F59E0B]/10 text-[#F59E0B]",
};

export function AuditLogPage() {
	const [filter, setFilter] = useState("all");

	return (
		<div className="flex-1 overflow-auto p-6">
			<div className="max-w-7xl mx-auto space-y-6">
				<div className="flex items-center justify-between">
					<div>
						<h1 className="text-2xl font-bold text-white">Audit Log</h1>
						<p className="text-sm text-slate-400 mt-1">
							SHA-256 chain verification · Tamper-evident event log
						</p>
					</div>
					<Button className="bg-[#E84040] hover:bg-[#B91C1C] text-white">
						<Download className="h-4 w-4 mr-2" />
						Export Audit Chain
					</Button>
				</div>

				{/* Chain integrity status */}
				<Card className="bg-[#1E293B] border-[#334155]">
					<CardContent className="pt-6">
						<div className="flex items-center gap-3">
							<ShieldCheck className="h-8 w-8 text-[#22C55E]" />
							<div>
								<p className="text-white font-semibold">Chain Integrity: VERIFIED ✓</p>
								<p className="text-sm text-slate-400">
									847 entries · SHA-256 sealed · Last verified 2s ago
								</p>
							</div>
						</div>
					</CardContent>
				</Card>

				{/* Filters */}
				<div className="flex items-center gap-2">
					<div className="relative flex-1 max-w-md">
						<Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500" />
						<input
							type="text"
							placeholder="Search events, rules, rooms..."
							className="w-full pl-10 pr-3 py-2 bg-[#1E293B] border border-[#334155] rounded-md text-sm text-white placeholder:text-slate-500 focus:outline-none focus:border-[#38BDF8]"
						/>
					</div>
					{["all", "fired", "violations", "NFPA", "SOLAS"].map((f) => (
						<button
							key={f}
							onClick={() => setFilter(f)}
							className={`px-3 py-1.5 text-xs rounded-md transition-colors ${
								filter === f
									? "bg-[#E84040] text-white"
									: "bg-[#1E293B] text-slate-400 hover:text-white"
							}`}
						>
							{f.charAt(0).toUpperCase() + f.slice(1)}
						</button>
					))}
				</div>

				{/* Audit table */}
				<Card className="bg-[#1E293B] border-[#334155]">
					<div className="overflow-x-auto">
						<table className="w-full text-sm">
							<thead>
								<tr className="text-slate-400 text-xs uppercase border-b border-[#334155]">
									<th className="text-left px-4 py-3">Timestamp</th>
									<th className="text-left">Event</th>
									<th className="text-left">Rule</th>
									<th className="text-left">Room/Zone</th>
									<th className="text-left">Severity</th>
									<th className="text-left">Hash</th>
								</tr>
							</thead>
							<tbody>
								{sampleEntries.map((entry, i) => (
									<tr key={i} className="border-b border-[#334155]/50 hover:bg-[#334155]/30">
										<td className="px-4 py-3 text-slate-300 font-mono text-xs">{entry.timestamp}</td>
										<td className="text-white">{entry.event}</td>
										<td className="text-[#38BDF8] font-mono text-xs">{entry.rule}</td>
										<td className="text-slate-300">{entry.room}</td>
										<td>
											<span className={`px-2 py-0.5 rounded text-xs font-medium ${severityColors[entry.severity]}`}>
												{entry.severity}
											</span>
										</td>
										<td className="text-slate-500 font-mono text-xs">{entry.hash}</td>
									</tr>
								))}
							</tbody>
						</table>
					</div>
				</Card>
			</div>
		</div>
	);
}
