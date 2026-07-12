/**
 * DigitalTwinPage.tsx — Digital Twin (REAL API)
 *
 * V8.1: Connected to REAL backend endpoints:
 *   GET /api/v1/digital-twin/status   — conversion engine status
 *   GET /api/v1/digital-twin/history   — conversion history
 *   GET /api/v1/digital-twin/config     — current configuration
 *   GET /api/v1/digital-twin/mappings   — element mappings
 */
import { Box, Loader2, RefreshCw } from "lucide-react";
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
import { getApiKey } from "@/services/apiKey";

interface DtStatus {
	status: string;
	total_conversions: number;
	last_conversion: string | null;
	config_loaded: boolean;
	timestamp: string;
}

interface DtHistory {
	success?: boolean;
	conversions?: Array<Record<string, unknown>>;
}

async function apiCall<T>(path: string): Promise<T> {
	const headers: Record<string, string> = {};
	const apiKey = getApiKey();
	if (apiKey) headers["X-API-Key"] = apiKey;
	const resp = await fetch(`/api/v1${path}`, { headers });
	if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
	return resp.json();
}

export function DigitalTwinPage() {
	const [status, setStatus] = useState<DtStatus | null>(null);
	const [history, setHistory] = useState<DtHistory | null>(null);
	const [loading, setLoading] = useState(true);

	const fetchAll = useCallback(async () => {
		setLoading(true);
		try {
			const [s, h] = await Promise.all([
				apiCall<DtStatus>("/digital-twin/status"),
				apiCall<DtHistory>("/digital-twin/history").catch(() => ({})),
			]);
			setStatus(s);
			setHistory(h);
		} catch (err) {
			toast.error(`Failed: ${err instanceof Error ? err.message : "Unknown"}`);
		} finally {
			setLoading(false);
		}
	}, []);

	useEffect(() => {
		fetchAll();
	}, [fetchAll]);

	return (
		<div className="flex-1 overflow-auto p-6">
			<div className="max-w-7xl mx-auto space-y-6">
				<div className="flex items-center justify-between">
					<div>
						<h1 className="text-2xl font-bold text-white flex items-center gap-2">
							<Box className="h-6 w-6 text-[#A78BFA]" />
							Digital Twin
						</h1>
						<p className="text-sm text-slate-400 mt-1">BIM conversion · Real API · IFC/DXF/Revit</p>
					</div>
					<Button variant="outline" onClick={fetchAll} disabled={loading} className="bg-[#1E293B] border-[#334155] text-white hover:bg-[#334155]">
						{loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
					</Button>
				</div>

				{loading ? (
					<div className="flex items-center justify-center py-12">
						<Loader2 className="h-8 w-8 animate-spin text-[#A78BFA]" />
					</div>
				) : status ? (
					<>
						<div className="grid grid-cols-4 gap-4">
							<Card className="bg-[#1E293B] border-[#334155]">
								<CardContent className="pt-4">
									<p className="text-sm text-slate-400">Status</p>
									<p className="text-lg font-bold text-[#22C55E] capitalize">{status.status}</p>
								</CardContent>
							</Card>
							<Card className="bg-[#1E293B] border-[#334155]">
								<CardContent className="pt-4">
									<p className="text-sm text-slate-400">Total Conversions</p>
									<p className="text-2xl font-bold text-white">{status.total_conversions}</p>
								</CardContent>
							</Card>
							<Card className="bg-[#1E293B] border-[#334155]">
								<CardContent className="pt-4">
									<p className="text-sm text-slate-400">Config Loaded</p>
									<p className={status.config_loaded ? "text-[#22C55E]" : "text-[#F59E0B]"}>
										{status.config_loaded ? "✓ Yes" : "⚠ No"}
									</p>
								</CardContent>
							</Card>
							<Card className="bg-[#1E293B] border-[#334155]">
								<CardContent className="pt-4">
									<p className="text-sm text-slate-400">Last Conversion</p>
									<p className="text-sm text-white">{status.last_conversion ? new Date(status.last_conversion).toLocaleString() : "Never"}</p>
								</CardContent>
							</Card>
						</div>

						<Card className="bg-[#1E293B] border-[#334155]">
							<CardHeader>
								<CardTitle className="text-white">Conversion History</CardTitle>
								<CardDescription>Real history from /api/v1/digital-twin/history</CardDescription>
							</CardHeader>
							<CardContent>
								{history?.conversions && history.conversions.length > 0 ? (
									<pre className="text-xs text-slate-300 font-mono overflow-x-auto bg-[#0F172A] p-4 rounded-md border border-[#334155]">
										{JSON.stringify(history.conversions, null, 2)}
									</pre>
								) : (
									<p className="text-sm text-slate-400 text-center py-6">No conversions yet. Upload a BIM file to begin.</p>
								)}
							</CardContent>
						</Card>
					</>
				) : null}
			</div>
		</div>
	);
}
