/**
 * ResultViewer — modal viewer for a single ResultStore entry.
 *
 * Opens from the session activity feed. Reads the `ResultEntry` produced by
 * the chat store (which already enriched a `result_ready` event with the
 * `GET /api/v1/results/{result_id}` payload). The viewer NEVER mutates the
 * result — it is strictly read-only and redacts secret-shaped keys.
 *
 * When the entry is missing a `summary` (e.g. the user opened a result the
 * store didn't enrich yet) it triggers a one-shot lazy load via
 * `loadResult(resultId)` from the store.
 */
import { Download, FileText, Network, X } from "lucide-react";
import { useEffect } from "react";
import { useChatStore, type ResultEntry } from "../../store/chatStore";
import { Button } from "../ui/Button";
import { Modal } from "../ui/Modal";
import { Skeleton } from "../ui/Skeleton";
import { GridEditorViewer } from "./GridEditorViewer";
import { toRedactedJson } from "./payload";

export interface ResultViewerProps {
  readonly result: ResultEntry | null;
  readonly onClose: () => void;
}

function SummaryPane({ result }: { readonly result: ResultEntry }) {
  if (result.loading) {
    return (
      <div className="space-y-2" data-testid="result-viewer-loading">
        <Skeleton className="h-4 w-1/2" />
        <Skeleton className="h-4 w-2/3" />
        <Skeleton className="h-24 w-full" />
      </div>
    );
  }
  if (result.error) {
    return (
      <p className="text-sm text-red-400" data-testid="result-viewer-error">
        {result.error}
      </p>
    );
  }
  if (result.summary) {
    return (
      <pre
        className="text-xs font-mono bg-[var(--bg-elevated)] border border-[var(--border-primary)] rounded-lg p-3 overflow-auto max-h-96"
        data-testid="result-viewer-summary"
      >
        {toRedactedJson(result.summary)}
      </pre>
    );
  }
  return (
    <p className="text-xs text-[var(--text-tertiary)]" data-testid="result-viewer-empty">
      No summary payload was returned by ResultStore for this result id.
    </p>
  );
}

export function ResultViewer({ result, onClose }: ResultViewerProps) {
  const loadResult = useChatStore((s) => s.loadResult);

  useEffect(() => {
    if (!result) return;
    if (result.loaded || result.loading || result.error) return;
    void loadResult(result.resultId);
  }, [result, loadResult]);

  if (!result) return null;

  const handleDownload = () => {
    try {
      const blob = new Blob([toRedactedJson(result.summary ?? { resultId: result.resultId })], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${result.tool ?? "result"}-${result.resultId}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch {
      // No-op: download is a UX nicety, never a critical path.
    }
  };

  return (
    <Modal
      open={true}
      onClose={onClose}
      title={result.tool ?? "Study result"}
      subtitle={
        <span className="font-mono text-xs text-[var(--text-tertiary)]">{result.resultId}</span>
      }
      size="xl"
      footer={
        <>
          <Button variant="secondary" icon={Download} onClick={handleDownload} data-testid="result-download">
            Download JSON
          </Button>
          <Button variant="primary" icon={X} onClick={onClose} data-testid="result-close">
            Close
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4" data-testid="result-viewer">
        <section>
          <header className="flex items-center gap-2 mb-2">
            <FileText className="w-4 h-4 text-[var(--text-secondary)]" />
            <h3 className="text-sm font-semibold text-[var(--text-secondary)]">Summary</h3>
          </header>
          <SummaryPane result={result} />
        </section>

        <section>
          <header className="flex items-center gap-2 mb-2">
            <Network className="w-4 h-4 text-[var(--text-secondary)]" />
            <h3 className="text-sm font-semibold text-[var(--text-secondary)]">Network snapshot</h3>
          </header>
          <GridEditorViewer
            snapshot={extractNetworkSnapshot(result)}
            loading={result.loading}
            error={result.error}
            data-testid="result-viewer-grid"
          />
        </section>
      </div>
    </Modal>
  );
}

function extractNetworkSnapshot(result: ResultEntry): unknown {
  const summary = result.summary;
  if (summary === null || summary === undefined) return null;
  if (typeof summary !== "object") return null;
  const record = summary as Record<string, unknown>;
  // Common shapes — never invent fields, only read existing keys.
  if (record.network_snapshot && typeof record.network_snapshot === "object") {
    return record.network_snapshot;
  }
  if (record.snapshot && typeof record.snapshot === "object") {
    return record.snapshot;
  }
  return null;
}