import {
  Activity,
  AlertCircle,
  FileText,
  Flame,
  Gauge,
  Layers,
  Radio,
  ShieldAlert,
  Zap,
} from "lucide-react";
import React, { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { fetchFeatureFlags } from "../../lib/api";
import { useChatStore } from "../../store/chatStore";
import { cn } from "../../utils/helpers";

export interface QuickActionItem {
  id: string;
  labelKey: string;
  defaultLabel: string;
  icon: React.ComponentType<{ className?: string }>;
  command: string;
  flagKey?: string;
  accentClass: string;
}

export const QUICK_ACTIONS: QuickActionItem[] = [
  {
    id: "load_flow",
    labelKey: "chat.quickActions.loadFlow",
    defaultLabel: "Load Flow",
    icon: Zap,
    command: "شغل دراسة سريان الأحمال (Load Flow) على الشبكة الحالية وفقاً لمعيار IEEE 3002.7",
    accentClass: "text-amber-400 hover:border-amber-500/50 hover:bg-amber-500/10",
  },
  {
    id: "short_circuit",
    labelKey: "chat.quickActions.shortCircuit",
    defaultLabel: "Short Circuit",
    icon: Activity,
    command: "احسب تيار القصر ثلاثي الأوجه (Short Circuit IEC 60909) لكافة قضبان التوزيع",
    accentClass: "text-rose-400 hover:border-rose-500/50 hover:bg-rose-500/10",
  },
  {
    id: "arc_flash",
    labelKey: "chat.quickActions.arcFlash",
    defaultLabel: "Arc Flash",
    icon: Flame,
    command: "احسب طاقة الوميض القوسي وحدود الأمان (Arc Flash IEEE 1584) للمشروع",
    accentClass: "text-orange-400 hover:border-orange-500/50 hover:bg-orange-500/10",
  },
  {
    id: "protection_coordination",
    labelKey: "chat.quickActions.coordination",
    defaultLabel: "Coordination",
    icon: ShieldAlert,
    command: "تحقق من التنسيق الزمني وقواطع الحماية ومطابقة المنحنيات (TCC) وفق IEC 60255",
    accentClass: "text-emerald-400 hover:border-emerald-500/50 hover:bg-emerald-500/10",
  },
  {
    id: "motor_starting",
    labelKey: "chat.quickActions.motorStarting",
    defaultLabel: "Motor Starting",
    icon: Gauge,
    command: "حلل هبوط الجهد عند إقلاع المحركات الحثية (Motor Starting IEEE 399)",
    flagKey: "motor_starting",
    accentClass: "text-cyan-400 hover:border-cyan-500/50 hover:bg-cyan-500/10",
  },
  {
    id: "harmonic",
    labelKey: "chat.quickActions.harmonic",
    defaultLabel: "Harmonics",
    icon: Radio,
    command: "حلل التوافقيات وتشويه الجهد الكلي THD وفق معيار IEEE 519",
    flagKey: "harmonic_analysis",
    accentClass: "text-indigo-400 hover:border-indigo-500/50 hover:bg-indigo-500/10",
  },
  {
    id: "stability",
    labelKey: "chat.quickActions.stability",
    defaultLabel: "Stability",
    icon: Layers,
    command: "افحص الاستقرار العابر والزمن الحرج لفصل الخطأ CCT",
    flagKey: "transient_stability",
    accentClass: "text-purple-400 hover:border-purple-500/50 hover:bg-purple-500/10",
  },
  {
    id: "report",
    labelKey: "chat.quickActions.report",
    defaultLabel: "Report",
    icon: FileText,
    command: "أنشئ تقريراً هندسياً شاملاً ومعتمداً لكافة دراسات ونتائج المشروع",
    accentClass: "text-sky-400 hover:border-sky-500/50 hover:bg-sky-500/10",
  },
];

export function QuickActionsBar() {
  const { t } = useTranslation();
  const projectId = useChatStore((s) => s.projectId);
  const streamStatus = useChatStore((s) => s.streamStatus);
  const sendMessage = useChatStore((s) => s.sendMessage);

  const [disabledFlags, setDisabledFlags] = useState<Set<string>>(new Set());
  const [warningToast, setWarningToast] = useState<string | null>(null);

  const isStreaming = streamStatus === "streaming" || streamStatus === "connecting";

  useEffect(() => {
    let alive = true;
    async function checkFlags() {
      try {
        const res = await fetchFeatureFlags();
        if (!alive || !res?.data) return;
        const disabled = new Set<string>();
        for (const item of res.data) {
          if (!item.effective_enabled) {
            disabled.add(item.key);
          }
        }
        setDisabledFlags(disabled);
      } catch {
        // fail-closed: if feature flags cannot be checked, leave empty or current
      }
    }
    void checkFlags();
    return () => {
      alive = false;
    };
  }, []);

  const handleActionClick = (action: QuickActionItem) => {
    if (isStreaming) return;

    if (!projectId) {
      setWarningToast(
        t("chat.selectProjectFirst", "يرجى اختيار مشروع أولاً لتشغيل هذه الدراسة (Please select a project first)")
      );
      setTimeout(() => setWarningToast(null), 3500);
      return;
    }

    // Sends command through chatStore.sendMessage, flowing through server tool_policy & approval gates
    void sendMessage(action.command);
  };

  return (
    <div className="relative px-4 py-2 border-t border-[#2A3441] bg-[#12161D]/90 backdrop-blur-xs select-none" data-testid="quick-actions-bar">
      {/* Inline Warning Banner if no project selected */}
      {warningToast && (
        <div
          className="absolute -top-10 left-4 right-4 z-40 flex items-center gap-2 px-3 py-1.5 rounded-lg bg-amber-500/20 border border-amber-500/40 text-amber-300 text-xs shadow-lg animate-in fade-in duration-200"
          data-testid="quick-actions-warning"
          role="alert"
        >
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span className="flex-1 font-medium">{warningToast}</span>
        </div>
      )}

      <div className="flex items-center gap-1.5 overflow-x-auto no-scrollbar py-0.5">
        <span className="text-[11px] font-mono text-slate-400 uppercase tracking-wider shrink-0 mr-1 hidden sm:inline">
          {t("chat.quickActions.title", "STUDIES:")}
        </span>

        {QUICK_ACTIONS.map((action) => {
          const Icon = action.icon;
          const isDisabledByFlag = !!action.flagKey && disabledFlags.has(action.flagKey);
          const isDisabled = isDisabledByFlag || isStreaming;

          const tooltip = isDisabledByFlag
            ? t("chat.quickActions.inDevelopment", "قيد التفعيل (In Development)")
            : isStreaming
            ? "Busy"
            : !projectId
            ? t("chat.selectProjectFirst", "Select a project first")
            : action.command;

          return (
            <button
              key={action.id}
              type="button"
              disabled={isDisabled}
              onClick={() => handleActionClick(action)}
              title={tooltip}
              data-testid={`quick-action-${action.id}`}
              className={cn(
                "inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md border text-xs font-medium font-sans whitespace-nowrap transition-all",
                "bg-[#1A202A] border-[#2A3544] text-slate-200",
                !isDisabled && action.accentClass,
                !isDisabled && "cursor-pointer active:scale-95",
                isDisabledByFlag &&
                  "opacity-45 cursor-not-allowed border-dashed border-slate-700 text-slate-500 bg-[#14181F]",
                isStreaming && !isDisabledByFlag && "opacity-60 cursor-not-allowed"
              )}
            >
              <Icon className={cn("w-3.5 h-3.5", isDisabledByFlag ? "text-slate-500" : "shrink-0")} />
              <span>{t(action.labelKey, action.defaultLabel)}</span>
              {isDisabledByFlag && (
                <span className="text-[9px] px-1 py-0.2 rounded bg-slate-800 text-slate-400 font-mono">
                  BETA
                </span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export default QuickActionsBar;
