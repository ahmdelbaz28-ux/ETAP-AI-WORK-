import {
  AlertTriangle,
  CheckCircle,
  Download,
  Link2,
  MousePointer,
  Play,
  Plus,
  Sliders,
  Sparkles,
  Trash2,
  Zap,
} from "lucide-react";
import type React from "react";
import { useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Badge, Button, Card } from "../components/ui";
import { useNotify } from "../context/NotificationContext";
import { API_BASE_URL } from "../lib/api-config";
import { cn } from "../utils/helpers";

// Types for local components representation
interface Bus {
  id: number;
  name: string;
  x: number;
  y: number;
  type: "slack" | "pv" | "pq";
  baseKv: number;
  voltageMagnitude: number;
  voltageAngle: number;
}

interface Line {
  id: number;
  fromBusId: number;
  toBusId: number;
  r1: number;
  x1: number;
  bshunt1: number;
}

interface Generator {
  id: number;
  busId: number;
  name: string;
  pg: number;
  qg: number;
  vSetpoint: number;
}

interface Load {
  id: number;
  busId: number;
  name: string;
  pMw: number;
  qMvar: number;
}

const CAIRO_TEMPLATE = {
  buses: [
    {
      id: 1,
      name: "Cairo West Gen Bus",
      x: 150,
      y: 150,
      type: "slack",
      baseKv: 13.8,
      voltageMagnitude: 1.05,
      voltageAngle: 0,
    },
    {
      id: 2,
      name: "Giza Distribution Bus",
      x: 450,
      y: 150,
      type: "pq",
      baseKv: 13.8,
      voltageMagnitude: 1.0,
      voltageAngle: 0,
    },
    {
      id: 3,
      name: "Helwan Substation Bus",
      x: 300,
      y: 350,
      type: "pq",
      baseKv: 13.8,
      voltageMagnitude: 1.0,
      voltageAngle: 0,
    },
  ] as Bus[],
  lines: [
    { id: 1, fromBusId: 1, toBusId: 2, r1: 0.015, x1: 0.045, bshunt1: 0.02 },
    { id: 2, fromBusId: 2, toBusId: 3, r1: 0.02, x1: 0.06, bshunt1: 0.02 },
    { id: 3, fromBusId: 1, toBusId: 3, r1: 0.018, x1: 0.055, bshunt1: 0.02 },
  ] as Line[],
  generators: [
    { id: 1, busId: 1, name: "G1 East Nile", pg: 80.0, qg: 25.0, vSetpoint: 1.05 },
  ] as Generator[],
  loads: [
    { id: 1, busId: 2, name: "Giza City Center", pMw: 45.0, qMvar: 15.0 },
    { id: 2, busId: 3, name: "Helwan Steel Plant", pMw: 30.0, qMvar: 10.0 },
  ] as Load[],
};

export default function GridEditor() {
  const { i18n } = useTranslation();
  const { notify } = useNotify();
  const isRtl = i18n.language === "ar";

  // Canvas State
  const [buses, setBuses] = useState<Bus[]>(CAIRO_TEMPLATE.buses);
  const [lines, setLines] = useState<Line[]>(CAIRO_TEMPLATE.lines);
  const [generators, setGenerators] = useState<Generator[]>(CAIRO_TEMPLATE.generators);
  const [loads, setLoads] = useState<Load[]>(CAIRO_TEMPLATE.loads);

  const [activeMode, setActiveMode] = useState<"select" | "bus" | "line" | "generator" | "load">(
    "select",
  );
  const [selectedElement, setSelectedElement] = useState<{
    type: "bus" | "line" | "generator" | "load";
    id: number;
  } | null>(null);
  const [connectingBusId, setConnectingBusId] = useState<number | null>(null);

  // Dragging State
  const [draggingNode, setDraggingNode] = useState<{
    id: number;
    offset: { x: number; y: number };
  } | null>(null);

  // API Results
  const [validationResults, setValidationResults] = useState<{
    valid: boolean;
    errors?: string[];
    warnings?: string[];
  } | null>(null);
  const [simulationResults, setSimulationResults] = useState<any | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  // Refs for tracking SVG mouse position
  const svgRef = useRef<SVGSVGElement>(null);

  // Load Egypt Grid Template
  const loadCairoTemplate = () => {
    setBuses(JSON.parse(JSON.stringify(CAIRO_TEMPLATE.buses)));
    setLines(JSON.parse(JSON.stringify(CAIRO_TEMPLATE.lines)));
    setGenerators(JSON.parse(JSON.stringify(CAIRO_TEMPLATE.generators)));
    setLoads(JSON.parse(JSON.stringify(CAIRO_TEMPLATE.loads)));
    setSelectedElement(null);
    setSimulationResults(null);
    setValidationResults(null);
    notify(
      "success",
      isRtl ? "تم تحميل نموذج شبكة القاهرة 13.8kV" : "Cairo 13.8kV Grid Template Loaded",
    );
  };

  // Clear Grid
  const clearGrid = () => {
    setBuses([]);
    setLines([]);
    setGenerators([]);
    setLoads([]);
    setSelectedElement(null);
    setSimulationResults(null);
    setValidationResults(null);
    notify("info", isRtl ? "تم تفريغ لوحة الرسم" : "Grid canvas cleared");
  };

  // Handle SVG Mouse down for placing elements or canceling connection
  const handleSvgMouseDown = (e: React.MouseEvent<SVGSVGElement>) => {
    if (activeMode === "select") return;

    const rect = svgRef.current?.getBoundingClientRect();
    if (!rect) return;

    // Standard Grid Snap (snap to 10px)
    const x = Math.round((e.clientX - rect.left) / 10) * 10;
    const y = Math.round((e.clientY - rect.top) / 10) * 10;

    if (activeMode === "bus") {
      const nextId = buses.length > 0 ? Math.max(...buses.map((b) => b.id)) + 1 : 1;
      const newBus: Bus = {
        id: nextId,
        name: `Bus ${nextId}`,
        x,
        y,
        type: "pq",
        baseKv: 13.8,
        voltageMagnitude: 1.0,
        voltageAngle: 0,
      };
      setBuses([...buses, newBus]);
      setActiveMode("select");
      setSelectedElement({ type: "bus", id: nextId });
      notify("success", isRtl ? `تمت إضافة ناقل جديد ${nextId}` : `Added Bus ${nextId}`);
    } else if (activeMode === "line") {
      // Connect line cancel if clicked outside bus
      setConnectingBusId(null);
    }
  };

  // Node Dragging Handlers
  const handleBusMouseDown = (e: React.MouseEvent, bus: Bus) => {
    if (activeMode !== "select") return;
    e.stopPropagation();

    const rect = svgRef.current?.getBoundingClientRect();
    if (!rect) return;

    setDraggingNode({
      id: bus.id,
      offset: {
        x: e.clientX - rect.left - bus.x,
        y: e.clientY - rect.top - bus.y,
      },
    });
    setSelectedElement({ type: "bus", id: bus.id });
  };

  const handleSvgMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    if (!draggingNode) return;

    const rect = svgRef.current?.getBoundingClientRect();
    if (!rect) return;

    const x = Math.round((e.clientX - rect.left - draggingNode.offset.x) / 10) * 10;
    const y = Math.round((e.clientY - rect.top - draggingNode.offset.y) / 10) * 10;

    setBuses((prev) => prev.map((b) => (b.id === draggingNode.id ? { ...b, x, y } : b)));
  };

  const handleSvgMouseUp = () => {
    setDraggingNode(null);
  };

  // Connecting line handler
  const handleBusClick = (e: React.MouseEvent, bus: Bus) => {
    e.stopPropagation();
    if (activeMode === "line") {
      if (connectingBusId === null) {
        setConnectingBusId(bus.id);
        notify(
          "info",
          isRtl ? "اختر الناقل الثاني لإكمال الربط" : "Select second bus to complete link",
        );
      } else if (connectingBusId === bus.id) {
        setConnectingBusId(null);
      } else {
        // Create new Line
        const nextId = lines.length > 0 ? Math.max(...lines.map((l) => l.id)) + 1 : 1;
        const newLine: Line = {
          id: nextId,
          fromBusId: connectingBusId,
          toBusId: bus.id,
          r1: 0.02,
          x1: 0.05,
          bshunt1: 0.02,
        };
        setLines([...lines, newLine]);
        setConnectingBusId(null);
        setActiveMode("select");
        notify(
          "success",
          isRtl ? "تم توصيل خط النقل بنجاح" : "Transmission line connected successfully",
        );
      }
    } else if (activeMode === "generator") {
      const nextId = generators.length > 0 ? Math.max(...generators.map((g) => g.id)) + 1 : 1;
      const newGen: Generator = {
        id: nextId,
        busId: bus.id,
        name: `Gen ${nextId}`,
        pg: 50.0,
        qg: 15.0,
        vSetpoint: 1.0,
      };
      setGenerators([...generators, newGen]);
      // Change target bus type to PV if slack isn't already present
      if (bus.type === "pq") {
        setBuses((prev) => prev.map((b) => (b.id === bus.id ? { ...b, type: "pv" } : b)));
      }
      setActiveMode("select");
      setSelectedElement({ type: "generator", id: nextId });
      notify("success", isRtl ? "تم إضافة المولد بنجاح" : "Generator added successfully");
    } else if (activeMode === "load") {
      const nextId = loads.length > 0 ? Math.max(...loads.map((l) => l.id)) + 1 : 1;
      const newLoad: Load = {
        id: nextId,
        busId: bus.id,
        name: `Load ${nextId}`,
        pMw: 30.0,
        qMvar: 10.0,
      };
      setLoads([...loads, newLoad]);
      setActiveMode("select");
      setSelectedElement({ type: "load", id: nextId });
      notify("success", isRtl ? "تم إضافة الحمل للناقل" : "Load attached to bus");
    } else {
      setSelectedElement({ type: "bus", id: bus.id });
    }
  };

  // Delete Selected Element
  const deleteSelected = () => {
    if (!selectedElement) return;

    const { type, id } = selectedElement;

    if (type === "bus") {
      setBuses((prev) => prev.filter((b) => b.id !== id));
      // Cascade delete attached lines, generators, loads
      setLines((prev) => prev.filter((l) => l.fromBusId !== id && l.toBusId !== id));
      setGenerators((prev) => prev.filter((g) => g.busId !== id));
      setLoads((prev) => prev.filter((l) => l.busId !== id));
    } else if (type === "line") {
      setLines((prev) => prev.filter((l) => l.id !== id));
    } else if (type === "generator") {
      setGenerators((prev) => prev.filter((g) => g.id !== id));
    } else if (type === "load") {
      setLoads((prev) => prev.filter((l) => l.id !== id));
    }

    setSelectedElement(null);
    notify("info", isRtl ? "تم الحذف بنجاح" : "Element deleted successfully");
  };

  // Export current grid state to SystemSpec format
  const getSystemSpecJson = () => {
    return {
      base_mva: 100.0,
      buses: buses.map((b) => ({
        bus_id: b.id,
        voltage_magnitude: b.voltageMagnitude,
        voltage_angle: b.voltageAngle,
        bus_type: b.type,
        base_kv: b.baseKv,
      })),
      lines: lines.map((l) => ({
        line_id: l.id,
        from_bus_id: l.fromBusId,
        to_bus_id: l.toBusId,
        r1: l.r1,
        x1: l.x1,
        bshunt1: l.bshunt1,
      })),
      generators: generators.map((g) => ({
        generator_id: g.id,
        bus_id: g.busId,
        pg: g.pg,
        qg: g.qg,
        v_setpoint: g.vSetpoint,
      })),
      loads: loads.map((l) => ({
        load_id: l.id,
        bus_id: l.busId,
        p_mw: l.pMw,
        q_mvar: l.qMvar,
      })),
    };
  };

  // Call backend Validation endpoint
  const handleValidateGrid = async () => {
    setIsLoading(true);
    setValidationResults(null);
    try {
      const spec = getSystemSpecJson();
      const token = localStorage.getItem("authToken");
      const response = await fetch(`${API_BASE_URL}/api/v1/system/validate`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(spec),
      });

      if (!response.ok) {
        throw new Error(await response.text());
      }

      const data = await response.json();
      setValidationResults(data);
      if (data.valid) {
        notify("success", isRtl ? "الشبكة صالحة هندسياً" : "Grid structure is structurally valid");
      } else {
        notify("error", isRtl ? "فشل التحقق من صحة الشبكة" : "Grid failed validation checks");
      }
    } catch (err: any) {
      notify("error", `Error: ${err.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  // Call backend Simulation (Load Flow) endpoint
  const handleRunLoadFlow = async () => {
    setIsLoading(true);
    setSimulationResults(null);
    try {
      const spec = getSystemSpecJson();
      const token = localStorage.getItem("authToken");
      const response = await fetch(`${API_BASE_URL}/api/v1/studies/run`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          study_type: "load_flow",
          system: spec,
          parameters: {},
          use_etap: false,
        }),
      });

      if (!response.ok) {
        throw new Error(await response.text());
      }

      const body = await response.json();
      // Real calculations extract results from study body
      const results = body.results || body.data;
      setSimulationResults(results);

      if (body.success && results.converged) {
        notify(
          "success",
          isRtl
            ? "اكتمل حل سريان الحمل (نيوتن-رافسون)"
            : "Load flow converged successfully (Newton-Raphson)",
        );
        // Update buses with actual calculated voltage profiles from simulation!
        if (results.buses) {
          setBuses((prev) =>
            prev.map((b) => {
              const resBus = results.buses[String(b.id)] || results.buses[`Bus${b.id}`];
              if (resBus) {
                return {
                  ...b,
                  voltageMagnitude:
                    resBus.voltage_magnitude_pu || resBus.voltage_magnitude || b.voltageMagnitude,
                  voltageAngle: resBus.voltage_angle || b.voltageAngle,
                };
              }
              return b;
            }),
          );
        }
      } else {
        notify("error", isRtl ? "سريان الحمل لم يتقارب!" : "Load flow failed to converge!");
      }
    } catch (err: any) {
      notify("error", `Error: ${err.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  // Get properties of currently selected item
  const selectedDetails = useMemo(() => {
    if (!selectedElement) return null;
    const { type, id } = selectedElement;

    if (type === "bus") return buses.find((b) => b.id === id);
    if (type === "line") return lines.find((l) => l.id === id);
    if (type === "generator") return generators.find((g) => g.id === id);
    if (type === "load") return loads.find((l) => l.id === id);
    return null;
  }, [selectedElement, buses, lines, generators, loads]);

  // Update properties of currently selected item
  const updateSelectedProperty = (key: string, value: any) => {
    if (!selectedElement) return;
    const { type, id } = selectedElement;

    if (type === "bus") {
      setBuses((prev) => prev.map((b) => (b.id === id ? { ...b, [key]: value } : b)));
    } else if (type === "line") {
      setLines((prev) => prev.map((l) => (l.id === id ? { ...l, [key]: value } : l)));
    } else if (type === "generator") {
      setGenerators((prev) => prev.map((g) => (g.id === id ? { ...g, [key]: value } : g)));
    } else if (type === "load") {
      setLoads((prev) => prev.map((l) => (l.id === id ? { ...l, [key]: value } : l)));
    }
  };

  // Helper to color code buses based on simulated voltage
  const getBusColor = (bus: Bus) => {
    if (simulationResults) {
      const v = bus.voltageMagnitude;
      if (v > 1.05) return "stroke-red-500 fill-red-950/20";
      if (v < 0.95) return "stroke-amber-500 fill-amber-950/20";
      return "stroke-green-500 fill-green-950/20";
    }
    if (selectedElement?.type === "bus" && selectedElement.id === bus.id) {
      return "stroke-[var(--accent-primary)] fill-blue-950/10";
    }
    return "stroke-[var(--text-secondary)] fill-[var(--bg-elevated)]";
  };

  return (
    <div className="space-y-6">
      {/* Header Title */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-[var(--text-primary)] flex items-center gap-2">
            <Sliders className="w-6 h-6 text-brand-500" />
            {isRtl ? "محرر الشبكة الكهربائية التفاعلي" : "Interactive Power Grid Editor"}
          </h2>
          <p className="text-sm text-[var(--text-tertiary)] mt-1">
            {isRtl
              ? "ارسم شبكتك الهندسية، تحقق من اتصالاتها، وشغل حسابات سريان الأحمال حياً."
              : "Design topological grids, validate structural links, and run live calculations."}
          </p>
        </div>
        <div className="flex items-center gap-2.5">
          <Button variant="secondary" size="sm" icon={Download} onClick={loadCairoTemplate}>
            {isRtl ? "شبكة القاهرة (13.8kV)" : "Cairo Template"}
          </Button>
          <Button variant="danger" size="sm" icon={Trash2} onClick={clearGrid}>
            {isRtl ? "تفريغ" : "Clear Canvas"}
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Toolbar & Canvas Panel */}
        <div className="lg:col-span-3 space-y-4">
          <Card padding="sm">
            {/* Design Controls */}
            <div className="flex flex-wrap items-center gap-2 border-b border-[var(--border-primary)] pb-3 mb-3">
              <Button
                variant={activeMode === "select" ? "primary" : "secondary"}
                size="sm"
                icon={MousePointer}
                onClick={() => {
                  setActiveMode("select");
                  setConnectingBusId(null);
                }}
              >
                {isRtl ? "تحديد" : "Select"}
              </Button>
              <Button
                variant={activeMode === "bus" ? "primary" : "secondary"}
                size="sm"
                icon={Plus}
                onClick={() => {
                  setActiveMode("bus");
                  setConnectingBusId(null);
                }}
              >
                {isRtl ? "إضافة ناقل (Bus)" : "Add Bus"}
              </Button>
              <Button
                variant={activeMode === "line" ? "primary" : "secondary"}
                size="sm"
                icon={Link2}
                onClick={() => {
                  setActiveMode("line");
                  setConnectingBusId(null);
                }}
              >
                {isRtl ? "خط نقل (Line)" : "Draw Line"}
              </Button>
              <Button
                variant={activeMode === "generator" ? "primary" : "secondary"}
                size="sm"
                icon={Sparkles}
                onClick={() => {
                  setActiveMode("generator");
                  setConnectingBusId(null);
                }}
              >
                {isRtl ? "مولد (Generator)" : "Attach Generator"}
              </Button>
              <Button
                variant={activeMode === "load" ? "primary" : "secondary"}
                size="sm"
                icon={Zap}
                onClick={() => {
                  setActiveMode("load");
                  setConnectingBusId(null);
                }}
              >
                {isRtl ? "حمل (Load)" : "Attach Load"}
              </Button>

              <div className="h-6 w-px bg-[var(--border-primary)] mx-2 hidden sm:block" />

              <div className="flex items-center gap-2 ml-auto">
                <Button
                  variant="secondary"
                  size="sm"
                  icon={CheckCircle}
                  loading={isLoading}
                  onClick={handleValidateGrid}
                >
                  {isRtl ? "تحقق من الشبكة" : "Validate"}
                </Button>
                <Button
                  variant="success"
                  size="sm"
                  icon={Play}
                  loading={isLoading}
                  onClick={handleRunLoadFlow}
                >
                  {isRtl ? "تشغيل الحسابات" : "Run Flow"}
                </Button>
              </div>
            </div>

            {/* SVG Interactive Canvas */}
            <div className="relative border border-[var(--border-primary)] rounded-lg bg-[var(--bg-primary)] overflow-hidden">
              <svg
                ref={svgRef}
                className="w-full h-[550px] cursor-crosshair select-none"
                onMouseMove={handleSvgMouseMove}
                onMouseUp={handleSvgMouseUp}
                onMouseDown={handleSvgMouseDown}
              >
                {/* SVG Grid pattern background */}
                <defs>
                  <pattern id="gridPattern" width="20" height="20" patternUnits="userSpaceOnUse">
                    <path
                      d="M 20 0 L 0 0 0 20"
                      fill="none"
                      stroke="var(--border-primary)"
                      strokeWidth="0.5"
                      opacity="0.3"
                    />
                  </pattern>
                </defs>
                <rect width="100%" height="100%" fill="url(#gridPattern)" />

                {/* Draw connecting temporary line */}
                {activeMode === "line" &&
                  connectingBusId !== null &&
                  (() => {
                    const startBus = buses.find((b) => b.id === connectingBusId);
                    if (!startBus) return null;
                    return (
                      <line
                        x1={startBus.x}
                        y1={startBus.y}
                        x2={startBus.x} // Will snap, dummy representation
                        y2={startBus.y}
                        stroke="var(--accent-primary)"
                        strokeWidth="2"
                        strokeDasharray="5,5"
                      />
                    );
                  })()}

                {/* Draw permanent transmission lines */}
                {lines.map((line) => {
                  const fromBus = buses.find((b) => b.id === line.fromBusId);
                  const toBus = buses.find((b) => b.id === line.toBusId);
                  if (!fromBus || !toBus) return null;
                  const isSelected =
                    selectedElement?.type === "line" && selectedElement.id === line.id;

                  return (
                    <g
                      key={`line-${line.id}`}
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedElement({ type: "line", id: line.id });
                      }}
                    >
                      <line
                        x1={fromBus.x}
                        y1={fromBus.y}
                        x2={toBus.x}
                        y2={toBus.y}
                        className={cn(
                          "cursor-pointer stroke-[3] transition-all hover:stroke-[5]",
                          isSelected
                            ? "stroke-[var(--accent-primary)]"
                            : "stroke-[var(--text-tertiary)]",
                        )}
                      />
                      {/* Midpoint line labels for simulation flow */}
                      {simulationResults && (
                        <circle
                          cx={(fromBus.x + toBus.x) / 2}
                          cy={(fromBus.y + toBus.y) / 2}
                          r="6"
                          fill="var(--accent-primary)"
                          className="animate-pulse"
                        />
                      )}
                    </g>
                  );
                })}

                {/* Draw buses */}
                {buses.map((bus) => {
                  return (
                    <g
                      key={`bus-${bus.id}`}
                      transform={`translate(${bus.x}, ${bus.y})`}
                      onMouseDown={(e) => handleBusMouseDown(e, bus)}
                      onClick={(e) => handleBusClick(e, bus)}
                      className="cursor-grab active:cursor-grabbing"
                    >
                      {/* Horizontal bar symbol representing Bus bar */}
                      <rect
                        x="-40"
                        y="-4"
                        width="80"
                        height="8"
                        rx="4"
                        className={cn("stroke-[2] transition-colors", getBusColor(bus))}
                      />
                      {/* Text Label */}
                      <text
                        y="-16"
                        textAnchor="middle"
                        className="text-xs font-semibold fill-[var(--text-primary)] pointer-events-none"
                      >
                        {bus.name} ({bus.baseKv} kV)
                      </text>
                      {/* Render Simulated Voltage on buses */}
                      {simulationResults && (
                        <text
                          y="24"
                          textAnchor="middle"
                          className="text-[10px] font-bold fill-green-400 pointer-events-none"
                        >
                          {bus.voltageMagnitude.toFixed(4)} pu / {bus.voltageAngle.toFixed(1)}°
                        </text>
                      )}
                      {/* Connection highlight */}
                      {connectingBusId === bus.id && (
                        <circle
                          r="12"
                          fill="none"
                          stroke="var(--accent-primary)"
                          strokeWidth="2"
                          className="animate-ping"
                        />
                      )}
                    </g>
                  );
                })}

                {/* Draw attached generators */}
                {generators.map((gen) => {
                  const bus = buses.find((b) => b.id === gen.busId);
                  if (!bus) return null;
                  const isSelected =
                    selectedElement?.type === "generator" && selectedElement.id === gen.id;
                  return (
                    <g
                      key={`gen-${gen.id}`}
                      transform={`translate(${bus.x}, ${bus.y - 45})`}
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedElement({ type: "generator", id: gen.id });
                      }}
                      className="cursor-pointer"
                    >
                      {/* Generator standard symbol: circle with AC wave */}
                      <circle
                        r="14"
                        className={cn(
                          "stroke-2 fill-[var(--bg-elevated)]",
                          isSelected ? "stroke-[var(--accent-primary)]" : "stroke-green-400",
                        )}
                      />
                      <path
                        d="M-8,0 Q-4,-6 0,0 T8,0"
                        fill="none"
                        className="stroke-2 stroke-green-400"
                      />
                      <line
                        x1="0"
                        y1="14"
                        x2="0"
                        y2="41"
                        stroke="var(--text-secondary)"
                        strokeWidth="2"
                      />
                      <text
                        x="20"
                        y="4"
                        className="text-[10px] fill-[var(--text-secondary)] font-medium"
                      >
                        {gen.name}
                      </text>
                    </g>
                  );
                })}

                {/* Draw attached loads */}
                {loads.map((ld) => {
                  const bus = buses.find((b) => b.id === ld.busId);
                  if (!bus) return null;
                  const isSelected =
                    selectedElement?.type === "load" && selectedElement.id === ld.id;
                  return (
                    <g
                      key={`load-${ld.id}`}
                      transform={`translate(${bus.x}, ${bus.y + 15})`}
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedElement({ type: "load", id: ld.id });
                      }}
                      className="cursor-pointer"
                    >
                      {/* Load symbol: Arrow pointing down */}
                      <line
                        x1="0"
                        y1="0"
                        x2="0"
                        y2="25"
                        stroke="var(--text-secondary)"
                        strokeWidth="2"
                      />
                      <polygon
                        points="0,25 -6,17 6,17"
                        className={cn(
                          "stroke-1",
                          isSelected
                            ? "fill-[var(--accent-primary)] stroke-[var(--accent-primary)]"
                            : "fill-amber-400 stroke-amber-400",
                        )}
                      />
                      <text
                        x="12"
                        y="16"
                        className="text-[10px] fill-[var(--text-secondary)] font-medium"
                      >
                        {ld.name}
                      </text>
                    </g>
                  );
                })}
              </svg>

              {/* Status overlay */}
              {activeMode !== "select" && (
                <div className="absolute bottom-4 left-4 bg-black/85 border border-[var(--border-primary)] px-3 py-1.5 rounded-md text-xs text-brand-400 font-medium">
                  {isRtl
                    ? `وضع الرسم النشط: ${activeMode.toUpperCase()}`
                    : `Active Tool: ${activeMode.toUpperCase()}`}
                </div>
              )}
            </div>
          </Card>
        </div>

        {/* Configuration Panel Sidebar */}
        <div className="space-y-4">
          {/* Element Properties Panel */}
          <Card padding="md">
            <h3 className="text-sm font-bold text-[var(--text-primary)] border-b border-[var(--border-primary)] pb-2 mb-3 flex items-center justify-between">
              <span>{isRtl ? "خصائص العنصر المحدد" : "Selected Component"}</span>
              {selectedElement && (
                <Button variant="danger" size="sm" icon={Trash2} onClick={deleteSelected}>
                  {isRtl ? "حذف" : "Delete"}
                </Button>
              )}
            </h3>

            {selectedDetails ? (
              <div className="space-y-4 text-xs">
                <div>
                  <label className="block text-[var(--text-tertiary)] mb-1">
                    {isRtl ? "الاسم" : "Name"}
                  </label>
                  <input
                    type="text"
                    value={(selectedDetails as any).name || `Line ${selectedDetails.id}`}
                    onChange={(e) => updateSelectedProperty("name", e.target.value)}
                    className="w-full bg-[var(--bg-primary)] border border-[var(--border-primary)] rounded px-2.5 py-1.5 text-[var(--text-primary)] focus:outline-none"
                  />
                </div>

                {/* Bus properties */}
                {selectedElement?.type === "bus" &&
                  (() => {
                    const b = selectedDetails as Bus;
                    return (
                      <>
                        <div>
                          <label className="block text-[var(--text-tertiary)] mb-1">
                            {isRtl ? "نوع الناقل" : "Bus Type"}
                          </label>
                          <select
                            value={b.type}
                            onChange={(e) => updateSelectedProperty("type", e.target.value)}
                            className="w-full bg-[var(--bg-primary)] border border-[var(--border-primary)] rounded px-2 py-1.5 text-[var(--text-primary)] focus:outline-none"
                          >
                            <option value="pq">PQ Bus (Load)</option>
                            <option value="pv">PV Bus (Generator)</option>
                            <option value="slack">Slack Bus (Swing)</option>
                          </select>
                        </div>
                        <div>
                          <label className="block text-[var(--text-tertiary)] mb-1">
                            {isRtl ? "الجهد الاسمي (kV)" : "Nominal KV"}
                          </label>
                          <input
                            type="number"
                            value={b.baseKv}
                            onChange={(e) =>
                              updateSelectedProperty("baseKv", Number.parseFloat(e.target.value))
                            }
                            className="w-full bg-[var(--bg-primary)] border border-[var(--border-primary)] rounded px-2.5 py-1.5 text-[var(--text-primary)] focus:outline-none"
                          />
                        </div>
                      </>
                    );
                  })()}

                {/* Line properties */}
                {selectedElement?.type === "line" &&
                  (() => {
                    const l = selectedDetails as Line;
                    return (
                      <>
                        <div>
                          <label className="block text-[var(--text-tertiary)] mb-1">
                            {isRtl ? "المقاومة R1 (pu)" : "Resistance R1 (pu)"}
                          </label>
                          <input
                            type="number"
                            step="0.001"
                            value={l.r1}
                            onChange={(e) =>
                              updateSelectedProperty("r1", Number.parseFloat(e.target.value))
                            }
                            className="w-full bg-[var(--bg-primary)] border border-[var(--border-primary)] rounded px-2.5 py-1.5 text-[var(--text-primary)] focus:outline-none"
                          />
                        </div>
                        <div>
                          <label className="block text-[var(--text-tertiary)] mb-1">
                            {isRtl ? "المفاعلة X1 (pu)" : "Reactance X1 (pu)"}
                          </label>
                          <input
                            type="number"
                            step="0.001"
                            value={l.x1}
                            onChange={(e) =>
                              updateSelectedProperty("x1", Number.parseFloat(e.target.value))
                            }
                            className="w-full bg-[var(--bg-primary)] border border-[var(--border-primary)] rounded px-2.5 py-1.5 text-[var(--text-primary)] focus:outline-none"
                          />
                        </div>
                      </>
                    );
                  })()}

                {/* Generator properties */}
                {selectedElement?.type === "generator" &&
                  (() => {
                    const g = selectedDetails as Generator;
                    return (
                      <>
                        <div>
                          <label className="block text-[var(--text-tertiary)] mb-1">
                            {isRtl ? "القدرة الحقيقية pg (MW)" : "Real Power pg (MW)"}
                          </label>
                          <input
                            type="number"
                            value={g.pg}
                            onChange={(e) =>
                              updateSelectedProperty("pg", Number.parseFloat(e.target.value))
                            }
                            className="w-full bg-[var(--bg-primary)] border border-[var(--border-primary)] rounded px-2.5 py-1.5 text-[var(--text-primary)] focus:outline-none"
                          />
                        </div>
                        <div>
                          <label className="block text-[var(--text-tertiary)] mb-1">
                            {isRtl ? "قيمة تنظيم الجهد" : "Voltage Setpoint (pu)"}
                          </label>
                          <input
                            type="number"
                            step="0.01"
                            value={g.vSetpoint}
                            onChange={(e) =>
                              updateSelectedProperty("vSetpoint", Number.parseFloat(e.target.value))
                            }
                            className="w-full bg-[var(--bg-primary)] border border-[var(--border-primary)] rounded px-2.5 py-1.5 text-[var(--text-primary)] focus:outline-none"
                          />
                        </div>
                      </>
                    );
                  })()}

                {/* Load properties */}
                {selectedElement?.type === "load" &&
                  (() => {
                    const ld = selectedDetails as Load;
                    return (
                      <>
                        <div>
                          <label className="block text-[var(--text-tertiary)] mb-1">
                            {isRtl ? "القدرة الفعالة P (MW)" : "Real Load P (MW)"}
                          </label>
                          <input
                            type="number"
                            value={ld.pMw}
                            onChange={(e) =>
                              updateSelectedProperty("pMw", Number.parseFloat(e.target.value))
                            }
                            className="w-full bg-[var(--bg-primary)] border border-[var(--border-primary)] rounded px-2.5 py-1.5 text-[var(--text-primary)] focus:outline-none"
                          />
                        </div>
                        <div>
                          <label className="block text-[var(--text-tertiary)] mb-1">
                            {isRtl ? "القدرة غير الفعالة Q (MVAR)" : "Reactive Load Q (MVAR)"}
                          </label>
                          <input
                            type="number"
                            value={ld.qMvar}
                            onChange={(e) =>
                              updateSelectedProperty("qMvar", Number.parseFloat(e.target.value))
                            }
                            className="w-full bg-[var(--bg-primary)] border border-[var(--border-primary)] rounded px-2.5 py-1.5 text-[var(--text-primary)] focus:outline-none"
                          />
                        </div>
                      </>
                    );
                  })()}
              </div>
            ) : (
              <p className="text-xs text-[var(--text-muted)] text-center py-4">
                {isRtl
                  ? "اضغط على أي عنصر في اللوحة لعرض وتعديل خصائصه الهندسية."
                  : "Select an element on the canvas to edit its properties."}
              </p>
            )}
          </Card>

          {/* Validation & Run Status */}
          <Card padding="md">
            <h3 className="text-sm font-bold text-[var(--text-primary)] border-b border-[var(--border-primary)] pb-2 mb-3">
              {isRtl ? "نتائج التحليل الهندسي" : "Engineering Validation"}
            </h3>

            {validationResults ? (
              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <Badge
                    variant={validationResults.valid ? "success" : "danger"}
                    size="sm"
                    className="w-full text-center"
                  >
                    {(() => {
                      if (validationResults.valid) {
                        return isRtl ? "بنية شبكة سليمة" : "Structure Valid";
                      }
                      return isRtl ? "خطأ في الربط" : "Invalid Connection";
                    })()}
                  </Badge>
                </div>

                {validationResults.errors && validationResults.errors.length > 0 && (
                  <div className="bg-red-500/10 border border-red-500/20 p-2.5 rounded text-xs space-y-1 text-red-400">
                    <p className="font-bold flex items-center gap-1">
                      <AlertTriangle className="w-3.5 h-3.5" />
                      {isRtl ? "الأخطاء الهندسية:" : "Errors Found:"}
                    </p>
                    <ul className="list-disc pl-4 space-y-0.5">
                      {validationResults.errors.map((err) => (
                        <li key={err}>{err}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {validationResults.warnings && validationResults.warnings.length > 0 && (
                  <div className="bg-amber-500/10 border border-amber-500/20 p-2.5 rounded text-xs space-y-1 text-amber-400">
                    <p className="font-bold flex items-center gap-1">
                      <AlertTriangle className="w-3.5 h-3.5" />
                      {isRtl ? "تحذيرات مهمة:" : "Warnings:"}
                    </p>
                    <ul className="list-disc pl-4 space-y-0.5">
                      {validationResults.warnings.map((warn) => (
                        <li key={warn}>{warn}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ) : (
              <p className="text-xs text-[var(--text-muted)] text-center py-2">
                {isRtl ? "لم يتم إجراء التحقق الهيكلي بعد." : "No validation performed yet."}
              </p>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
