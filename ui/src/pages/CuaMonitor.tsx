// NOSONAR — admin dashboard with complex UI patterns
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Activity, AlertTriangle, Power, Shield, ShieldOff } from "lucide-react";
import { Badge, Button, Card } from "../components/ui";
import { useNotify } from "../context/NotificationContext";
import { API_BASE_URL } from "../lib/api-config";

interface CUAActionLog {
  entry_id: number;
  hash: string;
  prev_hash: string;
  timestamp: string;
  entry_type: string;
  action: string;
  action_type?: string;
  blocked?: boolean;
  safety_level?: string;
}

interface KillSwitchStatus {
  active: boolean;
  activated_at: string | null;
  reason: string | null;
}

export default function CuaMonitor() {
  const { i18n } = useTranslation();
  const { notify } = useNotify();
  const isRtl = i18n.language === "ar";

  const [logs, setLogs] = useState<CUAActionLog[]>([]);
  const [killSwitch, setKillSwitch] = useState<KillSwitchStatus>({
    active: false, activated_at: null, reason: null,
  });
  const [loading, setLoading] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchKillSwitch = async () => {
    try {
      const token = localStorage.getItem("authToken");
      const resp = await fetch(`${API_BASE_URL}/admin/cua/kill-switch`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (resp.ok) {
        const data = await resp.json();
        setKillSwitch(data);
      }
    } catch {
      // silent
    }
  };

  const fetchAuditLog = async () => {
    try {
      const token = localStorage.getItem("authToken");
      const resp = await fetch(`${API_BASE_URL}/admin/cua/audit-log?limit=50`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (resp.ok) {
        const data = await resp.json();
        setLogs(data.entries || []);
      }
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  };

  const activateKill = async () => {
    try {
      const token = localStorage.getItem("authToken");
      const resp = await fetch(`${API_BASE_URL}/admin/cua/kill-switch/activate`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ reason: "manual_from_dashboard" }),
      });
      if (resp.ok) {
        notify("success", "Kill switch activated");
        fetchKillSwitch();
      } else {
        notify("error", "Failed to activate kill switch");
      }
    } catch {
      notify("error", "Network error activating kill switch");
    }
  };

  const deactivateKill = async () => {
    try {
      const token = localStorage.getItem("authToken");
      const resp = await fetch(`${API_BASE_URL}/admin/cua/kill-switch/deactivate`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (resp.ok) {
        notify("success", "Kill switch deactivated");
        fetchKillSwitch();
      } else {
        notify("error", "Failed to deactivate kill switch");
      }
    } catch {
      notify("error", "Network error deactivating kill switch");
    }
  };

  useEffect(() => {
    fetchKillSwitch();
    fetchAuditLog();

    if (autoRefresh) {
      intervalRef.current = setInterval(() => {
        fetchKillSwitch();
        fetchAuditLog();
      }, 5000);
    }

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [autoRefresh]);

  const getEntryColor = (entry: CUAActionLog) => {
    if (entry.blocked) return "text-red-400 border-red-500/30";
    if (entry.entry_type === "pre_action") return "text-yellow-400 border-yellow-500/30";
    if (entry.entry_type === "rollback") return "text-orange-400 border-orange-500/30";
    if (entry.entry_type === "post_action") return "text-green-400 border-green-500/30";
    return "text-blue-400 border-blue-500/30";
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-red-500/10 border border-red-500/20">
            <Shield className="w-5 h-5 text-red-400" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-[var(--text-primary)]">
              {isRtl ? "مراقبة إجراءات المساعد (CUA Monitor)" : "CUA Action Monitor"}
            </h2>
            <p className="text-sm text-[var(--text-tertiary)]">
              {isRtl
                ? "مراقبة حية لإجراءات المساعد الذكي وحالات الطوارئ"
                : "Real-time monitoring of AI agent actions and emergency controls"}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <label className="flex items-center gap-2 text-xs text-[var(--text-tertiary)]">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="w-3.5 h-3.5 rounded"
            />
            {isRtl ? "تحديث تلقائي" : "Auto-refresh"}
          </label>
        </div>
      </div>

      {/* Kill Switch Panel */}
      <Card padding="md" className={`border-2 ${killSwitch.active ? "border-red-500" : "border-green-500/50"}`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {killSwitch.active ? (
              <AlertTriangle className="w-8 h-8 text-red-500 animate-pulse" />
            ) : (
              <ShieldOff className="w-8 h-8 text-green-500" />
            )}
            <div>
              <h3 className="text-lg font-bold text-[var(--text-primary)]">
                {isRtl ? "مفتاح الإيقاف الطارئ" : "Emergency Kill Switch"}
              </h3>
              <span className="text-sm">
                {killSwitch.active ? (
                  <Badge variant="danger" size="sm" className="animate-pulse">
                    {isRtl ? "نشط — جميع الإجراءات محظورة" : "ACTIVE — All actions BLOCKED"}
                  </Badge>
                ) : (
                  <Badge variant="success" size="sm">
                    {isRtl ? "غير نشط — الإجراءات مسموحة" : "Inactive — Actions allowed"}
                  </Badge>
                )}
              </span>
              {killSwitch.activated_at && (
                <p className="text-xs text-[var(--text-muted)] mt-1">
                  {isRtl ? "تم التفعيل في:" : "Activated at:"} {killSwitch.activated_at}
                  {killSwitch.reason && ` — ${isRtl ? "السبب:" : "reason:"} ${killSwitch.reason}`}
                </p>
              )}
            </div>
          </div>

          <div className="flex gap-2">
            {!killSwitch.active ? (
              <Button variant="danger" icon={Power} onClick={activateKill}>
                {isRtl ? "تفعيل الطوارئ" : "Kill All"}
              </Button>
            ) : (
              <Button variant="secondary" icon={Power} onClick={deactivateKill}>
                {isRtl ? "إلغاء الطوارئ" : "Resume All"}
              </Button>
            )}
          </div>
        </div>
      </Card>

      {/* Action Log */}
      <Card padding="md">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-blue-400" />
            <h3 className="text-sm font-bold text-[var(--text-primary)]">
              {isRtl ? "سجل الإجراءات" : "Action Audit Log"}
            </h3>
          </div>
          <div className="flex gap-1">
            <Badge variant="default" size="sm">{logs.length} entries</Badge>
          </div>
        </div>

        <div className="overflow-x-auto max-h-[500px] overflow-y-auto">
          <table className="w-full text-xs text-left text-[var(--text-secondary)]">
            <thead className="text-[11px] uppercase tracking-wider text-[var(--text-muted)] border-b border-[var(--border-primary)] sticky top-0 bg-[var(--bg-secondary)]">
              <tr>
                <th className="py-2 px-2">#</th>
                <th className="py-2 px-2">{isRtl ? "النوع" : "Type"}</th>
                <th className="py-2 px-2">{isRtl ? "الوقت" : "Time"}</th>
                <th className="py-2 px-2">{isRtl ? "الإجراء" : "Action"}</th>
                <th className="py-2 px-2">{isRtl ? "المستوى" : "Safety"}</th>
                <th className="py-2 px-2">Hash</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border-primary)]">
              {loading ? (
                <tr><td colSpan={6} className="py-8 text-center text-[var(--text-muted)]">Loading...</td></tr>
              ) : logs.length === 0 ? (
                <tr><td colSpan={6} className="py-8 text-center text-[var(--text-muted)]">
                  {isRtl ? "لا توجد إجراءات مسجلة" : "No actions recorded"}
                </td></tr>
              ) : (
                logs.map((entry) => (
                  <tr key={entry.entry_id} className={`border-l-2 ${getEntryColor(entry)} hover:bg-[var(--bg-elevated)] transition-colors`}>
                    <td className="py-2 px-2 font-mono">{entry.entry_id}</td>
                    <td className="py-2 px-2">
                      <Badge
                        variant={
                          entry.entry_type === "pre_action" ? "warning" :
                          entry.entry_type === "post_action" ? "success" :
                          entry.entry_type === "rollback" ? "danger" : "default"
                        }
                        size="sm"
                      >
                        {entry.entry_type}
                      </Badge>
                    </td>
                    <td className="py-2 px-2 font-mono text-[10px]">{entry.timestamp}</td>
                    <td className="py-2 px-2 font-mono text-[10px] max-w-[200px] truncate">
                      {entry.action}
                    </td>
                    <td className="py-2 px-2">{entry.safety_level || "-"}</td>
                    <td className="py-2 px-2 font-mono text-[9px] text-[var(--text-muted)]">
                      {entry.hash?.slice(0, 12)}...
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
