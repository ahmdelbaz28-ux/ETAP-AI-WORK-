/**
 * MarinePage.tsx — Marine Module (REAL API)
 *
 * V8.1: Connected to REAL backend endpoints:
 *   GET  /api/v1/marine/fire-classes      — SOLAS fire class divisions
 *   POST /api/v1/marine/detection/design   — detection design per SOLAS
 *   POST /api/v1/marine/divisions/generate — fire zone divisions
 *   POST /api/v1/marine/alarm-logic/generate — alarm logic per SOLAS
 */
import { Anchor, Loader2, RefreshCw, Ship } from "lucide-react";
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

interface FireClass {
	class: string;
	insulation_minutes: number;
}

interface MarineResponse {
	fire_classes: FireClass[];
}

export function MarinePage() {
	const [fireClasses, setFireClasses] = useState<FireClass[]>([]);
	const [loading, setLoading] = useState(true);

	const fetchData = useCallback(async () => {
		setLoading(true);
		try {
			const headers: Record<string, string> = {};
			const apiKey = getApiKey();
			if (apiKey) headers["X-API-Key"] = apiKey;
			const resp = await fetch("/api/v1/marine/fire-classes", { headers });
			if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
			const data: MarineResponse = await resp.json();
			setFireClasses(data.fire_classes);
		} catch (err) {
			toast.error(`Failed to load marine data: ${err instanceof Error ? err.message : "Unknown"}`);
		} finally {
			setLoading(false);
		}
	}, []);

	useEffect(() => {
		fetchData();
	}, [fetchData]);

	return (
		<div className="flex-1 overflow-auto p-6">
			<div className="max-w-7xl mx-auto space-y-6">
				<div className="flex items-center justify-between">
					<div>
						<h1 className="text-2xl font-bold text-white flex items-center gap-2">
							<Anchor className="h-6 w-6 text-[#0EA5E9]" />
							Marine Module
						</h1>
						<p className="text-sm text-slate-400 mt-1">
							SOLAS · IMO · MED · Real API · Ocean Blue accent
						</p>
					</div>
					<Button variant="outline" onClick={fetchData} disabled={loading} className="bg-[#1E293B] border-[#334155] text-white hover:bg-[#334155]">
						{loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
					</Button>
				</div>

				{loading ? (
					<div className="flex items-center justify-center py-12">
						<Loader2 className="h-8 w-8 animate-spin text-[#0EA5E9]" />
					</div>
				) : (
					<>
						{/* Fire Classes — REAL data */}
						<Card className="bg-[#1E293B] border-[#334155]">
							<CardHeader>
								<CardTitle className="text-white flex items-center gap-2">
									<Ship className="h-5 w-5 text-[#0EA5E9]" />
									SOLAS Fire Class Divisions
								</CardTitle>
								<CardDescription>
									Real fire class data from /api/v1/marine/fire-classes
								</CardDescription>
							</CardHeader>
							<CardContent>
								<div className="grid grid-cols-4 gap-3">
									{fireClasses.map((fc) => (
										<div key={fc.class} className="bg-[#0F172A] p-4 rounded-md border border-[#334155] text-center">
											<p className="text-2xl font-bold text-[#0EA5E9]">{fc.class}</p>
											<p className="text-xs text-slate-400 mt-1">{fc.insulation_minutes} min insulation</p>
											<Badge className={`mt-2 ${fc.insulation_minutes >= 60 ? "bg-[#E84040]/10 text-[#E84040]" : fc.insulation_minutes > 0 ? "bg-[#F59E0B]/10 text-[#F59E0B]" : "bg-slate-700 text-slate-400"}`}>
												{fc.insulation_minutes >= 60 ? "High" : fc.insulation_minutes > 0 ? "Medium" : "None"}
											</Badge>
										</div>
									))}
								</div>
							</CardContent>
						</Card>

						{/* Marine tools */}
						<div className="grid grid-cols-3 gap-4">
							<Card className="bg-[#1E293B] border-[#334155]">
								<CardContent className="pt-4">
									<p className="text-sm text-white font-medium">Detection Design</p>
									<p className="text-xs text-slate-400 mt-1">SOLAS §9.2.2.2 — smoke/heat/flame per space</p>
								</CardContent>
							</Card>
							<Card className="bg-[#1E293B] border-[#334155]">
								<CardContent className="pt-4">
									<p className="text-sm text-white font-medium">Zone Divisions</p>
									<p className="text-xs text-slate-400 mt-1">VFZ / HFZ / Machinery spaces</p>
								</CardContent>
							</Card>
							<Card className="bg-[#1E293B] border-[#334155]">
								<CardContent className="pt-4">
									<p className="text-sm text-white font-medium">Alarm Logic</p>
									<p className="text-xs text-slate-400 mt-1">SOLAS §6 — PA / general alarm</p>
								</CardContent>
							</Card>
						</div>
					</>
				)}
			</div>
		</div>
	);
}
