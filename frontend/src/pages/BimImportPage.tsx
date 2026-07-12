/**
 * BimImportPage.tsx — BIM Import (Revit/IFC/DXF)
 *
 * V8.1 Screen 9.2: Per Stitch-Ready UI Prompt
 * Dropzone for .rvt/.ifc/.dwg/.dxf, geometry preview, element mapping.
 */
import { Upload, FileBox, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";

const elementMapping = [
	{ revit: "Rooms", bazspark: "Room", count: 1247 },
	{ revit: "Walls", bazspark: "Obstacle", count: 3421 },
	{ revit: "Doors", bazspark: "Opening", count: 189 },
	{ revit: "Windows", bazspark: "Opening", count: 156 },
	{ revit: "Floors", bazspark: "Level", count: 8 },
	{ revit: "MEP Equipment", bazspark: "Device", count: 312 },
];

export function BimImportPage() {
	return (
		<div className="flex-1 overflow-auto p-6">
			<div className="max-w-5xl mx-auto space-y-6">
				<div>
					<h1 className="text-2xl font-bold text-white">BIM Import</h1>
					<p className="text-sm text-slate-400 mt-1">
						Import Revit (.rvt) · IFC · AutoCAD (.dwg/.dxf) · JSON · max 500MB
					</p>
				</div>

				{/* Dropzone */}
				<Card className="bg-[#1E293B] border-[#334155] border-dashed">
					<CardContent className="pt-6">
						<div className="flex flex-col items-center justify-center py-12 text-center">
							<div className="h-16 w-16 rounded-full bg-[#E84040]/10 flex items-center justify-center mb-4">
								<Upload className="h-8 w-8 text-[#E84040]" />
							</div>
							<p className="text-white font-medium">Drop BIM file here</p>
							<p className="text-sm text-slate-400 mt-1">
								Supported: .rvt, .ifc, .dwg, .dxf, .json — max 500MB
							</p>
							<Button className="mt-4 bg-[#E84040] hover:bg-[#B91C1C] text-white">
								Browse Files
							</Button>
						</div>
					</CardContent>
				</Card>

				{/* Element mapping */}
				<Card className="bg-[#1E293B] border-[#334155]">
					<CardHeader>
						<CardTitle className="text-white flex items-center gap-2">
							<FileBox className="h-5 w-5 text-[#38BDF8]" />
							Element Mapping
						</CardTitle>
						<CardDescription className="text-slate-400">
							Revit Category → BAZspark Type (auto-mapped, editable)
						</CardDescription>
					</CardHeader>
					<CardContent>
						<table className="w-full text-sm">
							<thead>
								<tr className="text-slate-400 text-xs uppercase border-b border-[#334155]">
									<th className="text-left py-2">Revit Category</th>
									<th className="text-center"></th>
									<th className="text-left">BAZspark Type</th>
									<th className="text-right">Count</th>
								</tr>
							</thead>
							<tbody>
								{elementMapping.map((row) => (
									<tr key={row.revit} className="border-b border-[#334155]/50">
										<td className="py-2.5 text-slate-300">{row.revit}</td>
										<td className="text-center">
											<ArrowRight className="h-3 w-3 text-slate-500 inline" />
										</td>
										<td className="text-white">{row.bazspark}</td>
										<td className="text-right text-[#38BDF8] font-mono">{row.count.toLocaleString()}</td>
									</tr>
								))}
							</tbody>
						</table>
					</CardContent>
				</Card>

				<Button className="w-full bg-[#E84040] hover:bg-[#B91C1C] text-white h-12">
					Import &amp; Analyze
				</Button>
			</div>
		</div>
	);
}
