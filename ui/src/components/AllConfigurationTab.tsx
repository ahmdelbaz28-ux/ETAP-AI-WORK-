/**
 * AllConfigurationTab.tsx — Discoverability surface for hidden config keys.
 *
 * Audit context (2026-08-01):
 *   The existing Settings page exposes ~84 keys via TAB_SECTIONS, but the
 *   .env.example file documents ~173 keys. The remaining ~90 keys are
 *   "hidden" — they exist in the backend config, are referenced by tests or
 *   services, but have no UI surface. This tab closes that gap by listing
 *   every known config key with its category, sensitivity, source, and a
 *   Rotate button for secret-classified keys.
 *
 * Security invariants (enforced in this file):
 *   1. Secret-classified keys are NEVER displayed as raw values. The UI
 *      shows only the key NAME, category, and a boolean "is set" indicator.
 *   2. The Rotate button sends ONLY the key name to the backend. It does
 *      NOT transmit the current value. The backend is responsible for
 *      generating the new value and persisting it.
 *   3. Non-secret keys MAY show their current value (read from the cached
 *      settings object), but only after the user explicitly clicks
 *      "Reveal". This is a discoverability aid, not a primary surface.
 */

import { motion } from "framer-motion";
import {
  AlertTriangle,
  CheckCircle2,
  Eye,
  EyeOff,
  Filter,
  Key,
  Lock,
  RefreshCw,
  Search,
  Settings as SettingsIcon,
  Shield,
  ShieldAlert,
} from "lucide-react";
import { useCallback, useMemo, useState } from "react";
import { Badge, Button, Card, CardHeader } from "../components/ui";
import { useNotify } from "../context/NotificationContext";
import { API_BASE_URL, apiUrl, getCachedSettings } from "../lib/api-config";
import { cn } from "../utils/helpers";

// ─── Types ──────────────────────────────────────────────────────────────────

type ConfigCategory =
  | "security"
  | "database"
  | "ai"
  | "email"
  | "scada"
  | "etap"
  | "edge"
  | "observability"
  | "ratelimit"
  | "feature"
  | "storage"
  | "integration"
  | "misc";

type ConfigEntry = {
  readonly key: string;
  readonly category: ConfigCategory;
  readonly isSecret: boolean;
  readonly description: string;
};

type CategoryMeta = {
  readonly label: string;
  readonly icon: React.ElementType;
  readonly color: string;
};

// ─── Static catalogue ───────────────────────────────────────────────────────
// Source: .env.example (173 keys, audited 2026-08-01). Below is a curated
// subset of the keys that were NOT already exposed in Settings TAB_SECTIONS.
// Each entry is intentionally hand-curated so the description is accurate
// rather than auto-generated from the env var name.

const CATEGORIES: Record<ConfigCategory, CategoryMeta> = {
  security: { label: "Security & Auth", icon: Shield, color: "text-amber-400" },
  database: { label: "Database & Cache", icon: SettingsIcon, color: "text-blue-400" },
  ai: { label: "AI Providers", icon: Key, color: "text-brand-400" },
  email: { label: "Email", icon: SettingsIcon, color: "text-green-400" },
  scada: { label: "SCADA", icon: SettingsIcon, color: "text-purple-400" },
  etap: { label: "ETAP", icon: SettingsIcon, color: "text-cyan-400" },
  edge: { label: "Edge Protection", icon: ShieldAlert, color: "text-red-400" },
  observability: { label: "Observability", icon: Eye, color: "text-indigo-400" },
  ratelimit: { label: "Rate Limiting", icon: AlertTriangle, color: "text-orange-400" },
  feature: { label: "Feature Flags", icon: CheckCircle2, color: "text-emerald-400" },
  storage: { label: "Storage", icon: SettingsIcon, color: "text-teal-400" },
  integration: { label: "Integrations", icon: SettingsIcon, color: "text-pink-400" },
  misc: { label: "Misc", icon: SettingsIcon, color: "text-[var(--text-tertiary)]" },
};

const CONFIG_CATALOG: readonly ConfigEntry[] = [
  // ─── Security & Auth (hidden) ───────────────────────────────────────────
  {
    key: "FERNET_ENCRYPTION_KEY",
    category: "security",
    isSecret: true,
    description: "Fernet symmetric key for at-rest encryption of sensitive DB columns.",
  },
  {
    key: "ENCRYPTION_KEY",
    category: "security",
    isSecret: true,
    description: "Generic AES-256 key used by the legacy encrypt/decrypt helpers.",
  },
  {
    key: "ENVIRONMENT",
    category: "security",
    isSecret: false,
    description: "Runtime environment: development | staging | production.",
  },
  {
    key: "HOST",
    category: "security",
    isSecret: false,
    description: "Bind host for the FastAPI server.",
  },
  {
    key: "PORT",
    category: "security",
    isSecret: false,
    description: "Bind port for the FastAPI server.",
  },
  {
    key: "CSRF_SECRET",
    category: "security",
    isSecret: true,
    description: "HMAC secret for signing CSRF tokens.",
  },
  {
    key: "SESSION_SECRET",
    category: "security",
    isSecret: true,
    description: "Cookie-session signing secret.",
  },

  // ─── Database & Cache (hidden) ──────────────────────────────────────────
  {
    key: "POSTGRES_DB",
    category: "database",
    isSecret: false,
    description: "Postgres database name (docker-compose only).",
  },
  {
    key: "POSTGRES_USER",
    category: "database",
    isSecret: false,
    description: "Postgres username (docker-compose only).",
  },
  {
    key: "POSTGRES_PASSWORD",
    category: "database",
    isSecret: true,
    description: "Postgres password (docker-compose only).",
  },
  {
    key: "MASTRA_DB_URL",
    category: "database",
    isSecret: true,
    description: "Connection string for the Mastra agent-memory store.",
  },

  // ─── AI providers (hidden) ──────────────────────────────────────────────
  {
    key: "ANTHROPIC_MAX_RETRIES",
    category: "ai",
    isSecret: false,
    description: "Max retry attempts for Anthropic API calls.",
  },
  {
    key: "ANTHROPIC_TIMEOUT",
    category: "ai",
    isSecret: false,
    description: "Request timeout (seconds) for Anthropic API calls.",
  },
  {
    key: "ANTHROPIC_VISION_MODEL",
    category: "ai",
    isSecret: false,
    description: "Model name for Anthropic vision requests.",
  },
  {
    key: "BYNARA_BASE_URL",
    category: "ai",
    isSecret: false,
    description: "Base URL for the Bynara LLM provider.",
  },
  {
    key: "BYNARA_MODEL",
    category: "ai",
    isSecret: false,
    description: "Default model name for Bynara requests.",
  },
  {
    key: "CLOUDFLARE_BASE_URL",
    category: "ai",
    isSecret: false,
    description: "Base URL for Cloudflare AI gateway.",
  },
  {
    key: "CLOUDFLARE_MODEL",
    category: "ai",
    isSecret: false,
    description: "Default model name for Cloudflare AI.",
  },
  {
    key: "CLOUDFLARE_ACCOUNT_ID",
    category: "ai",
    isSecret: false,
    description: "Cloudflare account ID for AI gateway.",
  },
  {
    key: "ZENMUX_BASE_URL",
    category: "ai",
    isSecret: false,
    description: "Base URL for the Zenmux router.",
  },
  {
    key: "ZENMUX_MODEL",
    category: "ai",
    isSecret: false,
    description: "Default model for Zenmux.",
  },

  // ─── Email (hidden) ─────────────────────────────────────────────────────
  {
    key: "EMAIL_APP_URL",
    category: "email",
    isSecret: false,
    description: "Public URL used in email body links.",
  },
  {
    key: "EMAIL_BRAND_NAME",
    category: "email",
    isSecret: false,
    description: "Brand name shown in email headers.",
  },
  {
    key: "EMAIL_BRAND_TAGLINE",
    category: "email",
    isSecret: false,
    description: "Brand tagline shown under the logo.",
  },
  {
    key: "EMAIL_BRAND_PRIMARY",
    category: "email",
    isSecret: false,
    description: "Primary brand color (hex) for email template.",
  },
  {
    key: "EMAIL_BRAND_SECONDARY",
    category: "email",
    isSecret: false,
    description: "Secondary brand color (hex).",
  },
  {
    key: "EMAIL_BRAND_ACCENT",
    category: "email",
    isSecret: false,
    description: "Accent brand color (hex).",
  },
  {
    key: "EMAIL_BRAND_LOGO_EMOJI",
    category: "email",
    isSecret: false,
    description: "Emoji used as fallback logo.",
  },
  {
    key: "EMAIL_DASHBOARD_ENABLED",
    category: "email",
    isSecret: false,
    description: "Toggle the Resend email dashboard router.",
  },
  {
    key: "EMAIL_DASHBOARD_ADMIN_ROLES",
    category: "email",
    isSecret: false,
    description: "Comma-separated roles allowed to view the email dashboard.",
  },
  {
    key: "EMAIL_DASHBOARD_RETENTION_DAYS",
    category: "email",
    isSecret: false,
    description: "Days to retain email dashboard records.",
  },
  {
    key: "EMAIL_DIGEST_ENABLED",
    category: "email",
    isSecret: false,
    description: "Toggle daily digest emails.",
  },
  {
    key: "EMAIL_DIGEST_SCHEDULE_DAILY",
    category: "email",
    isSecret: false,
    description: "Cron-like daily schedule for digests.",
  },

  // ─── SCADA (hidden) ─────────────────────────────────────────────────────
  {
    key: "SCADA_SYSTEM_TYPE",
    category: "scada",
    isSecret: false,
    description: "SCADA vendor: zenon | iec61850 | openhab.",
  },
  {
    key: "SCADA_SYNC_INTERVAL_SEC",
    category: "scada",
    isSecret: false,
    description: "Telemetry poll interval (seconds).",
  },

  // ─── ETAP (hidden) ──────────────────────────────────────────────────────
  {
    key: "ETAP_WORKER_URL",
    category: "etap",
    isSecret: false,
    description: "URL of the ETAP worker bridge service.",
  },

  // ─── Edge protection (hidden) ───────────────────────────────────────────
  {
    key: "AKAMAI_ORIGIN_SECRET",
    category: "edge",
    isSecret: true,
    description: "Shared secret between Akamai edge and origin for request verification.",
  },
  {
    key: "CLOUDFLARE_ORIGIN_SECRET",
    category: "edge",
    isSecret: true,
    description: "Shared secret between Cloudflare edge and origin.",
  },
  {
    key: "CF_BLOCKED_COUNTRIES",
    category: "edge",
    isSecret: false,
    description: "Comma-separated ISO country codes to block at the edge.",
  },
  {
    key: "CF_ORIGIN_RATE_LIMIT",
    category: "edge",
    isSecret: false,
    description: "Per-IP rate limit enforced at the Cloudflare edge.",
  },

  // ─── Observability (hidden) ─────────────────────────────────────────────
  {
    key: "HEALTH_CHECK_API_URL",
    category: "observability",
    isSecret: false,
    description: "Upstream health-check probe URL.",
  },
  {
    key: "PROMETHEUS_ENABLED",
    category: "observability",
    isSecret: false,
    description: "Toggle Prometheus metrics export.",
  },
  {
    key: "PROMETHEUS_PORT",
    category: "observability",
    isSecret: false,
    description: "Port for the Prometheus metrics endpoint.",
  },
  {
    key: "OTEL_EXPORTER_OTLP_ENDPOINT",
    category: "observability",
    isSecret: false,
    description: "OpenTelemetry OTLP endpoint URL.",
  },
  {
    key: "OTEL_SERVICE_NAME",
    category: "observability",
    isSecret: false,
    description: "OpenTelemetry service name label.",
  },

  // ─── Rate limiting & circuit breaker (hidden) ───────────────────────────
  {
    key: "RATE_LIMIT_REQUESTS_PER_MINUTE",
    category: "ratelimit",
    isSecret: false,
    description: "Global per-IP rate limit.",
  },
  {
    key: "CIRCUIT_BREAKER_FAILURE_THRESHOLD",
    category: "ratelimit",
    isSecret: false,
    description: "Failure count that opens the circuit breaker.",
  },
  {
    key: "MAX_BODY_SIZE",
    category: "ratelimit",
    isSecret: false,
    description: "Max request body size in bytes.",
  },

  // ─── Feature flags (hidden) ─────────────────────────────────────────────
  {
    key: "ENABLE_ASYNC_EXECUTION",
    category: "feature",
    isSecret: false,
    description: "Toggle async study execution.",
  },
  {
    key: "ENABLE_CACHING",
    category: "feature",
    isSecret: false,
    description: "Toggle study result caching.",
  },
  {
    key: "ENABLE_OBSERVABILITY",
    category: "feature",
    isSecret: false,
    description: "Toggle OpenTelemetry instrumentation.",
  },

  // ─── Storage (hidden) ───────────────────────────────────────────────────
  {
    key: "R2_ACCOUNT_ID",
    category: "storage",
    isSecret: false,
    description: "Cloudflare R2 account ID.",
  },
  {
    key: "R2_ACCESS_KEY_ID",
    category: "storage",
    isSecret: true,
    description: "R2 access key ID.",
  },
  {
    key: "R2_SECRET_ACCESS_KEY",
    category: "storage",
    isSecret: true,
    description: "R2 secret access key.",
  },
  {
    key: "R2_BUCKET_NAME",
    category: "storage",
    isSecret: false,
    description: "R2 bucket name for project artifacts.",
  },

  // ─── Integrations (hidden) ──────────────────────────────────────────────
  {
    key: "VERCEL_ORG_ID",
    category: "integration",
    isSecret: false,
    description: "Vercel org ID for deploy webhooks.",
  },
  {
    key: "VERCEL_TOKEN",
    category: "integration",
    isSecret: true,
    description: "Vercel personal access token.",
  },
  {
    key: "VITE_API_URL",
    category: "integration",
    isSecret: false,
    description: "Frontend build-time API URL override.",
  },
  {
    key: "GITHUB_REPO",
    category: "integration",
    isSecret: false,
    description: "Default repo for code-agent PRs.",
  },
  {
    key: "HF_SPACE_NAME",
    category: "integration",
    isSecret: false,
    description: "Hugging Face Space name.",
  },
  {
    key: "HF_REPO_URL",
    category: "integration",
    isSecret: false,
    description: "Hugging Face repo URL.",
  },
  {
    key: "LANGWATCH_PROJECT",
    category: "integration",
    isSecret: false,
    description: "LangWatch project slug.",
  },
  {
    key: "LANGWATCH_ENDPOINT",
    category: "integration",
    isSecret: false,
    description: "LangWatch OTLP endpoint.",
  },
  {
    key: "SMITHERY_BASE_URL",
    category: "integration",
    isSecret: false,
    description: "Smithery MCP base URL.",
  },

  // ─── Misc (hidden) ──────────────────────────────────────────────────────
  {
    key: "MAX_WORKERS",
    category: "misc",
    isSecret: false,
    description: "Worker process count for the study executor.",
  },
  {
    key: "CACHE_SIZE_MB",
    category: "misc",
    isSecret: false,
    description: "In-memory cache size budget (MB).",
  },
  {
    key: "CACHE_DEFAULT_TTL",
    category: "misc",
    isSecret: false,
    description: "Default TTL for cache entries (seconds).",
  },
] as const;

// ─── Helpers ────────────────────────────────────────────────────────────────

function isSetInCache(key: string): boolean {
  try {
    const settings = getCachedSettings();
    const v = settings[key];
    return typeof v === "string" && v.length > 0;
  } catch {
    return false;
  }
}

function safeGetValue(key: string, isSecret: boolean): string {
  if (isSecret) return "";
  try {
    return getCachedSettings()[key] ?? "";
  } catch {
    return "";
  }
}

// ─── Sub-components ─────────────────────────────────────────────────────────

function ConfigRow({ entry }: { readonly entry: ConfigEntry }) {
  const { notify } = useNotify();
  const [revealed, setRevealed] = useState(false);
  const [rotating, setRotating] = useState(false);
  const [isSet, setIsSet] = useState<boolean>(() => isSetInCache(entry.key));

  const handleRotate = useCallback(async () => {
    setRotating(true);
    try {
      // Send ONLY the key name. Never transmit the current value.
      const res = await fetch(apiUrl("/api/v1/settings/rotate"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ key: entry.key }),
      });
      if (!res.ok) {
        const text = await res.text().catch(() => "");
        throw new Error(`HTTP ${res.status}: ${text || res.statusText}`);
      }
      setIsSet(true);
      setRevealed(false);
      notify("success", `Rotated ${entry.key}. New value is server-side only.`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Rotate failed";
      notify("error", msg);
    } finally {
      setRotating(false);
    }
  }, [entry.key, notify]);

  const value = safeGetValue(entry.key, entry.isSecret);
  const CategoryIcon = CATEGORIES[entry.category].icon;

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      className="flex items-start gap-3 p-3 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] hover:bg-[var(--bg-elevated)] transition-colors"
    >
      <div className={cn("p-1.5 rounded-md bg-brand-500/5", CATEGORIES[entry.category].color)}>
        <CategoryIcon className="w-3.5 h-3.5" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <code className="text-sm font-mono text-[var(--text-primary)] truncate">{entry.key}</code>
          {entry.isSecret ? (
            <Badge variant="warning" size="sm" dot>
              secret
            </Badge>
          ) : (
            <Badge variant="neutral" size="sm">
              {entry.category}
            </Badge>
          )}
          {isSet ? (
            <Badge variant="success" size="sm" dot>
              set
            </Badge>
          ) : (
            <Badge variant="default" size="sm">
              unset
            </Badge>
          )}
        </div>
        <p className="text-xs text-[var(--text-tertiary)] mt-1">{entry.description}</p>
        {!entry.isSecret && value && (
          <div className="mt-2 flex items-center gap-2 text-xs">
            <button
              type="button"
              onClick={() => setRevealed((r) => !r)}
              className="inline-flex items-center gap-1 text-[var(--text-muted)] hover:text-[var(--text-primary)]"
            >
              {revealed ? <EyeOff className="w-3 h-3" /> : <Eye className="w-3 h-3" />}
              {revealed ? "Hide" : "Reveal"}
            </button>
            {revealed && (
              <code className="font-mono text-[var(--text-secondary)] truncate max-w-full">
                {value}
              </code>
            )}
          </div>
        )}
      </div>
      {entry.isSecret && (
        <Button
          variant="outline"
          size="sm"
          icon={RefreshCw}
          loading={rotating}
          onClick={handleRotate}
          title="Rotate this secret on the backend. The new value never leaves the server."
        >
          Rotate
        </Button>
      )}
      {!entry.isSecret && (
        <Lock className="w-3 h-3 text-[var(--text-tertiary)] opacity-40" aria-hidden />
      )}
    </motion.div>
  );
}

// ─── Main component ─────────────────────────────────────────────────────────

export function AllConfigurationTab() {
  const [query, setQuery] = useState("");
  const [activeCategory, setActiveCategory] = useState<ConfigCategory | "all">("all");
  const [showSetOnly, setShowSetOnly] = useState(false);
  const [showSecretsOnly, setShowSecretsOnly] = useState(false);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return CONFIG_CATALOG.filter((e) => {
      if (activeCategory !== "all" && e.category !== activeCategory) return false;
      if (showSetOnly && !isSetInCache(e.key)) return false;
      if (showSecretsOnly && !e.isSecret) return false;
      if (q && !e.key.toLowerCase().includes(q) && !e.description.toLowerCase().includes(q)) {
        return false;
      }
      return true;
    });
  }, [query, activeCategory, showSetOnly, showSecretsOnly]);

  const stats = useMemo(() => {
    const total = CONFIG_CATALOG.length;
    const secrets = CONFIG_CATALOG.filter((e) => e.isSecret).length;
    const set = CONFIG_CATALOG.filter((e) => isSetInCache(e.key)).length;
    return { total, secrets, set, unset: total - set };
  }, []);

  const categories: readonly (ConfigCategory | "all")[] = useMemo(() => {
    const present = new Set<ConfigCategory>();
    for (const e of CONFIG_CATALOG) present.add(e.category);
    return ["all", ...Array.from(present).sort((a, b) => a.localeCompare(b))] as const;
  }, []);

  return (
    <Card padding="md">
      <CardHeader
        title="All Configuration Keys"
        subtitle={`${stats.total} keys · ${stats.secrets} secret · ${stats.set} set · ${stats.unset} unset`}
        icon={<SettingsIcon className="w-4 h-4" />}
        action={
          <Badge variant="brand" size="sm">
            audit 2026-08-01
          </Badge>
        }
      />

      {/* Controls */}
      <div className="space-y-3 mb-4">
        <div className="flex items-center gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-muted)]" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search by key name or description…"
              className="w-full pl-9 pr-3 py-2 bg-[var(--bg-input)] border border-[var(--border-primary)] rounded-lg text-sm text-[var(--text-primary)] focus:border-[var(--color-brand-500)] focus:ring-1 focus:ring-[var(--color-brand-500)]/30 outline-none"
            />
          </div>
          <Button
            variant={showSecretsOnly ? "primary" : "ghost"}
            size="sm"
            icon={ShieldAlert}
            onClick={() => setShowSecretsOnly((v) => !v)}
          >
            Secrets only
          </Button>
          <Button
            variant={showSetOnly ? "primary" : "ghost"}
            size="sm"
            icon={CheckCircle2}
            onClick={() => setShowSetOnly((v) => !v)}
          >
            Set only
          </Button>
        </div>

        <div className="flex items-center gap-1.5 flex-wrap">
          <Filter className="w-3.5 h-3.5 text-[var(--text-tertiary)]" />
          {categories.map((c) => {
            const meta = c === "all" ? null : CATEGORIES[c];
            const isActive = activeCategory === c;
            return (
              <button
                key={c}
                type="button"
                onClick={() => setActiveCategory(c)}
                className={cn(
                  "px-2.5 py-1 text-xs rounded-md border transition-colors",
                  isActive
                    ? "bg-brand-500/15 border-brand-500/40 text-brand-300"
                    : "bg-[var(--bg-elevated)] border-[var(--border-primary)] text-[var(--text-secondary)] hover:bg-[var(--bg-primary)]",
                )}
              >
                {meta ? meta.label : "All"}
              </button>
            );
          })}
        </div>
      </div>

      {/* List */}
      <div className="space-y-2 max-h-[60vh] overflow-y-auto pr-1">
        {filtered.length === 0 ? (
          <div className="text-center py-10 text-sm text-[var(--text-tertiary)]">
            No keys match the current filters.
          </div>
        ) : (
          filtered.map((entry) => <ConfigRow key={entry.key} entry={entry} />)
        )}
      </div>

      <p className="text-xs text-[var(--text-tertiary)] mt-4 leading-relaxed">
        <span>This tab is a discoverability surface, not an editor. Secret-classified keys never display their value — the Rotate button sends only the key name to </span>
        <code className="mx-1 font-mono text-[var(--text-muted)]">
          POST {API_BASE_URL}/api/v1/settings/rotate
        </code>
        <span> and the new value stays server-side. Non-secret values may be revealed on demand for debugging.</span>
      </p>
    </Card>
  );
}
