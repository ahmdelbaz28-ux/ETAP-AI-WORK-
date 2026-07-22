import { motion } from "framer-motion";
import {
  Activity,
  ArrowRight,
  BarChart3,
  Bot,
  CheckCircle,
  Clock,
  FlaskConical,
  Gauge,
  Server,
  XCircle,
  Zap,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Badge, Card, CardHeader, Sparkline } from "../components/ui";
import { useNotify } from "../context/NotificationContext";
import { type AgentMeta, type HealthResponse, fetchAgents, fetchHealth } from "../lib/api";
import { studyCategories } from "../lib/studyCategories";
import { cn } from "../utils/helpers";

import { ContextHelpButton } from "../components/help/ContextHelpButton";

// Generate deterministic-ish sparkline data for trend visualization
const generateSparklineData = (seed: number, points = 12): number[] => {
  const data: number[] = [];
  let val = 30 + seed;
  for (let i = 0; i < points; i++) {
    val += Math.sin(i * 0.8 + seed) * 8 + (Math.random() - 0.5) * 6;
    data.push(Math.max(5, Math.round(val)));
  }
  return data;
};

// Stable sparkline datasets seeded by card index
const sparklineDatasets = [
  generateSparklineData(10),
  generateSparklineData(25),
  generateSparklineData(40),
  generateSparklineData(55),
];

// Simulated time-series data for charts
const generateTimeSeriesData = () => {
  const data = [];
  const now = Date.now();
  for (let i = 23; i >= 0; i--) {
    data.push({
      time: new Date(now - i * 3600000).toLocaleTimeString("en-US", {
        hour: "2-digit",
        hour12: false,
      }),
      requests: Math.floor(Math.random() * 50) + 10,
      latency: Math.floor(Math.random() * 100) + 20,
    });
  }
  return data;
};

const studyDistributionData = [
  { name: "Load Flow", count: 45, color: "#3b82f6" },
  { name: "Short Circuit", count: 32, color: "#f59e0b" },
  { name: "Arc Flash", count: 28, color: "#ef4444" },
  { name: "Harmonic", count: 18, color: "#8b5cf6" },
  { name: "Protection", count: 15, color: "#06b6d4" },
  { name: "Motor Start", count: 12, color: "#22c55e" },
];

const systemHealthData = [
  { name: "CPU", value: 42, max: 100 },
  { name: "Memory", value: 68, max: 100 },
  { name: "API Queue", value: 12, max: 50 },
  { name: "Cache Hit", value: 89, max: 100 },
];

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.05 },
  },
};

const itemVariants = {
  hidden: { opacity: 0, y: 16 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.35, ease: [0.16, 1, 0.3, 1] },
  },
};

interface StatCardProps {
  icon: React.ElementType;
  label: string;
  value: string | number;
  sublabel?: string;
  color: "green" | "blue" | "amber" | "purple" | "red" | "cyan";
  trend?: string;
  sparklineData?: number[];
  onClick?: () => void;
}

function StatCard({ icon: Icon, label, value, sublabel, color, trend, sparklineData, onClick }: StatCardProps) {
  const colorMap = {
    green: "bg-green-500/10 text-green-400 border-green-500/20",
    blue: "bg-brand-500/10 text-brand-400 border-brand-500/20",
    amber: "bg-amber-500/10 text-amber-400 border-amber-500/20",
    purple: "bg-purple-500/10 text-purple-400 border-purple-500/20",
    red: "bg-red-500/10 text-red-400 border-red-500/20",
    cyan: "bg-cyan-500/10 text-cyan-400 border-cyan-500/20",
  };

  const sparkColorMap = {
    green: "var(--color-success, #22c55e)",
    blue: "var(--color-brand-400, #60a5fa)",
    amber: "var(--color-warning, #f59e0b)",
    purple: "var(--color-engine-impedance, #a78bfa)",
    red: "var(--color-danger, #ef4444)",
    cyan: "var(--color-engine-protection, #06b6d4)",
  };

  const iconBgColors = {
    green: "from-green-500/10 to-green-600/5",
    blue: "from-brand-500/10 to-brand-600/5",
    amber: "from-amber-500/10 to-amber-600/5",
    purple: "from-purple-500/10 to-purple-600/5",
    red: "from-red-500/10 to-red-600/5",
    cyan: "from-cyan-500/10 to-cyan-600/5",
  };

  return (
    <motion.div
      variants={itemVariants}
      onClick={onClick}
      className={cn(
        "stat-accent-line bg-[var(--bg-card)] rounded-xl border border-[var(--border-primary)] overflow-hidden",
        "transition-all duration-200 group relative card-shimmer-hover",
        onClick && "cursor-pointer hover:border-[var(--border-secondary)] hover:shadow-[var(--shadow-md)]",
      )}
    >
      {/* Subtle top accent glow */}
      <div className={cn("absolute top-0 left-0 right-0 h-[2px] opacity-60 bg-gradient-to-r", iconBgColors[color])} />

      <div className="p-5">
        <div className="flex items-start justify-between mb-2">
          <div className={cn("p-2.5 rounded-lg border", colorMap[color])}>
            <Icon className="w-5 h-5" />
          </div>
          <div className="flex items-center gap-2">
            {trend && (
              <span
                className={cn(
                  "text-xs font-medium px-2 py-0.5 rounded-full",
                  trend.startsWith("+")
                    ? "bg-green-500/10 text-green-400"
                    : "bg-red-500/10 text-red-400",
                )}
              >
                {trend}
              </span>
            )}
          </div>
        </div>

        <div>
          <p className="text-2xl font-bold text-[var(--text-primary)] mono-engineering tracking-tight">
            {value}
          </p>
          <p className="text-sm text-[var(--text-tertiary)] mt-0.5">{label}</p>
          {sublabel && (
            <p className="text-xs text-[var(--text-muted)] mt-0.5">{sublabel}</p>
          )}
        </div>

        {/* Sparkline mini-chart */}
        {sparklineData && sparklineData.length > 0 && (
          <div className="mt-3 pt-3 border-t border-[var(--border-primary)]/40">
            <div className="flex items-end justify-between">
              <Sparkline
                data={sparklineData}
                width={80}
                height={24}
                color={sparkColorMap[color]}
                strokeWidth={1.5}
                showArea
              />
              <span className="text-[10px] text-[var(--text-muted)] font-mono">
                {sparklineData[sparklineData.length - 1]}
              </span>
            </div>
          </div>
        )}
      </div>
    </motion.div>
  );
}

// Mini gauge component
function MiniGauge({
  label,
  value,
  max,
  color,
}: { label: string; value: number; max: number; color: string }) {
  const pct = Math.round((value / max) * 100);
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.3 }}
      className="flex flex-col items-center gap-1 p-2 rounded-lg hover:bg-[var(--bg-elevated)]/50 transition-colors"
    >
      <div className="relative w-12 h-12">
        <svg className="w-12 h-12 -rotate-90" viewBox="0 0 36 36">
          <path
            d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
            fill="none"
            stroke="var(--border-primary)"
            strokeWidth="3"
          />
          <path
            d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
            fill="none"
            stroke={color}
            strokeWidth="3"
            strokeDasharray={`${pct}, 100`}
            strokeLinecap="round"
            className="transition-all duration-700"
          />
        </svg>
        <span className="absolute inset-0 flex items-center justify-center text-[10px] font-bold text-[var(--text-primary)] mono-engineering">
          {pct}%
        </span>
      </div>
      <span className="text-[10px] text-[var(--text-muted)] leading-tight">{label}</span>
    </motion.div>
  );
}

function DashboardSkeleton() {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="space-y-6"
    >
      {/* Header skeleton */}
      <div className="flex items-center justify-between">
        <div className="space-y-2">
          <div className="h-8 w-48 skeleton rounded-lg" />
          <div className="h-4 w-72 skeleton rounded" />
        </div>
        <div className="flex gap-2">
          <div className="h-6 w-20 skeleton rounded-full" />
          <div className="h-6 w-16 skeleton rounded-full" />
        </div>
      </div>

      {/* Stat cards skeleton */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="bg-[var(--bg-card)] rounded-xl p-5 space-y-3 border border-[var(--border-primary)]">
            <div className="w-10 h-10 skeleton rounded-lg" />
            <div className="space-y-2">
              <div className="h-8 w-20 skeleton rounded" />
              <div className="h-4 w-32 skeleton rounded" />
              <div className="h-3 w-24 skeleton rounded" />
            </div>
          </div>
        ))}
      </div>

      {/* Charts skeleton */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {[...Array(2)].map((_, i) => (
          <div key={i} className="bg-[var(--bg-card)] rounded-xl p-5 border border-[var(--border-primary)]">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-8 h-8 skeleton rounded-lg" />
              <div className="space-y-1.5">
                <div className="h-4 w-28 skeleton rounded" />
                <div className="h-3 w-20 skeleton rounded" />
              </div>
            </div>
            <div className="h-[220px] skeleton rounded-lg" />
          </div>
        ))}
      </div>
    </motion.div>
  );
}

export default function Dashboard() {
  const { t } = useTranslation();
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [agents, setAgents] = useState<AgentMeta[]>([]);
  const [loading, setLoading] = useState(true);
  const { notify } = useNotify();
  const navigate = useNavigate();

  // Memoize chart data to prevent re-generation on re-renders
  const timeSeriesData = useMemo(generateTimeSeriesData, []);

  useEffect(() => {
    Promise.all([fetchHealth().catch(() => null), fetchAgents().catch(() => [])])
      .then(([h, a]) => {
        setHealth(h);
        setAgents(a);
        setLoading(false);
      })
      .catch(() => {
        notify("error", "Failed to load dashboard data");
        setLoading(false);
      });
  }, [notify]);

  if (loading) return <DashboardSkeleton />;

  const studyCount = agents.reduce((sum, a) => sum + (a.capabilities?.length ?? 0), 0);
  const engStatus = (() => {
    if (!health?.engineeringService?.configured) return "Not Configured";
    return health.engineeringService.healthy ? t("dashboard.healthy") : "Unhealthy";
  })();
  const engSublabel = health?.engineeringService?.latencyMs
    ? `${health.engineeringService.latencyMs}ms`
    : undefined;

  return (
    <motion.div
      variants={containerVariants}
      initial="hidden"
      animate="visible"
      className="space-y-6"
    >
      {/* ─── Page Header ─────────────────────────────────────────────── */}
      <motion.div variants={itemVariants} className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h2 className="text-2xl font-bold text-[var(--text-primary)]">{t("dashboard.title")}</h2>
          <div className="flex items-center gap-2 mt-0.5">
            <p className="text-[var(--text-tertiary)]">{t("dashboard.subtitle")}</p>
            <ContextHelpButton contextId="dashboard.overview" />
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant={health?.ok ? "success" : "danger"} dot>
            {health?.ok ? t("dashboard.online") : t("dashboard.offline")}
          </Badge>
          {health?.version && <Badge variant="neutral">v{health.version}</Badge>}
        </div>
      </motion.div>

      {/* ─── Status Cards with Sparklines ────────────────────────────── */}
      <motion.div
        variants={containerVariants}
        className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4"
      >
        <StatCard
          icon={health?.ok ? CheckCircle : XCircle}
          label={t("dashboard.systemHealth")}
          value={health?.ok ? t("dashboard.online") : t("dashboard.offline")}
          sublabel={health?.version ? `v${health.version}` : undefined}
          color={health?.ok ? "green" : "red"}
          sparklineData={sparklineDatasets[0]}
        />
        <StatCard
          icon={Bot}
          label={t("dashboard.agents")}
          value={agents.length}
          sublabel={`${studyCount} ${t("dashboard.studyCapabilities")}`}
          color="blue"
          trend="+2"
          sparklineData={sparklineDatasets[1]}
          onClick={() => navigate("/assistant")}
        />
        <StatCard
          icon={FlaskConical}
          label={t("dashboard.totalStudies")}
          value={studyCount}
          sublabel={t("dashboard.activeStudies")}
          color="amber"
          sparklineData={sparklineDatasets[2]}
          onClick={() => navigate("/studies")}
        />
        <StatCard
          icon={Server}
          label={t("dashboard.engineeringService")}
          value={engStatus}
          sublabel={engSublabel}
          color={health?.engineeringService?.healthy ? "green" : "purple"}
          sparklineData={sparklineDatasets[3]}
        />
      </motion.div>

      {/* ─── Charts Row ─────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Request Activity Chart */}
        <motion.div variants={itemVariants}>
          <Card padding="md">
            <CardHeader
              title="API Activity"
              subtitle="Last 24 hours"
              icon={<Activity className="w-4 h-4" />}
              action={
                <div className="flex items-center gap-3 text-xs text-[var(--text-muted)]">
                  <span className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-brand-500" /> Requests
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-amber-500" /> Latency
                  </span>
                </div>
              }
            />
            <ResponsiveContainer width="100%" height={220}>
              <AreaChart data={timeSeriesData}>
                <defs>
                  <linearGradient id="colorRequests" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="colorLatency" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.2} />
                    <stop offset="95%" stopColor="#f59e0b" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-primary)" />
                <XAxis dataKey="time" stroke="var(--text-muted)" tick={{ fontSize: 10 }} />
                <YAxis stroke="var(--text-muted)" tick={{ fontSize: 10 }} />
                <Tooltip
                  contentStyle={{
                    background: "var(--bg-card)",
                    border: "1px solid var(--border-primary)",
                    borderRadius: "8px",
                    fontSize: "12px",
                    color: "var(--text-primary)",
                  }}
                  labelStyle={{ color: "var(--text-tertiary)" }}
                />
                <Area
                  type="monotone"
                  dataKey="requests"
                  stroke="#3b82f6"
                  fill="url(#colorRequests)"
                  strokeWidth={2}
                />
              </AreaChart>
            </ResponsiveContainer>
          </Card>
        </motion.div>

        {/* Study Distribution Chart */}
        <motion.div variants={itemVariants}>
          <Card padding="md">
            <CardHeader
              title="Study Distribution"
              subtitle="By category"
              icon={<BarChart3 className="w-4 h-4" />}
              action={
                <button
                  onClick={() => navigate("/studies")}
                  className="text-xs text-brand-400 hover:text-brand-300 transition-colors flex items-center gap-1"
                >
                  View All <ArrowRight className="w-3 h-3" />
                </button>
              }
            />
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={studyDistributionData}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-primary)" />
                <XAxis dataKey="name" stroke="var(--text-muted)" tick={{ fontSize: 10 }} />
                <YAxis stroke="var(--text-muted)" tick={{ fontSize: 10 }} />
                <Tooltip
                  contentStyle={{
                    background: "var(--bg-card)",
                    border: "1px solid var(--border-primary)",
                    borderRadius: "8px",
                    fontSize: "12px",
                    color: "var(--text-primary)",
                  }}
                  labelStyle={{ color: "var(--text-tertiary)" }}
                />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                  {studyDistributionData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </Card>
        </motion.div>
      </div>

      {/* ─── System Health Gauges + Quick Studies + Agents ──────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* System Gauges */}
        <motion.div variants={itemVariants}>
          <Card padding="md">
            <CardHeader
              title="System Resources"
              subtitle="Real-time monitoring"
              icon={<Gauge className="w-4 h-4" />}
            />
            <div className="grid grid-cols-2 gap-2">
              {systemHealthData.map((g) => {
                const gaugeColor =
                  g.value > 80 ? "#ef4444" : g.value > 60 ? "#f59e0b" : "#22c55e";
                return (
                  <MiniGauge
                    key={g.name}
                    label={g.name}
                    value={g.value}
                    max={g.max}
                    color={gaugeColor}
                  />
                );
              })}
            </div>
          </Card>
        </motion.div>

        {/* Quick Studies */}
        <motion.div variants={itemVariants}>
          <Card padding="md">
            <CardHeader
              title={t("dashboard.quickActions")}
              icon={<Zap className="w-4 h-4" />}
              action={
                <button
                  onClick={() => navigate("/studies")}
                  className="text-xs text-brand-400 hover:text-brand-300 transition-colors flex items-center gap-1"
                >
                  {t("dashboard.viewAll")} <ArrowRight className="w-3 h-3" />
                </button>
              }
            />
            <div className="grid grid-cols-2 gap-2">
              {studyCategories.slice(0, 6).map((s) => (
                <button
                  key={s.id}
                  onClick={() => navigate(`/studies/${s.id}`)}
                  className="flex items-center gap-2 px-3 py-2.5 text-sm text-left rounded-lg bg-[var(--bg-elevated)] hover:bg-brand-600/20 text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-all group border border-transparent hover:border-brand-500/30"
                >
                  <span className="text-lg shrink-0">{s.icon}</span>
                  <span className="text-xs font-medium leading-tight line-clamp-2">{s.name}</span>
                </button>
              ))}
            </div>
          </Card>
        </motion.div>

        {/* AI Agents */}
        <motion.div variants={itemVariants}>
          <Card padding="md">
            <CardHeader
              title={t("dashboard.agents")}
              icon={<Bot className="w-4 h-4" />}
              action={
                <button
                  onClick={() => navigate("/assistant")}
                  className="text-xs text-brand-400 hover:text-brand-300 transition-colors flex items-center gap-1"
                >
                  {t("dashboard.viewAll")} <ArrowRight className="w-3 h-3" />
                </button>
              }
            />
            <div className="space-y-2 max-h-60 overflow-y-auto pr-1">
              {agents.length > 0 ? (
                agents.map((agent) => (
                  <button
                    key={agent.id}
                    onClick={() => navigate("/assistant")}
                    className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-[var(--bg-elevated)] transition-colors text-left group"
                  >
                    <div className="p-1.5 rounded-md bg-brand-500/10 shrink-0">
                      <Bot className="w-4 h-4 text-brand-400" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm text-[var(--text-primary)] font-medium truncate group-hover:text-brand-400 transition-colors">
                        {agent.name}
                      </p>
                      <p className="text-xs text-[var(--text-muted)] truncate">
                        {(agent.capabilities ?? []).slice(0, 3).join(" \u2022 ")}
                      </p>
                    </div>
                    <Badge variant="brand" size="sm">
                      {agent.provider || "active"}
                    </Badge>
                  </button>
                ))
              ) : (
                <div className="text-center py-6">
                  <Bot className="w-8 h-8 text-[var(--text-muted)] mx-auto mb-2 opacity-50" />
                  <p className="text-sm text-[var(--text-tertiary)]">No agents available</p>
                  <p className="text-xs text-[var(--text-muted)] mt-1">
                    Check API key configuration in Settings
                  </p>
                </div>
              )}
            </div>
          </Card>
        </motion.div>
      </div>

      {/* ─── Engineering Service Status ─────────────────────────────── */}
      {health?.engineeringService && (
        <motion.div variants={itemVariants}>
          <Card padding="md" variant="bordered">
            <CardHeader
              title={t("dashboard.engineeringService")}
              icon={<Server className="w-4 h-4" />}
            />
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-[var(--bg-primary)] rounded-lg p-3 text-center transition-colors hover:bg-[var(--bg-elevated)]/50">
                <p className="text-xs text-[var(--text-muted)] mb-1">{t("dashboard.configured")}</p>
                <span
                  className={cn(
                    "text-sm font-bold",
                    health.engineeringService.configured ? "text-green-400" : "text-red-400",
                  )}
                >
                  {health.engineeringService.configured ? "Yes" : "No"}
                </span>
              </div>
              <div className="bg-[var(--bg-primary)] rounded-lg p-3 text-center transition-colors hover:bg-[var(--bg-elevated)]/50">
                <p className="text-xs text-[var(--text-muted)] mb-1">{t("dashboard.healthy")}</p>
                <span
                  className={cn(
                    "text-sm font-bold",
                    health.engineeringService.healthy ? "text-green-400" : "text-red-400",
                  )}
                >
                  {health.engineeringService.healthy ? "Yes" : "No"}
                </span>
              </div>
              <div className="bg-[var(--bg-primary)] rounded-lg p-3 text-center transition-colors hover:bg-[var(--bg-elevated)]/50">
                <p className="text-xs text-[var(--text-muted)] mb-1">{t("dashboard.latency")}</p>
                <span className="text-sm font-bold text-[var(--text-primary)] mono-engineering">
                  {health.engineeringService.latencyMs ?? "N/A"}ms
                </span>
              </div>
              <div className="bg-[var(--bg-primary)] rounded-lg p-3 text-center transition-colors hover:bg-[var(--bg-elevated)]/50">
                <p className="text-xs text-[var(--text-muted)] mb-1">{t("dashboard.uptime")}</p>
                <span className="text-sm font-bold text-[var(--text-primary)] flex items-center justify-center gap-1 mono-engineering">
                  <Clock className="w-3.5 h-3.5" />
                  {health.uptime ? `${Math.round(health.uptime / 3600)}h` : "N/A"}
                </span>
              </div>
            </div>
          </Card>
        </motion.div>
      )}
    </motion.div>
  );
}
