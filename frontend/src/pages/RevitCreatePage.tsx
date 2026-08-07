/**
 * RevitCreatePage.tsx — Revit Element Creation (REAL API)
 *
 * V8.1: Connected to REAL backend endpoints:
 *   POST /api/v1/revit/elements/create/wall    — create wall
 *   POST /api/v1/revit/elements/create/door    — create door
 *   POST /api/v1/revit/elements/create/window  — create window
 *   POST /api/v1/revit/elements/create/column  — create column
 *   POST /api/v1/revit/elements/create/beam    — create beam
 *   POST /api/v1/revit/elements/create/floor   — create floor
 */
import { Box, Building2, Columns, Loader2, Plus } from "lucide-react";
import { useState } from "react";
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

type ElementType = "wall" | "door" | "window" | "column" | "beam" | "floor";

const elementTypes: Array<{ type: ElementType; label: string; icon: typeof Box }> = [
	{ type: "wall", label: "Wall", icon: Building2 },
	{ type: "door", label: "Door", icon: Box },
	{ type: "window", label: "Window", icon: Box },
	{ type: "column", label: "Column", icon: Columns },
	{ type: "beam", label: "Beam", icon: Box },
	{ type: "floor", label: "Floor", icon: Box },
];

export function RevitCreatePage() {
	const [selectedType, setSelectedType] = useState<ElementType>("wall");
	const [x1, setX1] = useState("0");
	const [y1, setY1] = useState("0");
	const [x2, setX2] = useState("5");
	const [y2, setY2] = useState("0");
	const [loading, setLoading] = useState(false);

	const handleCreate = async () => {
		setLoading(true);
		try {
			const headers: Record<string, string> = { "Content-Type": "application/json" };
			const apiKey = getApiKey();
			if (apiKey) headers["X-API-Key"] = apiKey;

			const body = {
				start_point: [parseFloat(x1), parseFloat(y1), 0],
				end_point: [parseFloat(x2), parseFloat(y2), 3],
				level: "Level 1",
			};

			const resp = await fetch(`/api/v1/revit/elements/create/${selectedType}`, {
				method: "POST",
				headers,
				body: JSON.stringify(body),
			});

			if (!resp.ok) {
				const err = await resp.json().catch(() => ({}));
				throw new Error(err?.detail || `HTTP ${resp.status}`);
			}

			const data = await resp.json();
			toast.success(`${selectedType} created: ${data.element_id || "success"}`);
		} catch (err) {
			toast.error(`Create failed: ${err instanceof Error ? err.message : "Revit not connected"}`);
		} finally {
			setLoading(false);
		}
	};

	return (
		<div className="flex-1 overflow-auto p-6">
			<div className="max-w-3xl mx-auto space-y-6">
				<div>
					<h1 className="text-2xl font-bold text-white">Create Revit Element</h1>
					<p className="text-sm text-slate-400 mt-1">
						Real API: POST /api/v1/revit/elements/create/{"{type}"}
					</p>
				</div>

				<Card className="bg-[#1E293B] border-[#334155]">
					<CardHeader>
						<CardTitle className="text-white">Element Type</CardTitle>
						<CardDescription>Select the type of Revit element to create</CardDescription>
					</CardHeader>
					<CardContent>
						<div className="grid grid-cols-3 gap-3">
							{elementTypes.map(({ type, label, icon: Icon }) => (
								<button
									key={type}
									onClick={() => setSelectedType(type)}
									className={`flex flex-col items-center gap-2 p-4 rounded-md border transition-colors ${
										selectedType === type
											? "bg-[#E84040]/10 border-[#E84040] text-[#E84040]"
											: "bg-[#0F172A] border-[#334155] text-slate-400 hover:text-white"
									}`}
								>
									<Icon className="h-6 w-6" />
									<span className="text-sm font-medium">{label}</span>
								</button>
							))}
						</div>
					</CardContent>
				</Card>

				<Card className="bg-[#1E293B] border-[#334155]">
					<CardHeader>
						<CardTitle className="text-white text-base">Geometry — {selectedType}</CardTitle>
					</CardHeader>
					<CardContent className="space-y-4">
						<div className="grid grid-cols-2 gap-4">
							<div>
								<Label className="text-slate-400 text-xs">Start X</Label>
								<Input type="number" value={x1} onChange={(e) => setX1(e.target.value)} className="bg-[#0F172A] border-[#334155] text-white font-mono" />
							</div>
							<div>
								<Label className="text-slate-400 text-xs">Start Y</Label>
								<Input type="number" value={y1} onChange={(e) => setY1(e.target.value)} className="bg-[#0F172A] border-[#334155] text-white font-mono" />
							</div>
							<div>
								<Label className="text-slate-400 text-xs">End X</Label>
								<Input type="number" value={x2} onChange={(e) => setX2(e.target.value)} className="bg-[#0F172A] border-[#334155] text-white font-mono" />
							</div>
							<div>
								<Label className="text-slate-400 text-xs">End Y</Label>
								<Input type="number" value={y2} onChange={(e) => setY2(e.target.value)} className="bg-[#0F172A] border-[#334155] text-white font-mono" />
							</div>
						</div>
						<Button onClick={handleCreate} disabled={loading} className="w-full bg-[#E84040] hover:bg-[#B91C1C] text-white">
							{loading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Plus className="h-4 w-4 mr-2" />}
							Create {selectedType}
						</Button>
						<p className="text-xs text-slate-500 text-center">
							Requires active Revit connection (POST /api/v1/revit/connect)
						</p>
					</CardContent>
				</Card>
			</div>
		</div>
	);
}
