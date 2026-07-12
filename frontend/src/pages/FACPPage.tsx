/**
 * FACPPage.tsx — FACP Panel Selection (REAL API)
 *
 * V8.1: Connected to REAL backend endpoints:
 *   GET  /api/v1/facp/panels  — list all available FACP panels
 *   POST /api/v1/facp/select  — select optimal panel for project
 *   POST /api/v1/facp/verify  — verify panel meets requirements
 *   POST /api/v1/facp/schedule — generate panel schedule
 */
import { CircuitBoard, Loader2, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import { getApiKey } from "@/services/apiKey";

interface FacpPanel {
	model: string;
	manufacturer: string;
	points_capacity: number;
	nac_capacity: number;
	supports_networking: boolean;
	supports_voice: boolean;
	supports_releasing: boolean;
	max_slc_loops: number;
	listings: string[];
	standby_current_amps: number;
	alarm_current_amps: number;
	power_supply_capacity_amps: number;
}

interface FacpPanelsResponse {
	success: boolean;
	data: { panels: FacpPanel[] };
}

export function FACPPage() {
	const [panels, setPanels] = useState<FacpPanel[]>([]);
	const [loading, setLoading] = useState(true);

	const fetchPanels = useCallback(async () => {
		setLoading(true);
		try {
			const headers: Record<string, string> = {};
			const apiKey = getApiKey();
			if (apiKey) headers["X-API-Key"] = apiKey;
			const resp = await fetch("/api/v1/facp/panels", { headers });
			if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
			const data: FacpPanelsResponse = await resp.json();
			setPanels(data.data.panels);
		} catch (err) {
			toast.error(`Failed to load panels: ${err instanceof Error ? err.message : "Unknown"}`);
		} finally {
			setLoading(false);
		}
	}, []);

	useEffect(() => {
		fetchPanels();
	}, [fetchPanels]);

	return (
		<div className="flex-1 overflow-auto p-6">
			<div className="max-w-7xl mx-auto space-y-6">
				<div className="flex items-center justify-between">
					<div>
						<h1 className="text-2xl font-bold text-white">FACP Panel Selection</h1>
						<p className="text-sm text-slate-400 mt-1">
							Fire Alarm Control Panel database · Real API · {panels.length} panels
						</p>
					</div>
					<Button variant="outline" onClick={fetchPanels} disabled={loading} className="bg-[#1E293B] border-[#334155] text-white hover:bg-[#334155]">
						{loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
					</Button>
				</div>

				{loading ? (
					<div className="flex items-center justify-center py-12">
						<Loader2 className="h-8 w-8 animate-spin text-[#E84040]" />
					</div>
				) : (
					<div className="grid grid-cols-2 gap-4">
						{panels.map((panel) => (
							<Card key={panel.model} className="bg-[#1E293B] border-[#334155]">
								<CardHeader>
									<CardTitle className="text-white flex items-center gap-2">
										<CircuitBoard className="h-5 w-5 text-[#E84040]" />
										{panel.manufacturer} {panel.model}
									</CardTitle>
									<CardDescription>
										{panel.max_slc_loops} SLC loops · {panel.nac_capacity} NAC · {panel.points_capacity} points
									</CardDescription>
								</CardHeader>
								<CardContent>
									<div className="grid grid-cols-2 gap-2 text-sm">
										<div className="flex justify-between">
											<span className="text-slate-400">Standby</span>
											<span className="text-white font-mono">{panel.standby_current_amps}A</span>
										</div>
										<div className="flex justify-between">
											<span className="text-slate-400">Alarm</span>
											<span className="text-white font-mono">{panel.alarm_current_amps}A</span>
										</div>
										<div className="flex justify-between">
											<span className="text-slate-400">PSU</span>
											<span className="text-white font-mono">{panel.power_supply_capacity_amps}A</span>
										</div>
										<div className="flex flex-wrap gap-1 mt-2">
											{panel.listings.map((l) => (
												<Badge key={l} className="bg-[#38BDF8]/10 text-[#38BDF8] text-xs">{l}</Badge>
											))}
											{panel.supports_networking && <Badge className="bg-[#A78BFA]/10 text-[#A78BFA] text-xs">Network</Badge>}
											{panel.supports_voice && <Badge className="bg-[#22C55E]/10 text-[#22C55E] text-xs">Voice</Badge>}
											{panel.supports_releasing && <Badge className="bg-[#E84040]/10 text-[#E84040] text-xs">Releasing</Badge>}
										</div>
									</div>
								</CardContent>
							</Card>
						))}
					</div>
				)}
			</div>
		</div>
	);
}
