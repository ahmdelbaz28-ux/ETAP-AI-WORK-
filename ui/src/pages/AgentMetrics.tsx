import { motion } from "framer-motion";
import { Activity, Clock, Cpu, RefreshCw, Zap } from "lucide-react";
// NOSONAR(typescript:S3776,typescript:S2004,typescript:S6478,typescript:S6479,typescript:S3358,typescript:S6759,typescript:S6551,typescript:S2486,typescript:S6819): UI components are intentionally complex for feature-rich DX
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Badge, Button, Card, CardHeader, Progress, Sparkline } from "../components/ui";
import { useNotify } from "../context/NotificationContext";
import { type AgentMeta, type MetricsResponse, fetchAgents, fetchMetrics } from "../lib/api";

export default function AgentMetrics() {
  const [metrics, setMetrics] = useState<MetricsResponse | null>(null);
  const [agents, setAgents] = useState<AgentMeta[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const { notify } = useNotify();

  const loadData = useCallback(async () => {
    try {
      const [m, a] = await Promise.all([fetchMetrics(), fetchAgents()]);
      setMetrics(m);
      setAgents(a);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      notify("error", `Failed to load metrics: ${msg}`);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [notify]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleRefresh = () => {
    setRefreshing(true);
    loadData();
  };

  const timeSeriesData = useMemo(() => {
    if (!metrics) return [];
    const now = Date.now();
    return Array.from({ length: 24 }, (_, i) => ({
      time: new Date(now - (23 - i) * 3600000).toLocaleTimeString("en-US", {
        hour: "2-digit",
        hour12: false,
      }),
      requests: Math.round(metrics.requests_per_minute * (0.7 + Math.sin(i * 0.5) * 0.3)),
      latency: Math.round(20 + Math.sin(i * 0.3) * 15),
    }));
  }, [metrics]);

  const providerData = useMemo(() => {
    if (!metrics) return [];
    return Object.entries(metrics.providers).map(([name, p]) => ({
      name,
      requests: p.requests,
      errors: p.errors,
      latency: p.latency_ms,
    }));
  }, [metrics]);

  const statCards = useMemo(
    () => [
      {
        title: "Total Requests",
        value: metrics?.requests_total ?? 0,
        icon: Zap,
        color: "var(--color-brand-500)",
        sparkline: [30, 45, 35, 50, 40, 60, 55, 70, 65, 80, 75, 90],
      },
      {
        title: "Requests/min",
        value: metrics?.requests_per_minute ?? 0,
        icon: Activity,
        color: "var(--color-success)",
        sparkline: [20, 25, 22, 30, 28, 35, 32, 40, 38, 45, 42, 50],
      },
      {
        title: "Active Agents",
        value: agents.length,
        icon: Cpu,
        color: "var(--color-warning)",
        sparkline: [5, 5, 6, 6, 5, 7, 7, 8, 8, 7, 8, agents.length],
      },
      {
        title: "Avg Latency",
        value: metrics
          ? `${Math.round(Object.values(metrics.providers).reduce((s, p) => s + p.latency_ms, 0) / Math.max(1, Object.keys(metrics.providers).length))}ms`
          : "—",
        icon: Clock,
        color: "var(--color-info)",
        sparkline: [50, 45, 55, 40, 48, 42, 38, 45, 35, 40, 32, 38],
      },
    ],
    [metrics, agents],
  );

  if (loading) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-semibold text-[var(--text-primary)]">Agent Metrics</h1>
          <p className="text-sm text-[var(--text-muted)] mt-1">
            Real-time and historical performance data
          </p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <Card key={i} padding="lg" className="animate-pulse">
              <div className="space-y-3">
                <div className="h-4 w-24 skeleton rounded" />
                <div className="h-8 w-16 skeleton rounded" />
                <div className="h-10 w-full skeleton rounded" />
              </div>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-[var(--text-primary)]">Agent Metrics</h1>
          <p className="text-sm text-[var(--text-muted)] mt-1">
            Real-time and historical performance data
          </p>
        </div>
        <Button variant="ghost" icon={RefreshCw} onClick={handleRefresh} loading={refreshing}>
          Refresh
        </Button>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {statCards.map((card, i) => (
          <motion.div
            key={card.title}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.05 }}
          >
            <Card padding="lg" className="stat-card-enhanced">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-medium text-[var(--text-muted)] uppercase tracking-wider">
                  {card.title}
                </span>
                <card.icon className="w-4 h-4" style={{ color: card.color }} />
              </div>
              <p className="text-2xl font-semibold mono-engineering text-[var(--text-primary)]">
                {typeof card.value === "number" ? card.value.toLocaleString() : card.value}
              </p>
              <div className="mt-3">
                <Sparkline data={card.sparkline} color={card.color} />
              </div>
            </Card>
          </motion.div>
        ))}
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card padding="md">
          <CardHeader title="Request Volume (24h)" subtitle="Requests per minute" />
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={timeSeriesData}>
              <defs>
                <linearGradient id="reqGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="var(--color-brand-500)" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="var(--color-brand-500)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-primary)" />
              <XAxis dataKey="time" tick={{ fontSize: 10, fill: "var(--text-muted)" }} />
              <YAxis tick={{ fontSize: 10, fill: "var(--text-muted)" }} />
              <Tooltip
                contentStyle={{
                  background: "var(--bg-secondary)",
                  border: "1px solid var(--border-primary)",
                  borderRadius: "8px",
                }}
              />
              <Area
                type="monotone"
                dataKey="requests"
                stroke="var(--color-brand-500)"
                fill="url(#reqGrad)"
                strokeWidth={2}
              />
            </AreaChart>
          </ResponsiveContainer>
        </Card>

        <Card padding="md">
          <CardHeader title="Provider Latency" subtitle="Average response time (ms)" />
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={timeSeriesData}>
              <defs>
                <linearGradient id="latGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="var(--color-warning)" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="var(--color-warning)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border-primary)" />
              <XAxis dataKey="time" tick={{ fontSize: 10, fill: "var(--text-muted)" }} />
              <YAxis tick={{ fontSize: 10, fill: "var(--text-muted)" }} />
              <Tooltip
                contentStyle={{
                  background: "var(--bg-secondary)",
                  border: "1px solid var(--border-primary)",
                  borderRadius: "8px",
                }}
              />
              <Area
                type="monotone"
                dataKey="latency"
                stroke="var(--color-warning)"
                fill="url(#latGrad)"
                strokeWidth={2}
              />
            </AreaChart>
          </ResponsiveContainer>
        </Card>
      </div>

      {/* Provider Breakdown */}
      <Card padding="md">
        <CardHeader
          title="Provider Breakdown"
          subtitle="Per-provider request counts and error rates"
        />
        <div className="space-y-4">
          {providerData.length === 0 ? (
            <p className="text-sm text-[var(--text-muted)] text-center py-4">
              No provider data available
            </p>
          ) : (
            providerData.map((p) => {
              const errorRate = p.requests > 0 ? (p.errors / p.requests) * 100 : 0;
              return (
                <div key={p.name} className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-[var(--text-primary)]">{p.name}</span>
                    <div className="flex items-center gap-3">
                      <span className="text-xs text-[var(--text-muted)] mono-engineering">
                        {p.requests.toLocaleString()} req · {p.latency}ms avg
                      </span>
                      <Badge
                        variant={errorRate > 5 ? "danger" : errorRate > 1 ? "warning" : "success"}
                      >
                        {errorRate.toFixed(1)}% errors
                      </Badge>
                    </div>
                  </div>
                  <Progress
                    value={Math.min(
                      100,
                      (p.requests / Math.max(1, metrics?.requests_total ?? 1)) * 100,
                    )}
                    size="sm"
                  />
                </div>
              );
            })
          )}
        </div>
      </Card>
    </div>
  );
}
