/**
 * DigitalTwinConvertPage.tsx — Digital Twin Conversion (REAL API)
 *
 * V8.1: Connected to REAL backend endpoints:
 *   POST /api/v1/digital-twin/convert           — convert BIM file
 *   POST /api/v1/digital-twin/upload-and-convert — upload + convert
 *   GET  /api/v1/digital-twin/download/{filename} — download converted file
 */
import { Download, Loader2, Upload } from "lucide-react";
import { useRef, useState } from "react";
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

interface ConvertResult {
	success?: boolean;
	output_file?: string;
	download_url?: string;
	error?: string;
}

export function DigitalTwinConvertPage() {
	const [uploading, setUploading] = useState(false);
	const [result, setResult] = useState<ConvertResult | null>(null);
	const fileRef = useRef<HTMLInputElement>(null);

	const handleUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
		const file = event.target.files?.[0];
		if (!file) return;
		setUploading(true);
		setResult(null);
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

			if (!resp.ok) {
				const err = await resp.json().catch(() => ({}));
				throw new Error(err?.detail || `HTTP ${resp.status}`);
			}

			const data: ConvertResult = await resp.json();
			setResult(data);
			toast.success(`Converted: ${file.name}`);
		} catch (err) {
			toast.error(`Conversion failed: ${err instanceof Error ? err.message : "Unknown"}`);
		} finally {
			setUploading(false);
		}
	};

	const handleDownload = async (filename: string) => {
		try {
			const apiKey = getApiKey();
			const headers: Record<string, string> = {};
			if (apiKey) headers["X-API-Key"] = apiKey;
			const resp = await fetch(`/api/v1/digital-twin/download/${filename}`, { headers });
			if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
			const blob = await resp.blob();
			const url = URL.createObjectURL(blob);
			const a = document.createElement("a");
			a.href = url;
			a.download = filename;
			a.click();
			URL.revokeObjectURL(url);
		} catch (err) {
			toast.error(`Download failed: ${err instanceof Error ? err.message : "Unknown"}`);
		}
	};

	return (
		<div className="flex-1 overflow-auto p-6">
			<div className="max-w-3xl mx-auto space-y-6">
				<div>
					<h1 className="text-2xl font-bold text-white">Digital Twin Conversion</h1>
					<p className="text-sm text-slate-400 mt-1">
						Real API: POST /api/v1/digital-twin/upload-and-convert
					</p>
				</div>

				<Card className="bg-[#1E293B] border-[#334155] border-dashed">
					<CardContent className="pt-6">
						<label className="flex flex-col items-center justify-center py-12 text-center cursor-pointer">
							<div className="h-16 w-16 rounded-full bg-[#A78BFA]/10 flex items-center justify-center mb-4">
								{uploading ? <Loader2 className="h-8 w-8 text-[#A78BFA] animate-spin" /> : <Upload className="h-8 w-8 text-[#A78BFA]" />}
							</div>
							<p className="text-white font-medium">
								{uploading ? "Converting..." : "Upload BIM file for conversion"}
							</p>
							<p className="text-sm text-slate-400 mt-1">.rvt, .ifc, .dwg, .dxf → IFC4/DXF/JSON</p>
							<input ref={fileRef} type="file" className="hidden" onChange={handleUpload} accept=".rvt,.ifc,.dwg,.dxf" />
						</label>
					</CardContent>
				</Card>

				{result && (
					<Card className="bg-[#1E293B] border-[#334155]">
						<CardHeader>
							<CardTitle className="text-white">Conversion Result</CardTitle>
							<CardDescription>Real response from conversion API</CardDescription>
						</CardHeader>
						<CardContent>
							{result.error ? (
								<p className="text-sm text-[#E84040]">{result.error}</p>
							) : (
								<div className="space-y-3">
									<pre className="text-xs text-slate-300 font-mono overflow-x-auto bg-[#0F172A] p-4 rounded-md border border-[#334155]">
										{JSON.stringify(result, null, 2)}
									</pre>
									{result.output_file && (
										<Button onClick={() => handleDownload(result.output_file!)} className="bg-[#A78BFA] hover:bg-[#A78BFA]/80 text-white">
											<Download className="h-4 w-4 mr-2" />
											Download {result.output_file}
										</Button>
									)}
								</div>
							)}
						</CardContent>
					</Card>
				)}
			</div>
		</div>
	);
}
