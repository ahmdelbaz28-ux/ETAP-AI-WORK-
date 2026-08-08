import { motion } from "framer-motion";
import { AlertTriangle, Download, FileText, Filter, RefreshCw, Search, Shield } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Badge, Button, Card, CardHeader } from "../components/ui";
import { ContextHelpButton } from "../components/help/ContextHelpButton";
import { useNotify } from "../context/NotificationContext";
import { API_BASE_URL } from "../lib/api-config";
import { getAuthToken } from "../lib/tokenStorage";
import { cn, formatDate } from "../utils/helpers";

// ─── Types ───────────────────────────────────────────────────────────

type Severity = "info" | "warning" | "error" | "critical";

interface AuditLogEntry {
  id: string;
  timestamp: string;
  user: string;
  action: string;
  resource: string;
  severity: Severity;
  details: string;
  ip_address: string;
}

interface AuditLogResponse {
  entries: AuditLogEntry[];
  total: number;
  page: number;
  page_size: number;
}

const SEVERITY_CONFIG: Record<Severity, { variant: "info" | "warning" | "danger" | "default"; label: string }> = {
  info: { variant: "info", label: "Info" },
  warning: { variant: "warning", label: "Warning" },
  error: { variant: "danger", label: "Error" },
  critical: { variant: "danger", label: "Critical" },
};

const PAGE_SIZE = 20;

// ─── Component ───────────────────────────────────────────────────────

export default function AuditLogViewer() {
  const { notify } = useNotify();
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [searchQuery, setSearchQuery] = useState("");
  const [severityFilter, setSeverityFilter] = useState<Severity | "all">("all");
  const [actionFilter, setActionFilter] = useState("");
  const [userFilter, setUserFilter] = useState("");

  const totalPages = Math.ceil(total / PAGE_SIZE);

  // Fetch audit logs
  const fetchLogs = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const token = getAuthToken();
      const params = new URLSearchParams({
        page: String(page),
        page_size: String(PAGE_SIZE),
      });
      if (severityFilter !== "all") params.set("severity", severityFilter);
      if (actionFilter) params.set("action", actionFilter);
      if (userFilter) params.set("user", userFilter);
      if (searchQuery) params.set("search", searchQuery);

      const r = await fetch(`${API_BASE_URL}/api/v1/security/audit-logs?${params.toString()}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        signal: AbortSignal.timeout(10000),
      });
      if (!r.ok) {
        const text = await r.text().catch(() => "Unknown error");
        throw new Error(`API ${r.status}: ${text.substring(0, 100)}`);
      }
      const data = await r.json();
      const response: AuditLogResponse = {
        entries: Array.isArray(data.entries ?? data)
          ? (data.entries ?? data).map((e: Record<string, unknown>) => ({
              id: String(e.id ?? crypto.randomUUID()),
              timestamp: String(e.timestamp ?? new Date().toISOString()),
              user: String(e.user ?? "—"),
              action: String(e.action ?? "—"),
              resource: String(e.resource ?? "—"),
              severity: (e.severity as Severity) ?? "info",
              details: String(e.details ?? ""),
              ip_address: String(e.ip_address ?? "—"),
            }))
          : [],
        total: Number(data.total ?? (Array.isArray(data) ? data.length : 0)),
        page: Number(data.page ?? page),
        page_size: Number(data.page_size ?? PAGE_SIZE),
      };
      setLogs(response.entries);
      setTotal(response.total);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [page, severityFilter, actionFilter, userFilter, searchQuery]);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  // CSV export
  const handleExportCSV = () => {
    const headers = ["Timestamp", "User", "Action", "Resource", "Severity", "Details", "IP Address"];
    const rows = logs.map((log) => [
      log.timestamp,
      log.user,
      log.action,
      log.resource,
      log.severity,
      `"${log.details.replace(/"/g, '""')}"`,
      log.ip_address,
    ]);

    const csv = [headers.join(","), ...rows.map((r) => r.join(","))].join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `audit-logs-${new Date().toISOString().slice(0, 10)}.csv`;
    link.click();
    URL.revokeObjectURL(url);
    notify("success", "Audit logs exported as CSV");
  };

  // Apply filters
  const applyFilters = () => {
    setPage(1);
    fetchLogs();
  };

  // ─── Loading state ────────────────────────────────────────────────
  if (loading && logs.length === 0 && error === null) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-[var(--accent-primary)] border-t-transparent rounded-full animate-spin" />
          <span className="text-sm text-[var(--text-muted)]">Loading audit logs…</span>
        </div>
      </div>
    );
  }

  // ─── Error state ──────────────────────────────────────────────────
  if (error && logs.length === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center max-w-md">
          <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-3" />
          <p className="text-sm text-[var(--text-secondary)] mb-2">Failed to load audit logs</p>
          <p className="text-xs text-[var(--text-muted)] mb-4 font-mono">{error}</p>
          <Button variant="secondary" size="sm" icon={RefreshCw} onClick={fetchLogs}>
            Retry
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between"
      >
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-brand-500/10 border border-brand-500/20">
            <Shield className="w-5 h-5 text-brand-400" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-[var(--text-primary)]">Audit Logs</h2>
            <div className="flex items-center gap-2">
              <p className="text-sm text-[var(--text-tertiary)]">Security audit trail & compliance records</p>
              <ContextHelpButton contextId="security.audit-logs" />
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" size="sm" icon={Download} onClick={handleExportCSV} disabled={logs.length === 0}>
            Export CSV
          </Button>
          <Button variant="secondary" size="sm" icon={RefreshCw} onClick={fetchLogs} loading={loading}>
            Refresh
          </Button>
        </div>
      </motion.div>

      {/* Filters */}
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
        <Card padding="md">
          <div className="flex flex-wrap items-end gap-4">
            {/* Search */}
            <div className="flex-1 min-w-[200px]">
              <label className="block text-xs font-medium text-[var(--text-tertiary)] mb-1.5">Search</label>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-muted)]" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") applyFilters(); }}
                  placeholder="Search logs..."
                  className="w-full pl-9 pr-3 py-2 rounded-lg bg-[var(--bg-primary)] border border-[var(--border-primary)] text-sm text-[var(--text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
                />
              </div>
            </div>

            {/* Severity filter */}
            <div className="min-w-[140px]">
              <label className="block text-xs font-medium text-[var(--text-tertiary)] mb-1.5">Severity</label>
              <select
                value={severityFilter}
                onChange={(e) => { setSeverityFilter(e.target.value as Severity | "all"); setPage(1); }}
                className="w-full px-3 py-2 rounded-lg bg-[var(--bg-primary)] border border-[var(--border-primary)] text-sm text-[var(--text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
              >
                <option value="all">All Severities</option>
                <option value="info">Info</option>
                <option value="warning">Warning</option>
                <option value="error">Error</option>
                <option value="critical">Critical</option>
              </select>
            </div>

            {/* Action filter */}
            <div className="min-w-[140px]">
              <label className="block text-xs font-medium text-[var(--text-tertiary)] mb-1.5">Action</label>
              <input
                type="text"
                value={actionFilter}
                onChange={(e) => setActionFilter(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") applyFilters(); }}
                placeholder="e.g. login, update"
                className="w-full px-3 py-2 rounded-lg bg-[var(--bg-primary)] border border-[var(--border-primary)] text-sm text-[var(--text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
              />
            </div>

            {/* User filter */}
            <div className="min-w-[140px]">
              <label className="block text-xs font-medium text-[var(--text-tertiary)] mb-1.5">User</label>
              <input
                type="text"
                value={userFilter}
                onChange={(e) => setUserFilter(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") applyFilters(); }}
                placeholder="Username"
                className="w-full px-3 py-2 rounded-lg bg-[var(--bg-primary)] border border-[var(--border-primary)] text-sm text-[var(--text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
              />
            </div>

            <Button variant="primary" size="sm" icon={Filter} onClick={applyFilters}>
              Filter
            </Button>
          </div>
        </Card>
      </motion.div>

      {/* Log table */}
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
        <Card padding="none">
          <CardHeader
            title="Log Entries"
            subtitle={`${total.toLocaleString()} entries found`}
            icon={<FileText className="w-4 h-4" />}
            action={
              <Badge variant="neutral" size="sm">
                Page {page} of {totalPages || 1}
              </Badge>
            }
          />

          {/* Table */}
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--border-primary)]">
                  <th className="text-left px-4 py-3 text-xs font-medium text-[var(--text-tertiary)] uppercase tracking-wider">
                    Timestamp
                  </th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-[var(--text-tertiary)] uppercase tracking-wider">
                    User
                  </th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-[var(--text-tertiary)] uppercase tracking-wider">
                    Action
                  </th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-[var(--text-tertiary)] uppercase tracking-wider">
                    Resource
                  </th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-[var(--text-tertiary)] uppercase tracking-wider">
                    Severity
                  </th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-[var(--text-tertiary)] uppercase tracking-wider">
                    IP
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-primary)]">
                {logs.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-[var(--text-muted)]">
                      No audit log entries found
                    </td>
                  </tr>
                ) : (
                  logs.map((log) => {
                    const sevConfig = SEVERITY_CONFIG[log.severity] ?? SEVERITY_CONFIG.info;
                    return (
                      <tr
                        key={log.id}
                        className="hover:bg-[var(--bg-elevated)] transition-colors"
                      >
                        <td className="px-4 py-3 text-xs text-[var(--text-muted)] font-mono whitespace-nowrap">
                          {formatDate(log.timestamp)}
                        </td>
                        <td className="px-4 py-3 text-sm text-[var(--text-primary)]">
                          {log.user}
                        </td>
                        <td className="px-4 py-3 text-sm text-[var(--text-secondary)]">
                          {log.action}
                        </td>
                        <td className="px-4 py-3 text-sm text-[var(--text-secondary)] max-w-[200px] truncate">
                          {log.resource}
                        </td>
                        <td className="px-4 py-3">
                          <Badge variant={sevConfig.variant} size="sm" dot>
                            {sevConfig.label}
                          </Badge>
                        </td>
                        <td className="px-4 py-3 text-xs text-[var(--text-muted)] font-mono">
                          {log.ip_address}
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between px-4 py-3 border-t border-[var(--border-primary)]">
              <p className="text-xs text-[var(--text-muted)]">
                Showing {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, total)} of {total.toLocaleString()}
              </p>
              <div className="flex items-center gap-1">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setPage(Math.max(1, page - 1))}
                  disabled={page <= 1}
                >
                  Previous
                </Button>
                {/* Page number buttons */}
                {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                  const startPage = Math.max(1, Math.min(page - 2, totalPages - 4));
                  const pageNum = startPage + i;
                  if (pageNum > totalPages) return null;
                  return (
                    <button
                      key={pageNum}
                      type="button"
                      onClick={() => setPage(pageNum)}
                      className={cn(
                        "w-8 h-8 rounded-lg text-xs font-medium transition-colors",
                        pageNum === page
                          ? "bg-brand-500 text-white"
                          : "text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)]",
                      )}
                    >
                      {pageNum}
                    </button>
                  );
                })}
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setPage(Math.min(totalPages, page + 1))}
                  disabled={page >= totalPages}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </Card>
      </motion.div>
    </div>
  );
}
