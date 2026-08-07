/**
 * CableRoutingPage.tsx — Cable Routing & Conduit Design (REAL API)
 *
 * V8.1 Screen 4: Connected to REAL backend endpoint:
 *   POST /api/v1/qomn/voltage-drop — NEC Chapter 9 Table 8 calculation
 *
 * No hardcoded values — user inputs real parameters, gets real computed results.
 */
import { Cable, Calculator, Loader2, Zap } from "lucide-react";
import { useState } from "react";
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

interface VoltageDropResult {
	success: boolean;
	voltage_drop_v?: number;
	voltage_drop_pct?: number;
	is_compliant?: boolean;
	max_allowed_pct?: number;
	wire_resistance_ohm_per_km?: number;
	nec_reference?: string;
	awg_gauge?: string;
	error?: string;
}

export function CableRoutingPage() {
	const [current, setCurrent] = useState("0.150");
	const [length, setLength] = useState("250");
	const [awgGauge, setAwgGauge] = useState("14");
	const [result, setResult] = useState<VoltageDropResult | null>(null);
	const [loading, setLoading] = useState(false);

	const calculate = async () => {
		setLoading(true);
		setResult(null);
		try {
			const headers: Record<string, string> = {
				"Content-Type": "application/json",
			};
			const apiKey = getApiKey();
			if (apiKey) headers["X-API-Key"] = apiKey;

			const resp = await fetch("/api/v1/qomn/voltage-drop", {
				method: "POST",
				headers,
				body: JSON.stringify({
					current_a: parseFloat(current),
					length_m: parseFloat(length),
					awg_gauge: awgGauge,
				}),
			});

			if (!resp.ok) {
				const err = await resp.json().catch(() => ({}));
				throw new Error(err?.detail?.[0]?.msg || err?.detail || `HTTP ${resp.status}`);
			}

			const data = await resp.json();
			setResult(data);
			toast.success(
				data.is_compliant
					? `COMPLIANT — ${data.voltage_drop_pct?.toFixed(2)}% drop`
					: `VIOLATION — ${data.voltage_drop_pct?.toFixed(2)}% exceeds ${data.max_allowed_pct}%`,
			);
		} catch (err) {
			toast.error(`Calculation failed: ${err instanceof Error ? err.message : "Unknown"}`);
		} finally {
			setLoading(false);
		}
	};

	return (
		<div className="flex-1 overflow-auto p-6">
			<div className="max-w-5xl mx-auto space-y-6">
				<div>
					<h1 className="text-2xl font-bold text-white">Cable Routing &amp; Voltage Drop</h1>
					<p className="text-sm text-slate-400 mt-1">
						NEC Chapter 9 Table 8 · NFPA 72 §10.6.4 · Real API calculation
					</p>
				</div>

				<div className="grid grid-cols-2 gap-6">
					{/* Input form */}
					<Card className="bg-[#1E293B] border-[#334155]">
						<CardHeader>
							<CardTitle className="text-white flex items-center gap-2">
								<Calculator className="h-5 w-5 text-[#E84040]" />
								Voltage Drop Calculator
							</CardTitle>
							<CardDescription>
								Formula: V = I × 2 × R × L (NEC Ch.9 Table 8)
							</CardDescription>
						</CardHeader>
						<CardContent className="space-y-4">
							<div>
								<Label className="text-slate-400 text-xs">Current (I) — Amperes</Label>
								<Input
									type="number"
									value={current}
									onChange={(e) => setCurrent(e.target.value)}
									className="bg-[#0F172A] border-[#334155] text-white font-mono mt-1"
								/>
							</div>
							<div>
								<Label className="text-slate-400 text-xs">One-way Length (L) — meters</Label>
								<Input
									type="number"
									value={length}
									onChange={(e) => setLength(e.target.value)}
									className="bg-[#0F172A] border-[#334155] text-white font-mono mt-1"
								/>
							</div>
							<div>
								<Label className="text-slate-400 text-xs">Wire Gauge (AWG)</Label>
								<div className="grid grid-cols-4 gap-2 mt-1">
									{["18", "16", "14", "12"].map((g) => (
										<button
											key={g}
											onClick={() => setAwgGauge(g)}
											className={`px-3 py-2 text-sm rounded-md border transition-colors ${
												awgGauge === g
													? "bg-[#E84040]/10 border-[#E84040] text-[#E84040]"
													: "bg-[#0F172A] border-[#334155] text-slate-400 hover:text-white"
											}`}
										>
											AWG {g}
										</button>
									))}
								</div>
							</div>
							<Button
								onClick={calculate}
								disabled={loading}
								className="w-full bg-[#E84040] hover:bg-[#B91C1C] text-white"
							>
								{loading ? (
									<Loader2 className="h-4 w-4 animate-spin mr-2" />
								) : (
									<Zap className="h-4 w-4 mr-2" />
								)}
								Calculate Voltage Drop
							</Button>
						</CardContent>
					</Card>

					{/* Results */}
					<Card className="bg-[#1E293B] border-[#334155]">
						<CardHeader>
							<CardTitle className="text-white flex items-center gap-2">
								<Cable className="h-5 w-5 text-[#38BDF8]" />
								Results
							</CardTitle>
							<CardDescription>
								Real-time calculation from QOMN kernel
							</CardDescription>
						</CardHeader>
						<CardContent>
							{result ? (
								<div className="space-y-4">
									<div className="bg-[#0F172A] rounded-md p-4 border border-[#334155]">
										<div className="grid grid-cols-2 gap-4 text-sm">
											<div>
												<p className="text-slate-400 text-xs">V_drop (volts)</p>
												<p className="text-white font-mono text-lg font-bold">
													{result.voltage_drop_v?.toFixed(4)} V
												</p>
											</div>
											<div>
												<p className="text-slate-400 text-xs">V_drop (%)</p>
												<p
													className={`font-mono text-lg font-bold ${
														result.is_compliant ? "text-[#22C55E]" : "text-[#E84040]"
													}`}
												>
													{result.voltage_drop_pct?.toFixed(2)}%
												</p>
											</div>
											<div>
												<p className="text-slate-400 text-xs">Resistance</p>
												<p className="text-[#38BDF8] font-mono">
													{result.wire_resistance_ohm_per_km?.toFixed(2)} Ω/km
												</p>
											</div>
											<div>
												<p className="text-slate-400 text-xs">Max Allowed</p>
												<p className="text-slate-300 font-mono">
													{result.max_allowed_pct}% (NFPA §10.6.4)
												</p>
											</div>
										</div>
									</div>
									{result.is_compliant !== undefined && (
										<div
											className={`px-4 py-3 rounded-md text-sm font-medium ${
												result.is_compliant
													? "bg-[#22C55E]/10 text-[#22C55E]"
													: "bg-[#E84040]/10 text-[#E84040]"
											}`}
										>
											{result.is_compliant
												? "✓ COMPLIANT — Within NFPA 72 limits"
												: "✗ VIOLATION — Exceeds NFPA 72 §10.6.4 limit"}
										</div>
									)}
									{result.nec_reference && (
										<Badge className="bg-[#334155] text-slate-300">
											{result.nec_reference}
										</Badge>
									)}
								</div>
							) : (
								<div className="flex flex-col items-center justify-center py-12 text-center">
									<Calculator className="h-12 w-12 text-slate-700 mb-3" />
									<p className="text-slate-500 text-sm">
										Enter parameters and click Calculate
									</p>
								</div>
							)}
						</CardContent>
					</Card>
				</div>
			</div>
		</div>
	);
}
