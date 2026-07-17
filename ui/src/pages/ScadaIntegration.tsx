import {
  Activity,
  Database,
  Pause,
  Play,
  Radio,
  RefreshCw,
  Save,
  Server,
  ShieldAlert,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Badge, Button, Card } from "../components/ui";
import { useNotify } from "../context/NotificationContext";
import { API_BASE_URL } from "../lib/api-config";

interface TelemetryPoint {
  tag: string;
  value: number;
  unit: string;
  quality: string;
}

interface SCADAAlarm {
  alarm_id: string;
  timestamp: string;
  severity: "WARNING" | "CRITICAL";
  description: string;
  location: string;
}

export default function ScadaIntegration() {
  const { i18n } = useTranslation();
  const { notify } = useNotify();
  const isRtl = i18n.language === "ar";

  // Settings state
  const [scadaUrl, setScadaUrl] = useState("http://localhost:8080/zenon");
  const [apiKey, setApiKey] = useState("");
  const [projectName, setProjectName] = useState("ETAP_Zenon_Sync");
  const [syncInterval, setSyncInterval] = useState(2);

  // Status & Telemetry state
  const [connectionStatus, setConnectionStatus] = useState<
    "disconnected" | "connecting" | "connected" | "simulated"
  >("disconnected");
  const [isLive, setIsLive] = useState(false);
  const [isSimulation, setIsSimulation] = useState(false);
  const [latency, setLatency] = useState<number | null>(null);

  const [telemetryPoints, setTelemetryPoints] = useState<TelemetryPoint[]>([
    { tag: "BUS1.V", value: 1.02, unit: "pu", quality: "GOOD" },
    { tag: "BUS1.F", value: 50.0, unit: "Hz", quality: "GOOD" },
    { tag: "FEEDER1.I", value: 412.5, unit: "A", quality: "GOOD" },
    { tag: "XF1.P", value: 2.8, unit: "MW", quality: "GOOD" },
    { tag: "XF1.Q", value: 0.9, unit: "MVAR", quality: "GOOD" },
  ]);

  const [alarms, setAlarms] = useState<SCADAAlarm[]>([]);
  const [logs, setLogs] = useState<string[]>([]);

  const socketRef = useRef<WebSocket | null>(null);
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Load configuration from local storage on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem("etap-settings");
      if (stored) {
        const parsed = JSON.parse(stored);
        if (parsed.SCADA_SERVER_URL) setScadaUrl(parsed.SCADA_SERVER_URL);
        if (parsed.SCADA_API_KEY) setApiKey(parsed.SCADA_API_KEY);
        if (parsed.SCADA_PROJECT_NAME) setProjectName(parsed.SCADA_PROJECT_NAME);
        if (parsed.SCADA_SYNC_INTERVAL_SEC)
          setSyncInterval(Number.parseInt(parsed.SCADA_SYNC_INTERVAL_SEC) || 2);
      }
      addLog(isRtl ? "تم تحميل إعدادات SCADA بنجاح." : "SCADA settings loaded successfully.");
    } catch (err: any) {
      console.error("Failed to load SCADA settings:", err);
    }
  }, []);

  // Add system logs helper
  const addLog = (msg: string) => {
    const timestamp = new Date().toLocaleTimeString();
    setLogs((prev) => [`[${timestamp}] ${msg}`, ...prev.slice(0, 49)]);
  };

  // Save Settings to Local Storage
  const handleSaveSettings = () => {
    try {
      const stored = localStorage.getItem("etap-settings");
      const currentSettings = stored ? JSON.parse(stored) : {};
      const updated = {
        ...currentSettings,
        SCADA_SERVER_URL: scadaUrl,
        SCADA_API_KEY: apiKey,
        SCADA_PROJECT_NAME: projectName,
        SCADA_SYNC_INTERVAL_SEC: String(syncInterval),
      };
      localStorage.setItem("etap-settings", JSON.stringify(updated));
      notify("success", isRtl ? "تم حفظ الإعدادات بنجاح!" : "SCADA Settings saved successfully!");
      addLog(
        isRtl
          ? "تم حفظ إعدادات خادم زينون في النظام."
          : "Zenon SCADA server configurations updated.",
      );
    } catch (err: any) {
      notify("error", `Error: ${err.message}`);
    }
  };

  // REST API connection probe
  const testConnection = async () => {
    setConnectionStatus("connecting");
    addLog(
      isRtl
        ? "جاري فحص الاتصال مع خادم Zenon SCADA..."
        : "Testing connection to Zenon SCADA server...",
    );
    const startTime = performance.now();

    try {
      const token = localStorage.getItem("authToken");
      const response = await fetch(`${API_BASE_URL}/api/v1/scada/live`, {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...(apiKey ? { "x-api-key": apiKey } : {}),
        },
      });

      const endTime = performance.now();
      setLatency(Math.round(endTime - startTime));

      if (response.ok) {
        const body = await response.json();
        if (body.success && body.data?.points) {
          setTelemetryPoints(body.data.points);
        }
        setConnectionStatus("connected");
        notify(
          "success",
          isRtl ? "تم الاتصال بنجاح مع نظام الإسكادا!" : "SCADA connection verified successfully!",
        );
        addLog(
          isRtl
            ? `تم الاتصال. زمن الاستجابة: ${Math.round(endTime - startTime)} ملي ثانية.`
            : `Connected. Latency: ${Math.round(endTime - startTime)} ms.`,
        );
      } else {
        throw new Error(`HTTP Error ${response.status}`);
      }
    } catch (err: any) {
      setConnectionStatus("disconnected");
      setLatency(null);
      notify(
        "error",
        isRtl
          ? "فشل الاتصال بنظام الإسكادا. تأكد من تشغيل خادم زينون."
          : "Connection failed. Ensure Zenon service is running.",
      );
      addLog(isRtl ? `خطأ في الاتصال: ${err.message}` : `Connection error: ${err.message}`);
    }
  };

  // Start / Stop Live Telemetry sync
  const toggleLiveSync = () => {
    if (isLive) {
      // Stop live
      stopSync();
      setIsLive(false);
    } else {
      // Start live
      setIsLive(true);
      if (isSimulation) {
        startSimulation();
      } else {
        startRealSync();
      }
    }
  };

  // Real API Sync (WebSocket & HTTP Fallback Polling)
  const startRealSync = () => {
    addLog(isRtl ? "بدء البث المباشر للبيانات..." : "Initializing real-time data sync...");

    // Connect WebSocket
    try {
      const wsProto = window.location.protocol === "https:" ? "wss:" : "ws:";
      const wsUrl = `${wsProto}//${API_BASE_URL.replace(/^https?:\/\//, "")}/ws/scada/live`;

      addLog(
        isRtl
          ? `جاري فتح اتصال WebSocket على: ${wsUrl}`
          : `Opening WebSocket connection to: ${wsUrl}`,
      );
      socketRef.current = new WebSocket(wsUrl);

      socketRef.current.onopen = () => {
        setConnectionStatus("connected");
        addLog(isRtl ? "اتصال WebSocket نشط الآن." : "WebSocket connection established.");
      };

      socketRef.current.onmessage = (event) => {
        try {
          const parsed = JSON.parse(event.data);
          if (parsed.measurements) {
            // Map structured measurements back to points format
            const mappedPoints: TelemetryPoint[] = [];
            if (parsed.measurements.bus_voltages) {
              parsed.measurements.bus_voltages.forEach((b: any) => {
                mappedPoints.push({
                  tag: `${b.bus_id}.V`,
                  value: b.voltage_kV,
                  unit: "kV",
                  quality: "GOOD",
                });
              });
            }
            if (parsed.measurements.generator_outputs) {
              parsed.measurements.generator_outputs.forEach((g: any) => {
                mappedPoints.push({
                  tag: `${g.gen_id}.P`,
                  value: g.mw,
                  unit: "MW",
                  quality: "GOOD",
                });
              });
            }
            setTelemetryPoints((prev) => (mappedPoints.length > 0 ? mappedPoints : prev));
          }
          if (parsed.alarms && parsed.alarms.length > 0) {
            setAlarms((prev) => [...parsed.alarms, ...prev].slice(0, 30));
          }
        } catch (e) {
          console.error("Error parsing WS message:", e);
        }
      };

      socketRef.current.onerror = () => {
        addLog(
          isRtl
            ? "فشل اتصال WebSocket. جاري التحويل لوضع الاقتراع الدؤوب (Polling)..."
            : "WebSocket connection failed. Falling back to HTTP Polling...",
        );
        startPolling();
      };

      socketRef.current.onclose = () => {
        addLog(isRtl ? "تم إغلاق اتصال WebSocket." : "WebSocket connection closed.");
      };
    } catch (err) {
      addLog(
        isRtl
          ? "تعذر تشغيل WebSocket. جاري تفعيل الاقتراع الدؤوب..."
          : "WebSocket client init error. Starting HTTP Polling...",
      );
      startPolling();
    }
  };

  const startPolling = () => {
    if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);

    pollIntervalRef.current = setInterval(async () => {
      try {
        const token = localStorage.getItem("authToken");
        const response = await fetch(`${API_BASE_URL}/api/v1/scada/live`, {
          headers: {
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
            ...(apiKey ? { "x-api-key": apiKey } : {}),
          },
        });
        if (response.ok) {
          const body = await response.json();
          if (body.success && body.data?.points) {
            setTelemetryPoints(body.data.points);
            setConnectionStatus("connected");
          }
        } else {
          setConnectionStatus("disconnected");
        }
      } catch (err) {
        setConnectionStatus("disconnected");
      }
    }, syncInterval * 1000);
  };

  // Simulation Mode Sync
  const startSimulation = () => {
    setConnectionStatus("simulated");
    addLog(
      isRtl ? "تفعيل محاكي إسكادا زينون المحلي." : "Activated local Zenon SCADA simulation feed.",
    );

    if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);

    // Extract telemetry update to reduce function nesting (SonarCloud S2004)
    const updateTelemetry = () => {
      const simRand = () => crypto.getRandomValues(new Uint32Array(1))[0] / 0x100000000;
      const simRandInt = (max: number) => Math.floor(simRand() * max);

      // Fluctuating values randomly
      setTelemetryPoints((prev) =>
        prev.map((p) => {
          let fluctuation = 0;
          if (p.tag.endsWith(".V")) fluctuation = (simRand() - 0.5) * 0.02;
          else if (p.tag.endsWith(".F")) fluctuation = (simRand() - 0.5) * 0.05;
          else fluctuation = (simRand() - 0.5) * 5;
          return { ...p, value: Number.parseFloat((p.value + fluctuation).toFixed(2)) };
        }),
      );

      // Randomly trigger alarms
      if (simRand() < 0.15) generateRandomAlarm(simRandInt);
    };

    const generateRandomAlarm = (simRandInt: (max: number) => number) => {
      const alarmTags = ["Transformer T1", "Breaker CB-04", "Bus Bar 2", "Feeder Line L-08"];
      const severities: ("WARNING" | "CRITICAL")[] = ["WARNING", "CRITICAL"];
      const descriptions = [
        "Overcurrent detected in substation",
        "High oil temperature warning",
        "Voltage transient fluctuation",
        "Communication delay with RTU",
      ];
      const newAlarm: SCADAAlarm = {
        alarm_id: `ALM-${simRandInt(9000) + 1000}`,
        timestamp: new Date().toLocaleTimeString(),
        severity: severities[simRandInt(severities.length)],
        description: `${descriptions[simRandInt(descriptions.length)]} on ${alarmTags[simRandInt(alarmTags.length)]}`,
        location: isRtl ? "محطة القاهرة الشمالية" : "Cairo North Substation",
      };
      setAlarms((prev) => [newAlarm, ...prev].slice(0, 30));
      addLog(`⚠️ ALARM: ${newAlarm.description} (${newAlarm.severity})`);
    };

    pollIntervalRef.current = setInterval(updateTelemetry, 1500);
  };

  const stopSync = () => {
    if (socketRef.current) {
      socketRef.current.close();
      socketRef.current = null;
    }
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
    setConnectionStatus("disconnected");
    addLog(isRtl ? "تم إيقاف المزامنة وبث البيانات." : "Data synchronization paused.");
  };

  useEffect(() => {
    return () => {
      stopSync();
    };
  }, []);

  return (
    <div className="space-y-6">
      {/* Header title */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-blue-500/10 border border-blue-500/20">
            <Activity className="w-5 h-5 text-blue-400" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-[var(--text-primary)]">
              {isRtl ? "اتصال إسكادا زينون (Zenon SCADA)" : "Copa-Data zenon SCADA Connection"}
            </h2>
            <p className="text-sm text-[var(--text-tertiary)]">
              {isRtl
                ? "مراقبة اتصال خادم إسكادا زينون ومزامنة القراءات والإنذارات الحية مع أحمد إيتاب."
                : "Monitor Zenon SCADA server connectivity and sync real-time telemetry variables."}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {/* Status Indicator */}
          {connectionStatus === "connected" && (
            <Badge variant="success" dot size="sm">
              {isRtl ? "متصل بنظام الإسكادا" : "SCADA Online"}
            </Badge>
          )}
          {connectionStatus === "simulated" && (
            <Badge variant="warning" dot size="sm" className="animate-pulse">
              {isRtl ? "وضع المحاكاة النشط" : "Simulation Mode"}
            </Badge>
          )}
          {connectionStatus === "connecting" && (
            <Badge variant="default" dot size="sm" className="animate-pulse">
              {isRtl ? "جاري فحص الاتصال..." : "Connecting..."}
            </Badge>
          )}
          {connectionStatus === "disconnected" && (
            <Badge variant="danger" dot size="sm">
              {isRtl ? "غير متصل" : "Disconnected"}
            </Badge>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Connection & Configuration Panel */}
        <div className="space-y-4">
          <Card padding="md">
            <div className="flex items-center gap-2 mb-4 pb-2 border-b border-[var(--border-primary)]">
              <Server className="w-4 h-4 text-blue-400" />
              <h3 className="text-sm font-bold text-[var(--text-primary)]">
                {isRtl ? "تكوين خادم إسكادا زينون" : "SCADA Server Config"}
              </h3>
            </div>

            <div className="space-y-3.5 text-xs">
              <div>
                <label className="block text-[var(--text-tertiary)] mb-1">
                  {isRtl ? "رابط خادم زينون (Zenon URL)" : "Zenon Server URL"}
                </label>
                <input
                  type="text"
                  value={scadaUrl}
                  onChange={(e) => setScadaUrl(e.target.value)}
                  className="w-full bg-[var(--bg-primary)] border border-[var(--border-primary)] rounded-lg px-3 py-2 text-[var(--text-primary)] focus:outline-none focus:border-blue-500 font-mono"
                />
              </div>

              <div>
                <label className="block text-[var(--text-tertiary)] mb-1">
                  {isRtl ? "مفتاح واجهة برمجة التطبيقات (API Key)" : "SCADA API Key / Token"}
                </label>
                <input
                  type="password"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="Paste zenon API token..."
                  className="w-full bg-[var(--bg-primary)] border border-[var(--border-primary)] rounded-lg px-3 py-2 text-[var(--text-primary)] focus:outline-none focus:border-blue-500 font-mono"
                />
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-[var(--text-tertiary)] mb-1">
                    {isRtl ? "اسم مشروع زينون" : "Project Name"}
                  </label>
                  <input
                    type="text"
                    value={projectName}
                    onChange={(e) => setProjectName(e.target.value)}
                    className="w-full bg-[var(--bg-primary)] border border-[var(--border-primary)] rounded-lg px-2.5 py-1.5 text-[var(--text-primary)] focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-[var(--text-tertiary)] mb-1">
                    {isRtl ? "معدل التحديث (ثانية)" : "Sync Rate (sec)"}
                  </label>
                  <input
                    type="number"
                    value={syncInterval}
                    onChange={(e) => setSyncInterval(Number.parseInt(e.target.value) || 1)}
                    className="w-full bg-[var(--bg-primary)] border border-[var(--border-primary)] rounded-lg px-2.5 py-1.5 text-[var(--text-primary)] focus:outline-none"
                  />
                </div>
              </div>

              <div className="pt-2 flex flex-col gap-2">
                <Button variant="primary" icon={Save} onClick={handleSaveSettings}>
                  {isRtl ? "حفظ إعدادات الربط" : "Save SCADA Configuration"}
                </Button>
                <div className="grid grid-cols-2 gap-2">
                  <Button
                    variant="secondary"
                    icon={RefreshCw}
                    loading={connectionStatus === "connecting"}
                    onClick={testConnection}
                  >
                    {isRtl ? "فحص الاتصال" : "Ping Server"}
                  </Button>
                  <Button
                    variant={isLive ? "danger" : "success"}
                    icon={isLive ? Pause : Play}
                    onClick={toggleLiveSync}
                  >
                    {(() => {
                      if (isLive) return isRtl ? "إيقاف البث" : "Pause Sync";
                      return isRtl ? "تشغيل البث" : "Start Live";
                    })()}
                  </Button>
                </div>
              </div>
            </div>
          </Card>

          {/* Simulation Toggle & Diagnostics Panel */}
          <Card padding="md">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-semibold text-[var(--text-primary)]">
                {isRtl ? "تفعيل بيئة المحاكاة المحلية" : "Offline Simulation Mode"}
              </span>
              <input
                type="checkbox"
                checked={isSimulation}
                onChange={(e) => {
                  setIsSimulation(e.target.checked);
                  if (isLive) {
                    stopSync();
                    setIsLive(false);
                  }
                }}
                className="w-4 h-4 rounded text-blue-600 focus:ring-blue-500 cursor-pointer"
              />
            </div>
            <p className="text-[10px] text-[var(--text-muted)] leading-relaxed">
              {isRtl
                ? "قم بتفعيل هذا الوضع لتجربة قراءة البيانات وحسابات المنصة في بيئة سحابية معزولة عن شبكة زينون الحقيقية."
                : "Turn this on to test streaming and warning alarms if a physical Zenon runtime is not reachable."}
            </p>

            {latency !== null && (
              <div className="mt-4 pt-3 border-t border-[var(--border-primary)] flex justify-between text-xs">
                <span className="text-[var(--text-muted)]">
                  {isRtl ? "زمن الاستجابة (Latency):" : "Latency Response:"}
                </span>
                <span className="font-mono font-bold text-green-400">{latency} ms</span>
              </div>
            )}
          </Card>
        </div>

        {/* Telemetry Tags Live Viewer */}
        <div className="lg:col-span-2 space-y-4">
          <Card padding="md">
            <div className="flex items-center justify-between mb-4 pb-2 border-b border-[var(--border-primary)]">
              <div className="flex items-center gap-2">
                <Database className="w-4 h-4 text-green-400" />
                <h3 className="text-sm font-bold text-[var(--text-primary)]">
                  {isRtl
                    ? "قراءات العدادات الحية (SCADA Telemetry Tags)"
                    : "SCADA Live Telemetry Tags"}
                </h3>
              </div>
              {isLive && <span className="w-2 h-2 rounded-full bg-green-500 animate-ping" />}
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left text-[var(--text-secondary)]">
                <thead className="text-[11px] uppercase tracking-wider text-[var(--text-muted)] border-b border-[var(--border-primary)]">
                  <tr>
                    <th className="py-2 px-3">{isRtl ? "مُعرف العداد" : "Variable/Tag"}</th>
                    <th className="py-2 px-3">{isRtl ? "القيمة الحالية" : "Value"}</th>
                    <th className="py-2 px-3">{isRtl ? "الوحدة" : "Unit"}</th>
                    <th className="py-2 px-3 text-right">{isRtl ? "حالة القراءة" : "Quality"}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border-primary)]">
                  {telemetryPoints.map((point) => (
                    <tr key={point.tag} className="hover:bg-[var(--bg-elevated)] transition-colors">
                      <td className="py-2.5 px-3 font-mono font-semibold text-[var(--text-primary)]">
                        {point.tag}
                      </td>
                      <td className="py-2.5 px-3 font-mono text-blue-400 font-bold text-sm">
                        {point.value}
                      </td>
                      <td className="py-2.5 px-3 text-[var(--text-tertiary)]">{point.unit}</td>
                      <td className="py-2.5 px-3 text-right">
                        <Badge variant={point.quality === "GOOD" ? "success" : "danger"} size="sm">
                          {point.quality}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          {/* Alarm Streams & System Log */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Alarm logs */}
            <Card padding="md" className="h-[260px] flex flex-col">
              <div className="flex items-center justify-between mb-3 pb-2 border-b border-[var(--border-primary)] shrink-0">
                <div className="flex items-center gap-1.5">
                  <ShieldAlert className="w-4 h-4 text-red-400" />
                  <h3 className="text-xs font-bold text-[var(--text-primary)]">
                    {isRtl ? "إنذارات الشبكة الحالية" : "Active Alarm Stream"}
                  </h3>
                </div>
                {alarms.length > 0 && (
                  <Badge variant="danger" size="sm">
                    {alarms.length}
                  </Badge>
                )}
              </div>
              <div className="flex-1 overflow-y-auto space-y-2 pr-1 text-xs">
                {alarms.length === 0 ? (
                  <p className="text-[var(--text-muted)] text-center py-12">
                    {isRtl ? "لا توجد إنذارات حالية." : "No active alarms."}
                  </p>
                ) : (
                  alarms.map((a) => (
                    <div
                      key={a.alarm_id}
                      className={`p-2 rounded border text-[11px] ${
                        a.severity === "CRITICAL"
                          ? "bg-red-500/10 border-red-500/20 text-red-400"
                          : "bg-amber-500/10 border-amber-500/20 text-amber-400"
                      }`}
                    >
                      <div className="flex justify-between font-bold mb-0.5">
                        <span>
                          {a.alarm_id} - {a.severity}
                        </span>
                        <span>{a.timestamp}</span>
                      </div>
                      <p>{a.description}</p>
                      <div className="text-[10px] text-[var(--text-muted)] mt-1">{a.location}</div>
                    </div>
                  ))
                )}
              </div>
            </Card>

            {/* Event trace logs */}
            <Card padding="md" className="h-[260px] flex flex-col">
              <div className="flex items-center justify-between mb-3 pb-2 border-b border-[var(--border-primary)] shrink-0">
                <div className="flex items-center gap-1.5">
                  <Radio className="w-4 h-4 text-blue-400" />
                  <h3 className="text-xs font-bold text-[var(--text-primary)]">
                    {isRtl ? "أثر اتصالات إسكادا" : "Connection Trace Logs"}
                  </h3>
                </div>
                <button
                  className="text-[10px] text-blue-400 hover:underline"
                  onClick={() => setLogs([])}
                >
                  {isRtl ? "تفريغ" : "Clear"}
                </button>
              </div>
              <div className="flex-1 overflow-y-auto font-mono text-[10px] text-[var(--text-secondary)] space-y-1.5">
                {logs.length === 0 ? (
                  <p className="text-[var(--text-muted)] text-center py-12">
                    {isRtl ? "السجلات فارغة." : "Trace is empty."}
                  </p>
                ) : (
                  logs.map((log) => (
                    <div key={log} className="border-b border-[var(--border-primary)]/40 pb-1">
                      {log}
                    </div>
                  ))
                )}
              </div>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}
