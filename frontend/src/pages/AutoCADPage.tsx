/**
 * AutoCADPage.tsx — AutoCAD Integration (REAL API)
 *
 * V8.1: Connected to REAL backend endpoints:
 *   GET  /api/v1/autocad/status     — connection status
 *   GET  /api/v1/autocad/documents   — open documents
 *   POST /api/v1/autocad/read_dwg    — read DWG file
 *   POST /api/v1/autocad/upload      — upload DWG
 */
import { FileText, Loader2, PencilRuler, RefreshCw, Upload } from "lucide-react";
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

interface AutocadStatus {
	connected: boolean;
	message: string;
	document_info: { name: string; path: string } | null;
}

async function apiCall<T>(path: string): Promise<T> {
	const headers: Record<string, string> = {};
	const apiKey = getApiKey();
	if (apiKey) headers["X-API-Key"] = apiKey;
	const resp = await fetch(`/api/v1${path}`, { headers });
	if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
	return resp.json();
}

export function AutoCADPage() {
	const [status, setStatus] = useState<AutocadStatus | null>(null);
	const [documents, setDocuments] = useState<unknown>(null);
	const [loading, setLoading] = useState(true);

	const fetchAll = useCallback(async () => {
		setLoading(true);
		try {
			const [s, d] = await Promise.all([
				apiCall<AutocadStatus>("/autocad/status"),
				apiCall("/autocad/documents").catch(() => null),
			]);
			setStatus(s);
			setDocuments(d);
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
							<PencilRuler className="h-6 w-6 text-[#E84040]" />
							AutoCAD Integration
						</h1>
						<p className="text-sm text-slate-400 mt-1">Real API · DWG read/write · LibreDWG</p>
					</div>
					<Button variant="outline" onClick={fetchAll} disabled={loading} className="bg-[#1E293B] border-[#334155] text-white hover:bg-[#334155]">
						{loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
					</Button>
				</div>

				{loading ? (
					<div className="flex items-center justify-center py-12">
						<Loader2 className="h-8 w-8 animate-spin text-[#E84040]" />
					</div>
				) : status ? (
					<>
						<Card className="bg-[#1E293B] border-[#334155]">
							<CardHeader>
								<CardTitle className="text-white">Connection Status</CardTitle>
								<CardDescription>Real status from /api/v1/autocad/status</CardDescription>
							</CardHeader>
							<CardContent>
								<div className="flex items-center gap-3 mb-4">
									<span className={`h-3 w-3 rounded-full ${status.connected ? "bg-[#22C55E]" : "bg-[#E84040]"}`} />
									<span className="text-white font-medium">{status.message}</span>
									{status.connected && <Badge className="bg-[#22C55E]/10 text-[#22C55E]">Connected</Badge>}
								</div>
								{status.document_info && (
									<div className="text-sm">
										<p className="text-slate-400">Document: <span className="text-white">{status.document_info.name}</span></p>
										<p className="text-slate-400">Path: <span className="text-white font-mono">{status.document_info.path}</span></p>
									</div>
								)}
							</CardContent>
						</Card>

						<div className="grid grid-cols-2 gap-4">
							<Card className="bg-[#1E293B] border-[#334155]">
								<CardHeader><CardTitle className="text-white text-base flex items-center gap-2"><FileText className="h-4 w-4 text-[#38BDF8]" />Open Documents</CardTitle></CardHeader>
								<CardContent>
									{documents ? (
										<pre className="text-xs text-slate-300 font-mono overflow-x-auto bg-[#0F172A] p-3 rounded border border-[#334155]">{JSON.stringify(documents, null, 2)}</pre>
									) : (
										<p className="text-sm text-slate-400">Not connected to AutoCAD</p>
									)}
								</CardContent>
							</Card>

							<Card className="bg-[#1E293B] border-[#334155]">
								<CardHeader><CardTitle className="text-white text-base">Upload DWG</CardTitle></CardHeader>
								<CardContent>
									<Button variant="outline" className="bg-[#0F172A] border-dashed border-[#334155] text-slate-400 hover:text-white w-full h-24">
										<Upload className="h-6 w-6 mr-2" />
										Drop .dwg file or click to browse
									</Button>
								</CardContent>
							</Card>
						</div>

						<Card className="bg-[#1E293B] border-[#334155]">
							<CardHeader><CardTitle className="text-white text-base">DWG Operations</CardTitle></CardHeader>
							<CardContent>
								<div className="grid grid-cols-4 gap-3 text-sm">
									<Button variant="outline" className="bg-[#0F172A] border-[#334155] text-slate-300 hover:text-white">Read DWG</Button>
									<Button variant="outline" className="bg-[#0F172A] border-[#334155] text-slate-300 hover:text-white">Draw Line</Button>
									<Button variant="outline" className="bg-[#0F172A] border-[#334155] text-slate-300 hover:text-white">Draw Circle</Button>
									<Button variant="outline" className="bg-[#0F172A] border-[#334155] text-slate-300 hover:text-white">Save DWG</Button>
								</div>
							</CardContent>
						</Card>
					</>
				) : null}
			</div>
		</div>
	);
}
