import { Database, Network } from "lucide-react";
import { EmptyState } from "../ui/EmptyState";
import { toRedactedJson } from "./payload";

export interface GridEditorViewerProps {
  readonly snapshot: unknown;
  readonly loading?: boolean;
  readonly error?: string | null;
  readonly className?: string;
  readonly "data-testid"?: string;
}

/**
 * Read-only viewer for a `network_snapshot` document when the session payload
 * actually contains one.
 *
 * SAFETY: this viewer never invents a schema, performs no mutations, and renders
 * the raw delivered document only — showing a clear empty state when no
 * snapshot exists.
 */
export function GridEditorViewer({
  snapshot,
  loading,
  error,
  className,
  "data-testid": testId,
}: GridEditorViewerProps) {
  if (loading) {
    return (
      <div className={className} data-testid={testId ?? "grid-editor-viewer"}>
        <div className="space-y-2" data-testid="grid-editor-viewer-loading">
          <div className="h-4 rounded bg-[var(--bg-elevated)] animate-pulse" />
          <div className="h-4 rounded bg-[var(--bg-elevated)] animate-pulse" />
          <div className="h-24 rounded bg-[var(--bg-elevated)] animate-pulse" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={className} data-testid={testId ?? "grid-editor-viewer"}>
        <EmptyState
          icon={<Network className="w-8 h-8" />}
          title="Network snapshot failed to load"
          description={error}
        />
      </div>
    );
  }

  const hasSnapshot =
    snapshot !== null &&
    snapshot !== undefined &&
    (typeof snapshot !== "object" || Object.keys(snapshot as Record<string, unknown>).length > 0);

  if (!hasSnapshot) {
    return (
      <div className={className} data-testid={testId ?? "grid-editor-viewer"}>
        <EmptyState
          icon={<Network className="w-8 h-8" />}
          title="No network snapshot available"
          description="The current session payload does not contain a network_snapshot document. No snapshot wire contract exists at this stage, so this viewer stays read-only rather than inventing one."
        />
      </div>
    );
  }

  return (
    <div className={className} data-testid={testId ?? "grid-editor-viewer"}>
      <div className="flex items-center gap-2 mb-2 px-1">
        <Database className="w-4 h-4 text-[var(--text-muted)]" />
        <span className="text-xs text-[var(--text-tertiary)]">
          Read-only network snapshot — the client performs no editor mutations.
        </span>
      </div>
      <pre className="text-xs font-mono bg-[var(--bg-elevated)] border border-[var(--border-primary)] rounded-lg p-3 overflow-auto max-h-96">
        {toRedactedJson(snapshot)}
      </pre>
    </div>
  );
}