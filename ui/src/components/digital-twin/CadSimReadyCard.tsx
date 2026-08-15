import { motion } from "framer-motion";
import {
  CheckCircle2,
  Cpu,
  Download,
  FileText as FileCode,
  Layers,
  Loader2,
  Sparkles,
} from "lucide-react";
import { useEffect, useState } from "react";
import { Badge, Button, Card, CardHeader, Input, Select, Toggle } from "../ui";
import { useNotify } from "../../context/NotificationContext";
import { API_BASE_URL } from "../../lib/api-config";
import { getAuthToken } from "../../lib/tokenStorage";

interface SimReadyNode {
  prim_path: string;
  type: string;
  material: string;
  physics_mass?: number;
  voltage_rating?: string;
  status?: string;
}

interface ConvertResponse {
  success: boolean;
  asset_id: string;
  asset_name: string;
  output_usd_path: string;
  output_usdz_path?: string;
  elements_processed: number;
  physics_bound: boolean;
  material_preset: string;
  nodes: SimReadyNode[];
  message: string;
}

interface Preset {
  id: string;
  name: string;
  description: string;
}

export function CadSimReadyCard() {
  const { notify } = useNotify();
  const [assetName, setAssetName] = useState("Substation_Unit_138kV");
  const [sourceFile, setSourceFile] = useState("substation_layout.dxf");
  const [enablePhysics, setEnablePhysics] = useState(true);
  const [exportUsdz, setExportUsdz] = useState(true);
  const [lodLevel, setLodLevel] = useState("high");
  const [materialPreset, setMaterialPreset] = useState("industrial_copper_steel");
  const [presets, setPresets] = useState<Preset[]>([]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ConvertResponse | null>(null);

  // Fetch presets on mount
  useEffect(() => {
    const fetchPresets = async () => {
      try {
        const token = getAuthToken();
        const res = await fetch(`${API_BASE_URL}/api/v1/cad-simready/presets`, {
          headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        });
        if (res.ok) {
          const data = await res.json();
          setPresets(data.presets || []);
        }
      } catch {
        // Fallback preset if backend offline
        setPresets([
          {
            id: "industrial_copper_steel",
            name: "Industrial Electrical (Copper & Steel)",
            description: "PBR materials for transformers, copper busbars, and steel enclosures.",
          },
        ]);
      }
    };
    fetchPresets();
  }, []);

  const handleConvert = async () => {
    setLoading(true);
    try {
      const token = getAuthToken();
      const res = await fetch(`${API_BASE_URL}/api/v1/cad-simready/convert`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          source_filename: sourceFile,
          asset_name: assetName,
          enable_physics: enablePhysics,
          material_preset: materialPreset,
          lod_level: lodLevel,
          export_usdz: exportUsdz,
        }),
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: ConvertResponse = await res.json();
      setResult(data);
      notify("success", `Generated SimReady 3D OpenUSD asset for '${data.asset_name}'`);
    } catch {
      notify("error", "Failed to generate SimReady 3D asset");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card variant="default" className="border-[var(--border-primary)] shadow-lg overflow-hidden">
      <CardHeader
        className="bg-gradient-to-r from-emerald-900/20 via-slate-900/40 to-cyan-900/20 border-b border-[var(--border-primary)] pb-4"
        icon={
          <div className="p-2.5 bg-emerald-500/10 rounded-xl border border-emerald-500/20 text-emerald-400">
            <Sparkles className="w-5 h-5 animate-pulse" />
          </div>
        }
        title={
          <span className="flex items-center gap-2">
            NVIDIA CAD to SimReady 3D Engine
            <Badge variant="success" size="sm">
              Active Skill
            </Badge>
          </span>
        }
        subtitle="Convert CAD/DXF & Revit BIM layouts to interactive 3D OpenUSD presentation models with physics & PBR materials."
        action={
          <Badge variant="info" size="sm" className="hidden sm:flex items-center gap-1">
            <Cpu className="w-3 h-3" /> PhysX 5 / OpenUSD
          </Badge>
        }
      />

      <div className="p-5 space-y-5">
        {/* Controls Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="text-xs font-medium text-[var(--text-secondary)] mb-1.5 block">
              CAD/BIM Source File
            </label>
            <Input
              value={sourceFile}
              onChange={(e) => setSourceFile(e.target.value)}
              placeholder="e.g. substation_layout.dxf"
            />
          </div>

          <div>
            <label className="text-xs font-medium text-[var(--text-secondary)] mb-1.5 block">
              Target 3D Asset Name
            </label>
            <Input
              value={assetName}
              onChange={(e) => setAssetName(e.target.value)}
              placeholder="e.g. Main_Substation_138kV"
            />
          </div>

          <div>
            <label className="text-xs font-medium text-[var(--text-secondary)] mb-1.5 block">
              PBR Material Preset (MDL)
            </label>
            <Select
              value={materialPreset}
              onChange={(e) => setMaterialPreset(e.target.value)}
              options={presets.length > 0 ? presets.map((p) => ({ value: p.id, label: p.name })) : [{ value: "industrial_copper_steel", label: "Industrial Electrical (Copper & Steel)" }]}
            />
          </div>

          <div>
            <label className="text-xs font-medium text-[var(--text-secondary)] mb-1.5 block">
              Level of Detail (LOD)
            </label>
            <Select value={lodLevel} onChange={(e) => setLodLevel(e.target.value)} options={[{ value: "high", label: "High (Full Geometry & Sub-assemblies)" }, { value: "medium", label: "Medium (Standard Interactive Presentation)" }, { value: "low", label: "Low (Lightweight Web Viewer)" }]} />
          </div>
        </div>

        {/* Toggles */}
        <div className="flex flex-wrap items-center justify-between gap-4 p-3 bg-[var(--bg-primary)] rounded-lg border border-[var(--border-primary)]">
          <div className="flex items-center space-x-3 gap-3">
            <Toggle checked={enablePhysics} onChange={setEnablePhysics} />
            <div>
              <span className="text-xs font-semibold text-[var(--text-primary)] block">
                UsdPhysics Rigid Body & Mass
              </span>
              <span className="text-[11px] text-[var(--text-secondary)]">
                Attach physical mass, friction, and collision meshes for 3D physics simulation.
              </span>
            </div>
          </div>

          <div className="flex items-center space-x-3 gap-3">
            <Toggle checked={exportUsdz} onChange={setExportUsdz} />
            <div>
              <span className="text-xs font-semibold text-[var(--text-primary)] block">
                Package USDZ for AR Presentation
              </span>
              <span className="text-[11px] text-[var(--text-secondary)]">
                Create iOS QuickLook & Web 3D preview archive.
              </span>
            </div>
          </div>
        </div>

        {/* Action Button */}
        <div className="flex items-center justify-end space-x-3 gap-3 pt-1">
          <Button
            variant="primary"
            onClick={handleConvert}
            disabled={loading}
            className="w-full sm:w-auto bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-medium"
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Generating SimReady 3D Asset...
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4 mr-2" />
                Generate SimReady 3D Presentation
              </>
            )}
          </Button>
        </div>

        {/* Result & USD Prim Tree View */}
        {result && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-4 p-4 rounded-lg bg-[var(--bg-primary)] border border-emerald-500/30 space-y-4"
          >
            <div className="flex items-center justify-between pb-3 border-b border-[var(--border-primary)]">
              <div className="flex items-center space-x-2 gap-2 text-emerald-400 font-medium text-xs">
                <CheckCircle2 className="w-4 h-4" />
                <span>3D SimReady OpenUSD Generated Successfully</span>
              </div>
              <div className="flex items-center space-x-2 gap-2">
                <Button variant="secondary" size="sm" onClick={() => notify("info", `Downloading ${result.output_usd_path}`)}>
                  <Download className="w-3.5 h-3.5 mr-1" /> OpenUSD (.usda)
                </Button>
                {result.output_usdz_path && (
                  <Button variant="outline" size="sm" onClick={() => notify("info", `Downloading ${result.output_usdz_path}`)}>
                    <Download className="w-3.5 h-3.5 mr-1" /> USDZ (AR)
                  </Button>
                )}
              </div>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
              <div className="p-2 bg-[var(--bg-card)] rounded border border-[var(--border-primary)]">
                <span className="text-[var(--text-secondary)] block text-[10px]">Asset ID</span>
                <span className="font-mono font-semibold text-[var(--text-primary)]">{result.asset_id}</span>
              </div>
              <div className="p-2 bg-[var(--bg-card)] rounded border border-[var(--border-primary)]">
                <span className="text-[var(--text-secondary)] block text-[10px]">Elements Processed</span>
                <span className="font-semibold text-[var(--text-primary)]">{result.elements_processed} Prim Nodes</span>
              </div>
              <div className="p-2 bg-[var(--bg-card)] rounded border border-[var(--border-primary)]">
                <span className="text-[var(--text-secondary)] block text-[10px]">Physics Bound</span>
                <span className="font-semibold text-emerald-400">{result.physics_bound ? "Enabled (PhysX)" : "Disabled"}</span>
              </div>
              <div className="p-2 bg-[var(--bg-card)] rounded border border-[var(--border-primary)]">
                <span className="text-[var(--text-secondary)] block text-[10px]">Material Preset</span>
                <span className="font-semibold text-[var(--text-primary)]">{result.material_preset}</span>
              </div>
            </div>

            {/* USD Hierarchy Tree Preview */}
            <div>
              <h4 className="text-xs font-semibold text-[var(--text-secondary)] mb-2 flex items-center gap-1.5">
                <Layers className="w-3.5 h-3.5" /> USD Prim Hierarchy & Materials
              </h4>
              <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
                {result.nodes.map((node, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-between p-2 rounded bg-[var(--bg-card)] border border-[var(--border-primary)] text-xs font-mono"
                  >
                    <div className="flex items-center space-x-2 gap-2 truncate">
                      <FileJson className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
                      <span className="text-[var(--text-primary)] truncate">{node.prim_path}</span>
                    </div>
                    <div className="flex items-center space-x-2 gap-2 shrink-0">
                      <Badge variant="default" size="sm">
                        {node.type}
                      </Badge>
                      <Badge variant="info" size="sm">
                        {node.material}
                      </Badge>
                      {node.physics_mass ? (
                        <Badge variant="warning" size="sm">
                          {node.physics_mass} kg
                        </Badge>
                      ) : null}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </motion.div>
        )}
      </div>
    </Card>
  );
}
