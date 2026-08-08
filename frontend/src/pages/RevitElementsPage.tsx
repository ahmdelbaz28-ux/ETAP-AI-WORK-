/**
 * RevitElementsPage.tsx — Revit Elements (REAL API)
 *
 * V8.1: Connected to REAL backend endpoints:
 *   GET    /api/v1/revit/elements              — all elements in document
 *   GET    /api/v1/revit/elements/selected      — currently selected elements
 *   GET    /api/v1/revit/elements/{id}          — element by ID
 *   GET    /api/v1/revit/elements/{id}/parameters — element parameters
 *   DELETE /api/v1/revit/elements/{id}          — delete element
 */
import { Loader2, RefreshCw, Trash2 } from "lucide-react";
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

interface RevitElement {
	id: string;
	category: string;
	name: string;
	level: string;
}

interface ElementsResponse {
	elements?: RevitElement[];
	success?: boolean;
	error?: string;
}

export function RevitElementsPage() {
	const [elements, setElements] = useState<RevitElement[]>([]);
	const [selected, setSelected] = useState<RevitElement[]>([]);
	const [loading, setLoading] = useState(true);

	const fetchData = useCallback(async () => {
		setLoading(true);
		try {
			const headers: Record<string, string> = {};
			const apiKey = getApiKey();
			if (apiKey) headers["X-API-Key"] = apiKey;

			const [allResp, selResp] = await Promise.all([
				fetch("/api/v1/revit/elements", { headers }),
				fetch("/api/v1/revit/elements/selected", { headers }),
			]);

			if (allResp.ok) {
				const allData: ElementsResponse = await allResp.json();
				setElements(allData.elements || []);
			}
			if (selResp.ok) {
				const selData: ElementsResponse = await selResp.json();
				setSelected(selData.elements || []);
			}
		} catch (err) {
			toast.error(`Failed: ${err instanceof Error ? err.message : "Revit not connected"}`);
		} finally {
			setLoading(false);
		}
	}, []);

	useEffect(() => {
		fetchData();
	}, [fetchData]);

	const handleDelete = async (id: string) => {
		try {
			const headers: Record<string, string> = {};
			const apiKey = getApiKey();
			if (apiKey) headers["X-API-Key"] = apiKey;
			const resp = await fetch(`/api/v1/revit/elements/${id}`, { method: "DELETE", headers });
			if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
			toast.success("Element deleted");
			fetchData();
		} catch (err) {
			toast.error(`Delete failed: ${err instanceof Error ? err.message : "Unknown"}`);
		}
	};

	return (
		<div className="flex-1 overflow-auto p-6">
			<div className="max-w-7xl mx-auto space-y-6">
				<div className="flex items-center justify-between">
					<div>
						<h1 className="text-2xl font-bold text-white">Revit Elements</h1>
						<p className="text-sm text-slate-400 mt-1">
							Real API: /api/v1/revit/elements · {elements.length} total · {selected.length} selected
						</p>
					</div>
					<Button variant="outline" onClick={fetchData} disabled={loading} className="bg-[#1E293B] border-[#334155] text-white hover:bg-[#334155]">
						{loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
					</Button>
				</div>

				{loading ? (
					<div className="flex items-center justify-center py-12">
						<Loader2 className="h-8 w-8 animate-spin text-[#E84040]" />
					</div>
				) : (
					<>
						{selected.length > 0 && (
							<Card className="bg-[#1E293B] border-[#38BDF8]/30">
								<CardHeader>
									<CardTitle className="text-white text-base">Selected Elements</CardTitle>
									<CardDescription>From /api/v1/revit/elements/selected</CardDescription>
								</CardHeader>
								<CardContent>
									<div className="space-y-1">
										{selected.map((el) => (
											<div key={el.id} className="flex items-center gap-3 p-2 bg-[#38BDF8]/5 rounded text-sm">
												<span className="text-[#38BDF8] font-mono text-xs">{el.id}</span>
												<span className="text-white">{el.name}</span>
												<span className="text-slate-400">{el.category}</span>
											</div>
										))}
									</div>
								</CardContent>
							</Card>
						)}

						<Card className="bg-[#1E293B] border-[#334155]">
							<CardHeader>
								<CardTitle className="text-white text-base">All Elements</CardTitle>
								<CardDescription>From /api/v1/revit/elements</CardDescription>
							</CardHeader>
							<CardContent>
								{elements.length > 0 ? (
									<div className="overflow-x-auto">
										<table className="w-full text-sm">
											<thead>
												<tr className="text-slate-400 text-xs uppercase border-b border-[#334155]">
													<th className="text-left py-2 px-2">ID</th>
													<th className="text-left px-2">Name</th>
													<th className="text-left px-2">Category</th>
													<th className="text-left px-2">Level</th>
													<th className="text-right px-2">Actions</th>
												</tr>
											</thead>
											<tbody>
												{elements.slice(0, 100).map((el) => (
													<tr key={el.id} className="border-b border-[#334155]/50">
														<td className="py-2 px-2 text-slate-300 font-mono text-xs">{el.id}</td>
														<td className="px-2 text-white">{el.name}</td>
														<td className="px-2 text-slate-400">{el.category}</td>
														<td className="px-2 text-slate-400">{el.level || "—"}</td>
														<td className="px-2 text-right">
															<Button variant="ghost" size="sm" onClick={() => handleDelete(el.id)} className="text-[#E84040] p-1">
																<Trash2 className="h-3.5 w-3.5" />
															</Button>
														</td>
													</tr>
												))}
											</tbody>
										</table>
										{elements.length > 100 && <p className="text-xs text-slate-500 mt-2 text-center">Showing 100 of {elements.length}</p>}
									</div>
								) : (
									<p className="text-sm text-slate-400 text-center py-6">No elements. Connect to Revit via /api/v1/revit/connect</p>
								)}
							</CardContent>
						</Card>
					</>
				)}
			</div>
		</div>
	);
}
