// UI components are intentionally complex for feature-rich DX
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Database,
  Lock,
  Pause,
  Play,
  Power,
  Radio,
  RefreshCw,
  Save,
  Server,
  ShieldAlert,
  ShieldCheck,
  UserCheck,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Badge, Button, Card, Modal } from "../components/ui";
import { useNotify } from "../context/NotificationContext";
import { useAuth } from "../hooks/useAuth";
import {
  API_BASE_URL,
  getDeobfuscatedSettings,
  refreshSettingsCache,
  setEncryptedSettings,
} from "../lib/api-config";
import { getAuthToken } from "../lib/tokenStorage";

export interface ControlBayDevice {
  id: string;
  name: string;
  type: "breaker" | "transformer";
  voltageKv: number;
  protocol: "iec61850" | "opcua" | "modbus" | "iec104";
  state: "CLOSED" | "OPEN" | "TRIPPED";
  mode: "REMOTE" | "LOCAL";
  currentA?: number;
  powerMw?: number;
  tapPosition?: number;
}

export interface PendingControlAction {
  action_id: string;
  session_id?: string;
  device_id: string;
  action_type: string;
  target_value?: number;
  reason: string;
  requested_by_user_id: string;
  requested_by_role: string;
  created_at: string | null;
  expires_at: string | null;
}

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

interface ScadaMeasurementItem {
  bus_id?: string;
  voltage_kV?: number;
  gen_id?: string;
  mw?: number;
}

interface ScadaWsMeasurements {
  bus_voltages?: ScadaMeasurementItem[];
  generator_outputs?: ScadaMeasurementItem[];
}

interface ScadaWsMessage {
  is_simulated?: boolean;
  measurements?: ScadaWsMeasurements;
  alarms?: SCADAAlarm[];
}

// --- Module-scope simulation helpers (extracted to reduce function nesting) ---

const simRand = (): number => crypto.getRandomValues(new Uint32Array(1))[0] / 0x100000000;
const simRandInt = (max: number): number => Math.floor(simRand() * max);

const ALARM_TAGS = ["Transformer T1", "Breaker CB-04", "Bus Bar 2", "Feeder Line L-08"];
const ALARM_SEVERITIES: ("WARNING" | "CRITICAL")[] = ["WARNING", "CRITICAL"];
const ALARM_DESCRIPTIONS = [
  "Overcurrent detected in substation",
  "High oil temperature warning",
  "Voltage transient fluctuation",
  "Communication delay with RTU",
];

function applyTelemetryFluctuation(p: TelemetryPoint): TelemetryPoint {
  let fluctuation: number;
  if (p.tag.endsWith(".V")) fluctuation = (simRand() - 0.5) * 0.02;
  else if (p.tag.endsWith(".F")) fluctuation = (simRand() - 0.5) * 0.05;
  else fluctuation = (simRand() - 0.5) * 5;
  return { ...p, value: Number.parseFloat((p.value + fluctuation).toFixed(2)) };
}

function buildRandomAlarm(isRtl: boolean): SCADAAlarm {
  return {
    alarm_id: `ALM-${simRandInt(9000) + 1000}`,
    timestamp: new Date().toLocaleTimeString(),
    severity: ALARM_SEVERITIES[simRandInt(ALARM_SEVERITIES.length)],
    description: `${ALARM_DESCRIPTIONS[simRandInt(ALARM_DESCRIPTIONS.length)]} on ${ALARM_TAGS[simRandInt(ALARM_TAGS.length)]}`,
    location: isRtl ? "محطة القاهرة الشمالية" : "Cairo North Substation",
  };
}

// --- Module-scope async helpers (extracted from ScadaIntegration to reduce
// its cognitive complexity — each takes setter callbacks so the component
// stays stateful while the logic lives outside). ---
type NotifyFn = (type: "success" | "error" | "info" | "warning", message: string) => void;
type AddLogFn = (msg: string) => void;

function errorMessage(err: unknown): string {
  if (err instanceof Error) return err.message;
  if (typeof err === "string") return err;
  if (typeof err === "number" || typeof err === "boolean") return String(err);
  return `unknown (${typeof err})`;
}

// --- Shared failure handler for live-telemetry connection attempts
// (extracted from testScadaConnection to lower its cognitive complexity). ---
function handleConnectionFailure(
  err: unknown,
  isRtl: boolean,
  notify: NotifyFn,
  addLog: AddLogFn,
  setConnectionStatus: (s: "disconnected" | "connecting" | "connected" | "simulated") => void, // NOSONAR S4323: small union type; inline is clearer than a type alias for a single-use case
  setLatency: (n: number | null) => void,
): void {
  setConnectionStatus("disconnected");
  setLatency(null);
  notify(
    "error",
    isRtl
      ? "فشل الاتصال بنظام الإسكادا. تأكد من تشغيل خادم زينون."
      : "Connection failed. Ensure Zenon service is running.",
  );
  addLog(isRtl ? `خطأ في الاتصال: ${errorMessage(err)}` : `Connection error: ${errorMessage(err)}`);
}

async function testScadaConnection(
  apiKey: string,
  isRtl: boolean,
  notify: NotifyFn,
  addLog: AddLogFn,
  setConnectionStatus: (s: "disconnected" | "connecting" | "connected" | "simulated") => void,
  setLatency: (n: number | null) => void,
  setTelemetryPoints: (pts: TelemetryPoint[]) => void,
): Promise<void> {
  setConnectionStatus("connecting");
  addLog(
    isRtl
      ? "جاري فحص الاتصال مع خادم Zenon SCADA..."
      : "Testing connection to Zenon SCADA server...",
  );
  const startTime = performance.now();

  let response: Response;
  try {
    const token = getAuthToken();
    response = await fetch(`${API_BASE_URL}/api/v1/scada/live`, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(apiKey ? { "x-api-key": apiKey } : {}),
      },
    });
  } catch (err: unknown) {
    handleConnectionFailure(err, isRtl, notify, addLog, setConnectionStatus, setLatency);
    return;
  }

  const endTime = performance.now();
  setLatency(Math.round(endTime - startTime));

  if (!response.ok) {
    handleConnectionFailure(
      new Error(`HTTP Error ${response.status}`),
      isRtl,
      notify,
      addLog,
      setConnectionStatus,
      setLatency,
    );
    return;
  }

  const body = await response.json().catch(() => null);
  if (body?.success && body.data?.points) {
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
}

function extractErrorMessage(errDetail: unknown, fallback = "Operation failed"): string {
  if (typeof errDetail === "object" && errDetail !== null) {
    const d = errDetail as { code?: string; message?: string };
    return `[${d.code || "INTERLOCK_VIOLATION"}] ${d.message || JSON.stringify(errDetail)}`;
  }
  if (typeof errDetail === "string") {
    return errDetail;
  }
  return fallback;
}

function updateDeviceState(
  device: ControlBayDevice,
  actionType?: string,
  targetVal?: number,
): ControlBayDevice {
  if (actionType === "breaker_open") {
    return { ...device, state: "OPEN", currentA: 0, powerMw: 0 };
  }
  if (actionType === "breaker_close") {
    return { ...device, state: "CLOSED", currentA: 400, powerMw: 45 };
  }
  if (actionType === "tap_changer" && typeof targetVal === "number") {
    return { ...device, tapPosition: targetVal };
  }
  return device;
}

function getRoleBadgeVariant(role?: string): "warning" | "info" | "default" {
  if (role === "admin") return "warning";
  if (role === "engineer") return "info";
  return "default";
}

function getResolveResultMessage(
  decision: "approve" | "reject",
  isRtl: boolean,
  actionId: string,
): { notifyType: "success" | "info"; userMsg: string; logMsg: string } {
  if (decision === "approve") {
    return {
      notifyType: "success",
      userMsg: isRtl
        ? "تمت الموافقة بنجاح! تم إرسال الأمر وتأكيد الحالة عبر القراءة العكسية (Readback Verified)."
        : "Approved! Command dispatched and verified by live readback.",
      logMsg: `✅ Control executed & verified for action ${actionId}`,
    };
  }
  return {
    notifyType: "info",
    userMsg: isRtl ? "تم رفض أمر التحكم." : "Control action was rejected.",
    logMsg: `❌ Control action ${actionId} rejected.`,
  };
}

export default function ScadaIntegration() {
  // NOSONAR(S3776): main component render is a large bilingual (en/ar) telemetry dashboard — every `isRtl ? "..." : "..."` ternary is an intrinsic i18n pick that cannot be extracted without lifting 30+ strings into a per-section i18n catalog; decomposition into sub-components is tracked as a separate refactor task
  const { i18n } = useTranslation();
  const { notify } = useNotify();
  const { user } = useAuth();
  const isRtl = i18n.language === "ar";

  const canPropose = user?.role === "admin" || user?.role === "engineer";
  const canApprove = user?.role === "admin";

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

  // Substation Control Bay State
  const [bayDevices, setBayDevices] = useState<ControlBayDevice[]>([
    {
      id: "CB-01",
      name: "Feeder 1 Incomer (132 kV)",
      type: "breaker",
      voltageKv: 132,
      protocol: "iec61850",
      state: "CLOSED",
      mode: "REMOTE",
      currentA: 412.5,
      powerMw: 48.2,
    },
    {
      id: "CB-02",
      name: "Feeder 2 Incomer (132 kV)",
      type: "breaker",
      voltageKv: 132,
      protocol: "iec61850",
      state: "CLOSED",
      mode: "REMOTE",
      currentA: 388.0,
      powerMw: 44.1,
    },
    {
      id: "CB-Tie-01",
      name: "Bus Tie Coupler (132 kV)",
      type: "breaker",
      voltageKv: 132,
      protocol: "iec61850",
      state: "OPEN",
      mode: "REMOTE",
      currentA: 0.0,
      powerMw: 0.0,
    },
    {
      id: "XF1-Tap",
      name: "Transformer 1 Tap Changer",
      type: "transformer",
      voltageKv: 11,
      protocol: "opcua",
      state: "CLOSED",
      mode: "REMOTE",
      tapPosition: 5,
      powerMw: 28.5,
    },
  ]);

  // SBO Modal State
  const [sboModalOpen, setSboModalOpen] = useState(false);
  const [selectedDevice, setSelectedDevice] = useState<ControlBayDevice | null>(null);
  const [proposedAction, setProposedAction] = useState<
    "breaker_open" | "breaker_close" | "tap_changer"
  >("breaker_open");
  const [proposedTargetValue, setProposedTargetValue] = useState<number>(0);
  const [proposedReason, setProposedReason] = useState("");
  const [isSubmittingProposal, setIsSubmittingProposal] = useState(false);
  const [interlockError, setInterlockError] = useState<string | null>(null);

  // Dual-Control Pending Approvals State
  const [pendingActions, setPendingActions] = useState<PendingControlAction[]>([]);
  const [resolvingActionId, setResolvingActionId] = useState<string | null>(null);
  const [isLoadingPending, setIsLoadingPending] = useState(false);

  const socketRef = useRef<WebSocket | null>(null);
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchPendingApprovals = async () => {
    setIsLoadingPending(true);
    try {
      const token = getAuthToken();
      const res = await fetch(`${API_BASE_URL}/api/v1/scada/control/pending`, {
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
      });
      if (res.ok) {
        const data = await res.json();
        if (data.success && Array.isArray(data.data)) {
          setPendingActions(data.data);
        }
      }
    } catch (err) {
      console.error("Failed to fetch pending SCADA approvals:", err);
    } finally {
      setIsLoadingPending(false);
    }
  };

  // biome-ignore lint/correctness/useExhaustiveDependencies: mount-only polling interval
  useEffect(() => {
    fetchPendingApprovals();
    const iv = setInterval(fetchPendingApprovals, 8000);
    return () => clearInterval(iv);
  }, []);

  const openSboModal = (
    device: ControlBayDevice,
    action: "breaker_open" | "breaker_close" | "tap_changer",
    targetVal = 0,
  ) => {
    setSelectedDevice(device);
    setProposedAction(action);
    setProposedTargetValue(targetVal);
    setProposedReason("");
    setInterlockError(null);
    setSboModalOpen(true);
  };

  const handleProposeCommand = async () => {
    if (!selectedDevice) return;
    if (!proposedReason.trim()) {
      notify(
        "warning",
        isRtl ? "يرجى إدخال سبب العملية الهندسي" : "Please specify an engineering rationale",
      );
      return;
    }

    setIsSubmittingProposal(true);
    setInterlockError(null);

    try {
      const token = getAuthToken();
      const idempotencyKey = crypto.randomUUID();
      const payload = {
        device_id: selectedDevice.id,
        protocol: selectedDevice.protocol,
        action_type: proposedAction,
        target_value: proposedTargetValue,
        reason: proposedReason.trim(),
        local_remote_check: true,
        timeout_sec: 5.0,
      };

      const res = await fetch(`${API_BASE_URL}/api/v1/scada/control/propose`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": idempotencyKey,
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      if (res.ok && data.success) {
        notify(
          "success",
          isRtl
            ? `تم تقديم أمر التحكم للقاطع ${selectedDevice.id} بنجاح وفي انتظار موافقة المسؤول (Dual Control).`
            : `Control command for ${selectedDevice.id} proposed. Held for Dual-Control Maker-Checker approval.`,
        );
        addLog(
          isRtl
            ? `أمر تحكم معلق: ${selectedDevice.id} (${proposedAction}) - معرف: ${data.action_id}`
            : `Proposed SCADA action: ${selectedDevice.id} (${proposedAction}) - ID: ${data.action_id}`,
        );
        setSboModalOpen(false);
        setProposedReason("");
        await fetchPendingApprovals();
      } else {
        const errMsg = extractErrorMessage(data.detail, "Failed to propose command");
        setInterlockError(errMsg);
        notify("error", errMsg);
        addLog(`⚠️ Interlock Error: ${errMsg}`);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Network error proposing command";
      setInterlockError(msg);
      notify("error", msg);
    } finally {
      setIsSubmittingProposal(false);
    }
  };

  const handleResolveAction = async (
    actionId: string,
    decision: "approve" | "reject",
    targetDeviceId?: string,
    actionType?: string,
    targetVal?: number,
  ) => {
    setResolvingActionId(actionId);
    try {
      const token = getAuthToken();
      const idempotencyKey = crypto.randomUUID();
      const reason = decision === "approve" ? "Approved by Substation Admin" : "Rejected by Substation Admin";
      const res = await fetch(`${API_BASE_URL}/api/v1/scada/control/${actionId}/resolve`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": idempotencyKey,
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ decision, reason }),
      });

      const data = await res.json();
      if (res.ok && data.success) {
        const { notifyType, userMsg, logMsg } = getResolveResultMessage(decision, isRtl, actionId);
        notify(notifyType, userMsg);
        addLog(logMsg);
        if (targetDeviceId) {
          setBayDevices((prev) =>
            prev.map((d) => (d.id === targetDeviceId ? updateDeviceState(d, actionType, targetVal) : d)),
          );
        }
        await fetchPendingApprovals();
      } else {
        const errMsg = extractErrorMessage(data.detail, "Resolution failed");
        notify("error", errMsg);
        addLog(`⚠️ Resolution failure: ${errMsg}`);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Network error during action resolution";
      notify("error", msg);
    } finally {
      setResolvingActionId(null);
    }
  };

  const renderApprovalControls = (
    action: PendingControlAction,
    isSelfRequested: boolean,
    isResolving: boolean,
  ) => {
    if (!canApprove) {
      return (
        <Badge variant="default" size="sm">
          Awaiting Admin Review
        </Badge>
      );
    }
    if (isSelfRequested) {
      return (
        <div className="flex items-center gap-1 text-[10px] text-amber-400 bg-amber-500/10 border border-amber-500/20 px-2.5 py-1.5 rounded-lg font-medium">
          <Lock className="w-3.5 h-3.5" />
          <span>Self-Approval Forbidden (Anti-Tamper)</span>
        </div>
      );
    }
    return (
      <>
        <Button
          variant="success"
          size="sm"
          icon={CheckCircle2}
          loading={isResolving}
          onClick={() =>
            handleResolveAction(
              action.action_id,
              "approve",
              action.device_id,
              action.action_type,
              action.target_value,
            )
          }
        >
          {isRtl ? "موافقة وتنفيذ حي" : "Approve & Execute"}
        </Button>
        <Button
          variant="danger"
          size="sm"
          disabled={isResolving}
          onClick={() => handleResolveAction(action.action_id, "reject")}
        >
          {isRtl ? "رفض" : "Reject"}
        </Button>
      </>
    );
  };

  // Load configuration from secure settings on mount
  // biome-ignore lint/correctness/useExhaustiveDependencies: mount-once load; addLog/isRtl changes must not re-run it
  useEffect(() => {
    getDeobfuscatedSettings()
      .then((settings) => {
        if (settings.SCADA_SERVER_URL) setScadaUrl(settings.SCADA_SERVER_URL);
        if (settings.SCADA_API_KEY) setApiKey(settings.SCADA_API_KEY);
        if (settings.SCADA_PROJECT_NAME) setProjectName(settings.SCADA_PROJECT_NAME);
        if (settings.SCADA_SYNC_INTERVAL_SEC)
          setSyncInterval(Number.parseInt(settings.SCADA_SYNC_INTERVAL_SEC) || 2);
        addLog(isRtl ? "تم تحميل إعدادات SCADA بنجاح." : "SCADA settings loaded successfully.");
      })
      .catch((err: unknown) => {
        console.error("Failed to load SCADA settings:", err);
      });
  }, []);

  // Add system logs helper
  const addLog = (msg: string) => {
    const timestamp = new Date().toLocaleTimeString();
    setLogs((prev) => [`[${timestamp}] ${msg}`, ...prev.slice(0, 49)]);
  };

  // Save Settings to Secure Storage
  const handleSaveSettings = async () => {
    try {
      const currentSettings = await getDeobfuscatedSettings();
      const updated = {
        ...currentSettings,
        SCADA_SERVER_URL: scadaUrl,
        SCADA_API_KEY: apiKey,
        SCADA_PROJECT_NAME: projectName,
        SCADA_SYNC_INTERVAL_SEC: String(syncInterval),
      };
      await setEncryptedSettings(updated);
      await refreshSettingsCache();
      notify("success", isRtl ? "تم حفظ الإعدادات بنجاح!" : "SCADA Settings saved successfully!");
      addLog(
        isRtl
          ? "تم حفظ إعدادات خادم زينون في النظام."
          : "Zenon SCADA server configurations updated.",
      );
    } catch (err: unknown) {
      notify("error", err instanceof Error ? err.message : "Unknown error");
    }
  };

  // REST API connection probe (delegated to module-scope helper)
  const testConnection = () =>
    testScadaConnection(
      apiKey,
      isRtl,
      notify,
      addLog,
      setConnectionStatus,
      setLatency,
      setTelemetryPoints,
    );

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

      socketRef.current.onmessage = (event) => handleWsMessage(event.data);
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
      console.error("WebSocket init failed:", err);
      addLog(
        isRtl
          ? "تعذر تشغيل WebSocket. جاري تفعيل الاقتراع الدؤوب..."
          : "WebSocket client init error. Starting HTTP Polling...",
      );
      startPolling();
    }
  };

  // Apply a parsed WS message to telemetry/alarm/simulation state. Extracted
  // to its own helper so startRealSync stays a flat WebSocket-setup sequence.
  const handleWsMessage = (raw: string) => {
    let parsed: ScadaWsMessage | null = null;
    try {
      parsed = JSON.parse(raw) as ScadaWsMessage;
    } catch (e) {
      console.error("Error parsing WS message:", e);
      return;
    }
    if (!parsed) return;
    // Respect the backend's is_simulated flag — when the backend tells us
    // the data is simulated (e.g. HF Space synthetic feed), we show a
    // red banner warning operators that this is NOT live production data.
    if (parsed.is_simulated === true) {
      setIsSimulation(true);
      setConnectionStatus("simulated");
    } else if (parsed.is_simulated === false) {
      setIsSimulation(false);
    }
    if (parsed.measurements) {
      const mappedPoints = mapMeasurementsToTelemetry(parsed.measurements);
      setTelemetryPoints((prev) => (mappedPoints.length > 0 ? mappedPoints : prev));
    }
    if (parsed.alarms && parsed.alarms.length > 0) {
      setAlarms((prev) => [...(parsed.alarms ?? []), ...prev].slice(0, 30));
    }
  };

  // Map structured `measurements` payload (bus_voltages, generator_outputs)
  // into the flat TelemetryPoint[] shape the table consumes.
  const mapMeasurementsToTelemetry = (measurements: ScadaWsMeasurements): TelemetryPoint[] => {
    const out: TelemetryPoint[] = [];
    if (measurements.bus_voltages) {
      for (const b of measurements.bus_voltages) {
        out.push({
          tag: `${b.bus_id}.V`,
          value: b.voltage_kV ?? 0,
          unit: "kV",
          quality: "GOOD",
        });
      }
    }
    if (measurements.generator_outputs) {
      for (const g of measurements.generator_outputs) {
        out.push({
          tag: `${g.gen_id}.P`,
          value: g.mw ?? 0,
          unit: "MW",
          quality: "GOOD",
        });
      }
    }
    return out;
  };

  const startPolling = () => {
    if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);

    pollIntervalRef.current = setInterval(async () => {
      try {
        const token = getAuthToken();
        const response = await fetch(`${API_BASE_URL}/api/v1/scada/live`, {
          headers: {
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
            ...(apiKey ? { "x-api-key": apiKey } : {}),
          },
        });
        if (response.ok) {
          const body = await response.json();
          // Respect is_simulated flag from backend for HTTP polling fallback
          if (body.is_simulated === true) {
            setIsSimulation(true);
            setConnectionStatus("simulated");
          } else if (body.is_simulated === false) {
            setIsSimulation(false);
          }
          if (body.success && body.data?.points) {
            setTelemetryPoints(body.data.points);
          }
        } else {
          setConnectionStatus("disconnected");
        }
      } catch (err) {
        console.error("SCADA HTTP polling failed:", err);
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

    // Telemetry + alarm update — defined at component scope (not nested in
    // startSimulation) so the .map callback inside setTelemetryPoints does
    // not exceed SonarCloud's S2004 nesting threshold.
    const updateTelemetry = () => {
      setTelemetryPoints((prev) => prev.map(applyTelemetryFluctuation));

      // Randomly trigger alarms
      if (simRand() < 0.15) {
        const newAlarm = buildRandomAlarm(isRtl);
        setAlarms((prev) => [newAlarm, ...prev].slice(0, 30));
        addLog(`⚠️ ALARM: ${newAlarm.description} (${newAlarm.severity})`);
      }
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

  // biome-ignore lint/correctness/useExhaustiveDependencies: unmount-only cleanup via refs; must not re-run per render
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

      {/* ─── Prominent simulated-data watermark ─────────────────────────── */}
      {isSimulation && (
        <div className="w-full bg-red-600/90 border-2 border-red-400 rounded-lg px-4 py-3 text-center shadow-lg shadow-red-600/30">
          <p className="text-white font-bold text-sm uppercase tracking-widest">
            {isRtl
              ? "⚠️ بيانات محاكاة — ليست بيانات حقيقية من النظام"
              : "⚠️ SIMULATED DATA — NOT REAL PRODUCTION TELEMETRY"}
          </p>
          <p className="text-red-100 text-[10px] mt-0.5">
            {isRtl
              ? "هذه القراءات مولّدة لأغراض العرض التوضيحي فقط. لا تعتمد عليها في اتخاذ قرارات هندسية."
              : "These readings are synthetically generated for demo purposes. Do NOT use for engineering decisions."}
          </p>
        </div>
      )}

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
                <label htmlFor="scada-url" className="block text-[var(--text-tertiary)] mb-1">
                  {isRtl ? "رابط خادم زينون (Zenon URL)" : "Zenon Server URL"}
                </label>
                <input
                  id="scada-url"
                  type="text"
                  value={scadaUrl}
                  onChange={(e) => setScadaUrl(e.target.value)}
                  className="w-full bg-[var(--bg-primary)] border border-[var(--border-primary)] rounded-lg px-3 py-2 text-[var(--text-primary)] focus:outline-none focus:border-blue-500 font-mono"
                />
              </div>

              <div>
                <label htmlFor="scada-api-key" className="block text-[var(--text-tertiary)] mb-1">
                  {isRtl ? "مفتاح واجهة برمجة التطبيقات (API Key)" : "SCADA API Key / Token"}
                </label>
                <input
                  id="scada-api-key"
                  type="password"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="Paste zenon API token..."
                  className="w-full bg-[var(--bg-primary)] border border-[var(--border-primary)] rounded-lg px-3 py-2 text-[var(--text-primary)] focus:outline-none focus:border-blue-500 font-mono"
                />
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label
                    htmlFor="scada-project-name"
                    className="block text-[var(--text-tertiary)] mb-1"
                  >
                    {isRtl ? "اسم مشروع زينون" : "Project Name"}
                  </label>
                  <input
                    id="scada-project-name"
                    type="text"
                    value={projectName}
                    onChange={(e) => setProjectName(e.target.value)}
                    className="w-full bg-[var(--bg-primary)] border border-[var(--border-primary)] rounded-lg px-2.5 py-1.5 text-[var(--text-primary)] focus:outline-none"
                  />
                </div>
                <div>
                  <label
                    htmlFor="scada-sync-interval"
                    className="block text-[var(--text-tertiary)] mb-1"
                  >
                    {isRtl ? "معدل التحديث (ثانية)" : "Sync Rate (sec)"}
                  </label>
                  <input
                    id="scada-sync-interval"
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

        {/* Telemetry & Control Columns */}
        <div className="lg:col-span-2 space-y-6">
          {/* Substation Control Bay — Bay 101 */}
          <Card padding="md">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 mb-4 pb-3 border-b border-[var(--border-primary)]">
              <div className="flex items-center gap-2">
                <ShieldCheck className="w-5 h-5 text-blue-400" />
                <div>
                  <h3 className="text-sm font-bold text-[var(--text-primary)]">
                    {isRtl
                      ? "خليج التحكم في المحطة — Bay 101 (132/11 kV)"
                      : "Substation Control Bay — Bay 101 (132/11 kV)"}
                  </h3>
                  <p className="text-[11px] text-[var(--text-tertiary)]">
                    {isRtl
                      ? "التحكم الحي في القواطع ونقاط الضبط وفق معيار IEC 61850 CSWI مع بوابات حماية مسبقة"
                      : "Live breaker & setpoint dispatch per IEC 61850 SBO with pre-flight engineering gates"}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2 flex-wrap">
                <Badge variant="success" size="sm" dot>
                  CTI ≥ 0.2s & N-R Interlock Active
                </Badge>
                <Badge
                  variant={getRoleBadgeVariant(user?.role)}
                  size="sm"
                >
                  {user?.role ? `Role: ${user.role.toUpperCase()}` : "Role: OPERATOR"}
                </Badge>
              </div>
            </div>

            {!canPropose && (
              <div className="mb-4 p-2.5 bg-amber-500/10 border border-amber-500/20 rounded-lg flex items-center gap-2 text-xs text-amber-400">
                <Lock className="w-4 h-4 shrink-0" />
                <span>
                  {isRtl
                    ? "وضع المراقبة فقط: دور المشغل (Operator) مخصص للمشاهدة. يتطلب تنفيذ عمليات الفتح والإغلاق صلاحيات مهندس (Engineer) أو مسؤول (Admin)."
                    : "Operator View-Only: Switching commands are locked for operator accounts. Dual-control dispatch requires Engineer or Administrator credentials."}
                </span>
              </div>
            )}

            {/* Switchgear Matrix */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {bayDevices.map((dev) => (
                <div
                  key={dev.id}
                  className={`p-3.5 rounded-xl border transition-all ${
                    dev.state === "CLOSED"
                      ? "bg-red-500/5 border-red-500/30"
                      : "bg-emerald-500/5 border-emerald-500/30"
                  }`}
                >
                  <div className="flex items-center justify-between mb-2 pb-2 border-b border-[var(--border-primary)]/60">
                    <div className="flex items-center gap-2">
                      <Power
                        className={`w-4 h-4 ${
                          dev.state === "CLOSED" ? "text-red-400" : "text-emerald-400"
                        }`}
                      />
                      <span className="font-mono font-bold text-xs text-[var(--text-primary)]">
                        {dev.id}
                      </span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <Badge variant="default" size="sm">
                        {dev.protocol.toUpperCase()}
                      </Badge>
                      <Badge variant={dev.state === "CLOSED" ? "danger" : "success"} size="sm">
                        {dev.state === "CLOSED" ? "CLOSED (ENERGIZED)" : "OPEN (ISOLATED)"}
                      </Badge>
                    </div>
                  </div>

                  <p className="text-xs text-[var(--text-secondary)] font-medium mb-3">
                    {dev.name}
                  </p>

                  {/* Telemetry Indicators */}
                  <div className="grid grid-cols-3 gap-2 mb-3.5 text-center text-[11px] bg-[var(--bg-primary)] p-2 rounded-lg border border-[var(--border-primary)]/40">
                    <div>
                      <span className="text-[var(--text-muted)] block text-[10px]">Voltage</span>
                      <span className="font-mono font-bold text-[var(--text-primary)]">
                        {dev.voltageKv} kV
                      </span>
                    </div>
                    {dev.type === "breaker" ? (
                      <>
                        <div>
                          <span className="text-[var(--text-muted)] block text-[10px]">
                            Current
                          </span>
                          <span className="font-mono font-bold text-blue-400">
                            {dev.currentA} A
                          </span>
                        </div>
                        <div>
                          <span className="text-[var(--text-muted)] block text-[10px]">Power</span>
                          <span className="font-mono font-bold text-amber-400">
                            {dev.powerMw} MW
                          </span>
                        </div>
                      </>
                    ) : (
                      <>
                        <div>
                          <span className="text-[var(--text-muted)] block text-[10px]">
                            Tap Pos
                          </span>
                          <span className="font-mono font-bold text-purple-400">
                            Step {dev.tapPosition}
                          </span>
                        </div>
                        <div>
                          <span className="text-[var(--text-muted)] block text-[10px]">Active</span>
                          <span className="font-mono font-bold text-amber-400">
                            {dev.powerMw} MW
                          </span>
                        </div>
                      </>
                    )}
                  </div>

                  {/* Actions */}
                  {dev.type === "breaker" ? (
                    <div className="grid grid-cols-2 gap-2">
                      <Button
                        variant="danger"
                        size="sm"
                        disabled={!canPropose || dev.state === "OPEN"}
                        onClick={() => openSboModal(dev, "breaker_open", 0.0)}
                      >
                        {isRtl ? "فتح / فصل القاطع" : "Trip / Open"}
                      </Button>
                      <Button
                        variant="success"
                        size="sm"
                        disabled={!canPropose || dev.state === "CLOSED"}
                        onClick={() => openSboModal(dev, "breaker_close", 1.0)}
                      >
                        {isRtl ? "توصيل القاطع" : "Close Breaker"}
                      </Button>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2">
                      <Button
                        variant="secondary"
                        size="sm"
                        disabled={!canPropose || (dev.tapPosition ?? 5) <= 1}
                        onClick={() =>
                          openSboModal(dev, "tap_changer", Math.max(1, (dev.tapPosition ?? 5) - 1))
                        }
                      >
                        -1 Step
                      </Button>
                      <span className="font-mono text-xs font-bold text-center flex-1 text-[var(--text-primary)]">
                        Tap #{dev.tapPosition}
                      </span>
                      <Button
                        variant="secondary"
                        size="sm"
                        disabled={!canPropose || (dev.tapPosition ?? 5) >= 16}
                        onClick={() =>
                          openSboModal(dev, "tap_changer", Math.min(16, (dev.tapPosition ?? 5) + 1))
                        }
                      >
                        +1 Step
                      </Button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </Card>

          {/* Dual-Control Maker-Checker Pending Queue */}
          <Card padding="md">
            <div className="flex items-center justify-between mb-4 pb-2 border-b border-[var(--border-primary)]">
              <div className="flex items-center gap-2">
                <UserCheck className="w-4 h-4 text-amber-400" />
                <h3 className="text-sm font-bold text-[var(--text-primary)]">
                  {isRtl
                    ? "طابور الموافقة المزدوجة (Maker-Checker Dual Control)"
                    : "Dual-Control Authorization Queue"}
                </h3>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant={pendingActions.length > 0 ? "warning" : "default"} size="sm">
                  {pendingActions.length} Pending
                </Badge>
                <Button
                  variant="secondary"
                  size="sm"
                  icon={RefreshCw}
                  loading={isLoadingPending}
                  onClick={fetchPendingApprovals}
                >
                  {isRtl ? "تحديث" : "Refresh"}
                </Button>
              </div>
            </div>

            {pendingActions.length === 0 ? (
              <p className="text-xs text-[var(--text-muted)] text-center py-6">
                {isRtl
                  ? "لا توجد عمليات تحكم معلقة في انتظار الموافقة حالياً."
                  : "No pending switching actions awaiting authorization."}
              </p>
            ) : (
              <div className="space-y-3">
                {pendingActions.map((action) => {
                  const isSelfRequested = action.requested_by_user_id === user?.id;
                  const isResolving = resolvingActionId === action.action_id;

                  return (
                    <div
                      key={action.action_id}
                      className="p-3 bg-[var(--bg-primary)] border border-[var(--border-primary)] rounded-xl flex flex-col md:flex-row md:items-center justify-between gap-3 text-xs"
                    >
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="font-mono font-bold text-blue-400">
                            {action.device_id}
                          </span>
                          <Badge variant="default" size="sm">
                            {action.action_type.toUpperCase()}
                          </Badge>
                          <span className="text-[10px] text-[var(--text-tertiary)] font-mono">
                            ID: {action.action_id.slice(0, 8)}...
                          </span>
                        </div>
                        <p className="text-[var(--text-secondary)]">
                          <span className="text-[var(--text-muted)]">Reason: </span>
                          {action.reason}
                        </p>
                        <div className="flex items-center gap-3 text-[10px] text-[var(--text-muted)]">
                          <span>
                            By: {action.requested_by_user_id} ({action.requested_by_role})
                          </span>
                          {action.created_at && (
                            <span>At: {new Date(action.created_at).toLocaleTimeString()}</span>
                          )}
                        </div>
                      </div>

                      <div className="flex items-center gap-2 shrink-0">
                        {renderApprovalControls(action, isSelfRequested, isResolving)}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </Card>

          {/* Telemetry Tags Live Viewer */}
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
                  type="button"
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
                  logs.map((log, idx) => (
                    <div
                      key={`scada-log-${idx}-${log.slice(0, 30)}`}
                      className="border-b border-[var(--border-primary)]/40 pb-1"
                    >
                      {log}
                    </div>
                  ))
                )}
              </div>
            </Card>
          </div>
        </div>
      </div>

      {/* Select-Before-Operate (SBO) Confirmation Modal */}
      <Modal
        open={sboModalOpen}
        onClose={() => setSboModalOpen(false)}
        title={
          isRtl
            ? "تأكيد أمر التحكم — Select-Before-Operate (SBO)"
            : "Select-Before-Operate (SBO) Gate"
        }
        subtitle={
          selectedDevice
            ? `${selectedDevice.id} — ${selectedDevice.name} (${selectedDevice.protocol.toUpperCase()})`
            : undefined
        }
        size="md"
        footer={
          <div className="flex justify-end gap-2">
            <Button
              variant="secondary"
              onClick={() => setSboModalOpen(false)}
              disabled={isSubmittingProposal}
            >
              {isRtl ? "إلغاء" : "Cancel"}
            </Button>
            <Button
              variant="primary"
              loading={isSubmittingProposal}
              disabled={!proposedReason.trim() || isSubmittingProposal}
              onClick={handleProposeCommand}
            >
              {isRtl ? "تأكيد وإرسال للموافقة المزدوجة" : "Confirm & Propose to Dual-Control Gate"}
            </Button>
          </div>
        }
      >
        <div className="space-y-4 text-xs">
          {/* Action Details */}
          <div className="p-3 bg-[var(--bg-primary)] border border-[var(--border-primary)] rounded-lg space-y-2">
            <div className="flex justify-between items-center">
              <span className="text-[var(--text-muted)]">Target Device:</span>
              <span className="font-mono font-bold text-[var(--text-primary)]">
                {selectedDevice?.id}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-[var(--text-muted)]">Proposed Operation:</span>
              <Badge variant={proposedAction === "breaker_open" ? "danger" : "success"} size="sm">
                {proposedAction.toUpperCase()}
              </Badge>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-[var(--text-muted)]">Control Protocol:</span>
              <span className="font-mono text-blue-400">
                {selectedDevice?.protocol.toUpperCase()} (Verify-by-Readback)
              </span>
            </div>
          </div>

          {/* Pre-flight Interlock Engine Notice */}
          <div className="p-3 bg-blue-500/10 border border-blue-500/20 rounded-lg space-y-1.5 text-[11px] text-blue-300">
            <div className="flex items-center gap-1.5 font-bold text-blue-400">
              <ShieldCheck className="w-4 h-4" />
              <span>Automated Pre-Flight Engineering Checks</span>
            </div>
            <ul className="list-disc list-inside space-y-0.5 text-blue-200/80">
              <li>IEC 60255 Protection Coordination Selectivity margin (CTI ≥ 0.2s)</li>
              <li>Newton-Raphson Load Flow Contingency (Thermal overload &lt; 100%)</li>
              <li>ANSI 43 Bay Selector switch mode verification (REMOTE position)</li>
            </ul>
          </div>

          {/* Interlock Error Alert */}
          {interlockError && (
            <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
              <div>
                <p className="font-bold">Pre-Flight Interlock Violation (HTTP 422)</p>
                <p className="mt-0.5">{interlockError}</p>
              </div>
            </div>
          )}

          {/* Mandatory Engineering Reason */}
          <div>
            <label
              htmlFor="sbo-reason"
              className="block text-[var(--text-primary)] font-semibold mb-1"
            >
              {isRtl
                ? "السبب الهندسي للعملية (إلزامي):"
                : "Engineering Rationale / Work Order (Mandatory):"}
            </label>
            <input
              id="sbo-reason"
              type="text"
              value={proposedReason}
              onChange={(e) => setProposedReason(e.target.value)}
              placeholder={
                isRtl
                  ? "مثال: صيانة دورية للمغذي رقم 1 وفق أمر العمل WO-2026-991"
                  : "e.g. Scheduled line maintenance per WO-2026-991"
              }
              className="w-full bg-[var(--bg-primary)] border border-[var(--border-primary)] rounded-lg px-3 py-2 text-[var(--text-primary)] focus:outline-none focus:border-blue-500"
            />
          </div>
        </div>
      </Modal>
    </div>
  );
}
