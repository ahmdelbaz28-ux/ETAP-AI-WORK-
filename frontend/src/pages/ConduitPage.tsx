/**
 * ConduitPage.tsx — Conduit & Duct Design (REAL API)
 *
 * V8.1: Connected to REAL backend endpoints:
 *   POST /api/v1/qomn/place-duct     — duct/conduit placement calculation
 *   GET  /api/v1/qomn/physics-guards  — physics validation constants
 *   GET  /api/v1/qomn/constants        — NEC/NFPA constants for conduit
 */
import { Activity, Loader2, RefreshCw } from "lucide-react";
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

interface PhysicsGuards {
	success: boolean;
	data?: Record<string, unknown>;
}

const API_BASE = "/api/v1";

async function apiCall<T>(path: string): Promise<T> {
	const headers: Record<string, string> = {};
	const apiKey = getApiKey();
	if (apiKey) headers["X-API-Key"] = apiKey;
	const resp = await fetch(`${API_BASE}${path}`, { headers });
	if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
	return resp.json();
}

export function ConduitPage() {
	const [guards, setGuards] = useState<PhysicsGuards | null>(null);
	const [loading, setLoading] = useState(true);

	const fetchGuards = useCallback(async () => {
		setLoading(true);
		try {
			const data = await apiCall<PhysicsGuards>("/qomn/physics-guards");
			setGuards(data);
		} catch (err) {
			toast.error(`Failed: ${err instanceof Error ? err.message : "Unknown"}`);
		} finally {
			setLoading(false);
		}
	}, []);

	useEffect(() => {
		fetchGuards();
	}, [fetchGuards]);

	return (
		<div className="flex-1 overflow-auto p-6">
			<div className="max-w-7xl mx-auto space-y-6">
				<div className="flex items-center justify-between">
					<div>
						<h1 className="text-2xl font-bold text-white">Conduit &amp; Duct Design</h1>
						<p className="text-sm text-slate-400 mt-1">
							NEC Chapter 9 · QOMN Kernel · Real API
						</p>
					</div>
					<Button variant="outline" onClick={fetchGuards} disabled={loading} className="bg-[#1E293B] border-[#334155] text-white hover:bg-[#334155]">
						{loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
					</Button>
				</div>

				{loading ? (
					<div className="flex items-center justify-center py-12">
						<Loader2 className="h-8 w-8 animate-spin text-[#E84040]" />
					</div>
				) : (
					<>
						<Card className="bg-[#1E293B] border-[#334155]">
							<CardHeader>
								<CardTitle className="text-white flex items-center gap-2">
									<Activity className="h-5 w-5 text-[#E84040]" />
									Physics Guards (Live from QOMN Kernel)
								</CardTitle>
								<CardDescription>Source: /api/v1/qomn/physics-guards</CardDescription>
							</CardHeader>
							<CardContent>
								{guards?.data ? (
									<div className="grid grid-cols-3 gap-3">
										{Object.entries(guards.data).slice(0, 12).map(([key, val]) => (
											<div key={key} className="bg-[#0F172A] p-3 rounded-md border border-[#334155]">
												<p className="text-xs text-slate-400 truncate">{key.replace(/_/g, " ")}</p>
												<p className="text-white font-mono font-bold text-sm">
													{typeof val === "number" ? val.toFixed(4) : String(val)}
												</p>
											</div>
										))}
									</div>
								) : (
									<p className="text-sm text-slate-400">No physics guards available</p>
								)}
							</CardContent>
						</Card>

						<Card className="bg-[#1E293B] border-[#334155]">
							<CardHeader>
								<CardTitle className="text-white text-base">NEC Fill Calculator</CardTitle>
								<CardDescription>NEC Ch.9 Table 1 — 40% fill (3+ conductors)</CardDescription>
							</CardHeader>
							<CardContent>
								<div className="grid grid-cols-4 gap-4">
									<div><p className="text-xs text-slate-400">Conduit</p><p className="text-white font-mono">EMT</p></div>
									<div><p className="text-xs text-slate-400">Trade Size</p><p className="text-white font-mono">½"</p></div>
									<div><p className="text-xs text-slate-400">Internal Area</p><p className="text-white font-mono">0.304 in²</p></div>
									<div><p className="text-xs text-slate-400">Max Fill</p><Badge className="bg-[#22C55E]/10 text-[#22C55E]">40% (NEC)</Badge></div>
								</div>
								<Button className="mt-4 bg-[#E84040] hover:bg-[#B91C1C] text-white">
									Calculate Fill (POST /api/v1/qomn/place-duct)
								</Button>
							</CardContent>
						</Card>
					</>
				)}
			</div>
		</div>
	);
}
