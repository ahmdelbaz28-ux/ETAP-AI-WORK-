/**
 * CableRoutingPage.tsx — Cable Routing & Conduit Design
 *
 * V8.1 Screen 4: Per Stitch-Ready UI Prompt
 * Tabs: Cable Routing | Conduit Fittings | Fill Calculator | Schedules | BOQ
 *
 * Status: Placeholder — full implementation with NEC calculators pending.
 * This page provides the route target so the sidebar link works.
 */
import { Cable, FileText, Calculator, BarChart3, Package } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";

const tabs = [
	{ id: "routing", label: "Cable Routing", icon: Cable },
	{ id: "conduit", label: "Conduit Fittings", icon: FileText },
	{ id: "fill", label: "Fill Calculator", icon: Calculator },
	{ id: "schedules", label: "Schedules", icon: BarChart3 },
	{ id: "boq", label: "BOQ", icon: Package },
];

export function CableRoutingPage() {
	const [activeTab, setActiveTab] = useState("routing");

	return (
		<div className="flex-1 overflow-auto p-6">
			<div className="max-w-7xl mx-auto space-y-6">
				<div>
					<h1 className="text-2xl font-bold text-white">
						Cable Routing & Conduit Design
					</h1>
					<p className="text-sm text-slate-400 mt-1">
						NEC 2022 · NFPA 72 §12.2 · Class A/B Circuits
					</p>
				</div>

				{/* Tabs */}
				<div className="flex gap-1 border-b border-slate-700">
					{tabs.map((tab) => (
						<button
							key={tab.id}
							onClick={() => setActiveTab(tab.id)}
							className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium transition-colors border-b-2 ${
								activeTab === tab.id
									? "text-[#E84040] border-[#E84040]"
									: "text-slate-400 border-transparent hover:text-white"
							}`}
						>
							<tab.icon className="h-4 w-4" />
							{tab.label}
						</button>
					))}
				</div>

				{/* Content placeholder */}
				<Card className="bg-[#1E293B] border-[#334155]">
					<CardHeader>
						<CardTitle className="text-white flex items-center gap-2">
							<Cable className="h-5 w-5 text-[#E84040]" />
							{tabs.find((t) => t.id === activeTab)?.label}
						</CardTitle>
						<CardDescription className="text-slate-400">
							NEC Chapter 9 Table 8 — Wire resistance &amp; ampacity
						</CardDescription>
					</CardHeader>
					<CardContent className="space-y-4">
						<div className="bg-[#0F172A] rounded-md p-6 border border-[#334155]">
							<h3 className="text-sm font-semibold text-[#38BDF8] mb-3 font-mono">
								Voltage Drop Calculator (NFPA 72 §10.6.4)
							</h3>
							<p className="text-sm text-slate-300 mb-4">
								Formula: V = I × 2 × R × L
							</p>
							<div className="grid grid-cols-4 gap-4 text-sm">
								<div>
									<label className="text-slate-400 text-xs">Current (I)</label>
									<p className="text-white font-mono">0.150 A</p>
								</div>
								<div>
									<label className="text-slate-400 text-xs">Resistance (R)</label>
									<p className="text-white font-mono">10.07 Ω/km</p>
								</div>
								<div>
									<label className="text-slate-400 text-xs">Length (L)</label>
									<p className="text-white font-mono">0.250 km</p>
								</div>
								<div>
									<label className="text-slate-400 text-xs">V_drop</label>
									<p className="text-[#22C55E] font-mono font-bold">0.756V (3.15%)</p>
								</div>
							</div>
							<div className="mt-4 flex items-center gap-2">
								<span className="px-2 py-1 bg-[#22C55E]/10 text-[#22C55E] text-xs rounded font-medium">
									✓ COMPLIANT (≤ 10%)
								</span>
								<span className="text-xs text-slate-500">NEC Ch.9 Table 8 · AWG 14</span>
							</div>
						</div>
						<Button className="bg-[#E84040] hover:bg-[#B91C1C] text-white">
							<Cable className="h-4 w-4 mr-2" />
							Run Route
						</Button>
					</CardContent>
				</Card>
			</div>
		</div>
	);
}
