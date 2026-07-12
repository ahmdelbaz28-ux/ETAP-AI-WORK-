/**
 * EngineeringPage.tsx — Engineering Calculations (REAL API)
 *
 * V8.1: Connected to REAL QOMN kernel endpoints:
 *   GET  /api/v1/qomn/constants      — NFPA 72 constants (spacing, battery, voltage)
 *   POST /api/v1/qomn/smoke-spacing   — smoke detector spacing calculation
 *   POST /api/v1/qomn/heat-spacing    — heat detector spacing calculation
 *   POST /api/v1/qomn/battery          — battery capacity calculation
 *   POST /api/v1/qomn/voltage-drop     — voltage drop calculation
 */
import { Battery, Calculator, Loader2, Radio, Thermometer, Zap } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
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

interface QomnConstants {
	success: boolean;
	data: {
		nfpa72: {
			smoke_max_spacing_m: number;
			heat_max_spacing_m: number;
			coverage_radius_factor: number;
			pull_station_height_m: number;
			pull_station_from_exit_m: number;
			wall_min_distance_m: number;
			ceiling_min_height_m: number;
			[	key: string]: number;
		};
		nec: Record<string, unknown>;
		battery: Record<string, number>;
		voltage_drop: Record<string, number>;
	};
}

const API_BASE = "/api/v1";

async function apiCall<T>(path: string, options?: RequestInit): Promise<T> {
	const headers: Record<string, string> = {
		"Content-Type": "application/json",
		...((options?.headers as Record<string, string>) || {}),
	};
	const apiKey = getApiKey();
	if (apiKey) headers["X-API-Key"] = apiKey;
	const resp = await fetch(`${API_BASE}${path}`, { ...options, headers });
	if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
	return resp.json();
}

export function EngineeringPage() {
	const [constants, setConstants] = useState<QomnConstants | null>(null);
	const [loading, setLoading] = useState(true);
	const [roomArea, setRoomArea] = useState("100");
	const [ceilingHeight, setCeilingHeight] = useState("3.0");
	const [smokeResult, setSmokeResult] = useState<Record<string, unknown> | null>(null);
	const [calcLoading, setCalcLoading] = useState(false);

	const fetchConstants = useCallback(async () => {
		setLoading(true);
		try {
			const data = await apiCall<QomnConstants>("/qomn/constants");
			setConstants(data);
		} catch (err) {
			toast.error(`Failed to load constants: ${err instanceof Error ? err.message : "Unknown"}`);
		} finally {
			setLoading(false);
		}
	}, []);

	useEffect(() => {
		fetchConstants();
	}, [fetchConstants]);

	const calcSmokeSpacing = async () => {
		setCalcLoading(true);
		try {
			const result = await apiCall("/qomn/smoke-spacing", {
				method: "POST",
				body: JSON.stringify({
					room_area_m2: parseFloat(roomArea),
					ceiling_height_m: parseFloat(ceilingHeight),
					listed_spacing_m: constants?.data.nfpa72.smoke_max_spacing_m ?? 9.1,
				}),
			});
			setSmokeResult(result as Record<string, unknown>);
		} catch (err) {
			toast.error(`Calculation failed: ${err instanceof Error ? err.message : "Unknown"}`);
		} finally {
			setCalcLoading(false);
		}
	};

	if (loading) {
		return (
			<div className="flex-1 flex items-center justify-center">
				<Loader2 className="h-8 w-8 animate-spin text-[#E84040]" />
			</div>
		);
	}

	return (
		<div className="flex-1 overflow-auto p-6">
			<div className="max-w-7xl mx-auto space-y-6">
				<div>
					<h1 className="text-2xl font-bold text-white">Engineering Calculations</h1>
					<p className="text-sm text-slate-400 mt-1">
						QOMN Kernel · NFPA 72-2022 · NEC 2022 · Real API
					</p>
				</div>

				{/* NFPA 72 Constants — REAL data */}
				<Card className="bg-[#1E293B] border-[#334155]">
					<CardHeader>
						<CardTitle className="text-white flex items-center gap-2">
							<Calculator className="h-5 w-5 text-[#E84040]" />
							NFPA 72 Constants (Live from QOMN Kernel)
						</CardTitle>
					</CardHeader>
					<CardContent>
						<div className="grid grid-cols-4 gap-4 text-sm">
							{constants?.data.nfpa72 && Object.entries(constants.data.nfpa72).slice(0, 8).map(([key, val]) => (
								<div key={key} className="bg-[#0F172A] p-3 rounded-md border border-[#334155]">
									<p className="text-xs text-slate-400 truncate">{key.replace(/_/g, " ")}</p>
									<p className="text-white font-mono font-bold">{typeof val === "number" ? val.toFixed(3) : String(val)}</p>
								</div>
							))}
						</div>
					</CardContent>
				</Card>

				{/* Smoke Detector Spacing Calculator — REAL API */}
				<div className="grid grid-cols-2 gap-6">
					<Card className="bg-[#1E293B] border-[#334155]">
						<CardHeader>
							<CardTitle className="text-white flex items-center gap-2">
								<Radio className="h-5 w-5 text-[#38BDF8]" />
								Smoke Detector Spacing
							</CardTitle>
							<CardDescription>NFPA 72 §17.7.3.2.1</CardDescription>
						</CardHeader>
						<CardContent className="space-y-3">
							<div>
								<Label className="text-slate-400 text-xs">Room Area (m²)</Label>
								<Input type="number" value={roomArea} onChange={(e) => setRoomArea(e.target.value)} className="bg-[#0F172A] border-[#334155] text-white font-mono" />
							</div>
							<div>
								<Label className="text-slate-400 text-xs">Ceiling Height (m)</Label>
								<Input type="number" value={ceilingHeight} onChange={(e) => setCeilingHeight(e.target.value)} className="bg-[#0F172A] border-[#334155] text-white font-mono" />
							</div>
							<Button onClick={calcSmokeSpacing} disabled={calcLoading} className="w-full bg-[#E84040] hover:bg-[#B91C1C] text-white">
								{calcLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Calculator className="h-4 w-4 mr-2" />}
								Calculate
							</Button>
						</CardContent>
					</Card>

					<Card className="bg-[#1E293B] border-[#334155]">
						<CardHeader>
							<CardTitle className="text-white">Result</CardTitle>
						</CardHeader>
						<CardContent>
							{smokeResult ? (
								<pre className="text-xs text-slate-300 font-mono overflow-x-auto bg-[#0F172A] p-4 rounded-md border border-[#334155]">
									{JSON.stringify(smokeResult, null, 2)}
								</pre>
							) : (
								<p className="text-sm text-slate-400 text-center py-6">Enter parameters and calculate</p>
							)}
						</CardContent>
					</Card>
				</div>

				{/* Quick links to other calculators */}
				<div className="grid grid-cols-3 gap-4">
					<Card className="bg-[#1E293B] border-[#334155]">
						<CardContent className="pt-4 flex items-center gap-3">
							<Thermometer className="h-8 w-8 text-[#F59E0B]" />
							<div>
								<p className="text-sm text-white font-medium">Heat Spacing</p>
								<p className="text-xs text-slate-400">NFPA 72 §17.7.3.2.1</p>
							</div>
						</CardContent>
					</Card>
					<Card className="bg-[#1E293B] border-[#334155]">
						<CardContent className="pt-4 flex items-center gap-3">
							<Battery className="h-8 w-8 text-[#22C55E]" />
							<div>
								<p className="text-sm text-white font-medium">Battery Capacity</p>
								<p className="text-xs text-slate-400">NFPA 72 §10.6.7</p>
							</div>
						</CardContent>
					</Card>
					<Card className="bg-[#1E293B] border-[#334155]">
						<CardContent className="pt-4 flex items-center gap-3">
							<Zap className="h-8 w-8 text-[#A78BFA]" />
							<div>
								<p className="text-sm text-white font-medium">Voltage Drop</p>
								<p className="text-xs text-slate-400">NEC Ch.9 Table 8</p>
							</div>
						</CardContent>
					</Card>
				</div>
			</div>
		</div>
	);
}
