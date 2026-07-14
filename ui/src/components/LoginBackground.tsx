import { AnimatePresence, motion } from "framer-motion";
import { Globe, Shield } from "lucide-react";
import { useCallback, useRef, useState } from "react";

interface LoginBackgroundProps {
  isRtl: boolean;
  onLanguageToggle: () => void;
  isBreakerOpen: boolean;
  setIsBreakerOpen: (val: boolean) => void;
  onTerminalLog: (msg: string) => void;
}

interface Coords {
  x: number;
  y: number;
}

export function LoginBackground({
  isRtl,
  onLanguageToggle,
  isBreakerOpen,
  setIsBreakerOpen,
  onTerminalLog,
}: LoginBackgroundProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [coords, setCoords] = useState<Coords>({ x: 0, y: 0 });
  const [hoveredComponent, setHoveredComponent] = useState<string | null>(null);
  const [tooltipPos, setTooltipPos] = useState<Coords>({ x: 0, y: 0 });

  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const x = Math.round(e.clientX - rect.left);
    const y = Math.round(e.clientY - rect.top);
    setCoords({ x, y });
  }, []);

  const handleComponentHover = useCallback((component: string | null, e?: React.MouseEvent) => {
    setHoveredComponent(component);
    if (component && e && containerRef.current) {
      const rect = containerRef.current.getBoundingClientRect();
      // Place tooltip slightly offset from mouse cursor
      setTooltipPos({
        x: e.clientX - rect.left + 15,
        y: e.clientY - rect.top + 15,
      });
    }
  }, []);

  const handleBreakerToggle = useCallback(() => {
    const nextState = !isBreakerOpen;
    setIsBreakerOpen(nextState);
    if (nextState) {
      onTerminalLog("CB-101 (TR-SEC) TRIP COMMAND RECEIVED — BUS-13.8KV DE-ENERGIZED");
      onTerminalLog("WARNING: Load flow solver reports islanded bus: BUS-13.8KV (0.00 kV, 0.0 Hz)");
    } else {
      onTerminalLog("CB-101 (TR-SEC) CLOSE COMMAND RECEIVED — BUS-13.8KV ENERGIZED");
      onTerminalLog(
        "SUCCESS: Newton-Raphson Load Flow converged in 3 iterations (13.82 kV, 50.0 Hz)",
      );
    }
  }, [isBreakerOpen, setIsBreakerOpen, onTerminalLog]);

  // Get active status telemetry details
  const getTooltipContent = () => {
    if (!hoveredComponent) return null;

    switch (hoveredComponent) {
      case "bus-a":
        return isRtl
          ? {
              title: "قضيب التوزيع الرئيسي (BUS-115KV)",
              details: [
                "الجهد الاسمي: 115.0 ك.ف (1.002 pu)",
                "التردد: 50.01 هرتز",
                "زاوية الطور: 0.0°",
                "الحالة: نشط ومستقر",
              ],
            }
          : {
              title: "Main Grid Bus (BUS-115KV)",
              details: [
                "Nominal Voltage: 115.0 kV (1.002 pu)",
                "Frequency: 50.01 Hz",
                "Phase Angle: 0.0°",
                "Status: ACTIVE & STABLE",
              ],
            };
      case "transformer":
        return isRtl
          ? {
              title: "محول خفض الجهد الرئيسي (TR-101)",
              details: [
                "القدرة الاسمية: 45 م.ف.أ",
                "نسبة الجهد: 115 / 13.8 ك.ف",
                "مجموعة التوصيل: Dyn11",
                `الحالة: ${isBreakerOpen ? "دون حمل (مفتوح)" : "نشط تحت الحمل"}`,
              ],
            }
          : {
              title: "Main Step-down XFRMR (TR-101)",
              details: [
                "Nominal Rating: 45 MVA",
                "Voltage Ratio: 115 / 13.8 kV",
                "Vector Group: Dyn11",
                `Status: ${isBreakerOpen ? "NO-LOAD (Open Circuit)" : "ON-LOAD (Active)"}`,
              ],
            };
      case "bus-b":
        return isRtl
          ? {
              title: "قضيب التوزيع الفرعي (BUS-13.8KV)",
              details: [
                `الجهد الحالي: ${isBreakerOpen ? "0.00" : "13.82"} ك.ف (${isBreakerOpen ? "0.000" : "1.001"} pu)`,
                `التردد: ${isBreakerOpen ? "0.0" : "50.0"} هرتز`,
                `الحمل الكلي: ${isBreakerOpen ? "0.0" : "12.5"} م.و`,
                `الحالة: ${isBreakerOpen ? "خارج الخدمة (غير مغذى)" : "نشط ومغذي للمصنع"}`,
              ],
            }
          : {
              title: "Distribution Bus (BUS-13.8KV)",
              details: [
                `Voltage: ${isBreakerOpen ? "0.00" : "13.82"} kV (${isBreakerOpen ? "0.000" : "1.001"} pu)`,
                `Frequency: ${isBreakerOpen ? "0.0" : "50.0"} Hz`,
                `Total Load: ${isBreakerOpen ? "0.0" : "12.5"} MW`,
                `Status: ${isBreakerOpen ? "DE-ENERGIZED (Isolated)" : "ENERGIZED (On Line)"}`,
              ],
            };
      case "generator":
        return isRtl
          ? {
              title: "مولد الطوارئ والشبكة (GEN-A)",
              details: [
                "القدرة الاسمية: 50 م.و",
                "الحمل الحالي: 32.4 م.و",
                "معامل القدرة: 0.85",
                "الحالة: جاري العمل (Swing Mode)",
              ],
            }
          : {
              title: "Swing Generator (GEN-A)",
              details: [
                "Nominal Rating: 50 MW",
                "Active Output: 32.4 MW",
                "Power Factor: 0.85 Lagging",
                "Status: RUNNING (Swing Mode)",
              ],
            };
      case "breaker":
        return isRtl
          ? {
              title: "قاطع الحماية الرئيسي (CB-101)",
              details: [
                "النوع: قاطع مفرغ من الهواء (Vacuum CB)",
                `الحالة الحالية: ${isBreakerOpen ? "مفتوح (TRIP)" : "مغلق (CLOSED)"}`,
                "الإجراء: اضغط على القاطع لتغيير الحالة للنمذجة",
              ],
            }
          : {
              title: "Main Circuit Breaker (CB-101)",
              details: [
                "Type: Vacuum Circuit Breaker",
                `Current State: ${isBreakerOpen ? "OPEN (Tripped)" : "CLOSED (Normal)"}`,
                "Action: CLICK to toggle simulation state",
              ],
            };
      case "feeder":
        return isRtl
          ? {
              title: "مغذي المصنع الرئيسي (LOAD-F1)",
              details: [
                `حمل الطلب: ${isBreakerOpen ? "0.0" : "12.5"} م.و`,
                `التيار الفعلي: ${isBreakerOpen ? "0" : "522"} أمبير`,
                `الحالة: ${isBreakerOpen ? "مقطوع" : "متصل"}`,
              ],
            }
          : {
              title: "Industrial Feeder (LOAD-F1)",
              details: [
                `Active Demand: ${isBreakerOpen ? "0.0" : "12.5"} MW`,
                `Current: ${isBreakerOpen ? "0" : "522"} A`,
                `Status: ${isBreakerOpen ? "DISCONNECTED" : "CONNECTED"}`,
              ],
            };
      default:
        return null;
    }
  };

  const tooltipData = getTooltipContent();

  return (
    <div
      ref={containerRef}
      onMouseMove={handleMouseMove}
      className="absolute inset-0 z-0 bg-[#070b14] overflow-hidden select-none"
    >
      {/* Top Controls Overlay */}
      <div
        className={`absolute top-6 ${isRtl ? "left-6" : "right-6"} z-50 flex items-center gap-3`}
      >
        <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-slate-800/80 bg-slate-900/60 text-slate-400 text-[10px] font-mono">
          <Shield className="w-3.5 h-3.5 text-blue-500" />
          <span>CAD SIM V2.1</span>
        </div>
        <button
          type="button"
          onClick={onLanguageToggle}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-slate-800 bg-slate-900/80 hover:bg-slate-800 text-slate-300 hover:text-white transition-all text-xs font-semibold"
        >
          <Globe className="w-3.5 h-3.5" />
          <span>{isRtl ? "English" : "العربية"}</span>
        </button>
      </div>

      {/* CAD Workbench Grid */}
      <div
        className="absolute inset-0 opacity-[0.035]"
        style={{
          backgroundImage:
            "linear-gradient(#3b82f6 1px, transparent 1px), linear-gradient(90deg, #3b82f6 1px, transparent 1px)",
          backgroundSize: "40px 40px",
        }}
      />
      <div
        className="absolute inset-0 opacity-[0.015]"
        style={{
          backgroundImage:
            "linear-gradient(#3b82f6 1px, transparent 1px), linear-gradient(90deg, #3b82f6 1px, transparent 1px)",
          backgroundSize: "8px 8px",
        }}
      />

      {/* Interactive Single-Line Diagram SVG */}
      <svg
        className="absolute inset-0 w-full h-full"
        viewBox="0 0 1440 900"
        preserveAspectRatio="xMidYMid slice"
        aria-hidden="true"
      >
        <defs>
          <linearGradient id="bus-grad-hv" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#1e293b" stopOpacity="0.2" />
            <stop offset="50%" stopColor="#3b82f6" stopOpacity="0.75" />
            <stop offset="100%" stopColor="#1e293b" stopOpacity="0.2" />
          </linearGradient>
          <linearGradient id="bus-grad-lv" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#1e293b" stopOpacity="0.2" />
            <stop
              offset="50%"
              stopColor={isBreakerOpen ? "#334155" : "#00d4ff"}
              stopOpacity={isBreakerOpen ? "0.3" : "0.75"}
            />
            <stop offset="100%" stopColor="#1e293b" stopOpacity="0.2" />
          </linearGradient>
        </defs>

        {/* --- HIGH VOLTAGE LEVEL (115 kV) --- */}
        {/* HV Bus Line */}
        <path
          d="M100,180 L1340,180"
          stroke="url(#bus-grad-hv)"
          strokeWidth="4"
          strokeLinecap="round"
          className="transition-colors duration-500"
        />
        <path
          d="M100,180 L1340,180"
          stroke="#3b82f6"
          strokeWidth="1.5"
          strokeLinecap="round"
          className="animate-pulse"
          opacity="0.8"
        />
        {/* Hover zone for Bus A */}
        <line
          x1="100"
          y1="180"
          x2="1340"
          y2="180"
          stroke="transparent"
          strokeWidth="15"
          className="cursor-pointer"
          onMouseEnter={(e) => handleComponentHover("bus-a", e)}
          onMouseLeave={() => handleComponentHover(null)}
        />

        {/* --- SWING GENERATOR SUB-CIRCUIT --- */}
        {/* Generator Branch Line */}
        <path d="M800,180 L800,90" stroke="#3b82f6" strokeWidth="2.5" />
        <path
          d="M800,180 L800,90"
          stroke="#22c55e"
          strokeWidth="1.5"
          strokeDasharray="10 10"
          strokeDashoffset="0"
          style={{ animation: "gridFlowRev 12s linear infinite" }}
        />
        {/* Generator Shell */}
        <g
          className="cursor-pointer group/gen"
          onMouseEnter={(e) => handleComponentHover("generator", e)}
          onMouseLeave={() => handleComponentHover(null)}
        >
          <circle
            cx="800"
            cy="70"
            r="20"
            fill="#070b14"
            stroke="#22c55e"
            strokeWidth="2.5"
            className="transition-all duration-300 group-hover/gen:shadow-[0_0_15px_rgba(34,197,94,0.5)]"
          />
          <circle
            cx="800"
            cy="70"
            r="16"
            fill="none"
            stroke="#22c55e"
            strokeWidth="1"
            strokeDasharray="4 4"
            className="animate-spin"
            style={{ animationDuration: "8s" }}
          />
          <text
            x="800"
            y="75"
            textAnchor="middle"
            fill="#22c55e"
            fontSize="14"
            fontWeight="bold"
            fontFamily="monospace"
          >
            G
          </text>
        </g>

        {/* --- MAIN TRANSFORMER BRANCH (TR-101) --- */}
        {/* Primary line to Transformer */}
        <path d="M400,180 L400,260" stroke="#3b82f6" strokeWidth="2.5" />
        <path
          d="M400,180 L400,260"
          stroke="#00d4ff"
          strokeWidth="1.5"
          strokeDasharray="8 12"
          strokeDashoffset="0"
          style={{ animation: "gridFlow 10s linear infinite" }}
        />

        {/* Transformer Windings */}
        <g
          className="cursor-pointer group/trans"
          onMouseEnter={(e) => handleComponentHover("transformer", e)}
          onMouseLeave={() => handleComponentHover(null)}
        >
          <circle
            cx="400"
            cy="276"
            r="16"
            fill="none"
            stroke="#00d4ff"
            strokeWidth="2.5"
            className="transition-all duration-300 group-hover/trans:stroke-[#60a5fa]"
          />
          <circle
            cx="400"
            cy="300"
            r="16"
            fill="none"
            stroke={isBreakerOpen ? "#334155" : "#3b82f6"}
            strokeWidth="2.5"
            className="transition-colors duration-500"
          />
        </g>

        {/* Transformer secondary line to Breaker */}
        <path
          d="M400,316 L400,355"
          stroke={isBreakerOpen ? "#1e293b" : "#3b82f6"}
          strokeWidth="2.5"
          className="transition-colors duration-500"
        />
        {!isBreakerOpen && (
          <path
            d="M400,316 L400,355"
            stroke="#00d4ff"
            strokeWidth="1.5"
            strokeDasharray="8 12"
            strokeDashoffset="0"
            style={{ animation: "gridFlow 10s linear infinite" }}
          />
        )}

        {/* --- INTERACTIVE CIRCUIT BREAKER (CB-101) --- */}
        <g
          className="cursor-pointer group/cb"
          onClick={handleBreakerToggle}
          onMouseEnter={(e) => handleComponentHover("breaker", e)}
          onMouseLeave={() => handleComponentHover(null)}
        >
          {/* Transparent hit target */}
          <rect x="375" y="350" width="50" height="40" fill="transparent" />
          {/* Outer box */}
          <rect
            x="390"
            y="355"
            width="20"
            height="30"
            rx="4"
            fill="#070b14"
            stroke={isBreakerOpen ? "#ef4444" : "#22c55e"}
            strokeWidth="2"
            className="transition-colors duration-300 group-hover/cb:shadow-[0_0_10px_rgba(34,197,94,0.4)]"
          />
          {/* CB Line Symbol */}
          {isBreakerOpen ? (
            // Open state: diagonal open contact
            <line
              x1="400"
              y1="362"
              x2="412"
              y2="378"
              stroke="#ef4444"
              strokeWidth="2.5"
              strokeLinecap="round"
              className="transition-all duration-300"
            />
          ) : (
            // Closed state: straight solid line
            <line
              x1="400"
              y1="360"
              x2="400"
              y2="380"
              stroke="#22c55e"
              strokeWidth="2.5"
              strokeLinecap="round"
              className="transition-all duration-300"
            />
          )}
          {/* Tripped Red Indicator LED */}
          <circle
            cx="400"
            cy="348"
            r="3.5"
            fill={isBreakerOpen ? "#ef4444" : "#1e293b"}
            className={isBreakerOpen ? "animate-ping" : ""}
            style={{ transformOrigin: "400px 348px" }}
          />
          <circle
            cx="400"
            cy="348"
            r="3"
            fill={isBreakerOpen ? "#ef4444" : "#22c55e"}
            stroke="#070b14"
            strokeWidth="0.5"
          />
        </g>

        {/* Line from Breaker to LV Bus */}
        <path
          d="M400,385 L400,450"
          stroke={isBreakerOpen ? "#1e293b" : "#3b82f6"}
          strokeWidth="2.5"
          className="transition-colors duration-500"
        />
        {!isBreakerOpen && (
          <path
            d="M400,385 L400,450"
            stroke="#00d4ff"
            strokeWidth="1.5"
            strokeDasharray="8 12"
            strokeDashoffset="0"
            style={{ animation: "gridFlow 10s linear infinite" }}
          />
        )}

        {/* --- LOW VOLTAGE DISTRIBUTION LEVEL (13.8 kV) --- */}
        {/* LV Bus Bar */}
        <path
          d="M250,450 L1190,450"
          stroke="url(#bus-grad-lv)"
          strokeWidth="3.5"
          strokeLinecap="round"
          className="transition-colors duration-500"
        />
        {!isBreakerOpen && (
          <path
            d="M250,450 L1190,450"
            stroke="#00d4ff"
            strokeWidth="1"
            strokeLinecap="round"
            className="animate-pulse"
            opacity="0.7"
          />
        )}
        {/* Hover zone for Bus B */}
        <line
          x1="250"
          y1="450"
          x2="1190"
          y2="450"
          stroke="transparent"
          strokeWidth="15"
          className="cursor-pointer"
          onMouseEnter={(e) => handleComponentHover("bus-b", e)}
          onMouseLeave={() => handleComponentHover(null)}
        />

        {/* --- FEEDER / LOAD BRANCH --- */}
        <path
          d="M600,450 L600,560"
          stroke={isBreakerOpen ? "#1e293b" : "#3b82f6"}
          strokeWidth="2.5"
          className="transition-colors duration-500"
        />
        {!isBreakerOpen && (
          <path
            d="M600,450 L600,560"
            stroke="#fbbf24"
            strokeWidth="1.5"
            strokeDasharray="8 10"
            strokeDashoffset="0"
            style={{ animation: "gridFlow 8s linear infinite" }}
          />
        )}
        {/* Load Arrow Symbol */}
        <g
          className="cursor-pointer group/feeder"
          onMouseEnter={(e) => handleComponentHover("feeder", e)}
          onMouseLeave={() => handleComponentHover(null)}
        >
          <polygon
            points="600,572 590,554 610,554"
            fill={isBreakerOpen ? "#1e293b" : "#fbbf24"}
            stroke={isBreakerOpen ? "#334155" : "#fbbf24"}
            strokeWidth="1.5"
            className="transition-colors duration-500"
          />
          <line x1="600" y1="450" x2="600" y2="550" stroke="transparent" strokeWidth="15" />
        </g>

        {/* Dynamic Electron Particles Motion */}
        {!isBreakerOpen && (
          <>
            <circle r="3.5" fill="#00d4ff" opacity="0.8">
              <animateMotion
                dur="7s"
                repeatCount="indefinite"
                path="M800,90 L800,180 L400,180 L400,450 L600,450 L600,554"
              />
            </circle>
            <circle r="2.5" fill="#22c55e" opacity="0.8">
              <animateMotion
                dur="7s"
                begin="2.3s"
                repeatCount="indefinite"
                path="M800,90 L800,180 L400,180 L400,450 L600,450 L600,554"
              />
            </circle>
            <circle r="2.5" fill="#fbbf24" opacity="0.8">
              <animateMotion
                dur="7s"
                begin="4.6s"
                repeatCount="indefinite"
                path="M800,90 L800,180 L400,180 L400,450 L600,450 L600,554"
              />
            </circle>
          </>
        )}

        {/* Styles for continuous flow */}
        <style>{`
          @keyframes gridFlow {
            to { stroke-dashoffset: -120; }
          }
          @keyframes gridFlowRev {
            to { stroke-dashoffset: 120; }
          }
        `}</style>
      </svg>

      {/* Dynamic Cursor Coordinates HUD (AutoCAD-style) */}
      <div className="absolute bottom-6 left-6 z-30 font-mono text-[9px] tracking-wider text-slate-500/80 bg-slate-950/40 px-3 py-1.5 rounded border border-slate-800/20 backdrop-blur-sm">
        CURSOR COORDINATES: X: {coords.x}px | Y: {coords.y}px
      </div>

      {/* Floating Interactive CAD Tooltip */}
      <AnimatePresence>
        {hoveredComponent && tooltipData && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            transition={{ duration: 0.15 }}
            style={{
              position: "absolute",
              left: tooltipPos.x,
              top: tooltipPos.y,
            }}
            className="z-50 min-w-[200px] pointer-events-none p-3.5 bg-slate-950/95 border border-slate-800 rounded-lg shadow-2xl font-mono text-[10px] text-white leading-relaxed backdrop-blur-md"
          >
            <div className="font-bold text-blue-400 border-b border-slate-800/80 pb-1.5 mb-1.5 flex items-center justify-between">
              <span>{tooltipData.title}</span>
              <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" />
            </div>
            <ul className="space-y-1 text-slate-300">
              {tooltipData.details.map((d, index) => (
                <li key={index} className="flex items-center gap-1.5">
                  <span className="text-blue-500">›</span>
                  <span>{d}</span>
                </li>
              ))}
            </ul>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Ambient background glows */}
      <div className="absolute top-10 right-20 w-[600px] h-[600px] rounded-full bg-blue-500/[0.015] blur-[140px]" />
      <div className="absolute bottom-10 left-20 w-[500px] h-[500px] rounded-full bg-blue-600/[0.01] blur-[120px]" />
    </div>
  );
}
