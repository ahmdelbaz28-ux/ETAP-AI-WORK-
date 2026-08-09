/**
 * DigitalTwinConfigPage.tsx — Digital Twin Configuration (REAL API)
 *
 * V8.1: Connected to REAL backend endpoints:
 *   GET /api/v1/digital-twin/config   — current config
 *   PUT /api/v1/digital-twin/config    — update config
 *   POST /api/v1/digital-twin/configure — configure conversion
 */
import { Loader2, RefreshCw, Save } from "lucide-react";
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

interface DtConfig {
	ifc_version: string;
	export_format: string;
	coordinate_system: string;
	unit_system: string;
	[	key: string]: string;
}

export function DigitalTwinConfigPage() {
	const [config, setConfig] = useState<DtConfig | null>(null);
	const [loading, setLoading] = useState(true);
	const [saving, setSaving] = useState(false);

	const fetchConfig = useCallback(async () => {
		setLoading(true);
		try {
			const headers: Record<string, string> = {};
			const apiKey = getApiKey();
			if (apiKey) headers["X-API-Key"] = apiKey;
			const resp = await fetch("/api/v1/digital-twin/config", { headers });
			if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
			const data = await resp.json();
			setConfig(data.config || data.data?.config || data);
		} catch (err) {
			toast.error(`Failed: ${err instanceof Error ? err.message : "Unknown"}`);
		} finally {
			setLoading(false);
		}
	}, []);

	useEffect(() => {
		fetchConfig();
	}, [fetchConfig]);

	const handleSave = async () => {
		if (!config) return;
		setSaving(true);
		try {
			const headers: Record<string, string> = { "Content-Type": "application/json" };
			const apiKey = getApiKey();
			if (apiKey) headers["X-API-Key"] = apiKey;
			const resp = await fetch("/api/v1/digital-twin/config", {
				method: "PUT",
				headers,
				body: JSON.stringify(config),
			});
			if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
			toast.success("Configuration saved");
		} catch (err) {
			toast.error(`Save failed: ${err instanceof Error ? err.message : "Unknown"}`);
		} finally {
			setSaving(false);
		}
	};

	return (
		<div className="flex-1 overflow-auto p-6">
			<div className="max-w-3xl mx-auto space-y-6">
				<div className="flex items-center justify-between">
					<div>
						<h1 className="text-2xl font-bold text-white">Digital Twin Configuration</h1>
						<p className="text-sm text-slate-400 mt-1">Real API: GET/PUT /api/v1/digital-twin/config</p>
					</div>
					<Button variant="outline" onClick={fetchConfig} disabled={loading} className="bg-[#1E293B] border-[#334155] text-white hover:bg-[#334155]">
						{loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
					</Button>
				</div>

				{loading ? (
					<div className="flex items-center justify-center py-12">
						<Loader2 className="h-8 w-8 animate-spin text-[#A78BFA]" />
					</div>
				) : config ? (
					<Card className="bg-[#1E293B] border-[#334155]">
						<CardHeader>
							<CardTitle className="text-white">Configuration</CardTitle>
							<CardDescription>Edit and save via PUT /api/v1/digital-twin/config</CardDescription>
						</CardHeader>
						<CardContent className="space-y-4">
							{Object.entries(config).slice(0, 8).map(([key, val]) => (
								<div key={key}>
									<Label className="text-slate-400 text-xs">{key.replace(/_/g, " ")}</Label>
									<Input
										value={String(val)}
										onChange={(e) => setConfig({ ...config, [key]: e.target.value })}
										className="bg-[#0F172A] border-[#334155] text-white font-mono"
									/>
								</div>
							))}
							<Button onClick={handleSave} disabled={saving} className="w-full bg-[#A78BFA] hover:bg-[#A78BFA]/80 text-white">
								{saving ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Save className="h-4 w-4 mr-2" />}
								Save Configuration
							</Button>
						</CardContent>
					</Card>
				) : null}
			</div>
		</div>
	);
}
