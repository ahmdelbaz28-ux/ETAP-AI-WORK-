/**
 * CircuitsPage.tsx — Circuit Configuration (SLC/NAC)
 *
 * V8.1 Screen 4 (Circuits): Per Stitch-Ready UI Prompt
 * Class A/B circuit design, device per segment, isolator placement.
 *
 * Status: Placeholder — full implementation pending.
 */
import { Zap, ShieldCheck } from "lucide-react";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";

export function CircuitsPage() {
	return (
		<div className="flex-1 overflow-auto p-6">
			<div className="max-w-7xl mx-auto space-y-6">
				<div>
					<h1 className="text-2xl font-bold text-white">Circuits</h1>
					<p className="text-sm text-slate-400 mt-1">
						SLC / NAC · Class A/B · NFPA 72 §12.3.1 Fault Isolation
					</p>
				</div>

				<div className="grid grid-cols-3 gap-4">
					<Card className="bg-[#1E293B] border-[#334155]">
						<CardHeader className="pb-3">
							<CardTitle className="text-white text-base flex items-center gap-2">
								<Zap className="h-4 w-4 text-[#E84040]" />
								SLC Loop 1
							</CardTitle>
						</CardHeader>
						<CardContent className="space-y-1 text-sm">
							<div className="flex justify-between">
								<span className="text-slate-400">Class</span>
								<span className="text-white font-mono">A</span>
							</div>
							<div className="flex justify-between">
								<span className="text-slate-400">Devices</span>
								<span className="text-white font-mono">31 / 318</span>
							</div>
							<div className="flex justify-between">
								<span className="text-slate-400">Isolators</span>
								<span className="text-white font-mono">2</span>
							</div>
						</CardContent>
					</Card>

					<Card className="bg-[#1E293B] border-[#334155]">
						<CardHeader className="pb-3">
							<CardTitle className="text-white text-base flex items-center gap-2">
								<Zap className="h-4 w-4 text-[#38BDF8]" />
								SLC Loop 2
							</CardTitle>
						</CardHeader>
						<CardContent className="space-y-1 text-sm">
							<div className="flex justify-between">
								<span className="text-slate-400">Class</span>
								<span className="text-white font-mono">B</span>
							</div>
							<div className="flex justify-between">
								<span className="text-slate-400">Devices</span>
								<span className="text-white font-mono">142 / 318</span>
							</div>
							<div className="flex justify-between">
								<span className="text-slate-400">Isolators</span>
								<span className="text-white font-mono">5</span>
							</div>
						</CardContent>
					</Card>

					<Card className="bg-[#1E293B] border-[#334155]">
						<CardHeader className="pb-3">
							<CardTitle className="text-white text-base flex items-center gap-2">
								<ShieldCheck className="h-4 w-4 text-[#22C55E]" />
								NAC Circuits
							</CardTitle>
						</CardHeader>
						<CardContent className="space-y-1 text-sm">
							<div className="flex justify-between">
								<span className="text-slate-400">Total NACs</span>
								<span className="text-white font-mono">8</span>
							</div>
							<div className="flex justify-between">
								<span className="text-slate-400">Active</span>
								<span className="text-white font-mono">6</span>
							</div>
							<div className="flex justify-between">
								<span className="text-slate-400">Devices</span>
								<span className="text-white font-mono">47</span>
							</div>
						</CardContent>
					</Card>
				</div>

				<Card className="bg-[#1E293B] border-[#334155]">
					<CardHeader>
						<CardTitle className="text-white">Fault Isolation (NFPA 72 §12.3.1)</CardTitle>
						<CardDescription className="text-slate-400">
							Max 32 devices per segment — isolator placement audit
						</CardDescription>
					</CardHeader>
					<CardContent>
						<div className="bg-[#22C55E]/10 text-[#22C55E] px-4 py-3 rounded-md text-sm font-medium">
							✓ All segments compliant — 32-device limit not exceeded
						</div>
					</CardContent>
				</Card>
			</div>
		</div>
	);
}
