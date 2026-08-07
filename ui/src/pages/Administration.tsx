<<<<<<< HEAD
import { motion } from "framer-motion";
import {
  Activity,
  Clock,
  Flag,
  Key,
  RefreshCw,
  Shield,
  TrendingUp,
  Users,
  Zap,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import {
  type AgentMeta,
  type FeatureFlag,
  type MetricsResponse,
  fetchAgents,
  fetchFeatureFlags,
  fetchMetrics,
  patchFeatureFlag,
} from "../lib/api";

// Legacy backend metrics format (pre-v2). Kept here so the Administration page
// can render both the old and new /metrics response shapes without breaking.
type LegacyMetrics = {
  requests_total?: number;
  requests_success?: number;
  requests_failed?: number;
  avg_execution_time_ms?: number;
  api?: Record<string, number>;
  perKey?: Record<string, number>;
  providers?: Record<string, { count: number; avgMs: number; failureRate: number }>;
};

type AdminMetrics = MetricsResponse | LegacyMetrics;

import { Badge, Button, Card, CardHeader } from "../components/ui";
import { useNotify } from "../context/NotificationContext";
import { cn } from "../utils/helpers";

import { ContextHelpButton } from "../components/help/ContextHelpButton";
export default function Administration() {
  const [metrics, setMetrics] = useState<AdminMetrics | null>(null);
  const [agents, setAgents] = useState<AgentMeta[]>([]);
  const [featureFlags, setFeatureFlags] = useState<FeatureFlag[]>([]);
  const [flagEnv, setFlagEnv] = useState<string>("");
  const [flagToggling, setFlagToggling] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const { notify } = useNotify();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [m, a, ff] = await Promise.all([
        fetchMetrics().catch(() => null),
        fetchAgents().catch(() => []),
        fetchFeatureFlags().catch(() => ({ success: false, data: [], total: 0, env: "" })),
      ]);
      setMetrics(m);
      setAgents(a);
      if (ff?.success) {
        setFeatureFlags(ff.data);
        setFlagEnv(ff.env);
      }
    } catch {
      notify("error", "Failed to load admin data");
    } finally {
      setLoading(false);
    }
  }, [notify]);

  const toggleFlag = useCallback(
    async (key: string, current: boolean) => {
      setFlagToggling(key);
      try {
        const resp = await patchFeatureFlag(key, !current);
        setFeatureFlags((prev) => prev.map((f) => (f.key === key ? { ...f, ...resp.data } : f)));
        setFlagEnv(resp.data.env);
        const isDev = resp.data.env?.match(/^(dev|test|development)$/);
        notify(
          "success",
          `Flag '${key}' ${resp.data.enabled ? "enabled" : "disabled"}${
            isDev ? " (dev override: effective ON)" : ""
          }`,
        );
      } catch (err) {
        notify(
          "error",
          `Failed to toggle flag '${key}': ${err instanceof Error ? err.message : "Unknown error"}`,
        );
      } finally {
        setFlagToggling(null);
      }
    },
    [notify],
  );

  useEffect(() => {
    load();
  }, [load]);

  // Handle both backend metrics formats gracefully.
  // Cast to LegacyMetrics for the legacy field accesses (api, perKey,
  // requests_success, requests_failed) — these only exist on the old format.
  const legacy = metrics as LegacyMetrics | null;
  const totalCalls =
    metrics?.requests_total ??
    (legacy ? Object.values(legacy.api || {}).reduce((a: number, b: number) => a + b, 0) : 0);
  const activeKeys =
    legacy?.requests_success ?? (legacy ? Object.keys(legacy.perKey || {}).length : 0);
  const errors = legacy?.requests_failed ?? 0;

  const statCards = [
    {
      title: "API Calls",
      value: totalCalls,
      subtitle: `${errors} errors`,
      icon: <Users className="w-4 h-4" />,
      color: "text-brand-400",
      bgColor: "bg-brand-500/10",
    },
    {
      title: "API Keys",
      value: activeKeys || 1,
      subtitle: activeKeys > 0 ? `${activeKeys} active` : "Legacy secret",
      icon: <Key className="w-4 h-4" />,
      color: "text-amber-400",
      bgColor: "bg-amber-500/10",
    },
    {
      title: "Agents",
      value: agents.length,
      subtitle: `${agents.reduce((s, a) => s + (a.capabilities?.length ?? 0), 0)} capabilities`,
      icon: <Shield className="w-4 h-4" />,
      color: "text-green-400",
      bgColor: "bg-green-500/10",
    },
    {
      title: "Uptime",
      value: "99.9%",
      subtitle: "Last 30 days",
      icon: <Clock className="w-4 h-4" />,
      color: "text-[var(--color-engine-voltage)]",
      bgColor: "bg-[var(--color-brand-500)]/10",
    },
  ];

  return (
    <div className="space-y-6">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between"
      >
=======
import { useState, useEffect, useCallback } from 'react'
import { motion } from 'framer-motion'
import { Shield, Users, Key, Activity, Clock, RefreshCw, Zap, TrendingUp } from 'lucide-react'
import { fetchMetrics, fetchAgents, type MetricsResponse, type AgentMeta } from '../lib/api'
import { useNotify } from '../context/NotificationContext'
import { Card, CardHeader, Badge, Button } from '../components/ui'
import { cn } from '../utils/helpers'

export function Administration() {
  const [metrics, setMetrics] = useState<MetricsResponse | null>(null)
  const [agents, setAgents] = useState<AgentMeta[]>([])
  const [loading, setLoading] = useState(true)
  const { notify } = useNotify()

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [m, a] = await Promise.all([
        fetchMetrics().catch(() => null),
        fetchAgents().catch(() => []),
      ])
      setMetrics(m)
      setAgents(a)
    } catch {
      notify('error', 'Failed to load admin data')
    } finally {
      setLoading(false)
    }
  }, [notify])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load()
  }, [load])

  const totalCalls = metrics ? Object.values(metrics.api as Record<string, number>).reduce((a: number, b: number) => a + b, 0) : 0
  const activeKeys = metrics ? Object.keys(metrics.perKey).length : 0
  const errors = (metrics?.api as Record<string, number>)?.errors ?? 0

  const statCards = [
    {
      title: 'API Calls',
      value: totalCalls,
      subtitle: `${errors} errors`,
      icon: <Users className="w-4 h-4" />,
      color: 'text-brand-400',
      bgColor: 'bg-brand-500/10',
    },
    {
      title: 'API Keys',
      value: activeKeys || 1,
      subtitle: activeKeys > 0 ? `${activeKeys} active` : 'Legacy secret',
      icon: <Key className="w-4 h-4" />,
      color: 'text-amber-400',
      bgColor: 'bg-amber-500/10',
    },
    {
      title: 'Agents',
      value: agents.length,
      subtitle: `${agents.reduce((s, a) => s + a.capabilities.length, 0)} capabilities`,
      icon: <Shield className="w-4 h-4" />,
      color: 'text-green-400',
      bgColor: 'bg-green-500/10',
    },
    {
      title: 'Uptime',
      value: '99.9%',
      subtitle: 'Last 30 days',
      icon: <Clock className="w-4 h-4" />,
      color: 'text-[var(--color-engine-voltage)]',
      bgColor: 'bg-[var(--color-brand-500)]/10',
    },
  ]

  return (
    <div className="space-y-6">
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="flex items-center justify-between">
>>>>>>> origin/fix/scenario-tests-properly
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-brand-500/10 border border-brand-500/20">
            <Shield className="w-5 h-5 text-brand-400" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-[var(--text-primary)]">Administration</h2>
<<<<<<< HEAD
            <div className="flex items-center gap-2">
              <p className="text-sm text-[var(--text-tertiary)]">
                Platform monitoring & management
              </p>
              <ContextHelpButton contextId="administration.overview" />
            </div>
=======
            <p className="text-sm text-[var(--text-tertiary)]">Platform monitoring & management</p>
>>>>>>> origin/fix/scenario-tests-properly
          </div>
        </div>
        <Button variant="secondary" size="sm" icon={RefreshCw} loading={loading} onClick={load}>
          Refresh
        </Button>
      </motion.div>

      {/* Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {statCards.map((card, i) => (
<<<<<<< HEAD
          <motion.div
            key={card.title}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.05 * i }}
          >
            <Card padding="md">
              <div className="flex items-center justify-between mb-3">
                <div className={cn("p-2 rounded-lg", card.bgColor, card.color)}>{card.icon}</div>
                <TrendingUp className="w-3.5 h-3.5 text-green-400" />
              </div>
              <p className="text-2xl font-bold text-[var(--text-primary)] mono-engineering">
                {card.value}
              </p>
=======
          <motion.div key={card.title} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 * i }}>
            <Card padding="md">
              <div className="flex items-center justify-between mb-3">
                <div className={cn('p-2 rounded-lg', card.bgColor, card.color)}>
                  {card.icon}
                </div>
                <TrendingUp className="w-3.5 h-3.5 text-green-400" />
              </div>
              <p className="text-2xl font-bold text-[var(--text-primary)] mono-engineering">{card.value}</p>
>>>>>>> origin/fix/scenario-tests-properly
              <p className="text-xs text-[var(--text-muted)] mt-1">{card.subtitle}</p>
              <p className="text-xs text-[var(--text-tertiary)] mt-2 font-medium">{card.title}</p>
            </Card>
          </motion.div>
        ))}
      </div>

      {/* API Metrics & Provider Latency */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* API Metrics */}
        {metrics && (
<<<<<<< HEAD
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
          >
=======
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
>>>>>>> origin/fix/scenario-tests-properly
            <Card padding="md">
              <CardHeader
                title="API Metrics"
                subtitle="Request distribution"
                icon={<Activity className="w-4 h-4" />}
              />
              <div className="grid grid-cols-2 gap-3">
<<<<<<< HEAD
                {/* Render metrics depending on which format we get */}
                {metrics?.requests_total === undefined ? (
                  Object.entries((legacy?.api as Record<string, number>) || {}).map(([k, v]) => (
                    <div
                      key={k}
                      className="p-3 bg-[var(--bg-primary)] rounded-lg border border-[var(--border-primary)]"
                    >
                      <p className="text-xs text-[var(--text-muted)] capitalize">
                        {k.replace(/([A-Z])/g, " $1").trim()}
                      </p>
                      <p className="text-lg font-bold text-[var(--text-primary)] mono-engineering mt-1">
                        {v}
                      </p>
                    </div>
                  ))
                ) : (
                  <>
                    <div className="p-3 bg-[var(--bg-primary)] rounded-lg border border-[var(--border-primary)]">
                      <p className="text-xs text-[var(--text-muted)]">Total Requests</p>
                      <p className="text-lg font-bold text-[var(--text-primary)] mono-engineering mt-1">
                        {metrics.requests_total}
                      </p>
                    </div>
                    <div className="p-3 bg-[var(--bg-primary)] rounded-lg border border-[var(--border-primary)]">
                      <p className="text-xs text-[var(--text-muted)]">Success</p>
                      <p className="text-lg font-bold text-[var(--text-primary)] mono-engineering mt-1">
                        {legacy?.requests_success}
                      </p>
                    </div>
                    <div className="p-3 bg-[var(--bg-primary)] rounded-lg border border-[var(--border-primary)]">
                      <p className="text-xs text-[var(--text-muted)]">Failed</p>
                      <p className="text-lg font-bold text-[var(--text-primary)] mono-engineering mt-1">
                        {legacy?.requests_failed}
                      </p>
                    </div>
                    <div className="p-3 bg-[var(--bg-primary)] rounded-lg border border-[var(--border-primary)]">
                      <p className="text-xs text-[var(--text-muted)]">Avg Execution</p>
                      <p className="text-lg font-bold text-[var(--text-primary)] mono-engineering mt-1">
                        {legacy?.avg_execution_time_ms}ms
                      </p>
                    </div>
                  </>
                )}
=======
                {Object.entries(metrics.api as Record<string, number>).map(([k, v]) => (
                  <div key={k} className="p-3 bg-[var(--bg-primary)] rounded-lg border border-[var(--border-primary)]">
                    <p className="text-xs text-[var(--text-muted)] capitalize">{k.replace(/([A-Z])/g, ' $1').trim()}</p>
                    <p className="text-lg font-bold text-[var(--text-primary)] mono-engineering mt-1">{v}</p>
                  </div>
                ))}
>>>>>>> origin/fix/scenario-tests-properly
              </div>
            </Card>
          </motion.div>
        )}

<<<<<<< HEAD
        {/* Provider Latency / Agent List */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
        >
          <Card padding="md">
            <CardHeader
              title="Provider Latency / Agent Registry"
              subtitle="Response time & agents"
              icon={<Zap className="w-4 h-4" />}
            />
            <div className="space-y-3">
              {metrics?.providers
                ? Object.entries(
                    metrics.providers as Record<
                      string,
                      { count: number; avgMs: number; failureRate: number }
                    >,
                  ).map(([name, p]) => {
                    let latencyColor: string;
                    if (p.avgMs < 500) latencyColor = "bg-green-500";
                    else if (p.avgMs < 1000) latencyColor = "bg-amber-500";
                    else latencyColor = "bg-red-500";
                    const latencyPercent = Math.min(100, (p.avgMs / 2000) * 100);
                    return (
                      <div
                        key={name}
                        className="p-3 bg-[var(--bg-primary)] rounded-lg border border-[var(--border-primary)]"
                      >
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-sm font-medium text-[var(--text-primary)] capitalize">
                            {name}
                          </span>
                          <div className="flex items-center gap-2">
                            <Badge variant={p.failureRate > 0.05 ? "warning" : "success"} size="sm">
                              {(p.failureRate * 100).toFixed(1)}% fail
                            </Badge>
                          </div>
                        </div>
                        <div className="flex items-center gap-3">
                          <div className="flex-1 h-1.5 bg-[var(--bg-elevated)] rounded-full overflow-hidden">
                            <div
                              className={cn("h-full rounded-full transition-all", latencyColor)}
                              style={{ width: `${latencyPercent}%` }}
                            />
                          </div>
                          <span className="text-xs text-[var(--text-muted)] mono-engineering w-16 text-right">
                            {p.avgMs}ms
                          </span>
                        </div>
                        <p className="text-xs text-[var(--text-muted)] mt-1.5">{p.count} calls</p>
                      </div>
                    );
                  })
                : agents.slice(0, 4).map((a) => (
                    <div
                      key={a.id}
                      className="p-3 bg-[var(--bg-primary)] rounded-lg border border-[var(--border-primary)]"
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium text-[var(--text-primary)]">
                          {a.name}
                        </span>
                        <span className="text-xs text-[var(--text-muted)]">
                          {(a.capabilities ?? []).slice(0, 3).join(", ")}
                        </span>
                      </div>
                    </div>
                  ))}
=======
        {/* Provider Latency */}
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}>
          <Card padding="md">
            <CardHeader
              title="Provider Latency"
              subtitle="Response time & failure rates"
              icon={<Zap className="w-4 h-4" />}
            />
            <div className="space-y-3">
              {metrics ? Object.entries(metrics.providers as Record<string, { count: number; avgMs: number; failureRate: number }>).map(([name, p]) => {
                const latencyColor = p.avgMs < 500 ? 'bg-green-500' : p.avgMs < 1000 ? 'bg-amber-500' : 'bg-red-500'
                const latencyPercent = Math.min(100, (p.avgMs / 2000) * 100)
                return (
                  <div key={name} className="p-3 bg-[var(--bg-primary)] rounded-lg border border-[var(--border-primary)]">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium text-[var(--text-primary)] capitalize">{name}</span>
                      <div className="flex items-center gap-2">
                        <Badge variant={p.failureRate > 0.05 ? 'warning' : 'success'} size="sm">
                          {(p.failureRate * 100).toFixed(1)}% fail
                        </Badge>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="flex-1 h-1.5 bg-[var(--bg-elevated)] rounded-full overflow-hidden">
                        <div className={cn('h-full rounded-full transition-all', latencyColor)} style={{ width: `${latencyPercent}%` }} />
                      </div>
                      <span className="text-xs text-[var(--text-muted)] mono-engineering w-16 text-right">{p.avgMs}ms</span>
                    </div>
                    <p className="text-xs text-[var(--text-muted)] mt-1.5">{p.count} calls</p>
                  </div>
                )
              }) : agents.slice(0, 4).map(a => (
                <div key={a.id} className="p-3 bg-[var(--bg-primary)] rounded-lg border border-[var(--border-primary)]">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-[var(--text-primary)]">{a.name}</span>
                    <span className="text-xs text-[var(--text-muted)]">{a.capabilities.slice(0, 3).join(', ')}</span>
                  </div>
                </div>
              ))}
>>>>>>> origin/fix/scenario-tests-properly
            </div>
          </Card>
        </motion.div>
      </div>

      {/* Agent Registry */}
      {agents.length > 0 && (
<<<<<<< HEAD
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
        >
=======
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4 }}>
>>>>>>> origin/fix/scenario-tests-properly
          <Card padding="md">
            <CardHeader
              title="Agent Registry"
              subtitle={`${agents.length} registered agents`}
              icon={<Users className="w-4 h-4" />}
            />
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
<<<<<<< HEAD
              {agents.map((agent) => (
                <div
                  key={agent.id}
                  className="p-3 bg-[var(--bg-primary)] rounded-lg border border-[var(--border-primary)]"
                >
=======
              {agents.map(agent => (
                <div key={agent.id} className="p-3 bg-[var(--bg-primary)] rounded-lg border border-[var(--border-primary)]">
>>>>>>> origin/fix/scenario-tests-properly
                  <div className="flex items-center gap-2.5 mb-2">
                    <div className="p-1.5 rounded-md bg-brand-500/10">
                      <Zap className="w-3.5 h-3.5 text-brand-400" />
                    </div>
                    <div>
                      <p className="text-sm font-medium text-[var(--text-primary)]">{agent.name}</p>
<<<<<<< HEAD
                      {agent.model && (
                        <p className="text-xs text-[var(--text-muted)]">{agent.model}</p>
                      )}
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-1 mt-2">
                    {(agent.capabilities ?? []).slice(0, 3).map((cap) => (
                      <Badge key={cap} variant="neutral" size="sm">
                        {cap}
                      </Badge>
                    ))}
                    {(agent.capabilities?.length ?? 0) > 3 && (
                      <Badge variant="neutral" size="sm">
                        +{(agent.capabilities?.length ?? 0) - 3}
                      </Badge>
=======
                      {agent.model && <p className="text-xs text-[var(--text-muted)]">{agent.model}</p>}
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-1 mt-2">
                    {agent.capabilities.slice(0, 3).map(cap => (
                      <Badge key={cap} variant="neutral" size="sm">{cap}</Badge>
                    ))}
                    {agent.capabilities.length > 3 && (
                      <Badge variant="neutral" size="sm">+{agent.capabilities.length - 3}</Badge>
>>>>>>> origin/fix/scenario-tests-properly
                    )}
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </motion.div>
      )}
<<<<<<< HEAD

      {/* ─── Feature Flags ──────────────────────────────────────────── */}
      {featureFlags.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
        >
          <Card padding="lg">
            <CardHeader
              title="Feature Flags"
              subtitle={`Toggle study-type feature flags${flagEnv ? ` · ENV=${flagEnv}` : ""}`}
              icon={<Flag className="w-4 h-4" />}
              action={
                <Button variant="ghost" size="sm" onClick={load} disabled={loading}>
                  <RefreshCw className={cn("w-3.5 h-3.5", loading && "animate-spin")} />
                  Refresh
                </Button>
              }
            />
            {flagEnv?.match(/^(dev|test|development)$/i) && (
              <div className="mt-2 mb-3 px-3 py-2 rounded-md bg-yellow-500/10 border border-yellow-500/20 text-yellow-300 text-xs">
                ⚠ Dev/test environment detected — all flags are{" "}
                <code>effective_enabled = true</code>
                regardless of the toggled value. Toggle is still persisted for production.
              </div>
            )}
            <div className="space-y-2 mt-3">
              {featureFlags.map((flag) => {
                const isToggling = flagToggling === flag.key;
                const isDevOverride =
                  !!flagEnv && flagEnv.match(/^(dev|test|development)$/i) !== null;
                return (
                  <div
                    key={flag.key}
                    className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3 bg-[var(--bg-elevated)] border border-[var(--border-primary)] rounded-lg hover:border-brand-500/30 transition-all"
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1 flex-wrap">
                        <code className="text-sm font-mono text-[var(--text-primary)]">
                          {flag.key}
                        </code>
                        <Badge variant={flag.status === "alpha" ? "warning" : "neutral"} size="sm">
                          {flag.status}
                        </Badge>
                        {isDevOverride && !flag.enabled && (
                          <Badge variant="success" size="sm">
                            effective: ON
                          </Badge>
                        )}
                      </div>
                      <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                        {flag.description}
                      </p>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <span className="text-xs text-[var(--text-muted)]">
                        {flag.enabled ? "Enabled" : "Disabled"}
                      </span>
                      <button
                        type="button"
                        onClick={() => toggleFlag(flag.key, flag.enabled)}
                        disabled={isToggling}
                        aria-label={`Toggle feature flag ${flag.key}`}
                        className={cn(
                          "relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-brand-500/40 focus:ring-offset-2 focus:ring-offset-[var(--bg-elevated)] disabled:opacity-50 disabled:cursor-not-allowed",
                          flag.enabled ? "bg-brand-500" : "bg-[var(--border-primary)]",
                        )}
                      >
                        <span
                          className={cn(
                            "inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform",
                            flag.enabled ? "translate-x-6" : "translate-x-1",
                          )}
                        />
                        {isToggling && (
                          <span className="absolute inset-0 flex items-center justify-center">
                            <RefreshCw className="w-3 h-3 animate-spin text-white" />
                          </span>
                        )}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
            <div className="mt-3 pt-3 border-t border-[var(--border-primary)]">
              <p className="text-[11px] text-[var(--text-muted)]">
                Source: <code>GET /api/v1/feature-flags</code> · Toggles via{" "}
                <code>PATCH /api/v1/feature-flags/{"{key}"}</code> (admin-only) · Persisted to{" "}
                <code>.feature-flags.json</code> · Audit logged
              </p>
            </div>
          </Card>
        </motion.div>
      )}
    </div>
  );
=======
    </div>
  )
>>>>>>> origin/fix/scenario-tests-properly
}
