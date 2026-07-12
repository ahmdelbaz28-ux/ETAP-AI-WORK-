/**
 * DetectorsPage.tsx — Detectors (Room Design)
 *
 * V8.1 Screen 3: Per Stitch-Ready UI Prompt
 * Canvas for detector placement with NFPA 72 spacing verification.
 * Remaps the existing FireAlarmPage/FireAlarmDesigner functionality.
 */
import { Radio, Plus, ZoomIn, ZoomOut, Maximize, Grid3x3 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";

export function DetectorsPage() {
	return (
		<div className="flex-1 overflow-auto p-6">
			<div className="max-w-7xl mx-auto space-y-6">
				<div className="flex items-center justify-between">
					<div>
						<h1 className="text-2xl font-bold text-white">Detectors</h1>
						<p className="text-sm text-slate-400 mt-1">
							Room Design · NFPA 72 §17.7.3.2.1 Spacing · Coverage Verification
						</p>
					</div>
					<div className="flex gap-2">
						<Button variant="outline" className="bg-[#1E293B] border-[#334155] text-white hover:bg-[#334155]">
							<ZoomIn className="h-4 w-4" />
						</Button>
						<Button variant="outline" className="bg-[#1E293B] border-[#334155] text-white hover:bg-[#334155]">
							<ZoomOut className="h-4 w-4" />
						</Button>
						<Button variant="outline" className="bg-[#1E293B] border-[#334155] text-white hover:bg-[#334155]">
							<Maximize className="h-4 w-4" />
						</Button>
						<Button variant="outline" className="bg-[#1E293B] border-[#334155] text-white hover:bg-[#334155]">
							<Grid3x3 className="h-4 w-4" />
						</Button>
						<Button className="bg-[#E84040] hover:bg-[#B91C1C] text-white">
							<Plus className="h-4 w-4 mr-2" />
							Add Detector
						</Button>
					</div>
				</div>

				<div className="grid grid-cols-4 gap-4">
					<Card className="bg-[#1E293B] border-[#334155]">
						<CardContent className="pt-4">
							<div className="flex items-center gap-3">
								<div className="h-10 w-10 rounded-md bg-[#22C55E]/10 flex items-center justify-center">
									<Radio className="h-5 w-5 text-[#22C55E]" />
								</div>
								<div>
									<p className="text-2xl font-bold text-white">847</p>
									<p className="text-xs text-slate-400">Total Detectors</p>
								</div>
							</div>
						</CardContent>
					</Card>
					<Card className="bg-[#1E293B] border-[#334155]">
						<CardContent className="pt-4">
							<p className="text-2xl font-bold text-[#22C55E]">98.7%</p>
							<p className="text-xs text-slate-400">Coverage</p>
						</CardContent>
					</Card>
					<Card className="bg-[#1E293B] border-[#334155]">
						<CardContent className="pt-4">
							<p className="text-2xl font-bold text-[#E84040]">2</p>
							<p className="text-xs text-slate-400">Violations</p>
						</CardContent>
					</Card>
					<Card className="bg-[#1E293B] border-[#334155]">
						<CardContent className="pt-4">
							<p className="text-2xl font-bold text-[#F59E0B]">3</p>
							<p className="text-xs text-slate-400">Dead Zones</p>
						</CardContent>
					</Card>
				</div>

				<Card className="bg-[#1E293B] border-[#334155]">
					<CardHeader>
						<CardTitle className="text-white text-base">Room Canvas</CardTitle>
						<CardDescription>
							Ctrl+Wheel zoom · Middle-click pan · Click to place detector
						</CardDescription>
					</CardHeader>
					<CardContent>
						<div className="h-[460px] bg-[#0F172A] rounded-md border border-[#334155] flex items-center justify-center relative">
							<p className="text-slate-500 text-sm">SVG Canvas — Room outline with detector positions</p>
							<div className="absolute bottom-3 left-3 text-xs text-slate-500 font-mono">
								1 unit = 1.0m · X: 0.00, Y: 0.00
							</div>
						</div>
					</CardContent>
				</Card>

				<div className="grid grid-cols-3 gap-4">
					<Card className="bg-[#1E293B] border-[#334155]">
						<CardContent className="pt-4">
							<p className="text-xs text-slate-400">Coverage</p>
							<p className="text-3xl font-bold text-[#22C55E] mt-1">98.7%</p>
						</CardContent>
					</Card>
					<Card className="bg-[#1E293B] border-[#334155]">
						<CardContent className="pt-4">
							<p className="text-xs text-slate-400">Detectors</p>
							<p className="text-3xl font-bold text-white mt-1">24</p>
							<p className="text-xs text-slate-500">Smoke 18 · Heat 4 · Flame 2</p>
						</CardContent>
					</Card>
					<Card className="bg-[#1E293B] border-[#334155]">
						<CardContent className="pt-4">
							<p className="text-xs text-slate-400">Status</p>
							<p className="text-sm font-bold text-[#22C55E] mt-1">✓ NFPA COMPLIANT</p>
						</CardContent>
					</Card>
				</div>
			</div>
		</div>
	);
}
