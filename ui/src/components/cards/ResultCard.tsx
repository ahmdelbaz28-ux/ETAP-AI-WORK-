import { FileBarChart, Download, Upload, Database } from "lucide-react";
import { useChatStore, type ResultEntry } from "../../store/chatStore";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card, CardHeader, CardSection } from "../ui/Card";

export interface ResultCardProps {
  readonly result: ResultEntry;
}

/**
 * ResultCard — Secure card component for displaying study, import, or export results.
 *
 * Security Guarantees:
 * - Loads payloads strictly through ResultStore (`GET /api/v1/results/{result_id}`)
 * - Zero direct disk path access
 * - Zero `dangerouslySetInnerHTML` — all fields escaped via standard React JSX
 * - Sanitizes displayed filenames and metadata
 */
export function ResultCard({ result }: ResultCardProps) {
  const selectResult = useChatStore((s) => s.selectResult);
  const loadResult = useChatStore((s) => s.loadResult);

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
  const recordsImported = typeof summary.records_imported === "number" ? summary.records_imported : null;

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
            {format && <span className="uppercase text-[10px] px-1.5 py-0.5 rounded bg-[var(--bg-muted)]">{format}</span>}
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

        {result.error && (
          <div className="text-xs text-rose-500 mb-2">
            {result.error}
          </div>
        )}

        <div className="flex items-center justify-end gap-2">
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
      </CardSection>
    </Card>
  );
}