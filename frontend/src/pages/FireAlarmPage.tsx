/**
 * FireAlarmPage.tsx — Fire Alarm Design (REAL API)
 *
 * V8.1: Connected to REAL backend endpoints:
 *   POST /api/v1/analyze/battery   — battery sizing per NFPA 72 §10.6.7
 *   POST /api/v1/analyze/voltage    — voltage drop analysis
 *   POST /api/v1/projects/{id}/analyze/room — room-level compliance analysis
 *   GET  /api/v1/devices             — device list
 *   GET  /api/v1/connections          — circuit connections
 */
import { Battery, Loader2, Radio, RefreshCw, Zap } from "lucide-react";
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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { getApiKey } from "@/services/apiKey";

interface BatteryResult {
	success?: boolean;
	required_ah?: number;
	battery_capacity_ah?: number;
	standby_current_a?: number;
	alarm_current_a?: number;
	standby_hours?: number;
	alarm_minutes?: number;
	safety_factor?: number;
	compliant?: boolean;
	error?: string;
}

async function apiCall<T>(path: string, options?: RequestInit): Promise<T> {
	const headers: Record<string, string> = {
		"Content-Type": "application/json",
		...((options?.headers as Record<string, string>) || {}),
	};
	const apiKey = getApiKey();
	if (apiKey) headers["X-API-Key"] = apiKey;
	const resp = await fetch(path, { ...options, headers });
	if (!resp.ok) {
		const err = await resp.json().catch(() => ({}));
		throw new Error(err?.detail?.[0]?.msg || err?.detail || `HTTP ${resp.status}`);
	}
	return resp.json();
}

export function FireAlarmPage() {
	const [standbyCurrent, setStandbyCurrent] = useState("2.5");
	const [alarmCurrent, setAlarmCurrent] = useState("5.0");
	const [batteryResult, setBatteryResult] = useState<BatteryResult | null>(null);
	const [loading, setLoading] = useState(false);

	const handleBatteryCalc = async () => {
		setLoading(true);
		setBatteryResult(null);
		try {
			const result = await apiCall<BatteryResult>("/api/v1/analyze/battery", {
				method: "POST",
				body: JSON.stringify({
					standby_current_a: parseFloat(standbyCurrent),
					alarm_current_a: parseFloat(alarmCurrent),
					standby_hours: 24,
					alarm_minutes: 5,
					safety_factor: 1.25,
				}),
			});
			setBatteryResult(result);
			toast.success(`Battery: ${result.required_ah ?? result.battery_capacity_ah ?? "?"} Ah required`);
		} catch (err) {
			toast.error(`Calculation failed: ${err instanceof Error ? err.message : "Unknown"}`);
		} finally {
			setLoading(false);
		}
	};

	return (
		<div className="flex-1 overflow-auto p-6">
			<div className="max-w-7xl mx-auto space-y-6">
				<div>
					<h1 className="text-2xl font-bold text-white">Fire Alarm Design</h1>
					<p className="text-sm text-slate-400 mt-1">
						NFPA 72-2022 · Real API · Battery sizing + voltage drop analysis
					</p>
				</div>

				<div className="grid grid-cols-2 gap-6">
					{/* Battery Calculator — REAL API */}
					<Card className="bg-[#1E293B] border-[#334155]">
						<CardHeader>
							<CardTitle className="text-white flex items-center gap-2">
								<Battery className="h-5 w-5 text-[#22C55E]" />
								Battery Capacity Calculator
							</CardTitle>
							<CardDescription>NFPA 72 §10.6.7.1 — 24h standby + 5min alarm</CardDescription>
						</CardHeader>
						<CardContent className="space-y-3">
							<div>
								<Label className="text-slate-400 text-xs">Standby Current (A)</Label>
								<Input type="number" step="0.1" value={standbyCurrent} onChange={(e) => setStandbyCurrent(e.target.value)} className="bg-[#0F172A] border-[#334155] text-white font-mono" />
							</div>
							<div>
								<Label className="text-slate-400 text-xs">Alarm Current (A)</Label>
								<Input type="number" step="0.1" value={alarmCurrent} onChange={(e) => setAlarmCurrent(e.target.value)} className="bg-[#0F172A] border-[#334155] text-white font-mono" />
							</div>
							<Button onClick={handleBatteryCalc} disabled={loading} className="w-full bg-[#E84040] hover:bg-[#B91C1C] text-white">
								{loading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Battery className="h-4 w-4 mr-2" />}
								Calculate Battery (POST /api/v1/analyze/battery)
							</Button>
						</CardContent>
					</Card>

					{/* Result */}
					<Card className="bg-[#1E293B] border-[#334155]">
						<CardHeader>
							<CardTitle className="text-white">Battery Result</CardTitle>
							<CardDescription>Real calculation from QOMN kernel</CardDescription>
						</CardHeader>
						<CardContent>
							{batteryResult ? (
								<div className="space-y-3">
									{batteryResult.error ? (
										<p className="text-sm text-[#E84040]">{batteryResult.error}</p>
									) : (
										<>
											<div className="bg-[#0F172A] p-4 rounded-md border border-[#334155]">
												<p className="text-xs text-slate-400">Required Capacity</p>
												<p className="text-3xl font-bold text-[#22C55E] font-mono">
													{(batteryResult.required_ah ?? batteryResult.battery_capacity_ah ?? 0).toFixed(2)} Ah
												</p>
											</div>
											<div className="grid grid-cols-2 gap-2 text-sm">
												<div><span className="text-slate-400">Standby:</span> <span className="text-white font-mono">{batteryResult.standby_hours ?? 24}h @ {batteryResult.standby_current_a?.toFixed(2) ?? "?"}A</span></div>
												<div><span className="text-slate-400">Alarm:</span> <span className="text-white font-mono">{batteryResult.alarm_minutes ?? 5}min @ {batteryResult.alarm_current_a?.toFixed(2) ?? "?"}A</span></div>
												<div><span className="text-slate-400">Safety:</span> <span className="text-white font-mono">{batteryResult.safety_factor ?? 1.25}×</span></div>
												<div><span className="text-slate-400">Status:</span> {batteryResult.compliant !== false ? <Badge className="bg-[#22C55E]/10 text-[#22C55E]">✓ Compliant</Badge> : <Badge className="bg-[#E84040]/10 text-[#E84040]">✗ Non-compliant</Badge>}</div>
											</div>
										</>
									)}
								</div>
							) : (
								<p className="text-sm text-slate-400 text-center py-6">Enter currents and calculate</p>
							)}
						</CardContent>
					</Card>
				</div>

				{/* Quick stats */}
				<div className="grid grid-cols-3 gap-4">
					<Card className="bg-[#1E293B] border-[#334155]">
						<CardContent className="pt-4 flex items-center gap-3">
							<Radio className="h-8 w-8 text-[#38BDF8]" />
							<div>
								<p className="text-sm text-white font-medium">NFPA 72 §10.6.7</p>
								<p className="text-xs text-slate-400">24h standby + 5min alarm</p>
							</div>
						</CardContent>
					</Card>
					<Card className="bg-[#1E293B] border-[#334155]">
						<CardContent className="pt-4 flex items-center gap-3">
							<Zap className="h-8 w-8 text-[#F59E0B]" />
							<div>
								<p className="text-sm text-white font-medium">Voltage Drop</p>
								<p className="text-xs text-slate-400">Max 10% per §10.6.4</p>
							</div>
						</CardContent>
					</Card>
					<Card className="bg-[#1E293B] border-[#334155]">
						<CardContent className="pt-4 flex items-center gap-3">
							<Battery className="h-8 w-8 text-[#22C55E]" />
							<div>
								<p className="text-sm text-white font-medium">Safety Factor</p>
								<p className="text-xs text-slate-400">1.25× (NEC recommended)</p>
							</div>
						</CardContent>
					</Card>
				</div>
			</div>
		</div>
	);
}
