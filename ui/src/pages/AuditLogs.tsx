import { Download, Filter, RefreshCw, ScrollText } from "lucide-react";
// NOSONAR(typescript:S3776,typescript:S2004,typescript:S6478,typescript:S6479,typescript:S3358,typescript:S6759,typescript:S6551,typescript:S2486,typescript:S6819): UI components are intentionally complex for feature-rich DX
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Badge,
  Button,
  Card,
  DataTable,
  DatePicker,
  EmptyState,
  Input,
  Select,
} from "../components/ui";
import { useNotify } from "../context/NotificationContext";
import { type AuditEntry, fetchAuditLogs } from "../lib/api";

type StatusFilter = "all" | "2xx" | "4xx" | "5xx";

function matchesSearch(entry: AuditEntry, query: string): boolean {
  if (!query) return true;
  const q = query.toLowerCase();
  return (
    entry.path.toLowerCase().includes(q) ||
    entry.action.toLowerCase().includes(q) ||
    (entry.userId ?? "").toLowerCase().includes(q)
  );
}

function matchesStatus(statusCode: number, filter: StatusFilter): boolean {
  if (filter === "all") return true;
  if (filter === "2xx") return statusCode >= 200 && statusCode < 300;
  if (filter === "4xx") return statusCode >= 400 && statusCode < 500;
  if (filter === "5xx") return statusCode >= 500;
  return true;
}

function matchesDateRange(timestamp: string, from?: string, to?: string): boolean {
  if (from && timestamp < from) return false;
  if (to && timestamp > `${to}T23:59:59`) return false;
  return true;
}

export default function AuditLogs() {
  const [logs, setLogs] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [methodFilter, setMethodFilter] = useState("all");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [showFilters, setShowFilters] = useState(false);
  const { notify } = useNotify();

  const loadLogs = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchAuditLogs();
      setLogs(Array.isArray(data) ? data : []);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadLogs();
  }, [loadLogs]);

  const safeLogs = useMemo(() => (Array.isArray(logs) ? logs : []), [logs]);

  const methods = useMemo(() => {
    const set = new Set(safeLogs.map((l) => l.method));
    return Array.from(set).sort((a, b) => a.localeCompare(b));
  }, [safeLogs]);

  const filtered = useMemo(() => {
    const q = search.trim();
    return safeLogs.filter(
      (entry) =>
        matchesSearch(entry, q) &&
        matchesStatus(entry.statusCode, statusFilter) &&
        (methodFilter === "all" || entry.method === methodFilter) &&
        matchesDateRange(entry.timestamp, dateFrom, dateTo),
    );
  }, [safeLogs, search, statusFilter, methodFilter, dateFrom, dateTo]);

  const columns = useMemo(
    () => [
      {
        key: "timestamp",
        label: "Time",
        render: (row: AuditEntry) => (
          <span className="text-xs mono-engineering text-[var(--text-muted)]">
            {new Date(row.timestamp).toLocaleString()}
          </span>
        ),
      },
      {
        key: "method",
        label: "Method",
        render: (row: AuditEntry) => {
          const variant =
            row.method === "GET"
              ? "info"
              : row.method === "POST"
                ? "success"
                : row.method === "DELETE"
                  ? "danger"
                  : "default";
          return <Badge variant={variant}>{row.method}</Badge>;
        },
      },
      {
        key: "path",
        label: "Path",
        render: (row: AuditEntry) => (
          <code className="text-xs mono-engineering text-[var(--text-secondary)]">{row.path}</code>
        ),
      },
      {
        key: "statusCode",
        label: "Status",
        render: (row: AuditEntry) => {
          const variant =
            row.statusCode < 300 ? "success" : row.statusCode < 500 ? "warning" : "danger";
          return <Badge variant={variant}>{row.statusCode}</Badge>;
        },
      },
      {
        key: "action",
        label: "Action",
        render: (row: AuditEntry) => (
          <span className="text-xs text-[var(--text-secondary)]">{row.action}</span>
        ),
      },
      {
        key: "userId",
        label: "User",
        render: (row: AuditEntry) => (
          <span className="text-xs text-[var(--text-muted)] mono-engineering">
            {row.userId || "system"}
          </span>
        ),
      },
      {
        key: "latencyMs",
        label: "Latency",
        render: (row: AuditEntry) => (
          <span className="text-xs mono-engineering text-[var(--text-muted)]">
            {row.latencyMs ? `${row.latencyMs}ms` : "—"}
          </span>
        ),
      },
    ],
    [],
  );

  const handleExport = useCallback(() => {
    const csv = [
      ["Timestamp", "Method", "Path", "Status", "Action", "User", "Latency"].join(","),
      ...filtered.map((l) =>
        [
          l.timestamp,
          l.method,
          `"${l.path}"`,
          l.statusCode,
          `"${l.action}"`,
          l.userId || "system",
          l.latencyMs ?? "",
        ].join(","),
      ),
    ].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `audit-logs-${new Date().toISOString().split("T")[0]}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    notify("success", `Exported ${filtered.length} entries`);
  }, [filtered, notify]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-[var(--text-primary)]">Audit Logs</h1>
          <p className="text-sm text-[var(--text-muted)] mt-1">
            System activity and request audit trail
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" icon={Filter} onClick={() => setShowFilters((p) => !p)}>
            Filters
          </Button>
          <Button variant="ghost" icon={Download} onClick={handleExport}>
            Export CSV
          </Button>
          <Button variant="ghost" icon={RefreshCw} onClick={loadLogs} loading={loading}>
            Refresh
          </Button>
        </div>
      </div>

      {error && (
        <Card padding="md" className="border-[var(--color-danger)]/30 bg-[var(--color-danger)]/5">
          <p className="text-sm text-[var(--color-danger)]">{error}</p>
          <Button variant="ghost" size="sm" onClick={loadLogs} className="mt-2">
            Retry
          </Button>
        </Card>
      )}

      {/* Filters */}
      {showFilters && (
        <Card padding="md">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            <Input
              label="Search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Path, action, user..."
            />
            <Select
              label="Status"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as StatusFilter)}
              options={[
                { value: "all", label: "All" },
                { value: "2xx", label: "2xx Success" },
                { value: "4xx", label: "4xx Client Error" },
                { value: "5xx", label: "5xx Server Error" },
              ]}
            />
            <Select
              label="Method"
              value={methodFilter}
              onChange={(e) => setMethodFilter(e.target.value)}
              options={[
                { value: "all", label: "All Methods" },
                ...methods.map((m) => ({ value: m, label: m })),
              ]}
            />
            <DatePicker label="From Date" value={dateFrom} onChange={(v) => setDateFrom(v)} />
          </div>
          <div className="mt-3">
            <DatePicker label="To Date" value={dateTo} onChange={(v) => setDateTo(v)} />
          </div>
        </Card>
      )}

      <Card padding="md">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <RefreshCw className="w-6 h-6 animate-spin text-[var(--text-muted)]" />
          </div>
        ) : filtered.length === 0 ? (
          <EmptyState
            icon={<ScrollText className="w-8 h-8" />}
            title="No audit logs"
            description="No log entries match your current filters."
          />
        ) : (
          <DataTable
            data={filtered}
            columns={columns}
            keyExtractor={(l, i) => `${l.timestamp}-${l.method}-${i}`}
            pageSize={20}
          />
        )}
      </Card>
    </div>
  );
}
