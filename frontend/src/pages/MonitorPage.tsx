/**
 * MonitorPage.tsx — System Monitor (REAL API)
 *
 * V8.1: Connected to REAL backend endpoints:
 *   GET /api/v1/monitor/health        — system health + engine count + alerts
 *   GET /api/v1/monitor/engine-status  — per-engine CPU/memory/uptime
 *   GET /api/v1/monitor/alerts         — active alerts + monitoring rules
 *   GET /api/v1/monitor/agent-activity — agent activity log
 *
 * No hardcoded data — all values from live API responses.
 */
import { Activity, AlertTriangle, CheckCircle2, Cpu, Loader2, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import { getApiKey } from "@/services/apiKey";

interface MonitorHealth {
	success: boolean;
	data: {
		status: string;
		uptime_seconds: number;
		uptime_human: string;
		version: string;
		timestamp: string;
		database: string;
		engines: {
			total: number;
			running: number;
			degraded: number;
			stopped: number;
			error: number;
		};
		engine_statuses: Record<string, string>;
		active_alerts: number;
		agent_activity_count: number;
		security_alert_count: number;
	};
}

interface EngineStatus {
	success: boolean;
	data: {
		engines: Array<{
			engine_id: string;
			name: string;
			status: string;
			cpu_percent: number;
			memory_mb: number;
			uptime_seconds: number;
			last_heartbeat: number;
			version: string;
			checks_passed: number;
			checks_failed: number;
		}>;
		total: number;
		timestamp: string;
	};
}

interface MonitorAlerts {
	success: boolean;
	data: {
		active_alerts: Array<{
			rule_id: string;
			name: string;
			severity: string;
			timestamp: string;
			message: string;
		}>;
		alert_count: number;
		rules: Array<{
			rule_id: string;
			name: string;
			severity: string;
			condition: string;
			enabled: boolean;
			last_evaluated: string | null;
			last_triggered: string | null;
		}>;
		rule_count: number;
		timestamp: string;
	};
}

const API_BASE = "/api/v1";

async function apiCall<T>(path: string): Promise<T> {
	const headers: Record<string, string> = {};
	const apiKey = getApiKey();
	if (apiKey) headers["X-API-Key"] = apiKey;
	const resp = await fetch(`${API_BASE}${path}`, { headers });
	if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
	return resp.json();
}

export function MonitorPage() {
	const [health, setHealth] = useState<MonitorHealth | null>(null);
	const [engines, setEngines] = useState<EngineStatus | null>(null);
	const [alerts, setAlerts] = useState<MonitorAlerts | null>(null);
	const [loading, setLoading] = useState(true);

	const fetchAll = useCallback(async () => {
		setLoading(true);
		try {
			const [h, e, a] = await Promise.all([
				apiCall<MonitorHealth>("/monitor/health"),
				apiCall<EngineStatus>("/monitor/engine-status"),
				apiCall<MonitorAlerts>("/monitor/alerts"),
			]);
			setHealth(h);
			setEngines(e);
			setAlerts(a);
		} catch (err) {
			toast.error(`Failed to load monitor data: ${err instanceof Error ? err.message : "Unknown"}`);
		} finally {
			setLoading(false);
		}
	}, []);

	useEffect(() => {
		fetchAll();
	}, [fetchAll]);

	const statusColor = (status: string) => {
		if (status === "running" || status === "ok") return "text-[#22C55E]";
		if (status === "degraded") return "text-[#F59E0B]";
		return "text-[#E84040]";
	};

	const severityBadge = (sev: string) => {
		if (sev === "critical") return "bg-[#E84040]/10 text-[#E84040]";
		if (sev === "warning") return "bg-[#F59E0B]/10 text-[#F59E0B]";
		return "bg-[#38BDF8]/10 text-[#38BDF8]";
	};

	return (
		<div className="flex-1 overflow-auto p-6">
			<div className="max-w-7xl mx-auto space-y-6">
				<div className="flex items-center justify-between">
					<div>
						<h1 className="text-2xl font-bold text-white">System Monitor</h1>
						<p className="text-sm text-slate-400 mt-1">
							Real-time engine health · Live API · v{health?.data.version ?? "—"}
						</p>
					</div>
					<Button
						variant="outline"
						onClick={fetchAll}
						disabled={loading}
						className="bg-[#1E293B] border-[#334155] text-white hover:bg-[#334155]"
					>
						{loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
					</Button>
				</div>

				{loading ? (
					<div className="flex items-center justify-center py-12">
						<Loader2 className="h-8 w-8 animate-spin text-[#E84040]" />
					</div>
				) : (
					<>
						{/* Health stats — REAL data */}
						<div className="grid grid-cols-4 gap-4">
							<Card className="bg-[#1E293B] border-[#334155]">
								<CardContent className="pt-4">
									<div className="flex items-center gap-3">
										<CheckCircle2 className={`h-8 w-8 ${statusColor(health?.data.status ?? "")}`} />
										<div>
											<p className="text-sm text-slate-400">System Status</p>
											<p className={`text-lg font-bold ${statusColor(health?.data.status ?? "")}`}>
												{health?.data.status?.toUpperCase() ?? "—"}
											</p>
										</div>
									</div>
								</CardContent>
							</Card>

							<Card className="bg-[#1E293B] border-[#334155]">
								<CardContent className="pt-4">
									<p className="text-sm text-slate-400">Engines</p>
									<p className="text-2xl font-bold text-white">
										{health?.data.engines.running ?? 0}/{health?.data.engines.total ?? 0}
									</p>
									<p className="text-xs text-slate-500">running</p>
								</CardContent>
							</Card>

							<Card className="bg-[#1E293B] border-[#334155]">
								<CardContent className="pt-4">
									<p className="text-sm text-slate-400">Active Alerts</p>
									<p className="text-2xl font-bold text-[#E84040]">
										{health?.data.active_alerts ?? 0}
									</p>
								</CardContent>
							</Card>

							<Card className="bg-[#1E293B] border-[#334155]">
								<CardContent className="pt-4">
									<p className="text-sm text-slate-400">Uptime</p>
									<p className="text-lg font-bold text-white font-mono">
										{health?.data.uptime_human ?? "—"}
									</p>
								</CardContent>
							</Card>
						</div>

						{/* Engine status — REAL data */}
						<Card className="bg-[#1E293B] border-[#334155]">
							<CardHeader>
								<CardTitle className="text-white flex items-center gap-2">
									<Cpu className="h-5 w-5 text-[#38BDF8]" />
									Engine Status ({engines?.data.total ?? 0})
								</CardTitle>
								<CardDescription>
									Real-time CPU, memory, and heartbeat per engine
								</CardDescription>
							</CardHeader>
							<CardContent>
								<div className="overflow-x-auto">
									<table className="w-full text-sm">
										<thead>
											<tr className="text-slate-400 text-xs uppercase border-b border-[#334155]">
												<th className="text-left py-2 px-2">Engine</th>
												<th className="text-left px-2">Status</th>
												<th className="text-right px-2">CPU %</th>
												<th className="text-right px-2">Memory (MB)</th>
												<th className="text-right px-2">Checks Passed</th>
												<th className="text-right px-2">Version</th>
											</tr>
										</thead>
										<tbody>
											{engines?.data.engines.map((engine) => (
												<tr key={engine.engine_id} className="border-b border-[#334155]/50">
													<td className="py-2 px-2">
														<p className="text-white font-medium">{engine.name}</p>
														<p className="text-xs text-slate-500 font-mono">{engine.engine_id}</p>
													</td>
													<td className="px-2">
														<span className={`text-xs font-medium ${statusColor(engine.status)}`}>
															● {engine.status}
														</span>
													</td>
													<td className="px-2 text-right text-slate-300 font-mono">
														{engine.cpu_percent.toFixed(1)}%
													</td>
													<td className="px-2 text-right text-slate-300 font-mono">
														{engine.memory_mb.toFixed(1)}
													</td>
													<td className="px-2 text-right text-[#22C55E] font-mono">
														{engine.checks_passed}
													</td>
													<td className="px-2 text-right text-slate-400 font-mono text-xs">
														v{engine.version}
													</td>
												</tr>
											))}
										</tbody>
									</table>
								</div>
							</CardContent>
						</Card>

						{/* Active alerts — REAL data */}
						{alerts && alerts.data.active_alerts.length > 0 && (
							<Card className="bg-[#1E293B] border-[#334155]">
								<CardHeader>
									<CardTitle className="text-white flex items-center gap-2">
										<AlertTriangle className="h-5 w-5 text-[#E84040]" />
										Active Alerts ({alerts.data.alert_count})
									</CardTitle>
								</CardHeader>
								<CardContent>
									<div className="space-y-2">
										{alerts.data.active_alerts.map((alert, i) => (
											<div
												key={i}
												className="flex items-center gap-3 p-3 bg-[#0F172A] rounded-md border border-[#334155]"
											>
												<Badge className={severityBadge(alert.severity)}>
													{alert.severity.toUpperCase()}
												</Badge>
												<div className="flex-1">
													<p className="text-sm text-white font-medium">{alert.name}</p>
													<p className="text-xs text-slate-400">{alert.message}</p>
												</div>
												<span className="text-xs text-slate-500 font-mono">
													{new Date(alert.timestamp).toLocaleTimeString()}
												</span>
											</div>
										))}
									</div>
								</CardContent>
							</Card>
						)}

						{/* Monitor rules — REAL data */}
						<Card className="bg-[#1E293B] border-[#334155]">
							<CardHeader>
								<CardTitle className="text-white flex items-center gap-2">
									<Activity className="h-5 w-5 text-[#38BDF8]" />
									Monitoring Rules ({alerts?.data.rule_count ?? 0})
								</CardTitle>
							</CardHeader>
							<CardContent>
								<div className="overflow-x-auto">
									<table className="w-full text-sm">
										<thead>
											<tr className="text-slate-400 text-xs uppercase border-b border-[#334155]">
												<th className="text-left py-2 px-2">Rule</th>
												<th className="text-left px-2">Severity</th>
												<th className="text-left px-2">Condition</th>
												<th className="text-left px-2">Last Triggered</th>
												<th className="text-left px-2">Status</th>
											</tr>
										</thead>
										<tbody>
											{alerts?.data.rules.map((rule) => (
												<tr key={rule.rule_id} className="border-b border-[#334155]/50">
													<td className="py-2 px-2 text-white">{rule.name}</td>
													<td className="px-2">
														<Badge className={severityBadge(rule.severity)}>
															{rule.severity}
														</Badge>
													</td>
													<td className="px-2 text-slate-300 font-mono text-xs">{rule.condition}</td>
													<td className="px-2 text-slate-500 text-xs">
														{rule.last_triggered
															? new Date(rule.last_triggered).toLocaleTimeString()
															: "Never"}
													</td>
													<td className="px-2">
														{rule.enabled ? (
															<span className="text-[#22C55E] text-xs">● Active</span>
														) : (
															<span className="text-slate-500 text-xs">○ Disabled</span>
														)}
													</td>
												</tr>
											))}
										</tbody>
									</table>
								</div>
							</CardContent>
						</Card>
					</>
				)}
			</div>
		</div>
	);
}
