import { motion } from "framer-motion";
import { AlertTriangle, Bot, Save, SlidersHorizontal } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Button, Card, CardHeader, Toggle } from "../components/ui";
import { ContextHelpButton } from "../components/help/ContextHelpButton";
import { useNotify } from "../context/NotificationContext";
import { API_BASE_URL } from "../lib/api-config";
import { getAuthToken } from "../lib/tokenStorage";
import { cn } from "../utils/helpers";

// ─── Types ───────────────────────────────────────────────────────────

interface AIConfig {
  model_cascade: string;
  temperature: number;
  max_tokens: number;
  fallback_notifications: boolean;
}

const MODEL_CASCADES = [
  { id: "fast-cheap", label: "Fast & Cheap (GPT-4o-mini → Haiku)", description: "Optimized for speed and cost" },
  { id: "balanced", label: "Balanced (GPT-4o → Sonnet)", description: "Best trade-off of quality and speed" },
  { id: "premium", label: "Premium (GPT-4o → Claude Opus)", description: "Highest quality, highest cost" },
  { id: "open-source", label: "Open Source (Llama 3.1 → Qwen 3)", description: "Self-hosted, no vendor lock-in" },
  { id: "code-focused", label: "Code Focused (DeepSeek V4 → Qwen Coder)", description: "Optimized for engineering code" },
];

const DEFAULT_CONFIG: AIConfig = {
  model_cascade: "balanced",
  temperature: 0.3,
  max_tokens: 4096,
  fallback_notifications: true,
};

// ─── Component ───────────────────────────────────────────────────────

export default function AISettingsPanel() {
  const { notify } = useNotify();
  const [config, setConfig] = useState<AIConfig>(DEFAULT_CONFIG);
  const [original, setOriginal] = useState<AIConfig>(DEFAULT_CONFIG);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch current config
  const fetchConfig = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const token = getAuthToken();
      const r = await fetch(`${API_BASE_URL}/api/v1/copilot/config`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        signal: AbortSignal.timeout(8000),
      });
      if (!r.ok) {
        const text = await r.text().catch(() => "Unknown error");
        throw new Error(`API ${r.status}: ${text.substring(0, 100)}`);
      }
      const data = await r.json();
      const fetched: AIConfig = {
        model_cascade: data.model_cascade ?? DEFAULT_CONFIG.model_cascade,
        temperature: data.temperature ?? DEFAULT_CONFIG.temperature,
        max_tokens: data.max_tokens ?? DEFAULT_CONFIG.max_tokens,
        fallback_notifications: data.fallback_notifications ?? DEFAULT_CONFIG.fallback_notifications,
      };
      setConfig(fetched);
      setOriginal(fetched);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchConfig();
  }, [fetchConfig]);

  // Save config
  const handleSave = async () => {
    setSaving(true);
    try {
      const token = getAuthToken();
      const r = await fetch(`${API_BASE_URL}/api/v1/copilot/config`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(config),
        signal: AbortSignal.timeout(8000),
      });
      if (!r.ok) {
        const text = await r.text().catch(() => "Unknown error");
        throw new Error(`API ${r.status}: ${text.substring(0, 100)}`);
      }
      setOriginal({ ...config });
      notify("success", "AI copilot configuration saved");
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      notify("error", `Failed to save AI config: ${msg}`);
    } finally {
      setSaving(false);
    }
  };

  const hasChanges = JSON.stringify(config) !== JSON.stringify(original);

  // ─── Loading state ────────────────────────────────────────────────
  if (loading && error === null) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-[var(--accent-primary)] border-t-transparent rounded-full animate-spin" />
          <span className="text-sm text-[var(--text-muted)]">Loading AI configuration…</span>
        </div>
      </div>
    );
  }

  // ─── Error state ──────────────────────────────────────────────────
  if (error && loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center max-w-md">
          <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-3" />
          <p className="text-sm text-[var(--text-secondary)] mb-2">Failed to load AI configuration</p>
          <p className="text-xs text-[var(--text-muted)] mb-4 font-mono">{error}</p>
          <Button variant="secondary" size="sm" onClick={fetchConfig}>
            Retry
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between"
      >
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-brand-500/10 border border-brand-500/20">
            <Bot className="w-5 h-5 text-brand-400" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-[var(--text-primary)]">AI Copilot Settings</h2>
            <div className="flex items-center gap-2">
              <p className="text-sm text-[var(--text-tertiary)]">Model selection, temperature & token limits</p>
              <ContextHelpButton contextId="ai.copilot-settings" />
            </div>
          </div>
        </div>
        <Button variant="primary" size="sm" icon={Save} loading={saving} onClick={handleSave} disabled={!hasChanges}>
          Save Changes
        </Button>
      </motion.div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Model Cascade */}
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
          <Card padding="md">
            <CardHeader
              title="Model Cascade"
              subtitle="Primary and fallback LLM selection"
              icon={<Bot className="w-4 h-4" />}
            />
            <div className="space-y-3">
              {MODEL_CASCADES.map((cascade) => (
                <label
                  key={cascade.id}
                  htmlFor={`model-cascade-${cascade.id}`}
                  className={cn(
                    "flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-all",
                    config.model_cascade === cascade.id
                      ? "bg-brand-500/10 border-brand-500/30"
                      : "bg-[var(--bg-primary)] border-[var(--border-primary)] hover:border-brand-500/30",
                  )}
                >
                  <input
                    id={`model-cascade-${cascade.id}`}
                    type="radio"
                    name="model-cascade"
                    value={cascade.id}
                    checked={config.model_cascade === cascade.id}
                    onChange={() => setConfig({ ...config, model_cascade: cascade.id })}
                    className="mt-0.5 accent-brand-500"
                  />
                  <div>
                    <p className="text-sm font-medium text-[var(--text-primary)]">{cascade.label}</p>
                    <p className="text-xs text-[var(--text-muted)] mt-0.5">{cascade.description}</p>
                  </div>
                </label>
              ))}
            </div>
          </Card>
        </motion.div>

        {/* Temperature & Tokens */}
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
          <Card padding="md">
            <CardHeader
              title="Generation Parameters"
              subtitle="Temperature & token limits"
              icon={<SlidersHorizontal className="w-4 h-4" />}
            />
            <div className="space-y-6">
              {/* Temperature slider */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <label htmlFor="ai-temperature" className="text-sm font-medium text-[var(--text-secondary)]">Temperature</label>
                  <span className="text-sm font-mono text-[var(--text-primary)]">{config.temperature.toFixed(2)}</span>
                </div>
                <input
                  id="ai-temperature"
                  type="range"
                  min={0}
                  max={100}
                  step={1}
                  value={config.temperature * 100}
                  onChange={(e) => setConfig({ ...config, temperature: Number(e.target.value) / 100 })}
                  className="w-full h-2 rounded-full appearance-none bg-[var(--border-primary)] cursor-pointer accent-brand-500"
                />
                <div className="flex justify-between mt-1">
                  <span className="text-xs text-[var(--text-muted)]">0.0 (deterministic)</span>
                  <span className="text-xs text-[var(--text-muted)]">1.0 (creative)</span>
                </div>
              </div>

              {/* Max Tokens slider */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <label htmlFor="ai-max-tokens" className="text-sm font-medium text-[var(--text-secondary)]">Max Tokens</label>
                  <span className="text-sm font-mono text-[var(--text-primary)]">{config.max_tokens.toLocaleString()}</span>
                </div>
                <input
                  id="ai-max-tokens"
                  type="range"
                  min={0}
                  max={100}
                  step={1}
                  value={((config.max_tokens - 256) / (16384 - 256)) * 100}
                  onChange={(e) => {
                    const val = Math.round(256 + (Number(e.target.value) / 100) * (16384 - 256));
                    // Snap to nearest power of 2 for clean values
                    const snapped = Math.pow(2, Math.round(Math.log2(val)));
                    setConfig({ ...config, max_tokens: Math.min(16384, Math.max(256, snapped)) });
                  }}
                  className="w-full h-2 rounded-full appearance-none bg-[var(--border-primary)] cursor-pointer accent-brand-500"
                />
                <div className="flex justify-between mt-1">
                  <span className="text-xs text-[var(--text-muted)]">256</span>
                  <span className="text-xs text-[var(--text-muted)]">16,384</span>
                </div>
              </div>

              {/* Fallback notifications toggle */}
              <div className="pt-2 border-t border-[var(--border-primary)]">
                <Toggle
                  checked={config.fallback_notifications}
                  onChange={(checked) => setConfig({ ...config, fallback_notifications: checked })}
                  label="Fallback Model Notifications"
                  description="Show a notification when the AI copilot falls back to a secondary model"
                />
              </div>

              {/* Config summary */}
              <div className="p-3 bg-[var(--bg-elevated)] rounded-lg border border-[var(--border-primary)]">
                <p className="text-xs text-[var(--text-muted)] mb-2 font-medium">Active Configuration</p>
                <div className="space-y-1.5 text-xs">
                  <div className="flex justify-between">
                    <span className="text-[var(--text-tertiary)]">Cascade</span>
                    <span className="text-[var(--text-primary)]">
                      {MODEL_CASCADES.find((c) => c.id === config.model_cascade)?.label ?? config.model_cascade}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[var(--text-tertiary)]">Temperature</span>
                    <span className="text-[var(--text-primary)] font-mono">{config.temperature.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[var(--text-tertiary)]">Max Tokens</span>
                    <span className="text-[var(--text-primary)] font-mono">{config.max_tokens.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[var(--text-tertiary)]">Fallback Alerts</span>
                    <span className={cn("font-mono", config.fallback_notifications ? "text-green-400" : "text-[var(--text-muted)]")}>
                      {config.fallback_notifications ? "On" : "Off"}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </Card>
        </motion.div>
      </div>

      {/* Unsaved changes indicator */}
      {hasChanges && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="fixed bottom-4 left-1/2 -translate-x-1/2 z-50 flex items-center gap-3 px-4 py-2.5 rounded-xl bg-[var(--bg-card)] border border-[var(--border-primary)] shadow-lg"
        >
          <span className="text-sm text-[var(--text-secondary)]">Unsaved changes</span>
          <Button variant="ghost" size="sm" onClick={() => setConfig({ ...original })}>
            Discard
          </Button>
          <Button variant="primary" size="sm" icon={Save} loading={saving} onClick={handleSave}>
            Save
          </Button>
        </motion.div>
      )}
    </div>
  );
}
