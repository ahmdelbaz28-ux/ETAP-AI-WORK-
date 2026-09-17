import { motion } from "framer-motion";
import { AlertCircle, Calendar, Download, FileText, Table } from "lucide-react";
import { useEffect, useState } from "react";
import { ContextHelpButton } from "../components/help/ContextHelpButton";
import { Badge, Button, Card } from "../components/ui";
import { useNotify } from "../context/NotificationContext";
import { API_BASE_URL } from "../lib/api-config";
import { getAuthToken, getCsrfToken } from "../lib/tokenStorage";

interface Report {
  id?: string;
  name: string;
  type: string;
  format: string;
  date: string;
  status: string;
  download_url?: string;
  project_id?: string;
}

const formatIcons: Record<string, React.ReactNode> = {
  PDF: <FileText className="w-4 h-4 text-red-400" />,
  XLSX: <Table className="w-4 h-4 text-green-400" />,
  CSV: <Table className="w-4 h-4 text-amber-400" />,
};

export default function Reports() {
  const { notify } = useNotify();
  const [reports, setReports] = useState<Report[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);

  const fetchReports = () => {
    setLoading(true);
    const token = getAuthToken();
    fetch(`${API_BASE_URL}/api/v1/reports`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then((r) => {
        if (!r.ok) {
          throw new Error(`API ${r.status}: ${r.statusText}`);
        }
        return r.json();
      })
      .then((data: Report[]) => {
        setReports(Array.isArray(data) ? data : []);
        setError(null);
      })
      .catch((err) => {
        console.error("Failed to load reports:", err);
        setError(err.message);
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchReports();
  }, []);

  const handleDownload = async (report: Report) => {
    const itemKey = report.id || `${report.name}-${report.format}`;
    setDownloadingId(itemKey);
    try {
      notify("info", `Downloading ${report.name}...`);
      const token = getAuthToken();
      const headers: Record<string, string> = {};
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const targetPath = report.download_url
        ? (report.download_url.startsWith("http") ? report.download_url : `${API_BASE_URL}${report.download_url}`)
        : `${API_BASE_URL}/api/v1/export/${report.project_id || "ieee-9bus-wscc"}/${(report.format || "pdf").toLowerCase()}`;

      const res = await fetch(targetPath, { headers });
      if (!res.ok) {
        const errDetail = await res.text().catch(() => res.statusText);
        throw new Error(`Server returned ${res.status}: ${errDetail}`);
      }

      const blob = await res.blob();
      const blobUrl = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = blobUrl;
      // P2.1 — Correct extension by actual format (not just xlsx vs pdf).
      const fmt = (report.format || "pdf").toLowerCase();
      const ext =
        fmt === "xlsx" || fmt === "excel" ? "xlsx"
        : fmt === "csv" ? "csv"
        : fmt === "json" ? "json"
        : "pdf";
      const cleanName = report.name.replace(/[^a-zA-Z0-9_\- ]/g, "").replace(/\s+/g, "_").toLowerCase();
      a.download = `${cleanName}.${ext}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(blobUrl);

      notify("success", `Downloaded ${report.name} successfully`);
    } catch (err: any) {
      console.error("Download failed:", err);
      notify("error", `Failed to download: ${err.message || "Network error"}`);
    } finally {
      setDownloadingId(null);
    }
  };

  const handleGenerateCertifiedReport = async () => {
    setGenerating(true);
    try {
      notify("info", "Generating IEEE 9-Bus Certified PE Report...");
      // P2.2 — Include X-CSRF-Token on state-changing (POST) generate request.
      const token = getAuthToken();
      const csrfToken = getCsrfToken();
      const headers: Record<string, string> = {};
      if (token) headers["Authorization"] = `Bearer ${token}`;
      if (csrfToken) headers["X-CSRF-Token"] = csrfToken;

      const res = await fetch(`${API_BASE_URL}/api/v1/export/ieee-9bus-wscc/pdf`, { headers });
      if (!res.ok) {
        throw new Error(`Failed to generate: HTTP ${res.status}`);
      }

      const blob = await res.blob();
      const blobUrl = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = blobUrl;
      a.download = "ieee_9bus_wscc_certified_pe_report.pdf";
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(blobUrl);

      notify("success", "IEEE 9-Bus Certified PE Report generated & downloaded!");
      fetchReports();
    } catch (err: any) {
      notify("error", `Generation failed: ${err.message}`);
    } finally {
      setGenerating(false);
    }
  };

  const safeReports = Array.isArray(reports) ? reports : [];
  const generatedCount = safeReports.filter((r) => r.status === "generated").length;
  const pendingCount = safeReports.filter((r) => r.status === "pending").length;

  return (
    <div className="space-y-6">
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-brand-500/10 border border-brand-500/20">
              <FileText className="w-5 h-5 text-brand-400" />
            </div>
            <div>
              <h2 className="text-2xl font-bold text-[var(--text-primary)]">Reports</h2>
              <div className="flex items-center gap-2">
                <p className="text-sm text-[var(--text-tertiary)]">
                  {generatedCount} generated · {pendingCount} pending
                </p>
                <ContextHelpButton contextId="reports.generate" />
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="primary"
              size="sm"
              icon={FileText}
              loading={generating}
              onClick={handleGenerateCertifiedReport}
            >
              Generate Certified PE Report (IEEE 9-Bus)
            </Button>
          </div>
        </div>
      </motion.div>

      {/* Reports Table */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
      >
        {loading && ( // NOSONAR - S3358: previously nested ternary, refactored to && chain
          <div className="flex items-center justify-center h-32">
            <div className="w-6 h-6 border-2 border-[var(--accent-primary)] border-t-transparent rounded-full animate-spin" />
          </div>
        )}
        {error &&
          !loading && ( // NOSONAR - S3358: previously nested ternary, refactored to && chain
            <Card>
              <div className="flex items-center gap-3 p-4 text-sm text-[var(--text-tertiary)]">
                <AlertCircle className="w-5 h-5 text-red-400" />
                <span>Failed to load reports: {error}</span>
              </div>
            </Card>
          )}
        {!loading && !error && safeReports.length === 0 && (
          <Card>
            <div className="flex flex-col items-center gap-2 py-8 text-sm text-[var(--text-tertiary)]">
              <FileText className="w-8 h-8 text-[var(--text-muted)]" />
              <p>No reports generated yet.</p>
              <p className="text-xs text-[var(--text-muted)]">Run a study to generate a report.</p>
            </div>
          </Card>
        )}
        {!loading && !error && safeReports.length > 0 && (
          <Card padding="none">
            {/* Table Header */}
            <div className="grid grid-cols-12 gap-4 px-5 py-3 border-b border-[var(--border-primary)] bg-[var(--bg-elevated)]">
              <div className="col-span-4 text-xs font-medium text-[var(--text-muted)] uppercase tracking-wider">
                Report
              </div>
              <div className="col-span-2 text-xs font-medium text-[var(--text-muted)] uppercase tracking-wider">
                Type
              </div>
              <div className="col-span-1 text-xs font-medium text-[var(--text-muted)] uppercase tracking-wider">
                Format
              </div>
              <div className="col-span-2 text-xs font-medium text-[var(--text-muted)] uppercase tracking-wider">
                Date
              </div>
              <div className="col-span-2 text-xs font-medium text-[var(--text-muted)] uppercase tracking-wider">
                Status
              </div>
              <div className="col-span-1 text-xs font-medium text-[var(--text-muted)] uppercase tracking-wider" />
            </div>

            {/* Table Rows */}
            {safeReports.map((report, i) => (
              <motion.div
                key={`${report.name}-${report.date}-${report.format}`}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.05 * i }}
                className="grid grid-cols-12 gap-4 px-5 py-3 border-b border-[var(--border-primary)] last:border-0 hover:bg-[var(--bg-elevated)]/50 transition-colors items-center"
              >
                <div className="col-span-4">
                  <p className="text-sm font-medium text-[var(--text-primary)]">{report.name}</p>
                </div>
                <div className="col-span-2">
                  <Badge variant="brand" size="sm">
                    {report.type}
                  </Badge>
                </div>
                <div className="col-span-1">
                  <div className="flex items-center gap-1.5">
                    {formatIcons[report.format] || (
                      <FileText className="w-4 h-4 text-[var(--text-muted)]" />
                    )}
                    <span className="text-xs text-[var(--text-muted)]">{report.format}</span>
                  </div>
                </div>
                <div className="col-span-2">
                  <div className="flex items-center gap-1.5 text-xs text-[var(--text-tertiary)]">
                    <Calendar className="w-3 h-3" />
                    {report.date}
                  </div>
                </div>
                <div className="col-span-2">
                  <Badge
                    variant={report.status === "generated" ? "success" : "warning"}
                    dot
                    size="sm"
                  >
                    {report.status}
                  </Badge>
                </div>
                <div className="col-span-1 flex justify-end">
                  <Button
                    variant="ghost"
                    size="icon"
                    icon={Download}
                    loading={downloadingId === (report.id || `${report.name}-${report.format}`)}
                    onClick={() => handleDownload(report)}
                    className="text-[var(--text-tertiary)] hover:text-[var(--text-primary)]"
                    title={`Download ${report.name}`}
                  />
                </div>
              </motion.div>
            ))}
          </Card>
        )}
      </motion.div>
    </div>
  );
}
