/**
 * AIPlayground.tsx — TASK-8
 *
 * Interactive playground for AI/ML endpoints:
 *   POST /api/v1/predict/load      — Load forecast (Prophet/LSTM/Linear)
 *   POST /api/v1/predict/fault     — Fault prediction (XGBoost + SHAP)
 *   POST /api/v1/predict/anomaly   — Anomaly detection (Isolation Forest / PyOD)
 *   POST /api/v1/gnn/predict       — Graph Neural Network power grid analysis
 *   POST /api/v1/rag/query         — RAG query against ETAP knowledge base
 *
 * Features:
 * - One tab per capability (5 tabs)
 * - JSON input editor with schema validation (basic JSON.parse + required-key check)
 * - Result viewer with formatted JSON
 * - Rate-limit indicator (parsed from response headers / body if present)
 * - Loading / error / empty states
 * - "Load sample" button per tab to pre-fill the editor with a known-good payload
 */

import { motion } from "framer-motion";
import { Activity, AlertCircle, Clock, Play, RotateCcw } from "lucide-react";
import { useCallback, useMemo, useState } from "react";
import { Badge, Button, Card, CardHeader } from "../components/ui";
import { useNotify } from "../context/NotificationContext";
import {
  AI_ML_CAPABILITIES,
  type AiMlCapabilityInfo,
  type AiMlResult,
  callAiMlEndpoint,
} from "../lib/api";
import { cn } from "../utils/helpers";

import { ContextHelpButton } from "../components/help/ContextHelpButton";

type TabId = AiMlCapabilityInfo["id"];

interface RunRecord {
  capability: TabId;
  startedAt: string;
  durationMs: number;
  success: boolean;
  result: AiMlResult | null;
  error: string | null;
  inputPreview: string;
}

function validateJson(
  input: string,
  schema: Record<string, unknown>,
): { ok: boolean; parsed?: unknown; error?: string } {
  let parsed: unknown;
  try {
    parsed = JSON.parse(input);
  } catch (e) {
    return { ok: false, error: `Invalid JSON: ${e instanceof Error ? e.message : String(e)}` };
  }
  // Basic required-key check (does not perform full JSON schema validation)
  const required = (schema as { required?: string[] }).required ?? [];
  if (Array.isArray(required) && typeof parsed === "object" && parsed !== null) {
    const obj = parsed as Record<string, unknown>;
    for (const k of required) {
      if (!(k in obj)) {
        return { ok: false, error: `Missing required field: '${k}'` };
      }
    }
  } else if (required.length > 0 && (typeof parsed !== "object" || parsed === null)) {
    return { ok: false, error: "Input must be a JSON object" };
  }
  return { ok: true, parsed };
}

function RateLimitIndicator({ result }: { readonly result: AiMlResult }) {
  const rl = result.rate_limit;
  if (!rl) return null;
  const remaining = typeof rl.remaining === "number" ? rl.remaining : null;
  const limit = typeof rl.limit === "number" ? rl.limit : null;
  return (
    <div className="flex items-center gap-2 text-xs text-[var(--text-muted)]">
      <Clock className="w-3.5 h-3.5" />
      <span>
        Rate limit:
        {limit !== null && (
          <code className="ml-1 font-mono">
            {remaining ?? "?"}/{limit}
          </code>
        )}
        {rl.reset_at && (
          <span className="ml-2">· resets {new Date(rl.reset_at).toLocaleTimeString()}</span>
        )}
      </span>
    </div>
  );
}

function ResultViewer({
  result,
  error,
}: { readonly result: AiMlResult | null; readonly error: string | null }) {
  if (error) {
    return (
      <div className="p-3 rounded-md bg-red-500/10 border border-red-500/20 text-red-300 text-xs font-mono whitespace-pre-wrap break-words">
        <div className="flex items-center gap-2 mb-2 font-sans font-semibold">
          <AlertCircle className="w-4 h-4" /> Error
        </div>
        {error}
      </div>
    );
  }
  if (!result) {
    return (
      <div className="p-4 rounded-md bg-[var(--bg-elevated)] border border-dashed border-[var(--border-primary)] text-[var(--text-muted)] text-xs text-center">
        Run a query to see results here.
      </div>
    );
  }
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 flex-wrap">
        <Badge variant={result.success ? "success" : "danger"} size="sm">
          {result.success ? "SUCCESS" : "FAILED"}
        </Badge>
        {result.trace_id && (
          <code className="text-[10px] text-[var(--text-muted)] font-mono">
            trace_id: {result.trace_id}
          </code>
        )}
        <RateLimitIndicator result={result} />
      </div>
      <pre className="p-3 rounded-md bg-[var(--bg-elevated)] border border-[var(--border-primary)] text-xs font-mono whitespace-pre-wrap break-words max-h-96 overflow-auto">
        {JSON.stringify(result.data ?? result.errors ?? result, null, 2)}
      </pre>
    </div>
  );
}

export default function AIPlayground() {
  const [activeTab, setActiveTab] = useState<TabId>("predict/load");
  const [inputs, setInputs] = useState<Record<TabId, string>>(() => {
    const init = {} as Record<TabId, string>;
    for (const c of AI_ML_CAPABILITIES) {
      init[c.id] = JSON.stringify(c.sampleInput, null, 2);
    }
    return init;
  });
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<AiMlResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<RunRecord[]>([]);
  const { notify } = useNotify();

  const activeCapability = useMemo(
    () => AI_ML_CAPABILITIES.find((c) => c.id === activeTab) ?? AI_ML_CAPABILITIES[0],
    [activeTab],
  );

  const run = useCallback(async () => {
    setRunning(true);
    setError(null);
    const started = performance.now();
    const startedAt = new Date().toISOString();
    const validation = validateJson(inputs[activeTab], activeCapability.inputSchema);
    if (!validation.ok || validation.parsed === undefined) {
      setError(validation.error ?? "Invalid input");
      setResult(null);
      setRunning(false);
      notify("error", `Validation failed: ${validation.error}`);
      return;
    }
    try {
      const resp = await callAiMlEndpoint(activeCapability.path, validation.parsed);
      setResult(resp);
      setError(null);
      const durationMs = Math.round(performance.now() - started);
      setHistory((prev) =>
        [
          {
            capability: activeTab,
            startedAt,
            durationMs,
            success: resp.success,
            result: resp,
            error: null,
            inputPreview: JSON.stringify(validation.parsed).slice(0, 120),
          },
          ...prev,
        ].slice(0, 10),
      );
      if (resp.success) {
        notify("success", `${activeCapability.label} completed in ${durationMs}ms`);
      } else {
        notify("warning", `${activeCapability.label} returned non-success response`);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Unknown error";
      setError(msg);
      setResult(null);
      const durationMs = Math.round(performance.now() - started);
      setHistory((prev) =>
        [
          {
            capability: activeTab,
            startedAt,
            durationMs,
            success: false,
            result: null,
            error: msg,
            inputPreview: JSON.stringify(validation.parsed).slice(0, 120),
          },
          ...prev,
        ].slice(0, 10),
      );
      notify("error", `${activeCapability.label} failed: ${msg}`);
    } finally {
      setRunning(false);
    }
  }, [activeTab, inputs, activeCapability, notify]);

  const loadSample = useCallback(() => {
    setInputs((prev) => ({
      ...prev,
      [activeTab]: JSON.stringify(activeCapability.sampleInput, null, 2),
    }));
    setResult(null);
    setError(null);
  }, [activeTab, activeCapability]);

  const resetAll = useCallback(() => {
    setResult(null);
    setError(null);
    setHistory([]);
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)] flex items-center gap-2">
            <Activity className="w-6 h-6 text-brand-400" />
            AI/ML Playground
          </h1>
          <p className="text-sm text-[var(--text-secondary)] mt-1">
            Interactive playground for 5 AI/ML endpoints. Each tab covers one capability with JSON
            input, schema validation, and a structured result viewer.
          </p>
        </div>
        <ContextHelpButton contextId="ai-playground" />
      </div>

      <Card padding="lg">
        {/* Tabs */}
        <div className="flex flex-wrap gap-2 mb-4 border-b border-[var(--border-primary)] pb-3">
          {AI_ML_CAPABILITIES.map((c) => (
            <button
              key={c.id}
              type="button"
              onClick={() => {
                setActiveTab(c.id);
                setResult(null);
                setError(null);
              }}
              className={cn(
                "px-3 py-1.5 rounded-md text-xs font-medium transition-all focus:outline-none focus:ring-2 focus:ring-brand-500/40",
                activeTab === c.id
                  ? "bg-brand-500 text-white shadow-md"
                  : "bg-[var(--bg-elevated)] text-[var(--text-secondary)] hover:bg-brand-500/10 hover:text-brand-400 border border-[var(--border-primary)]",
              )}
              aria-pressed={activeTab === c.id}
            >
              {c.label}
            </button>
          ))}
        </div>

        <motion.div
          key={activeTab}
          initial={{ opacity: 0, y: 5 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.2 }}
          className="grid grid-cols-1 lg:grid-cols-2 gap-6"
        >
          {/* Left: input */}
          <div className="space-y-3">
            <CardHeader
              title={activeCapability.label}
              subtitle={
                <span>
                  <code className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-[var(--bg-elevated)] border border-[var(--border-primary)]">
                    {activeCapability.method} {activeCapability.path}
                  </code>
                </span>
              }
            />
            <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
              {activeCapability.description}
            </p>
            <details className="text-xs">
              <summary className="cursor-pointer text-[var(--text-muted)] hover:text-brand-400">
                Input schema
              </summary>
              <pre className="mt-2 p-2 rounded bg-[var(--bg-elevated)] border border-[var(--border-primary)] text-[10px] font-mono overflow-auto max-h-48">
                {JSON.stringify(activeCapability.inputSchema, null, 2)}
              </pre>
            </details>
            <div>
              <div className="flex items-center justify-between mb-1">
                <label
                  htmlFor={`json-input-${activeTab}`}
                  className="text-xs font-semibold text-[var(--text-secondary)]"
                >
                  Request body (JSON)
                </label>
                <div className="flex gap-1">
                  <Button variant="ghost" size="sm" onClick={loadSample} disabled={running}>
                    <RotateCcw className="w-3 h-3" /> Sample
                  </Button>
                  <Button variant="primary" size="sm" onClick={run} disabled={running}>
                    <Play className="w-3 h-3" /> {running ? "Running…" : "Run"}
                  </Button>
                </div>
              </div>
              <textarea
                id={`json-input-${activeTab}`}
                value={inputs[activeTab]}
                onChange={(e) => setInputs((prev) => ({ ...prev, [activeTab]: e.target.value }))}
                disabled={running}
                spellCheck={false}
                className={cn(
                  "w-full h-64 p-3 rounded-md bg-[var(--bg-elevated)] border border-[var(--border-primary)] text-xs font-mono resize-y focus:outline-none focus:ring-2 focus:ring-brand-500/40",
                  error && "border-red-500/40",
                )}
                aria-label={`JSON input for ${activeCapability.label}`}
              />
            </div>
          </div>

          {/* Right: result */}
          <div className="space-y-3">
            <CardHeader
              title="Result"
              subtitle={
                running ? (
                  <span className="flex items-center gap-1.5 text-brand-400">
                    <span className="w-2 h-2 rounded-full bg-brand-400 animate-pulse" /> Running…
                  </span>
                ) : (
                  <span className="text-[var(--text-muted)]">Last response</span>
                )
              }
            />
            <ResultViewer result={result} error={error} />
          </div>
        </motion.div>
      </Card>

      {/* History */}
      {history.length > 0 && (
        <Card padding="md">
          <CardHeader
            title="Recent runs"
            subtitle="Last 10 calls in this session"
            action={
              <Button variant="ghost" size="sm" onClick={resetAll}>
                Clear
              </Button>
            }
          />
          <div className="space-y-2 mt-3">
            {history.map((r, i) => (
              <div
                key={`${r.startedAt}-${i}`}
                className="flex items-center gap-3 p-2 rounded-md bg-[var(--bg-elevated)] border border-[var(--border-primary)] text-xs"
              >
                <Badge variant={r.success ? "success" : "danger"} size="sm">
                  {r.success ? "OK" : "FAIL"}
                </Badge>
                <code className="font-mono text-[var(--text-primary)] truncate flex-1">
                  {r.capability}
                </code>
                <span className="text-[var(--text-muted)] shrink-0">{r.durationMs}ms</span>
                <span className="text-[var(--text-muted)] shrink-0 hidden sm:inline">
                  {new Date(r.startedAt).toLocaleTimeString()}
                </span>
                {r.error && (
                  <span className="text-red-400 truncate hidden md:inline" title={r.error}>
                    {r.error}
                  </span>
                )}
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
