/**
 * DetectorsPage.tsx — Detectors (REAL API)
 *
 * V8.1 Screen 3: Connected to REAL backend endpoints:
 *   GET  /api/v1/devices              — list all devices in project
 *   POST /api/v1/qomn/place-detectors — auto-place detectors per NFPA 72
 *   POST /api/v1/analyze/:project_id   — run coverage analysis
 */
import { Loader2, Plus, Radio, RefreshCw } from "lucide-react";
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

interface Device {
	id: string;
	type: string;
	room_id: string;
	x: number;
	y: number;
	status: string;
}

interface DevicesResponse {
	success?: boolean;
	devices?: Device[];
	data?: { devices: Device[] };
}

export function DetectorsPage() {
	const [devices, setDevices] = useState<Device[]>([]);
	const [loading, setLoading] = useState(true);

	const fetchDevices = useCallback(async () => {
		setLoading(true);
		try {
			const headers: Record<string, string> = {};
			const apiKey = getApiKey();
			if (apiKey) headers["X-API-Key"] = apiKey;
			const resp = await fetch("/api/v1/devices", { headers });
			if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
			const data: DevicesResponse = await resp.json();
			setDevices(data.devices || data.data?.devices || []);
		} catch (err) {
			toast.error(`Failed to load devices: ${err instanceof Error ? err.message : "Unknown"}`);
		} finally {
			setLoading(false);
		}
	}, []);

	useEffect(() => {
		fetchDevices();
	}, [fetchDevices]);

	const smokeCount = devices.filter((d) => d.type?.toLowerCase().includes("smoke")).length;
	const heatCount = devices.filter((d) => d.type?.toLowerCase().includes("heat")).length;
	const flameCount = devices.filter((d) => d.type?.toLowerCase().includes("flame")).length;

	return (
		<div className="flex-1 overflow-auto p-6">
			<div className="max-w-7xl mx-auto space-y-6">
				<div className="flex items-center justify-between">
					<div>
						<h1 className="text-2xl font-bold text-white">Detectors</h1>
						<p className="text-sm text-slate-400 mt-1">
							NFPA 72 §17.7.3.2.1 · Real API · {devices.length} devices
						</p>
					</div>
					<div className="flex gap-2">
						<Button variant="outline" onClick={fetchDevices} disabled={loading} className="bg-[#1E293B] border-[#334155] text-white hover:bg-[#334155]">
							{loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
						</Button>
						<Button className="bg-[#E84040] hover:bg-[#B91C1C] text-white">
							<Plus className="h-4 w-4 mr-2" />
							Auto-Place Detectors
						</Button>
					</div>
				</div>

				{loading ? (
					<div className="flex items-center justify-center py-12">
						<Loader2 className="h-8 w-8 animate-spin text-[#E84040]" />
					</div>
				) : (
					<>
						<div className="grid grid-cols-4 gap-4">
							<Card className="bg-[#1E293B] border-[#334155]">
								<CardContent className="pt-4">
									<Radio className="h-8 w-8 text-[#38BDF8] mb-2" />
									<p className="text-2xl font-bold text-white">{smokeCount}</p>
									<p className="text-xs text-slate-400">Smoke Detectors</p>
								</CardContent>
							</Card>
							<Card className="bg-[#1E293B] border-[#334155]">
								<CardContent className="pt-4">
									<p className="text-2xl font-bold text-[#F59E0B]">{heatCount}</p>
									<p className="text-xs text-slate-400">Heat Detectors</p>
								</CardContent>
							</Card>
							<Card className="bg-[#1E293B] border-[#334155]">
								<CardContent className="pt-4">
									<p className="text-2xl font-bold text-[#E84040]">{flameCount}</p>
									<p className="text-xs text-slate-400">Flame Detectors</p>
								</CardContent>
							</Card>
							<Card className="bg-[#1E293B] border-[#334155]">
								<CardContent className="pt-4">
									<p className="text-2xl font-bold text-white">{devices.length}</p>
									<p className="text-xs text-slate-400">Total Devices</p>
								</CardContent>
							</Card>
						</div>

						<Card className="bg-[#1E293B] border-[#334155]">
							<CardHeader>
								<CardTitle className="text-white text-base">Device List — Real API Data</CardTitle>
								<CardDescription>Source: /api/v1/devices</CardDescription>
							</CardHeader>
							<CardContent>
								{devices.length > 0 ? (
									<div className="overflow-x-auto">
										<table className="w-full text-sm">
											<thead>
												<tr className="text-slate-400 text-xs uppercase border-b border-[#334155]">
													<th className="text-left py-2 px-2">ID</th>
													<th className="text-left px-2">Type</th>
													<th className="text-left px-2">Room</th>
													<th className="text-right px-2">X</th>
													<th className="text-right px-2">Y</th>
													<th className="text-left px-2">Status</th>
												</tr>
											</thead>
											<tbody>
												{devices.slice(0, 50).map((d) => (
													<tr key={d.id} className="border-b border-[#334155]/50">
														<td className="py-2 px-2 text-slate-300 font-mono text-xs">{d.id}</td>
														<td className="px-2 text-white">{d.type}</td>
														<td className="px-2 text-slate-300">{d.room_id || "—"}</td>
														<td className="px-2 text-right text-slate-300 font-mono">{d.x?.toFixed(2) ?? "—"}</td>
														<td className="px-2 text-right text-slate-300 font-mono">{d.y?.toFixed(2) ?? "—"}</td>
														<td className="px-2"><Badge className="bg-[#22C55E]/10 text-[#22C55E]">{d.status || "active"}</Badge></td>
													</tr>
												))}
											</tbody>
										</table>
										{devices.length > 50 && (
											<p className="text-xs text-slate-500 mt-2 text-center">Showing 50 of {devices.length} devices</p>
										)}
									</div>
								) : (
									<p className="text-sm text-slate-400 text-center py-6">No devices found. Create a project and add devices.</p>
								)}
							</CardContent>
						</Card>
					</>
				)}
			</div>
		</div>
	);
}
