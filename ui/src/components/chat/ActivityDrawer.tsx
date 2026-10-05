/**
 * ActivityDrawer — session activity / progress via SessionStream events.
 *
 * Only reads events already persisted by chatStore (job_progress, approvals,
 * decisions, results). It never alters the SessionStream protocol or payloads.
 */
import {
  Activity,
  ArrowRight,
  Ban,
  Check,
  CheckCircle2,
  ChevronDown,
  CircleDot,
  HelpCircle,
  Loader2,
  RefreshCw,
  XCircle,
} from "lucide-react";
import { type ComponentType, type SVGProps, useEffect, useState } from "react";
import {
  type ActivityProgress,
  type DecisionEntry,
  useChatStore,
  type WsConnectionStatus,
} from "../../store/chatStore";
import { cn } from "../../utils/helpers";
import { Badge } from "../ui/Badge";
import { Card, CardHeader, CardSection } from "../ui/Card";
import { Progress } from "../ui/Progress";

const WS_META: Record<
  WsConnectionStatus,
  { label: string; variant: "success" | "warning" | "danger" | "info" | "neutral"; icon: ComponentType<SVGProps<SVGSVGElement>> }
> = {
  connecting: { label: "Connecting", variant: "info", icon: CircleDot },
  connected: { label: "Connected", variant: "success", icon: CheckCircle2 },
  reconnecting: { label: "Reconnecting", variant: "warning", icon: RefreshCw },
  disconnected: { label: "Disconnected", variant: "neutral", icon: XCircle },
  completed: { label: "Completed", variant: "success", icon: CheckCircle2 },
  failed: { label: "Failed", variant: "danger", icon: Ban },
};

function getProgressVariant(phase: string): "danger" | "success" | "default" {
  if (phase === "failed") return "danger";
  if (phase === "completed") return "success";
  return "default";
}

function ElapsedTimer({ startTime, isRunning }: { readonly startTime?: number; readonly isRunning: boolean }) {
  const [elapsed, setElapsed] = useState<number>(() => {
    if (!startTime) return 0;
    return Math.max(0, Math.floor((Date.now() - startTime) / 1000));
  });

  useEffect(() => {
    if (!isRunning || !startTime) return;
    const mediaQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    if (mediaQuery.matches) return;

    const interval = setInterval(() => {
      setElapsed(Math.max(0, Math.floor((Date.now() - startTime) / 1000)));
    }, 1000);

    return () => clearInterval(interval);
  }, [startTime, isRunning]);

  if (!startTime) return null;

  const mins = Math.floor(elapsed / 60);
  const secs = elapsed % 60;
  const formatted = mins > 0 ? `${mins}m ${secs.toString().padStart(2, "0")}s` : `${secs}s`;

  return (
    <span className="font-mono text-[10px] text-[var(--text-tertiary)] tabular-nums" data-testid="task-elapsed-timer">
      ⏱ {formatted}
    </span>
  );
}

function TaskRow({ progress: p }: { readonly progress: ActivityProgress }) {
  const [expanded, setExpanded] = useState(false);
  const isInProgress = p.phase !== "completed" && p.phase !== "failed";
  const hasTrace = p.trace && p.trace.length > 0;

  return (
    <div
      className="flex flex-col gap-1.5 p-2.5 rounded-lg bg-[var(--bg-input)] border border-[var(--border-primary)]"
      data-testid={`task-row-${p.execution_id || p.phase}`}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5 min-w-0">
          <span className="text-xs font-semibold text-[var(--text-primary)] truncate">
            {p.tool ? `${p.tool} > ` : ""}{p.phase}
          </span>
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          <ElapsedTimer startTime={p.started_at} isRunning={isInProgress} />
          {isInProgress && (
            <button
              type="button"
              onClick={() => useChatStore.getState().abortStream()}
              className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 border border-rose-500/40 transition-colors cursor-pointer"
              data-testid="stop-active-job"
              title="Stop this running job"
            >
              Stop
            </button>
          )}
        </div>
      </div>

      <Progress
        value={p.pct}
        variant={getProgressVariant(p.phase)}
        size="sm"
        showValue
      />

      <div className="flex items-center justify-between text-[10px] text-[var(--text-tertiary)] pt-0.5">
        <div className="flex items-center gap-1 font-mono">
          {p.tools_count !== undefined && (
            <span className="px-1.5 py-0.2 rounded bg-[var(--bg-card)] border border-[var(--border-primary)]">
              tools: {p.tools_count}
            </span>
          )}
          {p.messages_count !== undefined && (
            <span className="px-1.5 py-0.2 rounded bg-[var(--bg-card)] border border-[var(--border-primary)]">
              messages: {p.messages_count}
            </span>
          )}
        </div>

        {hasTrace && (
          <button
            type="button"
            onClick={() => setExpanded(!expanded)}
            className="flex items-center gap-0.5 text-brand-400 hover:text-brand-300 text-[10px] font-medium cursor-pointer"
            data-testid="toggle-trace-btn"
          >
            <span>{expanded ? "Hide trace" : `View trace (${p.trace!.length})`}</span>
            <ChevronDown className={cn("w-3 h-3 transition-transform duration-200", expanded && "rotate-180")} />
          </button>
        )}
      </div>

      {expanded && hasTrace && (
        <div className="mt-1.5 p-2 rounded bg-[var(--bg-card)] border border-[var(--border-primary)] font-mono text-[10px] text-[var(--text-tertiary)] space-y-1 max-h-36 overflow-y-auto">
          {p.trace!.map((line, idx) => (
            <div key={idx} className="leading-snug truncate">
              <span className="text-[var(--text-muted)] select-none">› </span>
              {line}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function DecisionCard({
  decisions,
}: {
  readonly decisions: readonly DecisionEntry[];
}) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [selectedOption, setSelectedOption] = useState<string | null>(null);
  const [resolved, setResolved] = useState<Record<number, string>>({});

  if (decisions.length === 0) {
    return <p className="text-xs text-[var(--text-tertiary)]">No decision requests yet.</p>;
  }

  const currentDecision = decisions[Math.min(currentIndex, decisions.length - 1)];
  const total = decisions.length;
  const currentStep = Math.min(currentIndex + 1, total);

  const payload = currentDecision.payload;
  const question =
    typeof payload.question === "string"
      ? payload.question
      : typeof payload.request === "string"
      ? payload.request
      : "Engineering configuration decision required";

  const rawOptions = Array.isArray(payload.options) ? (payload.options as string[]) : [];
  const defaultOptions = rawOptions.length > 0 ? rawOptions : ["Accept Recommended Settings", "Modify Convergence Parameters", "Abort Study"];
  const options = defaultOptions.slice(0, 3);

  const isCurrentResolved = resolved[currentDecision.seq] !== undefined;

  const handleSelect = (opt: string) => {
    setSelectedOption(opt);
  };

  const handleContinue = () => {
    if (selectedOption) {
      setResolved((prev) => ({ ...prev, [currentDecision.seq]: selectedOption }));
    }
    if (currentIndex < decisions.length - 1) {
      setCurrentIndex((prev) => prev + 1);
      setSelectedOption(null);
    }
  };

  const handleSkip = () => {
    if (currentIndex < decisions.length - 1) {
      setCurrentIndex((prev) => prev + 1);
      setSelectedOption(null);
    }
  };

  return (
    <div
      className="p-3 rounded-lg bg-[var(--bg-input)] border border-[var(--border-primary)] space-y-2.5 font-sans"
      data-testid="decision-approval-card"
    >
      <div className="flex items-center justify-between text-[11px]">
        <span className="font-semibold text-[var(--text-primary)] flex items-center gap-1.5">
          <HelpCircle className="w-3.5 h-3.5 text-brand-400" />
          Approval Gateway Question
        </span>
        <span className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-[var(--bg-card)] border border-[var(--border-primary)] text-[var(--text-tertiary)]">
          {currentStep} / {total}
        </span>
      </div>

      <p className="text-xs text-[var(--text-primary)] font-medium leading-relaxed">
        {question}
      </p>

      {/* Options */}
      <div className="space-y-1.5">
        {options.map((opt, idx) => {
          const isChosen = (selectedOption === opt) || (resolved[currentDecision.seq] === opt);
          return (
            <button
              key={idx}
              type="button"
              disabled={isCurrentResolved}
              onClick={() => handleSelect(opt)}
              className={cn(
                "w-full flex items-center justify-between px-2.5 py-1.5 rounded-md text-xs text-left transition-all border cursor-pointer",
                isChosen
                  ? "bg-brand-600/20 border-brand-500/50 text-[var(--text-primary)] font-medium shadow-xs"
                  : "bg-[var(--bg-card)] border-[var(--border-primary)] text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]",
                isCurrentResolved && "opacity-60 cursor-not-allowed"
              )}
              data-testid={`decision-option-${idx}`}
            >
              <span>{opt}</span>
              {isChosen && <Check className="w-3.5 h-3.5 text-brand-400 shrink-0" />}
            </button>
          );
        })}
      </div>

      {/* Action footer */}
      <div className="flex items-center justify-between pt-1 border-t border-[var(--border-primary)]">
        <button
          type="button"
          onClick={handleSkip}
          disabled={currentIndex >= decisions.length - 1}
          className="text-[11px] text-[var(--text-tertiary)] hover:text-[var(--text-primary)] disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
          data-testid="decision-skip-btn"
        >
          Skip
        </button>
        <button
          type="button"
          onClick={handleContinue}
          disabled={!selectedOption && !isCurrentResolved}
          className="inline-flex items-center gap-1 px-3 py-1 rounded-md bg-brand-600 hover:bg-brand-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-xs font-semibold shadow-xs transition-colors cursor-pointer"
          data-testid="decision-continue-btn"
        >
          <span>Continue</span>
          <ArrowRight className="w-3 h-3" />
        </button>
      </div>
    </div>
  );
}

export function ActivityDrawer() {
  const wsStatus = useChatStore((s) => s.wsStatus);
  const wsError = useChatStore((s) => s.wsError);
  const activity = useChatStore((s) => s.activity);
  const approvals = useChatStore((s) => s.approvals);
  const decisions = useChatStore((s) => s.decisions);
  const results = useChatStore((s) => s.results);

  const meta = WS_META[wsStatus] ?? WS_META.disconnected;
  const Icon = wsStatus === "connecting" || wsStatus === "reconnecting" ? Loader2 : meta.icon;

  return (
    <div className="flex flex-col gap-3" data-testid="activity-drawer">
      <div className="flex items-center gap-2 px-1">
        <Icon
          className={
            wsStatus === "connecting" || wsStatus === "reconnecting"
              ? "w-4 h-4 animate-spin text-[var(--text-secondary)]"
              : "w-4 h-4 text-[var(--text-secondary)]"
          }
          aria-hidden
        />
        <span className="text-sm font-medium text-[var(--text-secondary)]">Session stream</span>
        <Badge variant={meta.variant} dot className="ml-auto">
          {meta.label}
        </Badge>
      </div>
      {wsError && <p className="text-xs text-amber-400 px-1">{wsError}</p>}

      <Card>
        <CardHeader title="Progress" icon={<Activity className="w-4 h-4" />} />
        <CardSection>
          {activity.length === 0 ? (
            <p className="text-xs text-[var(--text-tertiary)]">No active jobs yet.</p>
          ) : (
            <div className="flex flex-col gap-2.5">
              {activity.map((p) => (
                <TaskRow key={p.execution_id ?? `${p.phase}-${p.ts ?? ""}`} progress={p} />
              ))}
            </div>
          )}
        </CardSection>
      </Card>

      <Card>
        <CardHeader title="Approvals" />
        <CardSection>
          {approvals.length === 0 ? (
            <p className="text-xs text-[var(--text-tertiary)]">No pending approvals.</p>
          ) : (
            <ul className="flex flex-col gap-1.5">
              {approvals.map((a) => (
                <li key={a.id} className="flex items-center gap-2 text-xs">
                  <Badge variant={a.risk_class === "critical" ? "danger" : "warning"} dot>
                    {a.risk_class}
                  </Badge>
                  <span className="text-[var(--text-secondary)] truncate">{a.tool}</span>
                </li>
              ))}
            </ul>
          )}
        </CardSection>
      </Card>

      <Card>
        <CardHeader title="Decisions" />
        <CardSection>
          <DecisionCard decisions={decisions} />
        </CardSection>
      </Card>

      <Card>
        <CardHeader title="Results" />
        <CardSection>
          {results.length === 0 ? (
            <p className="text-xs text-[var(--text-tertiary)]">No results yet.</p>
          ) : (
            <ul className="flex flex-col gap-1.5">
              {results.map((r) => (
                <li key={r.resultId} className="text-xs text-[var(--text-secondary)] truncate">
                  {r.tool ? `${r.tool} · ` : ""}
                  <span className="font-mono">{r.resultId.slice(0, 12)}…</span>
                </li>
              ))}
            </ul>
          )}
        </CardSection>
      </Card>
    </div>
  );
}