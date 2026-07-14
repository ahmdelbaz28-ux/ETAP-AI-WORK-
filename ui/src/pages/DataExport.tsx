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
import { cn } from "../utils/helpers";

const exportFormats = [
  {
    id: "pdf",
    name: "PDF Report",
    icon: <FileText className="w-6 h-6" />,
    desc: "Professional engineering report with charts and tables",
    color: "text-red-400",
    bgColor: "bg-red-500/10",
  },
  {
    id: "xlsx",
    name: "Excel Spreadsheet",
    icon: <FileSpreadsheet className="w-6 h-6" />,
    desc: "Tabular data for further analysis and processing",
    color: "text-green-400",
    bgColor: "bg-green-500/10",
  },
  {
    id: "json",
    name: "JSON Export",
    icon: <FileJson className="w-6 h-6" />,
    desc: "Raw structured data for API integration",
    color: "text-amber-400",
    bgColor: "bg-amber-500/10",
  },
];

interface RecentExport {
  name: string;
  size: string;
  date: string;
}

export default function DataExport() {
  const { notify } = useNotify();
  const [recentExports, setRecentExports] = useState<RecentExport[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = localStorage.getItem("authToken");
    fetch(`${API_BASE_URL}/api/v1/exports`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then((r) => {
        if (!r.ok) throw new Error(`API ${r.status}: ${r.statusText}`);
        return r.json();
      })
      .then((data: RecentExport[]) => {
        setRecentExports(data);
        setError(null); // Clear any previous error on successful fetch
      })
      .catch((err) => {
        console.error("Failed to load exports:", err);
        setError(err.message);
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-6">
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-brand-500/10 border border-brand-500/20">
            <Download className="w-5 h-5 text-brand-400" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-[var(--text-primary)]">Data Export</h2>
            <div className="flex items-center gap-2">
              <p className="text-sm text-[var(--text-tertiary)]">
                Export study results and system data
              </p>
              <ContextHelpButton contextId="data-export.overview" />
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
              className="cursor-pointer"
              onClick={() => notify("success", `Exporting as ${format.name}...`)}
            >
              <div className={cn("p-3 rounded-lg w-fit mb-4", format.bgColor, format.color)}>
                {format.icon}
              </div>
              <h3 className="text-base font-semibold text-[var(--text-primary)]">{format.name}</h3>
              <p className="text-sm text-[var(--text-muted)] mt-1.5">{format.desc}</p>
              <div className="mt-4 pt-3 border-t border-[var(--border-primary)]">
                <Button variant="outline" size="sm" icon={Download} className="w-full">
                  Export
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
            subtitle="Previously exported files"
            icon={<Clock className="w-4 h-4" />}
          />
          {loading && ( // NOSONAR - S3358: previously nested ternary, refactored to && chain
            <div className="flex items-center justify-center h-20">
              <div className="w-5 h-5 border-2 border-[var(--accent-primary)] border-t-transparent rounded-full animate-spin" />
            </div>
          )}
          {error &&
            !loading && ( // NOSONAR - S3358: previously nested ternary, refactored to && chain
              <div className="flex items-center gap-2 p-3 text-sm text-[var(--text-tertiary)]">
                <AlertCircle className="w-4 h-4 text-red-400" />
                <span>Failed to load exports: {error}</span>
              </div>
            )}
          {!loading && !error && recentExports.length === 0 && (
            <div className="flex flex-col items-center gap-2 py-6 text-sm text-[var(--text-tertiary)]">
              <HardDrive className="w-6 h-6 text-[var(--text-muted)]" />
              <p>No exports yet.</p>
              <p className="text-xs text-[var(--text-muted)]">Export a study to see it here.</p>
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
                    onClick={() => notify("info", "Download started")}
                    className="text-[var(--text-tertiary)] hover:text-[var(--text-primary)]"
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
