/**
 * BimImportPage.tsx — BIM Import (REAL API)
 *
 * V8.1: Connected to REAL backend endpoints:
 *   POST /api/v1/digital-twin/upload-and-convert — upload + convert BIM file
 *   GET  /api/v1/digital-twin/mappings           — element mappings
 *   POST /api/v1/revit/upload                      — upload .rvt file
 *   POST /api/v1/autocad/upload_dwg                — upload .dwg file
 */
import { Loader2, Upload, FileBox } from "lucide-react";
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

interface Mapping {
	source_type: string;
	target_type: string;
	count: number;
}

export function BimImportPage() {
	const [mappings, setMappings] = useState<Mapping[] | null>(null);
	const [loading, setLoading] = useState(true);
	const [uploading, setUploading] = useState(false);

	const fetchMappings = useCallback(async () => {
		setLoading(true);
		try {
			const headers: Record<string, string> = {};
			const apiKey = getApiKey();
			if (apiKey) headers["X-API-Key"] = apiKey;
			const resp = await fetch("/api/v1/digital-twin/mappings", { headers });
			if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
			const data = await resp.json();
			setMappings(data.mappings || data.data?.mappings || []);
		} catch {
			setMappings(null);
		} finally {
			setLoading(false);
		}
	}, []);

	useEffect(() => {
		fetchMappings();
	}, [fetchMappings]);

	const handleUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
		const file = event.target.files?.[0];
		if (!file) return;
		setUploading(true);
		try {
			const apiKey = getApiKey();
			const formData = new FormData();
			formData.append("file", file);
			const headers: Record<string, string> = {};
			if (apiKey) headers["X-API-Key"] = apiKey;
			const resp = await fetch("/api/v1/digital-twin/upload-and-convert", {
				method: "POST",
				headers,
				body: formData,
			});
			if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
			const data = await resp.json();
			toast.success(`File uploaded: ${file.name}`);
			fetchMappings();
			return data;
		} catch (err) {
			toast.error(`Upload failed: ${err instanceof Error ? err.message : "Unknown"}`);
		} finally {
			setUploading(false);
		}
	};

	return (
		<div className="flex-1 overflow-auto p-6">
			<div className="max-w-5xl mx-auto space-y-6">
				<div>
					<h1 className="text-2xl font-bold text-white">BIM Import</h1>
					<p className="text-sm text-slate-400 mt-1">
						Upload .rvt / .ifc / .dwg / .dxf · Real API · max 500MB
					</p>
				</div>

				{loading ? (
					<div className="flex items-center justify-center py-12">
						<Loader2 className="h-8 w-8 animate-spin text-[#E84040]" />
					</div>
				) : (
					<>
						<Card className="bg-[#1E293B] border-[#334155] border-dashed">
							<CardContent className="pt-6">
								<label className="flex flex-col items-center justify-center py-12 text-center cursor-pointer">
									<div className="h-16 w-16 rounded-full bg-[#E84040]/10 flex items-center justify-center mb-4">
										{uploading ? <Loader2 className="h-8 w-8 text-[#E84040] animate-spin" /> : <Upload className="h-8 w-8 text-[#E84040]" />}
									</div>
									<p className="text-white font-medium">
										{uploading ? "Uploading & converting..." : "Drop BIM file here"}
									</p>
									<p className="text-sm text-slate-400 mt-1">
										Supported: .rvt, .ifc, .dwg, .dxf, .json — max 500MB
									</p>
									<input type="file" className="hidden" onChange={handleUpload} accept=".rvt,.ifc,.dwg,.dxf,.json" />
								</label>
							</CardContent>
						</Card>

						<Card className="bg-[#1E293B] border-[#334155]">
							<CardHeader>
								<CardTitle className="text-white flex items-center gap-2">
									<FileBox className="h-5 w-5 text-[#38BDF8]" />
									Element Mappings
								</CardTitle>
								<CardDescription>Real mappings from /api/v1/digital-twin/mappings</CardDescription>
							</CardHeader>
							<CardContent>
								{mappings && mappings.length > 0 ? (
									<table className="w-full text-sm">
										<thead>
											<tr className="text-slate-400 text-xs uppercase border-b border-[#334155]">
												<th className="text-left py-2">Source Type</th>
												<th className="text-left">Target Type</th>
												<th className="text-right">Count</th>
											</tr>
										</thead>
										<tbody>
											{mappings.map((m, i) => (
												<tr key={i} className="border-b border-[#334155]/50">
													<td className="py-2 text-slate-300">{m.source_type}</td>
													<td className="text-white">{m.target_type}</td>
													<td className="text-right text-[#38BDF8] font-mono">{m.count}</td>
												</tr>
											))}
										</tbody>
									</table>
								) : (
									<p className="text-sm text-slate-400 text-center py-6">
										No mappings yet. Upload a BIM file to see element mappings.
									</p>
								)}
							</CardContent>
						</Card>
					</>
				)}
			</div>
		</div>
	);
}
