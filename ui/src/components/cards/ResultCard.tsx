import { Database, Download, FileBarChart, Upload } from "lucide-react";
import { useState } from "react";
import { API_BASE_URL } from "../../lib/api-config";
import { getAuthToken } from "../../lib/tokenStorage";
import { type ResultEntry, useChatStore } from "../../store/chatStore";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card, CardHeader, CardSection } from "../ui/Card";

export interface ResultCardProps {
  readonly result: ResultEntry;
}

const EXPORT_FORMATS = ["pdf", "excel", "csv", "json"] as const;
type ExportFormat = (typeof EXPORT_FORMATS)[number];

/**
 * ResultCard — Secure card component for displaying study, import, or export results.
 *
 * Security Guarantees:
 * - Loads payloads strictly through ResultStore (`GET /api/v1/results/{result_id}`)
 * - Zero direct disk path access
 * - Zero `dangerouslySetInnerHTML` — all fields escaped via standard React JSX
 * - Sanitizes displayed filenames and metadata
 * - Provides verified exports via `POST /api/v1/export/{project_id}/{format}` with X-Result-ID tracking
 */
export function ResultCard({ result }: ResultCardProps) {
  const selectResult = useChatStore((s) => s.selectResult);
  const loadResult = useChatStore((s) => s.loadResult);
  const addResult = useChatStore((s) => s.addResult);

  const [exportingFormat, setExportingFormat] = useState<ExportFormat | null>(null);
  const [exportedResultId, setExportedResultId] = useState<string | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);

  const open = () => {
    selectResult(result.resultId);
    if (!result.loading && !result.loaded) void loadResult(result.resultId);
  };

  const isImport = result.tool === "data_import" || result.tool === "import";
  const isExport = result.tool === "data_export" || result.tool === "export";

  let cardTitle = result.tool ?? "Study result";
  if (isImport) {
    cardTitle = "Data Import Result";
  } else if (isExport) {
    cardTitle = "Data Export Result";
  }

  let icon = <FileBarChart className="w-4 h-4 text-indigo-400" />;
  if (isImport) {
    icon = <Upload className="w-4 h-4 text-emerald-400" />;
  } else if (isExport) {
    icon = <Download className="w-4 h-4 text-sky-400" />;
  }

  const summary = result.summary ?? {};
  let fileName: string | null = null;
  if (typeof summary.filename === "string") {
    fileName = summary.filename;
  } else if (typeof summary.file_name === "string") {
    fileName = summary.file_name;
  }

  let format: string | null = null;
  if (typeof summary.format === "string") {
    format = summary.format;
  } else if (typeof summary.export_type === "string") {
    format = summary.export_type;
  }
  const busesCount = typeof summary.buses_count === "number" ? summary.buses_count : null;
  const branchesCount = typeof summary.branches_count === "number" ? summary.branches_count : null;
  const recordsImported =
    typeof summary.records_imported === "number" ? summary.records_imported : null;

  const projectId =
    (typeof summary.project_id === "string" && summary.project_id) ||
    (typeof result.project_id === "string" && result.project_id) ||
    (typeof summary.project_name === "string" && summary.project_name) ||
    result.resultId ||
    "default";

  const handleExport = async (fmt: ExportFormat) => {
    setExportingFormat(fmt);
    setExportError(null);

    try {
      const token = getAuthToken();
      const res = await fetch(
        `${API_BASE_URL}/api/v1/export/${encodeURIComponent(projectId)}/${encodeURIComponent(fmt)}`,
        {
          method: "POST",
          headers: {
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
        },
      );

      const xResultId =
        res.headers.get("x-result-id") ||
        res.headers.get("X-Result-ID") ||
        (
          await res
            .clone()
            .json()
            .catch(() => null)
        )?.result_id ||
        null;

      if (xResultId) {
        setExportedResultId(xResultId);
        addResult({
          resultId: xResultId,
          project_id: projectId,
          tool: "data_export",
          summary: {
            file_name: `${projectId}_results.${fmt === "excel" ? "xlsx" : fmt}`,
            export_type: fmt,
            project_id: projectId,
            source_result_id: result.resultId,
          },
          loaded: true,
          loading: false,
        });
      }

      if (!res.ok) {
        const errorText = await res.text().catch(() => "");
        throw new Error(`Export failed (${res.status}): ${errorText || res.statusText}`);
      }

      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${projectId}_results.${fmt === "excel" ? "xlsx" : fmt}`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setExportError(err instanceof Error ? err.message : "Export failed");
    } finally {
      setExportingFormat(null);
    }
  };

  return (
    <Card padding="sm" data-testid={`result-card-${result.resultId}`}>
      <CardHeader
        title={cardTitle}
        subtitle={<span className="font-mono">{result.resultId.slice(0, 16)}…</span>}
        icon={icon}
        action={<Badge variant="success">ready</Badge>}
      />
      <CardSection>
        {fileName && (
          <div className="mb-2 text-xs text-[var(--text-secondary)] truncate flex items-center gap-1">
            <Database className="w-3.5 h-3.5 opacity-70" />
            <span className="font-medium truncate">{fileName}</span>
            {format && (
              <span className="uppercase text-[10px] px-1.5 py-0.5 rounded bg-[var(--bg-muted)]">
                {format}
              </span>
            )}
          </div>
        )}

        {(busesCount !== null || branchesCount !== null || recordsImported !== null) && (
          <div className="grid grid-cols-2 gap-2 my-2 text-xs bg-[var(--bg-muted)] p-2 rounded">
            {recordsImported !== null && (
              <div>
                <span className="text-[var(--text-tertiary)]">Records: </span>
                <span className="font-semibold text-[var(--text-primary)]">{recordsImported}</span>
              </div>
            )}
            {busesCount !== null && (
              <div>
                <span className="text-[var(--text-tertiary)]">Buses: </span>
                <span className="font-semibold text-[var(--text-primary)]">{busesCount}</span>
              </div>
            )}
            {branchesCount !== null && (
              <div>
                <span className="text-[var(--text-tertiary)]">Branches: </span>
                <span className="font-semibold text-[var(--text-primary)]">{branchesCount}</span>
              </div>
            )}
          </div>
        )}

        {result.error && <div className="text-xs text-rose-500 mb-2">{result.error}</div>}

        <div className="flex items-center justify-end gap-2 mb-3">
          <Button
            size="sm"
            variant="outline"
            loading={result.loading}
            disabled={result.loading}
            onClick={open}
            data-testid={`open-result-${result.resultId}`}
          >
            View Result
          </Button>
        </div>

        {/* Export Formats with X-Result-ID tracking */}
        <div
          className="pt-2 border-t border-[var(--border-primary)]"
          data-testid={`export-section-${result.resultId}`}
        >
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-[11px] font-medium text-[var(--text-tertiary)] flex items-center gap-1">
              <Download className="w-3.5 h-3.5" />
              <span>Export results</span>
            </span>
          </div>
          <div
            className="flex flex-wrap items-center gap-1.5"
            data-testid={`export-buttons-${result.resultId}`}
          >
            {EXPORT_FORMATS.map((fmt) => (
              <Button
                key={fmt}
                size="sm"
                variant="outline"
                loading={exportingFormat === fmt}
                disabled={exportingFormat !== null}
                onClick={() => void handleExport(fmt)}
                data-testid={`export-${fmt}-btn`}
              >
                {fmt === "excel" ? "Excel" : fmt.toUpperCase()}
              </Button>
            ))}
          </div>

          {exportedResultId && (
            <div
              className="mt-2 text-xs flex items-center justify-between p-2 rounded bg-[var(--bg-muted)] border border-[var(--border-primary)]"
              data-testid="x-result-id-display"
            >
              <span className="text-[var(--text-tertiary)] font-mono">X-Result-ID:</span>
              <span
                className="font-mono text-xs font-semibold text-brand-400"
                data-testid="exported-result-id"
              >
                {exportedResultId}
              </span>
            </div>
          )}

          {exportError && (
            <div className="mt-1.5 text-xs text-rose-500" data-testid="export-error">
              {exportError}
            </div>
          )}
        </div>
      </CardSection>
    </Card>
  );
}
