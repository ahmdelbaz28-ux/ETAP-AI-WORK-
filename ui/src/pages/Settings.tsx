// NOSONAR(typescript:S3776,typescript:S2004,typescript:S6478,typescript:S6479,typescript:S3358,typescript:S6759,typescript:S6551,typescript:S2486,typescript:S6819): UI components are intentionally complex for feature-rich DX
import { motion } from "framer-motion";
import {
  Bot,
  CheckCircle2,
  ChevronRight,
  Code,
  Database,
  Download,
  ExternalLink,
  Eye,
  Gauge,
  Info,
  Key,
  Link2,
  Loader2,
  Save,
  Shield,
  Trash2,
  Upload,
  Wrench,
  XCircle,
  Zap,
} from "lucide-react"; // QUALITY v2.1.1: removed unused Terminal
import { useCallback, useEffect, useState } from "react";
import { ProviderLogo } from "../components/ProviderLogo";
import { Button, Card, CardHeader, TabPanels, Tabs, Toggle, useTabState } from "../components/ui";
import { useNotify } from "../context/NotificationContext";
import { getCachedSettings, isSecretField } from "../lib/api-config";
import { testProviderConnection } from "../lib/llm-chat";
import { cn } from "../utils/helpers";

import AISettingsPanel from "../components/AISettingsPanel";
import EngineeringEngineSettings from "../components/EngineeringEngineSettings";
import NotificationSettings from "../components/NotificationSettings";
import StorageManagement from "../components/StorageManagement";
import { ProviderKeysPanel } from "../components/settings/ProviderKeysPanel";
import { AgentsSkillsPromptsPanel } from "../components/settings/AgentsSkillsPromptsPanel";
import { AgentsTab } from "./settings/AgentsTab";
import { SkillsPromptsTab } from "./settings/SkillsPromptsTab";
import { McpServersTab } from "./settings/McpServersTab";
import { ImportExportTab } from "./settings/ImportExportTab";
import { useChatFirstUi } from "../lib/chat-first-ui";
import { SecurityFlagsPanel } from "../components/settings/SecurityFlagsPanel";
import { ContextHelpButton } from "../components/help/ContextHelpButton";
import {
  type VisionKeyConfig,
  deleteVisionKey,
  fetchVisionKeys,
  saveVisionKey,
  testVisionKey,
} from "../lib/api";

// ─── Provider card helpers ─────────────────────────────────────────
// Extracted from the inline `POPULAR_PROVIDERS.map(...)` callback in
// <Settings/> to keep the callback's cognitive complexity under 15
// (SonarCloud S3776). Each helper is a small, flat function.

type ProviderStatus = "ok" | "fail" | null | undefined;

function providerCardClass(hasKey: boolean, isFree: boolean): string {
  const base = "p-4 rounded-xl border-2 transition-all bg-[var(--bg-elevated)] relative";
  if (hasKey) return cn(base, "border-green-500/30");
  if (isFree) return cn(base, "border-green-500/20 hover:border-green-500/40");
  return cn(base, "border-[var(--border-primary)] hover:border-brand-500/40");
}

function providerButtonClass(hasKey: boolean, isTesting: boolean, status: ProviderStatus): string {
  const base =
    "w-full flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all";
  if (!hasKey || isTesting) {
    return cn(
      base,
      "bg-[var(--bg-primary)] text-[var(--text-muted)] cursor-not-allowed border border-[var(--border-primary)]",
    );
  }
  if (status === "ok") return cn(base, "bg-green-600 hover:bg-green-500 text-white");
  if (status === "fail") return cn(base, "bg-red-600 hover:bg-red-500 text-white");
  return cn(base, "bg-brand-600 hover:bg-brand-500 text-white");
}

function providerButtonContent(isTesting: boolean, status: ProviderStatus): React.ReactNode {
  if (isTesting)
    return (
      <>
        <Loader2 className="w-3.5 h-3.5 animate-spin" /> Testing...
      </>
    );
  if (status === "ok")
    return (
      <>
        <CheckCircle2 className="w-3.5 h-3.5" /> Valid ✓
      </>
    );
  if (status === "fail")
    return (
      <>
        <XCircle className="w-3.5 h-3.5" /> Failed — Retry
      </>
    );
  return (
    <>
      <Zap className="w-3.5 h-3.5" /> Test &amp; Save
    </>
  );
}


const SETTINGS_SCHEMA = {
  requiredKeys: ["OPENAI_MODEL", "OPENAI_BASE_URL", "ENGINEERING_SERVICE_URL"],
  maxFields: 100,
  maxKeyLength: 50,
  maxValueLength: 1000,
};

import {
  POPULAR_PROVIDERS,
  type PopularProvider,
  type ProviderModel,
  type ProviderApiType,
} from "../lib/providers";

export { POPULAR_PROVIDERS, type PopularProvider, type ProviderModel, type ProviderApiType };

function getDefaults(): Record<string, string> {
  return {
    API_KEY_SECRET: "",
    JWT_SECRET_KEY: "",
    OPENAI_API_KEY: "",
    OPENAI_MODEL: "gpt-4o-mini",
    OPENAI_BASE_URL: "https://api.openai.com/v1",
    NVIDIA_API_KEY: "",
    NVIDIA_MODEL: "meta/llama-3.1-8b-instruct",
    NVIDIA_BASE_URL: "https://integrate.api.nvidia.com/v1",
    // Additional LLM providers (added 2026-07-07)
    RENDER_API_KEY: "",
    RENDER_MODEL: "gpt-4o-mini",
    RENDER_BASE_URL: "https://api.render.com/v1",
    ZENMUX_API_KEY: "",
    ZENMUX_MODEL: "gpt-4o-mini",
    ZENMUX_BASE_URL: "https://api.zenmux.ai/v1",
    FIREWORKS_API_KEY: "",
    FIREWORKS_MODEL: "accounts/fireworks/models/kimi-k2p7-code",
    FIREWORKS_BASE_URL: "https://api.fireworks.ai/inference/v1",
    GITHUB_MODELS_API_KEY: "",
    GITHUB_MODELS_MODEL: "gpt-4o",
    GITHUB_MODELS_BASE_URL: "https://models.inference.ai.azure.com/v1",
    OPENMODEL_API_KEY: "",
    OPENMODEL_MODEL: "gpt-4o",
    OPENMODEL_BASE_URL: "https://api.openmodel.ai/v1",
    MODAL_API_KEY: "",
    MODAL_MODEL: "zai-org/GLM-5.1-FP8",
    MODAL_BASE_URL: "https://api.us-west-2.modal.direct/v1",
    // Additional LLM providers (added 2026-07-08)
    BYNARA_API_KEY: "",
    BYNARA_MODEL: "mimo-v2.5-free",
    BYNARA_BASE_URL: "https://router.bynara.id/v1",
    CLOUDFLARE_API_KEY: "",
    CLOUDFLARE_ACCOUNT_ID: "",
    CLOUDFLARE_MODEL: "@cf/moonshotai/kimi-k2.6",
    CLOUDFLARE_BASE_URL: "https://api.cloudflare.com/client/v4/accounts/PLACEHOLDER/ai/v1",
    QWEN_API_KEY: "",
    QWEN_BASE_URL: "",
    GLM_API_KEY: "",
    GLM_BASE_URL: "",
    ENGINEERING_SERVICE_URL: "http://localhost:8000",
    ENGINEERING_SERVICE_API_KEY: "",
    ENGINEERING_SERVICE_TIMEOUT_MS: "30000",
    MASTRA_DB_URL: "file:./mastra.db",
    DATABASE_URL: "",
    REDIS_URL: "",
    LANGWATCH_API_KEY: "",
    LANGWATCH_PROJECT: "AhmedETAP",
    LANGWATCH_ENDPOINT: "https://app.langwatch.ai",
    SMITHERY_API_KEY: "",
    SMITHERY_BASE_URL: "https://api.smithery.ai",
    HF_TOKEN: "",
    HF_SPACE_NAME: "ahmdelbaz28/AhmedETAP-Platform",
    HF_REPO_URL: "https://huggingface.co/spaces/ahmdelbaz28/AhmedETAP-Platform",
    GITHUB_TOKEN: "",
    GITHUB_REPO: "ahmdelbaz28-ux/ETAP-AI-WORK-",
    VERCEL_PROJECT_ID: "",
    VERCEL_ACCESS_TOKEN: "",
    HEALTH_CHECK_API_URL: "",
    PROMETHEUS_ENABLED: "",
    PROMETHEUS_PORT: "9090",
    RATE_LIMIT_REQUESTS_PER_MINUTE: "60",
    CIRCUIT_BREAKER_FAILURE_THRESHOLD: "3",
    MAX_BODY_SIZE: "100000",
    ETAP_LICENSE_PATH: "",
    ETAP_WORKER_URL: "",
    VAULT_ADDR: "",
    VAULT_TOKEN: "",
    SMTP_SERVER: "",
    SMTP_PORT: "587",
    SMTP_USERNAME: "",
    ALERT_EMAIL_TO: "",
    ENABLE_ASYNC_EXECUTION: "true",
    ENABLE_CACHING: "true",
    ENABLE_OBSERVABILITY: "true",
    MAX_WORKERS: "4",
    CACHE_SIZE_MB: "512",
    CACHE_DEFAULT_TTL: "3600",
    // SCADA zenon Configs
    SCADA_SYSTEM_TYPE: "Copa-Data zenon SCADA",
    SCADA_SERVER_URL: "http://localhost:8080/zenon",
    SCADA_PROJECT_NAME: "ETAP_Zenon_Sync",
    SCADA_SYNC_INTERVAL_SEC: "10",
    SCADA_API_KEY: "",
    // Custom Model Configs
    CUSTOM_BASE_URL: "https://api.yourproxy.com/v1",
    CUSTOM_MODEL_ID: "deepseek-coder",
    CUSTOM_API_KEY: "",
    CUSTOM_CONFIG_TYPE: "json",
    CURL_PASTE_CONTENT: "",
    // Coding Agents Configs
    OPENHANDS_ENABLED: "false",
    OPENHANDS_URL: "http://localhost:3000",
    OPENHANDS_WORKSPACE: "",
    OPENCODE_ENABLED: "false",
    OPENCODE_URL: "http://localhost:8080",
    KILOCODE_ENABLED: "false",
    KILOCODE_URL: "http://localhost:8090",
    // Popular Providers Configs
    PROVIDER_OPENAI_KEY: "",
    PROVIDER_OPENAI_MODEL: "gpt-4o-mini",
    PROVIDER_ANTHROPIC_KEY: "",
    PROVIDER_ANTHROPIC_MODEL: "claude-3-5-sonnet-latest",
    PROVIDER_GEMINI_KEY: "",
    PROVIDER_GEMINI_MODEL: "gemini-1.5-flash",
    PROVIDER_DEEPSEEK_KEY: "",
    PROVIDER_DEEPSEEK_MODEL: "deepseek-chat",
    PROVIDER_GROQ_KEY: "",
    PROVIDER_GROQ_MODEL: "llama-3.3-70b-versatile",
    PROVIDER_COHERE_KEY: "",
    PROVIDER_COHERE_MODEL: "command-r-plus",
    PROVIDER_HUGGINGFACE_KEY: "",
    PROVIDER_HUGGINGFACE_MODEL: "meta-llama/Llama-3.3-70B-Instruct",
  };
}

function validateImportedSettings(data: unknown): { valid: boolean; errors: string[] } {
  const errors: string[] = [];
  if (!data || typeof data !== "object" || Array.isArray(data)) {
    return { valid: false, errors: ["Invalid settings format: expected an object"] };
  }
  const obj = data as Record<string, unknown>;
  const keys = Object.keys(obj);
  if (keys.length > SETTINGS_SCHEMA.maxFields) {
    errors.push(`Too many fields: ${keys.length} (max ${SETTINGS_SCHEMA.maxFields})`);
  }
  for (const key of keys) {
    if (typeof key !== "string" || key.length > SETTINGS_SCHEMA.maxKeyLength) {
      errors.push(`Invalid key: ${key.substring(0, 20)}`);
    }
    if (typeof obj[key] !== "string") {
      errors.push(`Non-string value for key: ${key}`);
    }
    if (typeof obj[key] === "string" && obj[key].length > SETTINGS_SCHEMA.maxValueLength) {
      errors.push(`Value too long for key: ${key}`);
    }
  }
  return { valid: errors.length === 0, errors };
}

interface SettingsSection {
  title: string;
  fields: string[];
}

const TAB_SECTIONS: Record<
  string,
  { label: string; icon: React.ReactNode; sections: SettingsSection[] }
> = {
  agentsTab: {
    label: "Agents",
    icon: <Bot className="w-4 h-4" />,
    sections: [],
  },
  skillsPromptsTab: {
    label: "Skills & Prompts",
    icon: <Code className="w-4 h-4" />,
    sections: [],
  },
  ai: {
    label: "AI Providers",
    icon: <Bot className="w-4 h-4" />,
    sections: [], // Custom-rendered panel
  },
  providers: {
    label: "Providers & API Keys",
    icon: <Key className="w-4 h-4" />,
    sections: [], // Custom-rendered panel — ProviderKeysPanel (P7a)
  },
  agentsSkillsPrompts: {
    label: "Agents · Skills · Prompts",
    icon: <Bot className="w-4 h-4" />,
    sections: [], // Custom-rendered panel — AgentsSkillsPromptsPanel (P7b)
  },
  mcp: {
    label: "MCP Servers",
    icon: <Database className="w-4 h-4" />,
    sections: [], // Custom-rendered panel — McpServersTab (P7c)
  },
  importExport: {
    label: "Import / Export",
    icon: <Upload className="w-4 h-4" />,
    sections: [], // Custom-rendered panel — ImportExportTab (P7c)
  },
  agents: {
    label: "Coding Agents",
    icon: <Code className="w-4 h-4" />,
    sections: [
      {
        title: "OpenHands Integration (formerly Devin)",
        fields: ["OPENHANDS_ENABLED", "OPENHANDS_URL", "OPENHANDS_WORKSPACE"],
      },
      { title: "OpenCode Integration", fields: ["OPENCODE_ENABLED", "OPENCODE_URL"] },
      { title: "KiloCode Integration", fields: ["KILOCODE_ENABLED", "KILOCODE_URL"] },
    ],
  },
  engineering: {
    label: "Engineering Service",
    icon: <Wrench className="w-4 h-4" />,
    sections: [
      {
        title: "Engineering Service",
        fields: [
          "ENGINEERING_SERVICE_URL",
          "ENGINEERING_SERVICE_API_KEY",
          "ENGINEERING_SERVICE_TIMEOUT_MS",
        ],
      },
    ],
  },
  database: {
    label: "Database & Cache",
    icon: <Database className="w-4 h-4" />,
    sections: [
      { title: "Database", fields: ["MASTRA_DB_URL", "DATABASE_URL", "REDIS_URL"] },
      {
        title: "Cache & Performance",
        fields: ["CACHE_SIZE_MB", "CACHE_DEFAULT_TTL", "MAX_WORKERS"],
      },
    ],
  },
  security: {
    label: "Security",
    icon: <Shield className="w-4 h-4" />,
    sections: [
      // P7d: SecurityFlagsPanel (backend feature-flag registry) renders above
      // these legacy local-settings sections in the TabPanels default branch.
      { title: "Authentication", fields: ["API_KEY_SECRET", "JWT_SECRET_KEY"] },
      { title: "Vault & Secrets", fields: ["VAULT_ADDR", "VAULT_TOKEN"] },
    ],
  },
  integration: {
    label: "Integration",
    icon: <Link2 className="w-4 h-4" />,
    sections: [
      { title: "ETAP Integration", fields: ["ETAP_LICENSE_PATH", "ETAP_WORKER_URL"] },
      {
        title: "Copa-Data zenon SCADA Integration",
        fields: [
          "SCADA_SYSTEM_TYPE",
          "SCADA_SERVER_URL",
          "SCADA_PROJECT_NAME",
          "SCADA_SYNC_INTERVAL_SEC",
          "SCADA_API_KEY",
        ],
      },
      {
        title: "Email Alerts",
        fields: ["SMTP_SERVER", "SMTP_PORT", "SMTP_USERNAME", "ALERT_EMAIL_TO"],
      },
    ],
  },
  external: {
    label: "External Services",
    icon: <Link2 className="w-4 h-4" />,
    sections: [
      {
        title: "LangWatch (LLM Observability)",
        fields: ["LANGWATCH_API_KEY", "LANGWATCH_PROJECT", "LANGWATCH_ENDPOINT"],
      },
      { title: "Smithery MCP", fields: ["SMITHERY_API_KEY", "SMITHERY_BASE_URL"] },
      { title: "Hugging Face", fields: ["HF_TOKEN", "HF_SPACE_NAME", "HF_REPO_URL"] },
      { title: "GitHub", fields: ["GITHUB_TOKEN", "GITHUB_REPO"] },
      { title: "Vercel", fields: ["VERCEL_PROJECT_ID", "VERCEL_ACCESS_TOKEN"] },
    ],
  },
  performance: {
    label: "Performance",
    icon: <Gauge className="w-4 h-4" />,
    sections: [
      {
        title: "Observability",
        fields: ["HEALTH_CHECK_API_URL", "PROMETHEUS_ENABLED", "PROMETHEUS_PORT"],
      },
      {
        title: "Rate Limiting & Circuit Breaker",
        fields: [
          "RATE_LIMIT_REQUESTS_PER_MINUTE",
          "CIRCUIT_BREAKER_FAILURE_THRESHOLD",
          "MAX_BODY_SIZE",
        ],
      },
      {
        title: "Feature Flags",
        fields: ["ENABLE_ASYNC_EXECUTION", "ENABLE_CACHING", "ENABLE_OBSERVABILITY"],
      },
    ],
  },
  vision: {
    label: "Vision API Keys",
    icon: <Eye className="w-4 h-4" />,
    sections: [],
  },
  engineeringEngine: {
    label: "Engineering Engine",
    icon: <Wrench className="w-4 h-4" />,
    sections: [], // Custom-rendered panel — EngineeringEngineSettings
  },
  aiCopilot: {
    label: "AI Copilot",
    icon: <Bot className="w-4 h-4" />,
    sections: [], // Custom-rendered panel — AISettingsPanel
  },
  storage: {
    label: "Storage & Backup",
    icon: <Database className="w-4 h-4" />,
    sections: [], // Custom-rendered panel — StorageManagement
  },
  notifications: {
    label: "Notifications",
    icon: <Zap className="w-4 h-4" />,
    sections: [], // Custom-rendered panel — NotificationSettings
  },
};

// P7c: MCPConfig, MCP_SERVERS_FALLBACK, and McpServersTab (MCPSettingsPanel)
// are extracted into ./settings/McpServersTab.tsx to prevent duplication and maintain modular settings architecture.


type NotifyType = "success" | "error" | "info" | "warning";

interface AISettingsPanelProps {
  readonly settings: Record<string, string>;
  readonly setSettings: React.Dispatch<React.SetStateAction<Record<string, string>>>;
  readonly notify: (type: NotifyType, message: string) => void;
}

function AISettingsPanelInline({ settings, setSettings, notify }: AISettingsPanelProps) {
  // Quick Setup: which provider is being tested + status
  const [testingProvider, setTestingProvider] = useState<string | null>(null);
  const [providerStatus, setProviderStatus] = useState<Record<string, "ok" | "fail" | null>>({});

  // Quick Setup: test a provider API key by making a REAL chat completion
  // request to the provider's endpoint. Returns detailed error info.
  // Uses the testProviderConnection() function from llm-chat.ts which
  // performs an actual /chat/completions call (not just /models).
  const [testResults, setTestResults] = useState<
    Record<
      string,
      { message: string; details?: string; suggestion?: string; latencyMs?: number } | null
    >
  >({});

  const handleTestProvider = async (providerId: string) => {
    if (providerId === "custom_openai") {
      // Custom provider requires all 3 fields
      if (
        !settings.CUSTOM_OPENAI_API_KEY ||
        !settings.CUSTOM_OPENAI_BASE_URL ||
        !settings.CUSTOM_OPENAI_MODEL_ID
      ) {
        notify("error", "Please fill in all 3 fields: Endpoint URL, API Key, Model ID");
        return;
      }
    } else {
      // Built-in providers require just the API key
      const keyName = `PROVIDER_${providerId.toUpperCase()}_KEY`;
      if (!settings[keyName]) {
        notify("error", "Please enter an API key first");
        return;
      }
    }

    setTestingProvider(providerId);
    setProviderStatus((prev) => ({ ...prev, [providerId]: null }));
    setTestResults((prev) => ({ ...prev, [providerId]: null }));

    try {
      // Save settings with encryption BEFORE testing so testProviderConnection can read them.
      const { setEncryptedSettings, refreshSettingsCache } = await import("../lib/api-config");
      await setEncryptedSettings(settings);
      await refreshSettingsCache();

      // Call the real test function from llm-chat.ts
      const result = await testProviderConnection(providerId);

      setProviderStatus((prev) => ({ ...prev, [providerId]: result.success ? "ok" : "fail" }));
      setTestResults((prev) => ({
        ...prev,
        [providerId]: {
          message: result.message,
          details: result.details,
          suggestion: result.suggestion,
          latencyMs: result.latencyMs,
        },
      }));

      if (result.success) {
        notify("success", result.message);
      } else {
        notify("error", result.message);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Unknown error";
      setProviderStatus((prev) => ({ ...prev, [providerId]: "fail" }));
      setTestResults((prev) => ({
        ...prev,
        [providerId]: { message: `Test failed: ${msg}` },
      }));
      notify("error", `Test failed: ${msg}`);
    } finally {
      setTestingProvider(null);
    }
  };

  // Quick Setup: check which providers have keys
  const connectedCount =
    POPULAR_PROVIDERS.filter((p) => !!settings[`PROVIDER_${p.id.toUpperCase()}_KEY`]).length +
    (settings.CUSTOM_OPENAI_API_KEY ? 1 : 0);

  const activeProviderId = settings.PROVIDER_ACTIVE_PROVIDER_ID || "openai";
  const activeProvider = POPULAR_PROVIDERS.find((p) => p.id === activeProviderId);

  // Custom OpenAI compatible presets
  const customPresets = [
    { name: "Ollama (Local)", url: "http://localhost:11434/v1", model: "llama3.2", key: "ollama" },
    {
      name: "LM Studio (Local)",
      url: "http://localhost:1234/v1",
      model: "loaded-model-name",
      key: "lm-studio",
    },
    {
      name: "OpenRouter (Proxy)",
      url: "https://openrouter.ai/api/v1",
      model: "openai/gpt-4o-mini",
      key: "",
    },
    {
      name: "OpenClaude (Proxy)",
      url: "https://api.openclaude.com/v1",
      model: "claude-3-5-sonnet",
      key: "",
    },
  ];

  const applyCustomPreset = (preset: { name: string; url: string; model: string; key: string }) => {
    setSettings((prev) => ({
      ...prev,
      CUSTOM_OPENAI_BASE_URL: preset.url,
      CUSTOM_OPENAI_MODEL_ID: preset.model,
      CUSTOM_OPENAI_API_KEY: preset.key,
      PROVIDER_ACTIVE_PROVIDER_ID: "custom_openai",
    }));
    notify("info", `Applied preset for ${preset.name}`);
  };

  return (
    <div className="space-y-6 col-span-2">
      {/* ─── Active AI Provider Card ────────────────────────────────── */}
      <Card
        padding="md"
        className="border-2 border-brand-500/30 shadow-lg shadow-brand-500/5 bg-gradient-to-br from-brand-500/[0.03] to-transparent"
      >
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-5 pb-4 border-b border-[var(--border-primary)]">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-xl bg-brand-500/15 flex items-center justify-center shrink-0">
              <Bot className="w-5 h-5 text-brand-400" />
            </div>
            <div>
              <h3 className="text-base font-semibold text-[var(--text-primary)]">
                Active AI Engine / حدد المحرك النشط
              </h3>
              <p className="text-xs text-[var(--text-secondary)] mt-0.5">
                Select your default AI Provider and model. All engineering chat pages will route
                through this provider.
              </p>
            </div>
          </div>
          <div className="shrink-0 px-3 py-1.5 rounded-lg bg-[var(--bg-elevated)] border border-[var(--border-primary)] text-center">
            <div className="text-[10px] uppercase tracking-wider text-[var(--text-muted)] font-semibold">
              Connected
            </div>
            <div className="text-lg font-bold text-brand-400">{connectedCount}</div>
          </div>
        </div>

        {/* Dropdown for Active Provider */}
        <div className="mb-6 max-w-md">
          <label
            className="block text-xs font-semibold text-[var(--text-secondary)] mb-2"
            htmlFor="active-provider-select"
          >
            Active Provider
          </label>
          <select
            id="active-provider-select"
            value={activeProviderId}
            onChange={(e) =>
              setSettings((prev) => ({ ...prev, PROVIDER_ACTIVE_PROVIDER_ID: e.target.value }))
            }
            className="w-full px-3 py-2 bg-[var(--bg-primary)] border border-[var(--border-primary)] rounded-lg text-xs text-[var(--text-primary)] focus:border-brand-500 outline-none transition-colors cursor-pointer font-medium"
          >
            {POPULAR_PROVIDERS.map((p) => (
              <option key={p.id} value={p.id} className="dark:bg-gray-800">
                {p.name} {p.isFree ? "(Free Tier Available)" : ""}
              </option>
            ))}
            <option value="custom_openai" className="dark:bg-gray-800">
              Custom (OpenAI-compatible) ...
            </option>
          </select>
        </div>

        {/* Dynamic configuration inputs based on selection */}
        {activeProviderId === "custom_openai" && (
          <div className="space-y-4 pt-2 border-t border-[var(--border-primary)]">
            <div className="flex items-center gap-2">
              <span className="text-[10px] text-[var(--text-muted)] font-semibold uppercase tracking-wider">
                Custom Presets:
              </span>
              <div className="flex flex-wrap gap-1.5">
                {customPresets.map((preset) => (
                  <button
                    key={preset.name}
                    type="button"
                    onClick={() => applyCustomPreset(preset)}
                    className="px-2.5 py-1 text-[10px] font-medium rounded bg-[var(--bg-primary)] hover:bg-brand-500/10 border border-[var(--border-primary)] hover:border-brand-500/30 text-[var(--text-secondary)] hover:text-brand-400 transition-colors"
                  >
                    {preset.name}
                  </button>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              <div>
                <label
                  htmlFor="custom-openai-url"
                  className="block text-xs font-semibold text-[var(--text-secondary)] mb-1.5"
                >
                  Endpoint URL
                </label>
                <input
                  id="custom-openai-url"
                  type="url"
                  placeholder="https://api.example.com/v1"
                  value={settings.CUSTOM_OPENAI_BASE_URL || ""}
                  onChange={(e) =>
                    setSettings((prev) => ({ ...prev, CUSTOM_OPENAI_BASE_URL: e.target.value }))
                  }
                  className="w-full px-3 py-2 bg-[var(--bg-primary)] border border-[var(--border-primary)] rounded-lg text-xs text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:border-brand-500 outline-none transition-colors font-mono"
                />
              </div>

              <div>
                <label
                  htmlFor="custom-openai-key"
                  className="block text-xs font-semibold text-[var(--text-secondary)] mb-1.5"
                >
                  API Key
                </label>
                <div className="relative">
                  <input
                    id="custom-openai-key"
                    type="password"
                    placeholder="sk-... or dummy-key"
                    value={settings.CUSTOM_OPENAI_API_KEY || ""}
                    onChange={(e) =>
                      setSettings((prev) => ({ ...prev, CUSTOM_OPENAI_API_KEY: e.target.value }))
                    }
                    className="w-full px-3 py-2 pr-9 bg-[var(--bg-primary)] border border-[var(--border-primary)] rounded-lg text-xs text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:border-brand-500 outline-none transition-colors font-mono"
                  />
                  <Key className="absolute right-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[var(--text-muted)] pointer-events-none" />
                </div>
              </div>

              <div>
                <label
                  htmlFor="custom-openai-model"
                  className="block text-xs font-semibold text-[var(--text-secondary)] mb-1.5"
                >
                  Model ID
                </label>
                <input
                  id="custom-openai-model"
                  type="text"
                  placeholder="llama3.2 / loaded-model-name"
                  value={settings.CUSTOM_OPENAI_MODEL_ID || ""}
                  onChange={(e) =>
                    setSettings((prev) => ({ ...prev, CUSTOM_OPENAI_MODEL_ID: e.target.value }))
                  }
                  className="w-full px-3 py-2 bg-[var(--bg-primary)] border border-[var(--border-primary)] rounded-lg text-xs text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:border-brand-500 outline-none transition-colors font-mono"
                />
              </div>
            </div>

            <div className="mt-4 flex flex-col sm:flex-row items-start sm:items-center gap-3">
              <button
                type="button"
                onClick={() => handleTestProvider("custom_openai")}
                disabled={
                  testingProvider === "custom_openai" ||
                  !settings.CUSTOM_OPENAI_API_KEY ||
                  !settings.CUSTOM_OPENAI_BASE_URL ||
                  !settings.CUSTOM_OPENAI_MODEL_ID
                }
                className={cn(
                  "flex items-center gap-1.5 px-5 py-2 rounded-lg text-xs font-semibold transition-all shrink-0",
                  "disabled:bg-[var(--bg-primary)] disabled:text-[var(--text-muted)] disabled:cursor-not-allowed disabled:border disabled:border-[var(--border-primary)]",
                  (() => {
                    const s = providerStatus.custom_openai;
                    if (s === "ok") return "bg-green-600 hover:bg-green-500 text-white";
                    if (s === "fail") return "bg-red-600 hover:bg-red-500 text-white";
                    return "bg-purple-600 hover:bg-purple-500 text-white";
                  })(),
                )}
              >
                {(() => {
                  if (testingProvider === "custom_openai")
                    return (
                      <>
                        <Loader2 className="w-3.5 h-3.5 animate-spin" /> Testing...
                      </>
                    );
                  if (providerStatus.custom_openai === "ok")
                    return (
                      <>
                        <CheckCircle2 className="w-3.5 h-3.5" /> Valid ✓
                      </>
                    );
                  if (providerStatus.custom_openai === "fail")
                    return (
                      <>
                        <XCircle className="w-3.5 h-3.5" /> Failed — Retry
                      </>
                    );
                  return (
                    <>
                      <Zap className="w-3.5 h-3.5" /> Test Connection
                    </>
                  );
                })()}
              </button>

              {testResults.custom_openai && (
                <div
                  className={cn(
                    "flex-1 min-w-0 p-3 rounded-lg border text-xs",
                    providerStatus.custom_openai === "ok"
                      ? "bg-green-500/10 border-green-500/30 text-green-400"
                      : "bg-red-500/10 border-red-500/30 text-red-400",
                  )}
                >
                  <div className="font-semibold mb-1">{testResults.custom_openai.message}</div>
                  {testResults.custom_openai.latencyMs && (
                    <div className="text-[10px] opacity-80 mb-1">
                      Latency: {testResults.custom_openai.latencyMs}ms
                    </div>
                  )}
                  {testResults.custom_openai.suggestion && (
                    <div className="text-[10px] opacity-80 mt-1.5 p-2 bg-black/20 rounded">
                      💡 {testResults.custom_openai.suggestion}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )}
        {activeProviderId !== "custom_openai" && activeProvider && (
          <div className="space-y-4 pt-2 border-t border-[var(--border-primary)]">
            <div className="flex items-center gap-3">
              <ProviderLogo providerId={activeProvider.id} size={48} />
              <div>
                <h4 className="text-sm font-semibold text-[var(--text-primary)]">
                  {activeProvider.name} Config
                </h4>
                <p className="text-xs text-[var(--text-muted)]">
                  Configure authentication and default models for {activeProvider.name}.
                </p>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 max-w-2xl">
              <div>
                <label
                  htmlFor={"prov-active-key"}
                  className="block text-xs font-semibold text-[var(--text-secondary)] mb-1.5"
                >
                  API Key
                </label>
                <div className="relative">
                  <input
                    id={"prov-active-key"}
                    type="password"
                    placeholder={`Paste ${activeProvider.name} API key...`}
                    value={settings[`PROVIDER_${activeProvider.id.toUpperCase()}_KEY`] || ""}
                    onChange={(e) =>
                      setSettings((prev) => ({
                        ...prev,
                        [`PROVIDER_${activeProvider.id.toUpperCase()}_KEY`]: e.target.value,
                      }))
                    }
                    className="w-full px-3 py-2 pr-9 bg-[var(--bg-primary)] border border-[var(--border-primary)] rounded-lg text-xs text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:border-brand-500 outline-none transition-colors font-mono"
                  />
                  <Key className="absolute right-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[var(--text-muted)] pointer-events-none" />
                </div>
              </div>

              <div>
                <label
                  htmlFor={"prov-active-model"}
                  className="block text-xs font-semibold text-[var(--text-secondary)] mb-1.5"
                >
                  Select Model
                </label>
                <select
                  id={"prov-active-model"}
                  value={
                    settings[`PROVIDER_${activeProvider.id.toUpperCase()}_MODEL`] ||
                    activeProvider.defaultModel
                  }
                  onChange={(e) =>
                    setSettings((prev) => ({
                      ...prev,
                      [`PROVIDER_${activeProvider.id.toUpperCase()}_MODEL`]: e.target.value,
                    }))
                  }
                  className="w-full px-3 py-2 bg-[var(--bg-primary)] border border-[var(--border-primary)] rounded-lg text-xs text-[var(--text-primary)] focus:border-brand-500 outline-none transition-colors cursor-pointer"
                >
                  {activeProvider.models.map((m) => (
                    <option key={m.id} value={m.id} className="dark:bg-gray-800">
                      {m.isFree ? "Freelimit " : ""}
                      {m.name} ({m.id})
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="mt-4 flex flex-col sm:flex-row items-start sm:items-center gap-3">
              <button
                type="button"
                onClick={() => handleTestProvider(activeProvider.id)}
                disabled={
                  testingProvider === activeProvider.id ||
                  !settings[`PROVIDER_${activeProvider.id.toUpperCase()}_KEY`]
                }
                className={cn(
                  "flex items-center gap-1.5 px-5 py-2 rounded-lg text-xs font-semibold transition-all shrink-0",
                  "disabled:bg-[var(--bg-primary)] disabled:text-[var(--text-muted)] disabled:cursor-not-allowed disabled:border disabled:border-[var(--border-primary)]",
                  (() => {
                    const s = providerStatus[activeProvider.id];
                    if (s === "ok") return "bg-green-600 hover:bg-green-500 text-white";
                    if (s === "fail") return "bg-red-600 hover:bg-red-500 text-white";
                    return "bg-brand-600 hover:bg-brand-500 text-white";
                  })(),
                )}
              >
                {providerButtonContent(
                  testingProvider === activeProvider.id,
                  providerStatus[activeProvider.id],
                )}
              </button>

              {testResults[activeProvider.id] && (
                <div
                  className={cn(
                    "flex-1 min-w-0 p-3 rounded-lg border text-xs",
                    providerStatus[activeProvider.id] === "ok"
                      ? "bg-green-500/10 border-green-500/30 text-green-400"
                      : "bg-red-500/10 border-red-500/30 text-red-400",
                  )}
                >
                  <div className="font-semibold mb-1">
                    {testResults[activeProvider.id]?.message}
                  </div>
                  {testResults[activeProvider.id]?.latencyMs && (
                    <div className="text-[10px] opacity-80 mb-1">
                      Latency: {testResults[activeProvider.id]?.latencyMs}ms
                    </div>
                  )}
                  {testResults[activeProvider.id]?.suggestion && (
                    <div className="text-[10px] opacity-80 mt-1.5 p-2 bg-black/20 rounded">
                      💡 {testResults[activeProvider.id]?.suggestion}
                    </div>
                  )}
                </div>
              )}
            </div>

            <a
              href={activeProvider.apiKeyUrl || "#"}
              target="_blank"
              rel="noopener noreferrer"
              className={cn(
                "mt-2 inline-flex items-center gap-1 text-[10px] transition-colors",
                activeProvider.isFree
                  ? "text-green-500 hover:text-green-400 font-medium"
                  : "text-[var(--text-muted)] hover:text-brand-400",
              )}
            >
              {activeProvider.isFree && (
                <span className="inline-block w-1.5 h-1.5 rounded-full bg-green-500" />
              )}
              Get API key from {activeProvider.name}
              {activeProvider.isFree && (
                <span className="text-[9px] uppercase tracking-wide ml-1">
                  (free tier available)
                </span>
              )}
              <ExternalLink className="w-2.5 h-2.5 ml-1" />
            </a>
          </div>
        )}
      </Card>

      {/* ─── Collapsible Configure Other Providers Card ────────────────── */}
      <details className="group border border-[var(--border-primary)] rounded-lg bg-[var(--bg-elevated)]">
        <summary className="flex items-center gap-2 cursor-pointer p-4 text-sm font-semibold text-[var(--text-secondary)] list-none hover:text-[var(--text-primary)] transition-colors select-none">
          <ChevronRight className="w-4 h-4 text-[var(--text-muted)] group-open:rotate-90 transition-transform" />
          <span>
            Configure Other Providers / تهيئة موفري الخدمة الآخرين ({POPULAR_PROVIDERS.length}{" "}
            Available)
          </span>
        </summary>
        <div className="p-4 border-t border-[var(--border-primary)] bg-[var(--bg-primary)] space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {POPULAR_PROVIDERS.map((p) => {
              const keyName = `PROVIDER_${p.id.toUpperCase()}_KEY`;
              const hasKey = !!settings[keyName];
              const status = providerStatus[p.id];
              const isTesting = testingProvider === p.id;
              const cardClass = providerCardClass(hasKey, p.isFree);
              const buttonClass = providerButtonClass(!!settings[keyName], isTesting, status);
              const buttonContent = providerButtonContent(isTesting, status);
              return (
                <div key={p.id} className={cardClass}>
                  {p.isFree && !hasKey && (
                    <span className="absolute -top-2 -right-2 px-2 py-0.5 rounded-full bg-green-500 text-white text-[9px] font-bold uppercase tracking-wide shadow-md z-10">
                      Free
                    </span>
                  )}
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2.5">
                      <ProviderLogo providerId={p.id} size={40} />
                      <div>
                        <div className="text-sm font-semibold text-[var(--text-primary)]">
                          {p.name}
                        </div>
                        <div className="text-[10px] text-[var(--text-muted)]">{p.defaultModel}</div>
                      </div>
                    </div>
                    {hasKey && (
                      <span className="inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-full bg-green-500/15 text-green-400 border border-green-500/25">
                        <CheckCircle2 className="w-3 h-3" />
                        Saved
                      </span>
                    )}
                  </div>

                  <div className="relative mb-2">
                    <input
                      type="password"
                      placeholder={`Paste ${p.name} API key...`}
                      value={settings[keyName] || ""}
                      onChange={(e) => {
                        setSettings((prev) => ({ ...prev, [keyName]: e.target.value }));
                        if (providerStatus[p.id]) {
                          setProviderStatus((prev) => ({ ...prev, [p.id]: null }));
                        }
                      }}
                      className="w-full px-3 py-2 pr-9 bg-[var(--bg-primary)] border border-[var(--border-primary)] rounded-lg text-xs text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:border-brand-500 outline-none transition-colors font-mono"
                    />
                    <Key className="absolute right-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[var(--text-muted)] pointer-events-none" />
                  </div>

                  <div className="mb-2">
                    <label
                      className="block text-[9px] text-[var(--text-tertiary)] mb-1 font-medium uppercase tracking-wide"
                      htmlFor={`model-collapsible-${p.id}`}
                    >
                      Model
                    </label>
                    <select
                      id={`model-collapsible-${p.id}`}
                      value={settings[`PROVIDER_${p.id.toUpperCase()}_MODEL`] || p.defaultModel}
                      onChange={(e) =>
                        setSettings((prev) => ({
                          ...prev,
                          [`PROVIDER_${p.id.toUpperCase()}_MODEL`]: e.target.value,
                        }))
                      }
                      className="w-full px-2 py-1.5 bg-[var(--bg-primary)] border border-[var(--border-primary)] rounded-lg text-[11px] text-[var(--text-primary)] focus:border-brand-500 outline-none transition-colors cursor-pointer"
                    >
                      {p.models.map((m) => (
                        <option key={m.id} value={m.id} className="dark:bg-gray-800">
                          {m.isFree ? "Freelimit " : ""}
                          {m.name} ({m.id})
                        </option>
                      ))}
                    </select>
                  </div>

                  <button
                    type="button"
                    onClick={() => handleTestProvider(p.id)}
                    disabled={!settings[keyName] || isTesting}
                    className={buttonClass}
                  >
                    {buttonContent}
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      </details>
    </div>
  );
}

// ============================================================================
// ExternalServicesPanel — dedicated panel with Test Connection buttons + status
// ============================================================================
import {
  type TestStatus,
  type ServiceDescriptor,
  EXTERNAL_SERVICES,
} from "../lib/external-services";

function ExternalServicesPanel({
  settings,
  setSettings,
  notify,
}: {
  readonly settings: Record<string, string>;
  readonly setSettings: React.Dispatch<React.SetStateAction<Record<string, string>>>;
  readonly notify: (type: NotifyType, message: string) => void;
}) {
  // status[id] = { state, detail }
  const [status, setStatus] = useState<Record<string, { state: TestStatus; detail: string }>>({});

  const handleTest = async (svc: ServiceDescriptor) => {
    const result = svc.testConnection(settings);
    if (result === null) {
      notify("warning", `Please fill in all required fields for ${svc.name}`);
      return;
    }
    setStatus((prev) => ({ ...prev, [svc.id]: { state: "testing", detail: "Testing…" } }));
    try {
      const r = await result;
      setStatus((prev) => ({
        ...prev,
        [svc.id]: { state: r.ok ? "ok" : "fail", detail: r.detail },
      }));
      notify(r.ok ? "success" : "error", `${svc.name}: ${r.detail}`);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setStatus((prev) => ({ ...prev, [svc.id]: { state: "fail", detail: msg } }));
      notify("error", `${svc.name}: ${msg}`);
    }
  };

  return (
    <div className="space-y-6 col-span-2">
      <Card padding="md" className="border border-[var(--border-primary)] shadow-sm">
        <div className="flex items-center gap-2 mb-4 border-b border-[var(--border-primary)] pb-3">
          <Link2 className="w-5 h-5 text-brand-400" />
          <div>
            <h3 className="text-sm font-semibold text-[var(--text-primary)]">External Services</h3>
            <p className="text-[10px] text-[var(--text-muted)]">
              Configure and verify connections to LangWatch, Smithery, Hugging Face, GitHub, and
              Vercel. Click "Test" to verify each integration in real-time.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {EXTERNAL_SERVICES.map((svc) => {
            const st = status[svc.id] || { state: "idle" as TestStatus, detail: "" };
            const isConfigured = svc.fields
              .filter((f) => f.required)
              .every((f) => (settings[f.key] || "").trim().length > 0);

            return (
              <div
                key={svc.id}
                className="rounded-xl border border-[var(--border-primary)] p-4 bg-[var(--bg-secondary)] hover:border-[var(--color-brand-500)] transition-colors"
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <div
                      className="w-3 h-3 rounded-full"
                      style={{ backgroundColor: svc.color }}
                      aria-hidden
                    />
                    <div>
                      <h4 className="text-sm font-semibold text-[var(--text-primary)]">
                        {svc.name}
                      </h4>
                      <p className="text-[10px] text-[var(--text-muted)]">{svc.description}</p>
                    </div>
                  </div>
                  {st.state === "ok" && <CheckCircle2 className="w-4 h-4 text-green-500" />}
                  {st.state === "fail" && <XCircle className="w-4 h-4 text-red-500" />}
                  {st.state === "testing" && (
                    <Loader2 className="w-4 h-4 text-yellow-400 animate-spin" />
                  )}
                </div>

                <div className="space-y-2 mb-3">
                  {svc.fields.map((f) => (
                    <div key={f.key}>
                      <label
                        htmlFor={`svc-${svc.id}-${f.key}`}
                        className="block text-[10px] font-medium text-[var(--text-tertiary)] mb-1"
                      >
                        {f.label}
                        {f.required && <span className="text-red-400"> *</span>}
                      </label>
                      <input
                        id={`svc-${svc.id}-${f.key}`}
                        type={f.type === "password" ? "password" : "text"}
                        placeholder={f.placeholder}
                        value={settings[f.key] || ""}
                        onChange={
                          (
                            e, // NOSONAR — S2004: inline form onChange
                          ) => setSettings((prev) => ({ ...prev, [f.key]: e.target.value })) // NOSONAR — S2004: inline form onChange
                        }
                        className="w-full px-2.5 py-1.5 bg-[var(--bg-input)] border border-[var(--border-primary)] rounded-md text-[var(--text-primary)] text-xs focus:border-brand-500 outline-none font-mono transition-colors"
                      />
                    </div>
                  ))}
                </div>

                {st.detail &&
                  (() => {
                    const stateColor: string =
                      st.state === "ok"
                        ? "bg-green-500/10 text-green-400"
                        : st.state === "fail"
                          ? "bg-red-500/10 text-red-400"
                          : "bg-yellow-500/10 text-yellow-400";
                    return (
                      <div className={`text-[10px] mb-2 px-2 py-1 rounded ${stateColor}`}>
                        {st.detail}
                      </div>
                    );
                  })()}

                <div className="flex items-center gap-2">
                  <Button
                    variant={isConfigured ? "primary" : "ghost"}
                    size="sm"
                    disabled={st.state === "testing"}
                    onClick={() => handleTest(svc)}
                    className="flex-1"
                  >
                    {st.state === "testing" ? "Testing…" : "Test Connection"}
                  </Button>
                  <a
                    href={svc.dashboardUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="px-2.5 py-1.5 text-xs rounded-md border border-[var(--border-primary)] text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)] flex items-center gap-1"
                    title={`Open ${svc.name} dashboard`}
                  >
                    <ExternalLink className="w-3 h-3" />
                  </a>
                </div>
              </div>
            );
          })}
        </div>

        <div className="mt-4 p-3 rounded-lg bg-[var(--bg-tertiary)] border border-[var(--border-primary)] text-[11px] text-[var(--text-muted)] leading-relaxed">
          <Info className="w-3.5 h-3.5 inline-block mr-1.5 -mt-0.5" />
          <strong>How it works:</strong> Each service is tested by calling its public API with your
          credentials. Tokens are stored locally (obfuscated) and never sent to our backend. After
          saving, copy the same values into your HF Space secrets or server <code>.env</code> for
          backend runtime access.
        </div>
      </Card>
    </div>
  );
}

function SettingsField({
  field,
  value,
  onChange,
}: { readonly field: string; readonly value: string; readonly onChange: (v: string) => void }) {
  const isSecret = field.includes("KEY") || field.includes("SECRET");
  const isFeatureFlag = field.startsWith("ENABLE_") || field.endsWith("_ENABLED");
  const isNumber =
    field.includes("_MS") ||
    field.includes("PORT") ||
    field.includes("SIZE") ||
    field.includes("TTL") ||
    field.includes("RATE") ||
    field.includes("THRESHOLD") ||
    field.includes("MAX_");
  const inputType = isSecret ? "password" : isNumber ? "number" : "text";

  if (isFeatureFlag) {
    return (
      <Toggle
        checked={value === "true"}
        onChange={(checked) => onChange(checked ? "true" : "false")}
        label={field.replaceAll("_", " ").replaceAll("ENABLE ", "").replaceAll(" ENABLED", "")}
        description={`Toggle ${field.replaceAll("_", " ").toLowerCase()}`}
        size="sm"
      />
    );
  }

  return (
    <div>
      <label
        htmlFor={`field-${field}`}
        className="block text-xs font-medium text-[var(--text-tertiary)] mb-1.5"
      >
        {field
          .replaceAll("_", " ")
          .toLowerCase()
          .replace(/\b\w/g, (c) => c.toUpperCase())}
      </label>
      <input
        id={`field-${field}`}
        type={inputType}
        value={value || ""}
        onChange={(e) => onChange(e.target.value)}
        className="w-full px-3 py-2 bg-[var(--bg-input)] border border-[var(--border-primary)] rounded-lg text-[var(--text-primary)] text-sm focus:border-[var(--color-brand-500)] focus:ring-1 focus:ring-[var(--color-brand-500)]/30 outline-none font-mono transition-colors"
      />
    </div>
  );
}

function loadInitialSettings(): Record<string, string> {
  const defaults = getDefaults();
  try {
    const cached = getCachedSettings();
    return { ...defaults, ...cached };
  } catch {
    return defaults;
  }
}

// ─── Vision API Keys Panel ─────────────────────────────────────────────────
// Connects to the backend /api/v1/settings/keys endpoints.
// Allows users to enter OpenAI/Gemini/Anthropic API keys (encrypted server-side).

const VISION_PROVIDERS = [
  {
    id: "openai",
    label: "OpenAI-Compatible",
    description: "Works with OpenAI, Azure, Together AI, Groq, freemodel.dev, etc.",
    defaultBaseUrl: "https://api.openai.com/v1",
    defaultModel: "gpt-4o",
    placeholder: "sk-...",
    docsUrl: "https://platform.openai.com/api-keys",
  },
  {
    id: "gemini",
    label: "Google Gemini",
    description: "Google AI Studio Gemini Vision API",
    defaultBaseUrl: "",
    defaultModel: "gemini-2.0-flash-exp",
    placeholder: "AIza...",
    docsUrl: "https://aistudio.google.com/app/apikey",
  },
  {
    id: "anthropic",
    label: "Anthropic Claude",
    description: "Claude 3.5 Sonnet / Opus / Haiku Vision",
    defaultBaseUrl: "https://api.anthropic.com",
    defaultModel: "claude-3-5-sonnet-20241022",
    placeholder: "sk-ant-...",
    docsUrl: "https://console.anthropic.com/",
  },
];

function VisionApiKeysPanel({
  notify,
}: { readonly notify: (type: NotifyType, message: string) => void }) {
  const [keys, setKeys] = useState<Record<string, VisionKeyConfig>>({});
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<
    Record<string, { apiKey: string; baseUrl: string; modelName: string }>
  >({});
  const [savingProvider, setSavingProvider] = useState<string | null>(null);
  const [testingProvider, setTestingProvider] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<
    Record<string, { success: boolean; message: string }>
  >({});

  const loadKeys = useCallback(async () => {
    setLoading(true);
    try {
      const resp = await fetchVisionKeys();
      setKeys(resp.data || {});
    } catch (err) {
      notify(
        "error",
        `Failed to load API keys: ${err instanceof Error ? err.message : "Unknown error"}`,
      );
    } finally {
      setLoading(false);
    }
  }, [notify]);

  useEffect(() => {
    loadKeys();
  }, [loadKeys]);

  const handleSave = async (providerId: string) => {
    const edit = editing[providerId];
    if (!edit?.apiKey?.trim()) {
      notify("error", "Please enter an API key");
      return;
    }
    setSavingProvider(providerId);
    try {
      await saveVisionKey(
        providerId,
        edit.apiKey.trim(),
        edit.baseUrl.trim() || undefined,
        edit.modelName.trim() || undefined,
        true,
      );
      notify("success", `${providerId} API key saved (encrypted)`);
      setEditing((prev) => {
        const next = { ...prev };
        delete next[providerId];
        return next;
      });
      setTestResults((prev) => {
        const next = { ...prev };
        delete next[providerId];
        return next;
      });
      await loadKeys();
    } catch (err) {
      notify("error", `Failed to save: ${err instanceof Error ? err.message : "Unknown error"}`);
    } finally {
      setSavingProvider(null);
    }
  };

  const handleDelete = async (providerId: string) => {
    if (!confirm(`Delete the ${providerId} API key? This cannot be undone.`)) return;
    try {
      await deleteVisionKey(providerId);
      notify("info", `${providerId} API key deleted`);
      setTestResults((prev) => {
        const next = { ...prev };
        delete next[providerId];
        return next;
      });
      await loadKeys();
    } catch (err) {
      notify("error", `Failed to delete: ${err instanceof Error ? err.message : "Unknown error"}`);
    }
  };

  const handleTest = async (providerId: string) => {
    setTestingProvider(providerId);
    setTestResults((prev) => ({
      ...prev,
      [providerId]: { success: false, message: "Testing..." },
    }));
    try {
      const resp = await testVisionKey(providerId);
      const result = resp.data;
      setTestResults((prev) => ({
        ...prev,
        [providerId]: { success: result.success, message: result.message },
      }));
      if (result.success) {
        notify("success", `${providerId} key is valid!`);
      } else {
        notify("warning", `${providerId} key test failed: ${result.message}`);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Unknown error";
      setTestResults((prev) => ({ ...prev, [providerId]: { success: false, message: msg } }));
      notify("error", `Test failed: ${msg}`);
    } finally {
      setTestingProvider(null);
    }
  };

  const startEditing = (providerId: string, existing?: VisionKeyConfig) => {
    setEditing((prev) => ({
      ...prev,
      [providerId]: {
        apiKey: "",
        baseUrl:
          existing?.base_url ||
          VISION_PROVIDERS.find((p) => p.id === providerId)?.defaultBaseUrl ||
          "",
        modelName:
          existing?.model_name ||
          VISION_PROVIDERS.find((p) => p.id === providerId)?.defaultModel ||
          "",
      },
    }));
  };

  const cancelEditing = (providerId: string) => {
    setEditing((prev) => {
      const next = { ...prev };
      delete next[providerId];
      return next;
    });
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-[var(--accent-primary)]" />
        <span className="ml-3 text-[var(--text-muted)]">Loading API keys...</span>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Card padding="md">
        <CardHeader
          title="Vision API Keys"
          subtitle="Enter your own API keys for the CUA Loop vision backends. Keys are encrypted (AES-256) and stored server-side — never exposed in the frontend."
          icon={<Eye className="w-5 h-5" />}
        />
        <div className="mt-4 p-3 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border-primary)]">
          <div className="flex items-start gap-2">
            <Info className="w-4 h-4 text-[var(--accent-primary)] mt-0.5 flex-shrink-0" />
            <div className="text-sm text-[var(--text-secondary)]">
              <p className="font-medium mb-1">How it works:</p>
              <ul className="list-disc list-inside space-y-1 text-xs">
                <li>
                  Keys are <strong>optional</strong> — the CUA Loop works without them (falls back
                  to OpenCV)
                </li>
                <li>
                  Keys are <strong>encrypted</strong> with AES-256 before storage
                </li>
                <li>
                  Keys <strong>override</strong> server-side env vars when set
                </li>
                <li>
                  Keys are <strong>masked</strong> in the UI (sk-***...***) — never shown in
                  plaintext
                </li>
                <li>
                  You can enter keys <strong>anytime</strong> — changes take effect immediately
                </li>
              </ul>
            </div>
          </div>
        </div>
      </Card>

      {VISION_PROVIDERS.map((provider) => {
        const existing = keys[provider.id];
        const isEditing = !!editing[provider.id];
        const edit = editing[provider.id];
        const testResult = testResults[provider.id];
        const isSaving = savingProvider === provider.id;
        const isTesting = testingProvider === provider.id;

        return (
          <Card key={provider.id} padding="md">
            <CardHeader
              title={
                <div className="flex items-center gap-2">
                  <Key className="w-4 h-4" />
                  <span>{provider.label}</span>
                  {existing?.is_active && (
                    <span className="px-2 py-0.5 text-xs rounded-full bg-green-500/20 text-green-400 border border-green-500/30">
                      Active
                    </span>
                  )}
                </div>
              }
              subtitle={provider.description}
              icon={null}
            />

            <div className="mt-4 space-y-4">
              {/* Existing key display (masked) */}
              {existing && !isEditing && (
                <div className="space-y-3">
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                    <div>
                      <span className="text-xs text-[var(--text-muted)]">API Key</span>
                      <div className="font-mono text-sm text-[var(--text-secondary)] bg-[var(--bg-secondary)] px-3 py-2 rounded-md border border-[var(--border-primary)]">
                        {existing.api_key_masked}
                      </div>
                    </div>
                    {existing.base_url && (
                      <div>
                        <span className="text-xs text-[var(--text-muted)]">Base URL</span>
                        <div className="text-sm text-[var(--text-secondary)] bg-[var(--bg-secondary)] px-3 py-2 rounded-md border border-[var(--border-primary)] truncate">
                          {existing.base_url}
                        </div>
                      </div>
                    )}
                    {existing.model_name && (
                      <div>
                        <span className="text-xs text-[var(--text-muted)]">Model</span>
                        <div className="text-sm text-[var(--text-secondary)] bg-[var(--bg-secondary)] px-3 py-2 rounded-md border border-[var(--border-primary)] truncate">
                          {existing.model_name}
                        </div>
                      </div>
                    )}
                  </div>

                  {testResult && (
                    <div
                      className={`flex items-center gap-2 p-2 rounded-md text-sm ${
                        testResult.success
                          ? "bg-green-500/10 text-green-400 border border-green-500/20"
                          : "bg-red-500/10 text-red-400 border border-red-500/20"
                      }`}
                    >
                      {testResult.success ? (
                        <CheckCircle2 className="w-4 h-4" />
                      ) : (
                        <XCircle className="w-4 h-4" />
                      )}
                      <span className="truncate">{testResult.message}</span>
                    </div>
                  )}

                  <div className="flex items-center gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      icon={isTesting ? Loader2 : Zap}
                      onClick={() => handleTest(provider.id)}
                      disabled={isTesting}
                    >
                      {isTesting ? "Testing..." : "Test"}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => startEditing(provider.id, existing)}
                    >
                      Update
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      icon={Trash2}
                      onClick={() => handleDelete(provider.id)}
                      className="text-red-400 hover:text-red-300"
                    >
                      Delete
                    </Button>
                    <a
                      href={provider.docsUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="ml-auto text-xs text-[var(--accent-primary)] hover:underline flex items-center gap-1"
                    >
                      Get API key <ExternalLink className="w-3 h-3" />
                    </a>
                  </div>
                </div>
              )}

              {/* Edit / new key form */}
              {(isEditing || !existing) && edit && (
                <div className="space-y-3">
                  <div>
                    <label
                      htmlFor={`vision-${provider.id}-key`}
                      className="text-xs text-[var(--text-muted)] mb-1 block"
                    >
                      API Key
                    </label>
                    <input
                      id={`vision-${provider.id}-key`}
                      type="password"
                      value={edit.apiKey}
                      onChange={(e) =>
                        setEditing((prev) => ({
                          ...prev,
                          [provider.id]: { ...edit, apiKey: e.target.value },
                        }))
                      }
                      placeholder={provider.placeholder}
                      className="w-full px-3 py-2 rounded-md bg-[var(--bg-secondary)] border border-[var(--border-primary)] text-[var(--text-primary)] text-sm focus:outline-none focus:border-[var(--accent-primary)]"
                      autoComplete="off"
                    />
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <div>
                      <label
                        htmlFor={`vision-${provider.id}-base`}
                        className="text-xs text-[var(--text-muted)] mb-1 block"
                      >
                        Base URL (optional)
                      </label>
                      <input
                        id={`vision-${provider.id}-base`}
                        type="text"
                        value={edit.baseUrl}
                        onChange={(e) =>
                          setEditing((prev) => ({
                            ...prev,
                            [provider.id]: { ...edit, baseUrl: e.target.value },
                          }))
                        }
                        placeholder={provider.defaultBaseUrl || "(default)"}
                        className="w-full px-3 py-2 rounded-md bg-[var(--bg-secondary)] border border-[var(--border-primary)] text-[var(--text-primary)] text-sm focus:outline-none focus:border-[var(--accent-primary)]"
                      />
                    </div>
                    <div>
                      <label
                        htmlFor={`vision-${provider.id}-model`}
                        className="text-xs text-[var(--text-muted)] mb-1 block"
                      >
                        Model (optional)
                      </label>
                      <input
                        id={`vision-${provider.id}-model`}
                        type="text"
                        value={edit.modelName}
                        onChange={(e) =>
                          setEditing((prev) => ({
                            ...prev,
                            [provider.id]: { ...edit, modelName: e.target.value },
                          }))
                        }
                        placeholder={provider.defaultModel}
                        className="w-full px-3 py-2 rounded-md bg-[var(--bg-secondary)] border border-[var(--border-primary)] text-[var(--text-primary)] text-sm focus:outline-none focus:border-[var(--accent-primary)]"
                      />
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="primary"
                      size="sm"
                      icon={isSaving ? Loader2 : Save}
                      onClick={() => handleSave(provider.id)}
                      disabled={isSaving || !edit.apiKey.trim()}
                    >
                      {isSaving ? "Saving..." : "Save Key"}
                    </Button>
                    {isEditing && (
                      <Button variant="ghost" size="sm" onClick={() => cancelEditing(provider.id)}>
                        Cancel
                      </Button>
                    )}
                    <a
                      href={provider.docsUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="ml-auto text-xs text-[var(--accent-primary)] hover:underline flex items-center gap-1"
                    >
                      Get API key <ExternalLink className="w-3 h-3" />
                    </a>
                  </div>
                </div>
              )}

              {/* No key + not editing → show "Add Key" button */}
              {!existing && !isEditing && (
                <div className="flex items-center gap-3">
                  <p className="text-sm text-[var(--text-muted)]">
                    No key configured — using server default or OpenCV fallback
                  </p>
                  <Button
                    variant="ghost"
                    size="sm"
                    icon={Key}
                    onClick={() => startEditing(provider.id)}
                  >
                    Add Key
                  </Button>
                  <a
                    href={provider.docsUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-[var(--accent-primary)] hover:underline flex items-center gap-1"
                  >
                    Get API key <ExternalLink className="w-3 h-3" />
                  </a>
                </div>
              )}
            </div>
          </Card>
        );
      })}
    </div>
  );
}

interface SettingsActiveTabPanelProps {
  readonly activeTab: string;
  readonly chatFirstEnabled: boolean;
  readonly notify: (type: "success" | "error" | "info" | "warning", message: string) => void;
  readonly settings: Record<string, string>;
  readonly setSettings: React.Dispatch<React.SetStateAction<Record<string, string>>>;
  readonly currentSections: Array<{ title: string; fields: string[] }>;
}

function SettingsActiveTabPanel({
  activeTab,
  chatFirstEnabled,
  notify,
  settings,
  setSettings,
  currentSections,
}: SettingsActiveTabPanelProps) {
  switch (activeTab) {
    case "agentsTab":
      return chatFirstEnabled ? <AgentsTab notify={notify} /> : null;
    case "skillsPromptsTab":
      return chatFirstEnabled ? <SkillsPromptsTab notify={notify} /> : null;
    case "ai":
      return (
        <AISettingsPanelInline
          settings={settings}
          setSettings={setSettings}
          notify={notify}
        />
      );
    case "providers":
      return <ProviderKeysPanel notify={notify} />;
    case "agentsSkillsPrompts":
      return <AgentsSkillsPromptsPanel notify={notify} />;
    case "mcp":
      return chatFirstEnabled ? <McpServersTab /> : null;
    case "importExport":
      return chatFirstEnabled ? <ImportExportTab notify={notify} /> : null;
    case "external":
      return (
        <ExternalServicesPanel
          settings={settings}
          setSettings={setSettings}
          notify={notify}
        />
      );
    case "vision":
      return <VisionApiKeysPanel notify={notify} />;
    case "engineeringEngine":
      return <EngineeringEngineSettings />;
    case "aiCopilot":
      return <AISettingsPanel />;
    case "storage":
      return <StorageManagement />;
    case "notifications":
      return <NotificationSettings />;
    default:
      return (
        <>
          {activeTab === "security" && <SecurityFlagsPanel notify={notify} />}
          {currentSections.map((section) => (
            <Card key={section.title} padding="md">
              <CardHeader
                title={section.title}
                subtitle={`${section.fields.length} field${section.fields.length === 1 ? "" : "s"}`}
                icon={TAB_SECTIONS[activeTab]?.icon}
              />
              <div className="space-y-4">
                {section.fields.map((field) => (
                  <SettingsField
                    key={field}
                    field={field}
                    value={settings[field] || ""}
                    onChange={(v) => setSettings((p) => ({ ...p, [field]: v }))}
                  />
                ))}
              </div>
            </Card>
          ))}
        </>
      );
  }
}

export default function Settings() {
  const [settings, setSettings] = useState<Record<string, string>>(loadInitialSettings);
  const [saving, setSaving] = useState(false);
  const { notify } = useNotify();
  const chatFirstUi = useChatFirstUi();
  const { activeTab, setActiveTab } = useTabState("ai");

  // Fallback to "ai" if active tab is restricted behind chat_first_ui but the feature is disabled
  useEffect(() => {
    if (
      !chatFirstUi.enabled &&
      (activeTab === "agentsTab" ||
        activeTab === "skillsPromptsTab" ||
        activeTab === "mcp" ||
        activeTab === "importExport")
    ) {
      setActiveTab("ai");
    }
  }, [chatFirstUi.enabled, activeTab, setActiveTab]);

  const handleSave = async () => {
    setSaving(true);
    try {
      // Use the AES-GCM encryption for secret fields
      const { setEncryptedSettings, refreshSettingsCache } = await import("../lib/api-config");
      await setEncryptedSettings(settings);

      // Refresh the sync cache so getCachedSettings() returns the new values
      await refreshSettingsCache();

      notify("success", "Settings saved successfully");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to save settings";
      notify("error", msg);
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    const d = getDefaults();
    setSettings(d);
    localStorage.removeItem("etap-settings");
    notify("info", "Settings reset to defaults");
  };

  const handleExport = () => {
    const exportData: Record<string, string> = {};
    for (const [k, v] of Object.entries(settings)) {
      exportData[k] = isSecretField(k) ? "" : v;
    }
    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "etap-settings.json";
    a.click();
    URL.revokeObjectURL(url);
    notify("success", "Settings exported (secrets excluded for security)");
  };

  const handleImport = () => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = ".json";
    input.onchange = async () => {
      const file = input.files?.[0];
      if (!file) return;
      const text = await file.text();
      try {
        const parsed = JSON.parse(text);
        const validation = validateImportedSettings(parsed);
        if (!validation.valid) {
          notify("error", `Invalid settings: ${validation.errors.join(", ")}`);
          return;
        }
        setSettings((prev) => ({ ...prev, ...parsed }));
        notify("success", "Settings imported (secrets must be re-entered)");
      } catch {
        notify("error", "Invalid settings file format");
      }
    };
    input.click();
  };

  const tabs = Object.entries(TAB_SECTIONS)
    .filter(([id]) => {
      if (
        (id === "agentsTab" || id === "skillsPromptsTab" || id === "mcp" || id === "importExport") &&
        !chatFirstUi.enabled
      ) {
        return false;
      }
      return true;
    })
    .map(([id, tab]) => ({
      id,
      label: tab.label,
      icon: tab.icon,
    }));

  const currentSections = TAB_SECTIONS[activeTab]?.sections ?? [];

  return (
    <div className="space-y-6">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between"
      >
        <div className="flex items-center gap-2">
          <h2 className="text-2xl font-bold text-[var(--text-primary)]">Settings</h2>
          <ContextHelpButton contextId="settings.backend" />
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" icon={Upload} onClick={handleImport}>
            Import
          </Button>
          <Button variant="ghost" size="sm" icon={Download} onClick={handleExport}>
            Export
          </Button>
          <Button
            variant="ghost"
            size="sm"
            icon={Trash2}
            onClick={handleReset}
            className="text-red-400 hover:text-red-300"
          >
            Reset
          </Button>
          <Button variant="primary" size="sm" icon={Save} loading={saving} onClick={handleSave}>
            {saving ? "Saving..." : "Save"}
          </Button>
        </div>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
      >
        <Tabs tabs={tabs} activeTab={activeTab} onChange={setActiveTab} />
      </motion.div>

      <TabPanels>
        <motion.div
          key={activeTab}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.2 }}
        >
          <SettingsActiveTabPanel
            activeTab={activeTab}
            chatFirstEnabled={chatFirstUi.enabled}
            notify={notify}
            settings={settings}
            setSettings={setSettings}
            currentSections={currentSections}
          />
        </motion.div>
      </TabPanels>
    </div>
  );
}
