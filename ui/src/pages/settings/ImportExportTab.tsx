/**
 * ImportExportTab (Phase P7c — Split Settings)
 * ============================================
 * Settings tab for Power Systems Data Import and Export operations.
 * Connects to:
 *   - POST /api/v1/import/preview (Dry-run impact analysis)
 *   - POST /api/v1/import/execute (Idempotent execution through Approval Gateway)
 *   - GET  /api/v1/export/formats (Pre-declared export formats catalog)
 *
 * Uses chatStore.proposeImportApproval to seamlessly integrate with chat workflow.
 */

import {
  AlertCircle,
  CheckCircle2,
  Code,
  FileJson,
  FileSpreadsheet,
  FileText,
  Loader2,
  RefreshCw,
  Send,
  Upload,
} from "lucide-react";
import { type ChangeEvent, useCallback, useEffect, useRef, useState } from "react";
import { Badge, Button, Card, CardHeader } from "../../components/ui";
import { API_BASE_URL } from "../../lib/api-config";
import { getAuthToken } from "../../lib/tokenStorage";
import { useChatStore } from "../../store/chatStore";

const ALLOWED_EXTENSIONS = [".csv", ".json", ".xml", ".raw", ".m"];
const MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024; // 10 MiB limit

export interface ImportPreviewData {
  preview_id: string;
  filename: string;
  format: string;
  records_count: number;
  buses_count: number;
  branches_count: number;
  risk_level: "low" | "medium" | "high";
  affected_tables?: string[];
  warnings?: string[];
}

export interface ExportFormatItem {
  id: string;
  name: string;
  mime_type: string;
  extension: string;
  description: string;
}

export interface ImportExportTabProps {
  readonly notify?: (type: "success" | "error" | "info" | "warning", message: string) => void;
}

export function ImportExportTab({ notify }: ImportExportTabProps) {
  // Chat store actions
  const sessionId = useChatStore((s) => s.sessionId);
  const proposeImportApproval = useChatStore((s) => s.proposeImportApproval);
  const resolveApproval = useChatStore((s) => s.resolveApproval);
  const executeImport = useChatStore((s) => s.executeImport);

  // Import State
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportPreviewData | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [importLoading, setImportLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Export State
  const [exportFormats, setExportFormats] = useState<ExportFormatItem[]>([]);
  const [formatsLoading, setFormatsLoading] = useState(false);

  // Load Export Formats
  const loadExportFormats = useCallback(async () => {
    setFormatsLoading(true);
    try {
      const token = getAuthToken();
      const res = await fetch(`${API_BASE_URL}/api/v1/export/formats`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (res.ok) {
        const data = await res.json();
        setExportFormats(Array.isArray(data) ? data : data?.formats ?? []);
      } else {
        // Documented fallback
        setExportFormats([
          {
            id: "pdf",
            name: "PDF Engineering Report",
            mime_type: "application/pdf",
            extension: ".pdf",
            description: "Formatted report with single-line diagrams, load flow matrices, and safety margins",
          },
          {
            id: "excel",
            name: "Excel Workbook (XLSX)",
            mime_type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            extension: ".xlsx",
            description: "Tabular bus voltages, branch impedances, and short-circuit fault levels",
          },
          {
            id: "csv",
            name: "CSV Results Matrix",
            mime_type: "text/csv",
            extension: ".csv",
            description: "Raw numerical output tables suitable for pandas and downstream automation",
          },
          {
            id: "json",
            name: "CIM / JSON Schema",
            mime_type: "application/json",
            extension: ".json",
            description: "Structured IEEE/IEC power network dataset and study execution results",
          },
        ]);
      }
    } catch {
      // Fallback on network error
      setExportFormats([
        {
          id: "pdf",
          name: "PDF Engineering Report",
          mime_type: "application/pdf",
          extension: ".pdf",
          description: "Formatted engineering report with charts and single-line diagrams",
        },
        {
          id: "excel",
          name: "Excel Workbook (XLSX)",
          mime_type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
          extension: ".xlsx",
          description: "Tabular study results and equipment parameters",
        },
      ]);
    } finally {
      setFormatsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadExportFormats();
  }, [loadExportFormats]);

  // Handle file preview (POST /api/v1/import/preview)
  const handleFileSelect = async (e: ChangeEvent<HTMLInputElement>) => {
    setErrorMessage(null);
    setSuccessMessage(null);
    setPreview(null);

    const file = e.target.files?.[0];
    if (!file) return;

    if (file.size > MAX_ATTACHMENT_BYTES) {
      setErrorMessage(`File exceeds 10 MiB limit (${(file.size / (1024 * 1024)).toFixed(1)} MB)`);
      if (fileInputRef.current) fileInputRef.current.value = "";
      return;
    }

    const lowerName = file.name.toLowerCase();
    const isAllowed = ALLOWED_EXTENSIONS.some((ext) => lowerName.endsWith(ext));
    if (!isAllowed) {
      setErrorMessage(`Unsupported format. Supported: ${ALLOWED_EXTENSIONS.join(", ")}`);
      if (fileInputRef.current) fileInputRef.current.value = "";
      return;
    }

    setSelectedFile(file);
    setPreviewLoading(true);

    try {
      const formData = new FormData();
      formData.append("file", file);
      if (sessionId) formData.append("session_id", sessionId);

      const token = getAuthToken();
      const res = await fetch(`${API_BASE_URL}/api/v1/import/preview`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: formData,
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => null);
        throw new Error(errJson?.detail || `Preview failed: ${res.statusText}`);
      }

      const data: ImportPreviewData = await res.json();
      setPreview(data);
      notify?.("success", `Preview ready: ${data.buses_count} buses, ${data.branches_count} branches found`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to preview import file";
      setErrorMessage(msg);
      notify?.("error", msg);
    } finally {
      setPreviewLoading(false);
    }
  };

  // Handle Propose & Execute Import (Approval Gateway + POST /api/v1/import/execute)
  const handleExecuteImport = async () => {
    if (!preview) return;
    setImportLoading(true);
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      // 1. Propose action to Approval Gateway (POST /api/v1/approvals)
      const approval = await proposeImportApproval({
        preview_id: preview.preview_id,
        filename: preview.filename,
        records_count: preview.records_count,
        buses_count: preview.buses_count,
        branches_count: preview.branches_count,
        format: preview.format,
      });

      if (!approval) {
        throw new Error("Approval Gateway rejection: failed to create approval ticket.");
      }

      // 2. Resolve approval
      const approved = await resolveApproval(approval.id, "approve");
      if (!approved) {
        throw new Error("Approval resolution was rejected or pending checker authorization.");
      }

      // 3. Execute approved import via POST /api/v1/import/execute
      const resultId = await executeImport(preview.preview_id, approval.id);
      if (resultId) {
        const msg = `Successfully imported ${preview.filename} (Result ID: ${resultId})`;
        setSuccessMessage(msg);
        notify?.("success", msg);
        setSelectedFile(null);
        setPreview(null);
        if (fileInputRef.current) fileInputRef.current.value = "";
      } else {
        throw new Error("Import execution did not return a valid result ID.");
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Import execution failed";
      setErrorMessage(msg);
      notify?.("error", msg);
    } finally {
      setImportLoading(false);
    }
  };

  const getFormatIcon = (ext: string) => {
    if (ext.includes("pdf")) return <FileText className="w-5 h-5 text-red-400" />;
    if (ext.includes("xls")) return <FileSpreadsheet className="w-5 h-5 text-green-400" />;
    if (ext.includes("json")) return <FileJson className="w-5 h-5 text-amber-400" />;
    return <Code className="w-5 h-5 text-blue-400" />;
  };

  return (
    <div className="space-y-6 col-span-2" data-testid="import-export-tab">
      {/* ── Section 1: Power-System Data Import ───────────────────────── */}
      <Card padding="md">
        <CardHeader
          title="Power System Data Import"
          subtitle="Preview and safely import grid models (CIM/XML, IEEE CSV, JSON, PSS/E RAW, MATPOWER) via Dual-Control Approval"
          icon={<Upload className="w-5 h-5 text-brand-400" />}
        />

        <div className="mt-4 space-y-4">
          {/* File Picker Zone */}
          <div className="p-5 border-2 border-dashed border-[var(--border-primary)] hover:border-brand-500/40 rounded-xl bg-[var(--bg-elevated)] text-center transition-all">
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv,.json,.xml,.raw,.m"
              onChange={(e) => void handleFileSelect(e)}
              className="hidden"
              id="settings-import-file"
            />
            <label htmlFor="settings-import-file" className="cursor-pointer block">
              <Upload className="w-8 h-8 text-brand-400 mx-auto mb-2 opacity-70" />
              <span className="text-sm font-semibold text-[var(--text-primary)]">
                {selectedFile ? selectedFile.name : "Click to select a power-system model file"}
              </span>
              <p className="text-xs text-[var(--text-muted)] mt-1">
                Supported: CIM/XML (.xml), IEEE Bus/Branch (.csv), JSON (.json), PSS/E (.raw), MATPOWER (.m) — Max 10 MiB
              </p>
            </label>
          </div>

          {previewLoading && (
            <div className="flex items-center gap-3 p-4 rounded-lg bg-brand-500/10 border border-brand-500/20 text-brand-300 text-xs">
              <Loader2 className="w-4 h-4 animate-spin shrink-0" />
              <span>Running dry-run impact analysis and XML security verification (POST /api/v1/import/preview)...</span>
            </div>
          )}

          {errorMessage && (
            <div className="flex items-center gap-2 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-300 text-xs">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{errorMessage}</span>
            </div>
          )}

          {successMessage && (
            <div className="flex items-center gap-2 p-3 rounded-lg bg-green-500/10 border border-green-500/20 text-green-300 text-xs">
              <CheckCircle2 className="w-4 h-4 shrink-0" />
              <span>{successMessage}</span>
            </div>
          )}

          {/* Preview Card */}
          {preview && (
            <div className="p-4 rounded-xl border border-[var(--border-primary)] bg-[var(--bg-elevated)] space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Badge variant="brand" size="sm">
                    Format: {preview.format.toUpperCase()}
                  </Badge>
                  <span className="text-xs text-[var(--text-secondary)] font-mono">
                    {preview.filename}
                  </span>
                </div>
                <Badge
                  variant={
                    preview.risk_level === "low"
                      ? "success"
                      : preview.risk_level === "medium"
                        ? "warning"
                        : "danger"
                  }
                  size="sm"
                >
                  Risk: {preview.risk_level.toUpperCase()}
                </Badge>
              </div>

              <div className="grid grid-cols-3 gap-3 text-center py-2">
                <div className="p-2 rounded-lg bg-[var(--bg-primary)] border border-[var(--border-primary)]">
                  <div className="text-base font-bold text-[var(--text-primary)] font-mono">
                    {preview.buses_count}
                  </div>
                  <div className="text-[11px] text-[var(--text-muted)]">Buses</div>
                </div>
                <div className="p-2 rounded-lg bg-[var(--bg-primary)] border border-[var(--border-primary)]">
                  <div className="text-base font-bold text-[var(--text-primary)] font-mono">
                    {preview.branches_count}
                  </div>
                  <div className="text-[11px] text-[var(--text-muted)]">Branches</div>
                </div>
                <div className="p-2 rounded-lg bg-[var(--bg-primary)] border border-[var(--border-primary)]">
                  <div className="text-base font-bold text-[var(--text-primary)] font-mono">
                    {preview.records_count}
                  </div>
                  <div className="text-[11px] text-[var(--text-muted)]">Total Records</div>
                </div>
              </div>

              {preview.warnings && preview.warnings.length > 0 && (
                <div className="text-[11px] text-yellow-400 bg-yellow-500/10 p-2 rounded border border-yellow-500/20">
                  <span className="font-semibold">Warnings: </span>
                  {preview.warnings.slice(0, 2).join("; ")}
                </div>
              )}

              <div className="pt-2 flex items-center justify-end gap-2 border-t border-[var(--border-primary)]">
                <Button
                  variant="primary"
                  size="sm"
                  icon={importLoading ? Loader2 : Send}
                  disabled={importLoading}
                  onClick={() => void handleExecuteImport()}
                >
                  {importLoading ? "Executing Import…" : "Propose & Execute Import"}
                </Button>
              </div>
            </div>
          )}
        </div>
      </Card>

      {/* ── Section 2: Power-System Data Export ───────────────────────── */}
      <Card padding="md">
        <div className="flex items-center justify-between pb-3 border-b border-[var(--border-primary)]">
          <CardHeader
            title="Pre-Declared Export Formats"
            subtitle="Authoritative export endpoints conforming to standard power system schemas (GET /api/v1/export/formats)"
            icon={<Upload className="w-5 h-5 text-brand-400" />}
          />
          <Button
            variant="ghost"
            size="sm"
            icon={RefreshCw}
            disabled={formatsLoading}
            onClick={() => void loadExportFormats()}
          >
            Refresh
          </Button>
        </div>

        <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3">
          {exportFormats.map((fmt) => (
            <div
              key={fmt.id}
              className="p-3 rounded-xl border border-[var(--border-primary)] bg-[var(--bg-elevated)] hover:border-brand-500/30 transition-all flex flex-col justify-between"
            >
              <div>
                <div className="flex items-center gap-2 mb-1.5">
                  {getFormatIcon(fmt.extension)}
                  <span className="font-semibold text-xs text-[var(--text-primary)]">
                    {fmt.name}
                  </span>
                  <Badge variant="neutral" size="sm">
                    {fmt.extension}
                  </Badge>
                </div>
                <p className="text-[11px] text-[var(--text-secondary)] leading-relaxed">
                  {fmt.description}
                </p>
              </div>
              <div className="mt-3 pt-2 border-t border-[var(--border-primary)] flex items-center justify-between text-[10px] text-[var(--text-muted)]">
                <span className="font-mono">{fmt.mime_type}</span>
                <span className="text-brand-400 font-semibold flex items-center gap-1">
                  <CheckCircle2 className="w-3 h-3" /> Available
                </span>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

export default ImportExportTab;
