import { motion } from "framer-motion";
import {
  AlertCircle,
  Clock,
  Download,
  FileJson,
  FileSpreadsheet,
  FileText,
  HardDrive,
} from "lucide-react";
import { useEffect, useState } from "react";
import { ContextHelpButton } from "../components/help/ContextHelpButton";
import { Button, Card, CardHeader } from "../components/ui";
import { useNotify } from "../context/NotificationContext";
import { API_BASE_URL } from "../lib/api-config";
import { getAuthToken } from "../lib/tokenStorage";
import { useChatStore } from "../store/chatStore";
import { cn } from "../utils/helpers";

const exportFormats = [
  {
    id: "pdf",
    name: "PDF Report",
    icon: <FileText className="w-6 h-6" />,
    desc: "Professional certified engineering report with PE stamp & IEEE/IEC tables",
    color: "text-red-400",
    bgColor: "bg-red-500/10",
  },
  {
    id: "excel",
    name: "Excel Spreadsheet",
    icon: <FileSpreadsheet className="w-6 h-6" />,
    desc: "Multi-sheet workbook (IEEE 3002.7 & IEC 60909) for analysis",
    color: "text-green-400",
    bgColor: "bg-green-500/10",
  },
  {
    id: "json",
    name: "JSON Export",
    icon: <FileJson className="w-6 h-6" />,
    desc: "Raw structured network topology and study results for API integration",
    color: "text-amber-400",
    bgColor: "bg-amber-500/10",
  },
];

interface RecentExport {
  id?: string;
  name: string;
  size: string;
  date: string;
  format?: string;
  project_id?: string;
  download_url?: string;
}

export default function DataExport() {
  const { notify } = useNotify();
  const projectId = useChatStore((s) => s.projectId);
  const activeProjectId = projectId || "ieee-9bus-wscc";

  const [recentExports, setRecentExports] = useState<RecentExport[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [exportingFormat, setExportingFormat] = useState<string | null>(null);
  const [downloadingFile, setDownloadingFile] = useState<string | null>(null);

  const fetchExports = () => {
    const token = getAuthToken();
    fetch(`${API_BASE_URL}/api/v1/exports`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then((r) => {
        if (!r.ok) throw new Error(`API ${r.status}: ${r.statusText}`);
        return r.json();
      })
      .then((data: RecentExport[]) => {
        setRecentExports(Array.isArray(data) ? data : []);
        setError(null);
      })
      .catch((err) => {
        console.error("Failed to load exports:", err);
        setError(err.message);
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchExports();
  }, []);

  const handleExport = async (formatId: string, formatName: string) => {
    setExportingFormat(formatId);
    try {
      notify("info", `Exporting ${formatName} for ${activeProjectId}...`);
      const token = getAuthToken();
      const headers: Record<string, string> = {};
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const endpoint = `${API_BASE_URL}/api/v1/export/${activeProjectId}/${formatId}`;
      const res = await fetch(endpoint, { headers });
      if (!res.ok) {
        const detail = await res.text().catch(() => res.statusText);
        throw new Error(`Export failed (${res.status}): ${detail}`);
      }

      const blob = await res.blob();
      const blobUrl = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = blobUrl;
      const ext = formatId === "excel" ? "xlsx" : formatId;
      const filename = `${activeProjectId.toLowerCase().replace(/[^a-z0-9]+/g, "_")}_export.${ext}`;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(blobUrl);

      notify("success", `Exported ${filename} successfully!`);
      fetchExports();
    } catch (err: any) {
      console.error("Export error:", err);
      notify("error", err.message || "Failed to export data");
    } finally {
      setExportingFormat(null);
    }
  };

  const handleDownloadRecent = async (file: RecentExport) => {
    setDownloadingFile(file.name);
    try {
      notify("info", `Downloading ${file.name}...`);
      const token = getAuthToken();
      const headers: Record<string, string> = {};
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const targetUrl = file.download_url
        ? (file.download_url.startsWith("http") ? file.download_url : `${API_BASE_URL}${file.download_url}`)
        : `${API_BASE_URL}/api/v1/export/${file.project_id || activeProjectId}/${file.format || "pdf"}`;

      const res = await fetch(targetUrl, { headers });
      if (!res.ok) {
        throw new Error(`Download failed (${res.status})`);
      }

      const blob = await res.blob();
      const blobUrl = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = blobUrl;
      a.download = file.name;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(blobUrl);

      notify("success", `Downloaded ${file.name}`);
    } catch (err: any) {
      console.error("Download error:", err);
      notify("error", `Download failed: ${err.message}`);
    } finally {
      setDownloadingFile(null);
    }
  };

  return (
    <div className="space-y-6">
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-brand-500/10 border border-brand-500/20">
              <Download className="w-5 h-5 text-brand-400" />
            </div>
            <div>
              <h2 className="text-2xl font-bold text-[var(--text-primary)]">Data Export</h2>
              <div className="flex items-center gap-2">
                <p className="text-sm text-[var(--text-tertiary)]">
                  Export study results and system data for{" "}
                  <span className="font-semibold text-brand-400">{activeProjectId}</span>
                </p>
                <ContextHelpButton contextId="data-export.overview" />
              </div>
            </div>
          </div>
        </div>
      </motion.div>

      {/* Export Format Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {exportFormats.map((format, i) => (
          <motion.div
            key={format.id}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.05 * i }}
          >
            <Card
              variant="bordered"
              padding="lg"
              className="cursor-pointer hover:border-brand-500/40 transition-colors"
              onClick={() => {
                if (!exportingFormat) handleExport(format.id, format.name);
              }}
            >
              <div className={cn("p-3 rounded-lg w-fit mb-4", format.bgColor, format.color)}>
                {format.icon}
              </div>
              <h3 className="text-base font-semibold text-[var(--text-primary)]">{format.name}</h3>
              <p className="text-sm text-[var(--text-muted)] mt-1.5">{format.desc}</p>
              <div className="mt-4 pt-3 border-t border-[var(--border-primary)]">
                <Button
                  variant="outline"
                  size="sm"
                  icon={Download}
                  loading={exportingFormat === format.id}
                  onClick={(e) => {
                    e.stopPropagation();
                    handleExport(format.id, format.name);
                  }}
                  className="w-full"
                >
                  Export {format.name.split(" ")[0]}
                </Button>
              </div>
            </Card>
          </motion.div>
        ))}
      </div>

      {/* Recent Exports */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
      >
        <Card padding="md">
          <CardHeader
            title="Recent Exports"
            subtitle="Previously exported files and certified reports"
            icon={<Clock className="w-4 h-4" />}
          />
          {loading && (
            <div className="flex items-center justify-center h-20">
              <div className="w-5 h-5 border-2 border-[var(--accent-primary)] border-t-transparent rounded-full animate-spin" />
            </div>
          )}
          {error && !loading && (
            <div className="flex items-center gap-2 p-3 text-sm text-[var(--text-tertiary)]">
              <AlertCircle className="w-4 h-4 text-red-400" />
              <span>Failed to load exports: {error}</span>
            </div>
          )}
          {!loading && !error && recentExports.length === 0 && (
            <div className="flex flex-col items-center gap-2 py-6 text-sm text-[var(--text-tertiary)]">
              <HardDrive className="w-6 h-6 text-[var(--text-muted)]" />
              <p>No exports yet.</p>
              <p className="text-xs text-[var(--text-muted)]">
                Click any card above to generate and download a report.
              </p>
            </div>
          )}
          {!loading && !error && recentExports.length > 0 && (
            <div className="space-y-3">
              {recentExports.map((file) => (
                <div
                  key={file.name}
                  className="flex items-center justify-between p-3 bg-[var(--bg-primary)] rounded-lg border border-[var(--border-primary)]"
                >
                  <div className="flex items-center gap-3">
                    <div className="p-1.5 rounded-md bg-brand-500/10">
                      <HardDrive className="w-3.5 h-3.5 text-brand-400" />
                    </div>
                    <div>
                      <p className="text-sm font-medium text-[var(--text-primary)] font-mono">
                        {file.name}
                      </p>
                      <div className="flex items-center gap-2 text-xs text-[var(--text-muted)] mt-0.5">
                        <span>{file.size}</span>
                        <span>·</span>
                        <span>{file.date}</span>
                      </div>
                    </div>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    icon={Download}
                    loading={downloadingFile === file.name}
                    onClick={() => handleDownloadRecent(file)}
                    className="text-[var(--text-tertiary)] hover:text-[var(--text-primary)]"
                    title={`Download ${file.name}`}
                  />
                </div>
              ))}
            </div>
          )}
        </Card>
      </motion.div>
    </div>
  );
}
