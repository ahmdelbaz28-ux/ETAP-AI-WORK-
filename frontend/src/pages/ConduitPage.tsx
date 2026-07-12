/**
 * ConduitPage.tsx — Conduit Fittings & Fill Calculator
 *
 * V8.1 Screen 4 (Conduit tab): Per Stitch-Ready UI Prompt
 * NEC Chapter 9 fill calculator, bend analysis, fitting schedule.
 *
 * Status: Placeholder — full implementation with NEC tables pending.
 */
import { Activity, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";

export function ConduitPage() {
	return (
		<div className="flex-1 overflow-auto p-6">
			<div className="max-w-7xl mx-auto space-y-6">
				<div>
					<h1 className="text-2xl font-bold text-white">Conduit &amp; Fittings</h1>
					<p className="text-sm text-slate-400 mt-1">
						NEC Chapter 9 · Fill Calculator · Bend Analysis
					</p>
				</div>

				<div className="grid grid-cols-2 gap-6">
					<Card className="bg-[#1E293B] border-[#334155]">
						<CardHeader>
							<CardTitle className="text-white flex items-center gap-2">
								<Activity className="h-5 w-5 text-[#E84040]" />
								NEC Fill Calculator
							</CardTitle>
							<CardDescription className="text-slate-400">
								NEC Ch.9 Table 1 — 40% fill (3+ conductors)
							</CardDescription>
						</CardHeader>
						<CardContent className="space-y-3">
							<div className="flex justify-between text-sm">
								<span className="text-slate-400">Conduit Type</span>
								<span className="text-white font-mono">EMT</span>
							</div>
							<div className="flex justify-between text-sm">
								<span className="text-slate-400">Trade Size</span>
								<span className="text-white font-mono">½"</span>
							</div>
							<div className="flex justify-between text-sm">
								<span className="text-slate-400">Internal Area</span>
								<span className="text-white font-mono">0.304 in²</span>
							</div>
							<div className="flex justify-between text-sm">
								<span className="text-slate-400">Fill %</span>
								<span className="text-[#22C55E] font-mono font-bold">22.4%</span>
							</div>
							<div className="bg-[#22C55E]/10 text-[#22C55E] px-3 py-2 rounded text-sm font-medium">
								✓ COMPLIANT (≤ 40%)
							</div>
						</CardContent>
					</Card>

					<Card className="bg-[#1E293B] border-[#334155]">
						<CardHeader>
							<CardTitle className="text-white flex items-center gap-2">
								<FileText className="h-5 w-5 text-[#38BDF8]" />
								Material Schedule
							</CardTitle>
							<CardDescription className="text-slate-400">
								Fittings BOM with NEC references
							</CardDescription>
						</CardHeader>
						<CardContent>
							<table className="w-full text-sm">
								<thead>
									<tr className="text-slate-400 text-xs border-b border-[#334155]">
										<th className="text-left py-2">Catalog</th>
										<th className="text-left">Desc</th>
										<th className="text-right">Qty</th>
										<th className="text-right">NEC Ref</th>
									</tr>
								</thead>
								<tbody className="text-slate-300">
									<tr className="border-b border-[#334155]/50">
										<td className="py-2 font-mono text-xs">E90-050</td>
										<td className="text-xs">EMT Elbow 90° ½"</td>
										<td className="text-right">4</td>
										<td className="text-right font-mono text-xs">358.24</td>
									</tr>
									<tr className="border-b border-[#334155]/50">
										<td className="py-2 font-mono text-xs">EC-050</td>
										<td className="text-xs">EMT Coupling ½"</td>
										<td className="text-right">12</td>
										<td className="text-right font-mono text-xs">358.42</td>
									</tr>
								</tbody>
							</table>
						</CardContent>
					</Card>
				</div>

				<Button className="bg-[#E84040] hover:bg-[#B91C1C] text-white">
					Export Material Schedule (CSV/PDF/Revit JSON)
				</Button>
			</div>
		</div>
	);
}
