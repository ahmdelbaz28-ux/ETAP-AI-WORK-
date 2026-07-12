/**
 * AuditLogPage.tsx — Audit Log & SHA-256 Chain (REAL API)
 *
 * V8.1 Screen 13: Connected to REAL backend endpoints:
 *   GET /api/v1/self-healing/audit  — healing event log + chain integrity
 *   GET /api/v1/qomn/audit          — QOMN computation audit chain
 *   GET /api/v1/monitor/alerts      — active system alerts
 *
 * No hardcoded data — all values come from live API responses.
 */
import { AlertTriangle, CheckCircle2, Download, Loader2, RefreshCw, ShieldCheck } from "lucide-react";
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

interface SelfHealingAudit {
	success: boolean;
	stats: {
		total_events: number;
		failed_writes: number;
		bytes_written: number;
		filepath: string;
		chain_hash: string;
	};
	chain_integrity: {
		chain_valid: boolean;
		error: string | null;
		total_entries: number;
		break_points: string[];
	};
	entries?: Array<{
		timestamp: string;
		event_type: string;
		method: string;
		success: boolean;
		error: string | null;
		previous_hash: string;
		current_hash: string;
	}>;
	limit: number;
}

interface QomnAudit {
	success: boolean;
	chain_valid: boolean;
	data: {
		qomn_version: string;
		chain_hash: string;
		total_entries: number;
		entries: Array<Record<string, unknown>>;
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
	if (!resp.ok) throw new Error(`HTTP ${resp.status}: ${resp.statusText}`);
	return resp.json();
}

export function AuditLogPage() {
	const [shAudit, setShAudit] = useState<SelfHealingAudit | null>(null);
	const [qomnAudit, setQomnAudit] = useState<QomnAudit | null>(null);
	const [alerts, setAlerts] = useState<MonitorAlerts | null>(null);
	const [loading, setLoading] = useState(true);

	const fetchAll = useCallback(async () => {
		setLoading(true);
		try {
			const [sh, qomn, mon] = await Promise.all([
				apiCall<SelfHealingAudit>("/self-healing/audit?limit=20"),
				apiCall<QomnAudit>("/qomn/audit"),
				apiCall<MonitorAlerts>("/monitor/alerts"),
			]);
			setShAudit(sh);
			setQomnAudit(qomn);
			setAlerts(mon);
		} catch (err) {
			toast.error(`Failed to load audit data: ${err instanceof Error ? err.message : "Unknown"}`);
		} finally {
			setLoading(false);
		}
	}, []);

	useEffect(() => {
		fetchAll();
	}, [fetchAll]);

	const severityColor = (sev: string) => {
		if (sev === "critical") return "bg-[#E84040]/10 text-[#E84040]";
		if (sev === "warning") return "bg-[#F59E0B]/10 text-[#F59E0B]";
		return "bg-[#38BDF8]/10 text-[#38BDF8]";
	};

	return (
		<div className="flex-1 overflow-auto p-6">
			<div className="max-w-7xl mx-auto space-y-6">
				<div className="flex items-center justify-between">
					<div>
						<h1 className="text-2xl font-bold text-white">Audit Log</h1>
						<p className="text-sm text-slate-400 mt-1">
							SHA-256 chain verification · Tamper-evident event log · Live API
						</p>
					</div>
					<div className="flex gap-2">
						<Button
							variant="outline"
							onClick={fetchAll}
							disabled={loading}
							className="bg-[#1E293B] border-[#334155] text-white hover:bg-[#334155]"
						>
							{loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
						</Button>
						<Button className="bg-[#E84040] hover:bg-[#B91C1C] text-white">
							<Download className="h-4 w-4 mr-2" />
							Export Audit Chain
						</Button>
					</div>
				</div>

				{loading ? (
					<div className="flex items-center justify-center py-12">
						<Loader2 className="h-8 w-8 animate-spin text-[#E84040]" />
					</div>
				) : (
					<>
						{/* Chain Integrity Status — REAL data */}
						<div className="grid grid-cols-3 gap-4">
							<Card className="bg-[#1E293B] border-[#334155]">
								<CardContent className="pt-4">
									<div className="flex items-center gap-3">
										{shAudit?.chain_integrity.chain_valid ? (
											<CheckCircle2 className="h-8 w-8 text-[#22C55E]" />
										) : (
											<AlertTriangle className="h-8 w-8 text-[#F59E0B]" />
										)}
										<div>
											<p className="text-white font-semibold text-sm">
												Self-Healing Chain
											</p>
											<p className="text-xs text-slate-400">
												{shAudit?.chain_integrity.chain_valid
													? `VERIFIED ✓ · ${shAudit.chain_integrity.total_entries} entries`
													: shAudit?.chain_integrity.error || "Not initialized"}
											</p>
										</div>
									</div>
								</CardContent>
							</Card>

							<Card className="bg-[#1E293B] border-[#334155]">
								<CardContent className="pt-4">
									<div className="flex items-center gap-3">
										{qomnAudit?.chain_valid ? (
											<CheckCircle2 className="h-8 w-8 text-[#22C55E]" />
										) : (
											<AlertTriangle className="h-8 w-8 text-[#E84040]" />
										)}
										<div>
											<p className="text-white font-semibold text-sm">
												QOMN Audit Chain
											</p>
											<p className="text-xs text-slate-400">
												{qomnAudit?.chain_valid
													? `VERIFIED ✓ · v${qomnAudit.data.qomn_version} · ${qomnAudit.data.total_entries} entries`
													: "CHAIN BROKEN"}
											</p>
										</div>
									</div>
								</CardContent>
							</Card>

							<Card className="bg-[#1E293B] border-[#334155]">
								<CardContent className="pt-4">
									<div className="flex items-center gap-3">
										<ShieldCheck className="h-8 w-8 text-[#38BDF8]" />
										<div>
											<p className="text-white font-semibold text-sm">
												Monitor Alerts
											</p>
											<p className="text-xs text-slate-400">
												{alerts?.data.alert_count ?? 0} active · {alerts?.data.rule_count ?? 0} rules
											</p>
										</div>
									</div>
								</CardContent>
							</Card>
						</div>

						{/* Active Alerts — REAL data from /monitor/alerts */}
						{alerts && alerts.data.active_alerts.length > 0 && (
							<Card className="bg-[#1E293B] border-[#334155]">
								<CardHeader>
									<CardTitle className="text-white text-base flex items-center gap-2">
										<AlertTriangle className="h-4 w-4 text-[#E84040]" />
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
												<Badge className={severityColor(alert.severity)}>
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

						{/* Self-Healing Audit Entries — REAL data */}
						<Card className="bg-[#1E293B] border-[#334155]">
							<CardHeader>
								<CardTitle className="text-white text-base">
									Self-Healing Event Log
								</CardTitle>
								<CardDescription>
									Source: {shAudit?.stats.filepath || "N/A"} · {shAudit?.stats.total_events ?? 0} total events · {shAudit?.stats.bytes_written ?? 0} bytes
								</CardDescription>
							</CardHeader>
							<CardContent>
								{shAudit?.entries && shAudit.entries.length > 0 ? (
									<div className="overflow-x-auto">
										<table className="w-full text-sm">
											<thead>
												<tr className="text-slate-400 text-xs uppercase border-b border-[#334155]">
													<th className="text-left py-2 px-2">Timestamp</th>
													<th className="text-left px-2">Event</th>
													<th className="text-left px-2">Method</th>
													<th className="text-left px-2">Status</th>
													<th className="text-left px-2">Hash</th>
												</tr>
											</thead>
											<tbody>
												{shAudit.entries.map((entry, i) => (
													<tr key={i} className="border-b border-[#334155]/50">
														<td className="py-2 px-2 text-slate-300 font-mono text-xs">
															{entry.timestamp ? new Date(entry.timestamp).toLocaleString() : "—"}
														</td>
														<td className="px-2 text-white">{entry.event_type}</td>
														<td className="px-2 text-slate-300 font-mono text-xs">{entry.method}</td>
														<td className="px-2">
															{entry.success ? (
																<span className="text-[#22C55E] text-xs">✓ PASS</span>
															) : (
																<span className="text-[#E84040] text-xs">✗ FAIL</span>
															)}
														</td>
														<td className="px-2 text-slate-500 font-mono text-xs">
															{entry.current_hash?.substring(0, 12) ?? "—"}
														</td>
													</tr>
												))}
											</tbody>
										</table>
									</div>
								) : (
									<p className="text-sm text-slate-400 text-center py-6">
														No audit entries yet. Self-healing events will appear here when computation methods encounter errors.
													</p>
								)}
							</CardContent>
						</Card>

						{/* Monitor Rules — REAL data */}
						<Card className="bg-[#1E293B] border-[#334155]">
							<CardHeader>
								<CardTitle className="text-white text-base">
									Monitor Rules ({alerts?.data.rule_count ?? 0})
								</CardTitle>
								<CardDescription>
									Real-time system health monitoring rules
								</CardDescription>
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
														<Badge className={severityColor(rule.severity)}>
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
