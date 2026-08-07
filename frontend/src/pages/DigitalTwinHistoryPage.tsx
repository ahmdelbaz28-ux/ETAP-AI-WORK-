/**
 * DigitalTwinHistoryPage.tsx — Digital Twin Conversion History (REAL API)
 *
 * V8.1: Connected to REAL backend endpoints:
 *   GET  /api/v1/digital-twin/history           — conversion history
 *   POST /api/v1/digital-twin/rollback/{id}      — rollback to version
 */
import { History, Loader2, RefreshCw, RotateCcw } from "lucide-react";
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

interface HistoryEntry {
	version_id: string;
	timestamp: string;
	input_file: string;
	output_format: string;
	status: string;
	file_size_bytes?: number;
}

interface HistoryResponse {
	success?: boolean;
	history?: HistoryEntry[];
	conversions?: HistoryEntry[];
	data?: { history: HistoryEntry[] };
}

export function DigitalTwinHistoryPage() {
	const [history, setHistory] = useState<HistoryEntry[]>([]);
	const [loading, setLoading] = useState(true);

	const fetchHistory = useCallback(async () => {
		setLoading(true);
		try {
			const headers: Record<string, string> = {};
			const apiKey = getApiKey();
			if (apiKey) headers["X-API-Key"] = apiKey;
			const resp = await fetch("/api/v1/digital-twin/history", { headers });
			if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
			const data: HistoryResponse = await resp.json();
			setHistory(data.history || data.conversions || data.data?.history || []);
		} catch (err) {
			toast.error(`Failed: ${err instanceof Error ? err.message : "Unknown"}`);
		} finally {
			setLoading(false);
		}
	}, []);

	useEffect(() => {
		fetchHistory();
	}, [fetchHistory]);

	const handleRollback = async (versionId: string) => {
		try {
			const headers: Record<string, string> = {};
			const apiKey = getApiKey();
			if (apiKey) headers["X-API-Key"] = apiKey;
			const resp = await fetch(`/api/v1/digital-twin/rollback/${versionId}`, { method: "POST", headers });
			if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
			toast.success(`Rolled back to ${versionId}`);
			fetchHistory();
		} catch (err) {
			toast.error(`Rollback failed: ${err instanceof Error ? err.message : "Unknown"}`);
		}
	};

	return (
		<div className="flex-1 overflow-auto p-6">
			<div className="max-w-5xl mx-auto space-y-6">
				<div className="flex items-center justify-between">
					<div>
						<h1 className="text-2xl font-bold text-white flex items-center gap-2">
							<History className="h-6 w-6 text-[#A78BFA]" />
							Conversion History
						</h1>
						<p className="text-sm text-slate-400 mt-1">Real API: GET /api/v1/digital-twin/history · {history.length} entries</p>
					</div>
					<Button variant="outline" onClick={fetchHistory} disabled={loading} className="bg-[#1E293B] border-[#334155] text-white hover:bg-[#334155]">
						{loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
					</Button>
				</div>

				{loading ? (
					<div className="flex items-center justify-center py-12">
						<Loader2 className="h-8 w-8 animate-spin text-[#A78BFA]" />
					</div>
				) : (
					<Card className="bg-[#1E293B] border-[#334155]">
						<CardHeader>
							<CardTitle className="text-white text-base">All Conversions</CardTitle>
							<CardDescription>From /api/v1/digital-twin/history</CardDescription>
						</CardHeader>
						<CardContent>
							{history.length > 0 ? (
								<div className="overflow-x-auto">
									<table className="w-full text-sm">
										<thead>
											<tr className="text-slate-400 text-xs uppercase border-b border-[#334155]">
												<th className="text-left py-2 px-2">Version</th>
												<th className="text-left px-2">Timestamp</th>
												<th className="text-left px-2">Input</th>
												<th className="text-left px-2">Format</th>
												<th className="text-left px-2">Status</th>
												<th className="text-right px-2">Actions</th>
											</tr>
										</thead>
										<tbody>
											{history.map((entry) => (
												<tr key={entry.version_id} className="border-b border-[#334155]/50">
													<td className="py-2 px-2 text-slate-300 font-mono text-xs">{entry.version_id}</td>
													<td className="px-2 text-slate-300 text-xs">{entry.timestamp ? new Date(entry.timestamp).toLocaleString() : "—"}</td>
													<td className="px-2 text-white text-xs">{entry.input_file || "—"}</td>
													<td className="px-2 text-slate-400">{entry.output_format || "—"}</td>
													<td className="px-2">
														<Badge className={entry.status === "success" ? "bg-[#22C55E]/10 text-[#22C55E]" : "bg-[#F59E0B]/10 text-[#F59E0B]"}>
															{entry.status || "unknown"}
														</Badge>
													</td>
													<td className="px-2 text-right">
														<Button variant="ghost" size="sm" onClick={() => handleRollback(entry.version_id)} className="text-[#A78BFA] p-1">
															<RotateCcw className="h-3.5 w-3.5" />
														</Button>
													</td>
												</tr>
											))}
										</tbody>
									</table>
								</div>
							) : (
								<p className="text-sm text-slate-400 text-center py-6">No conversions yet. Upload a file via Convert page.</p>
							)}
						</CardContent>
					</Card>
				)}
			</div>
		</div>
	);
}
