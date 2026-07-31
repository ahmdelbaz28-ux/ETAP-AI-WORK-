import { motion } from "framer-motion";
import { Brain, Search, AlertTriangle, Loader2, FileCode, Share2, ArrowRight, Info } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { ContextHelpButton } from "../components/help/ContextHelpButton";
import { Badge, Card, CardHeader } from "../components/ui";
import { useNotify } from "../context/NotificationContext";
import { cn } from "../utils/helpers";
import { API_BASE_URL } from "../lib/api-config";

interface ContextResult {
  snippet: string;
  file: string;
  score: number;
  line_start: number;
  line_end: number;
}

interface ImpactResult {
  component: string;
  affected_components: Array<{ name: string; impact: string; severity: string }>;
  max_depth: number;
}

export default function ContextEngine() {
  const { t } = useTranslation();
  const notify = useNotify();
  const [query, setQuery] = useState("");
  const [component, setComponent] = useState("");
  const [topK, setTopK] = useState(5);
  const [maxDepth, setMaxDepth] = useState(2);
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState<"retrieve" | "impact">("retrieve");
  const [results, setResults] = useState<ContextResult[] | null>(null);
  const [impactResult, setImpactResult] = useState<ImpactResult | null>(null);

  const handleRetrieve = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setResults(null);
    try {
      const token = localStorage.getItem("authToken");
      const res = await fetch(`${API_BASE_URL}/api/v1/context/retrieve`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ query: query.trim(), top_k: topK, max_tokens: 2000 }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setResults(data.results || data.snippets || []);
    } catch (err: any) {
      notify.error(err.message || "Failed to retrieve context");
    } finally {
      setLoading(false);
    }
  };

  const handleImpact = async () => {
    if (!component.trim()) return;
    setLoading(true);
    setImpactResult(null);
    try {
      const token = localStorage.getItem("authToken");
      const res = await fetch(`${API_BASE_URL}/api/v1/context/impact`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ component: component.trim(), max_depth: maxDepth }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setImpactResult(data);
    } catch (err: any) {
      notify.error(err.message || "Failed to analyze impact");
    } finally {
      setLoading(false);
    }
  };

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)] flex items-center gap-2">
            <Brain className="w-6 h-6 text-brand-500" />
            {t("contextEngine.title") || "Context Engine"}
          </h1>
          <p className="text-sm text-[var(--text-muted)] mt-1">
            {t("contextEngine.description") || "AI-powered code retrieval and dependency impact analysis"}
          </p>
        </div>
        <ContextHelpButton contextId="context-engine" />
      </div>

      {/* Mode Toggle */}
      <div className="flex gap-2 bg-[var(--bg-elevated)] p-1 rounded-lg w-fit border border-[var(--border-primary)]">
        <button
          onClick={() => setMode("retrieve")}
          className={cn(
            "flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-all",
            mode === "retrieve"
              ? "bg-brand-600 text-white shadow-sm"
              : "text-[var(--text-muted)] hover:text-[var(--text-primary)]",
          )}
          type="button"
        >
          <Search className="w-4 h-4" />
          Code Retrieval
        </button>
        <button
          onClick={() => setMode("impact")}
          className={cn(
            "flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-all",
            mode === "impact"
              ? "bg-brand-600 text-white shadow-sm"
              : "text-[var(--text-muted)] hover:text-[var(--text-primary)]",
          )}
          type="button"
        >
          <Share2 className="w-4 h-4" />
          Impact Analysis
        </button>
      </div>

      <Card>
        <CardHeader>
          <h2 className="text-lg font-semibold text-[var(--text-primary)]">
            {mode === "retrieve" ? "Code Snippet Retrieval" : "Dependency Impact Analysis"}
          </h2>
        </CardHeader>
        <div className="p-4 space-y-4">
          {mode === "retrieve" ? (
            <>
              <div className="flex gap-3">
                <input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search for code patterns, functions, or documentation..."
                  className="flex-1 px-4 py-2.5 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:ring-2 focus:ring-brand-500/50"
                  onKeyDown={(e) => e.key === "Enter" && handleRetrieve()}
                />
                <div className="flex items-center gap-2">
                  <label className="text-xs text-[var(--text-muted)]">Top K:</label>
                  <select
                    value={topK}
                    onChange={(e) => setTopK(Number(e.target.value))}
                    className="px-2 py-2 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] text-[var(--text-primary)] text-sm"
                  >
                    {[3, 5, 10, 20].map((n) => (
                      <option key={n} value={n}>{n}</option>
                    ))}
                  </select>
                </div>
                <button
                  onClick={handleRetrieve}
                  disabled={loading || !query.trim()}
                  className="flex items-center gap-2 px-5 py-2.5 bg-brand-600 hover:bg-brand-500 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg font-medium transition-all"
                  type="button"
                >
                  {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
                  Search
                </button>
              </div>
            </>
          ) : (
            <>
              <div className="flex gap-3">
                <input
                  type="text"
                  value={component}
                  onChange={(e) => setComponent(e.target.value)}
                  placeholder="Enter component name (e.g., LoadFlowEngine, Bus)..."
                  className="flex-1 px-4 py-2.5 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:ring-2 focus:ring-brand-500/50"
                  onKeyDown={(e) => e.key === "Enter" && handleImpact()}
                />
                <div className="flex items-center gap-2">
                  <label className="text-xs text-[var(--text-muted)]">Max Depth:</label>
                  <select
                    value={maxDepth}
                    onChange={(e) => setMaxDepth(Number(e.target.value))}
                    className="px-2 py-2 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] text-[var(--text-primary)] text-sm"
                  >
                    {[1, 2, 3, 5].map((n) => (
                      <option key={n} value={n}>{n}</option>
                    ))}
                  </select>
                </div>
                <button
                  onClick={handleImpact}
                  disabled={loading || !component.trim()}
                  className="flex items-center gap-2 px-5 py-2.5 bg-brand-600 hover:bg-brand-500 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg font-medium transition-all"
                  type="button"
                >
                  {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Share2 className="w-4 h-4" />}
                  Analyze
                </button>
              </div>
            </>
          )}
        </div>
      </Card>

      {/* Results */}
      {results && results.length > 0 && (
        <Card>
          <CardHeader>
            <h2 className="text-lg font-semibold text-[var(--text-primary)] flex items-center gap-2">
              <FileCode className="w-5 h-5 text-brand-500" />
              Results ({results.length})
            </h2>
          </CardHeader>
          <div className="p-4 space-y-3">
            {results.map((r, i) => (
              <div key={i} className="p-3 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-elevated)] space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-[var(--text-primary)]">{r.file}</span>
                  <Badge variant={r.score > 0.8 ? "success" : r.score > 0.5 ? "warning" : "default"}>
                    {(r.score * 100).toFixed(0)}% match
                  </Badge>
                </div>
                <pre className="text-xs text-[var(--text-secondary)] bg-[var(--bg-primary)] p-2 rounded overflow-x-auto max-h-32">
                  <code>{r.snippet}</code>
                </pre>
                <div className="text-xs text-[var(--text-muted)]">
                  Lines {r.line_start}-{r.line_end}
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      {impactResult && (
        <Card>
          <CardHeader>
            <h2 className="text-lg font-semibold text-[var(--text-primary)] flex items-center gap-2">
              <Share2 className="w-5 h-5 text-brand-500" />
              Impact Analysis: {impactResult.component}
            </h2>
          </CardHeader>
          <div className="p-4 space-y-3">
            {impactResult.affected_components.length === 0 ? (
              <div className="flex items-center gap-2 p-3 rounded-lg bg-green-500/10 text-green-400 text-sm">
                <Info className="w-4 h-4" />
                No affected components found — {impactResult.component} is isolated.
              </div>
            ) : (
              impactResult.affected_components.map((ac, i) => (
                <div key={i} className="flex items-center justify-between p-3 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-elevated)]">
                  <div className="flex items-center gap-3">
                    <ArrowRight className="w-4 h-4 text-[var(--text-muted)]" />
                    <span className="text-sm font-medium text-[var(--text-primary)]">{ac.name}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant={ac.severity === "high" ? "error" : ac.severity === "medium" ? "warning" : "default"}>
                      {ac.severity}
                    </Badge>
                    <span className="text-xs text-[var(--text-muted)]">{ac.impact}</span>
                  </div>
                </div>
              ))
            )}
            <div className="text-xs text-[var(--text-muted)]">Max depth: {impactResult.max_depth}</div>
          </div>
        </Card>
      )}

      {results && results.length === 0 && !loading && (
        <Card>
          <div className="p-8 text-center">
            <AlertTriangle className="w-8 h-8 text-amber-400 mx-auto mb-2" />
            <p className="text-sm text-[var(--text-muted)]">No results found for your query.</p>
          </div>
        </Card>
      )}
    </motion.div>
  );
}