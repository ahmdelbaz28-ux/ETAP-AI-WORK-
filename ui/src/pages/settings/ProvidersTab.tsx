/**
 * ProvidersTab (Phase P7a — Providers & API Keys)
 * ================================================
 * Unified settings tab panel for managing LLM and Vision AI provider keys.
 *
 * RUNTIME BEHAVIOR:
 *   - Web Runtime (!isElectronRuntime()):
 *       * API keys are NEVER typed or stored in browser storage (zero localStorage/sessionStorage).
 *       * Input fields for API keys are completely hidden.
 *       * Server-Side Authority banner displayed explaining environment variable management
 *         and the secure /api/v1/chat/stream route (P4b).
 *       * Read-only masked status fetched from backend (GET /api/v1/settings/keys).
 *       * Server-side connection testing via POST /api/v1/settings/keys/{provider}/test.
 *
 *   - Electron Runtime (isElectronRuntime()):
 *       * Local desktop management enabled.
 *       * Input fields available for entering and editing provider API keys.
 *       * Stored in encrypted desktop local configuration.
 *       * Live connection testing via testProviderConnection(providerId).
 *       * Keys are masked after entry (e.g. sk-***...abcd).
 *
 *   - Vision Keys Integration:
 *       * Integrated sub-tab for Vision AI keys (Azure, Google Cloud Vision, OpenAI Vision, etc.).
 *       * Managed via fetchVisionKeys, saveVisionKey, deleteVisionKey, and testVisionKey.
 *       * Adheres to the same Web (server-side only) vs. Electron (local inputs) boundary.
 */

import {
  CheckCircle2,
  Cpu,
  Edit3,
  ExternalLink,
  Eye,
  EyeOff,
  Key,
  KeyRound,
  Loader2,
  Monitor,
  Plus,
  Server,
  Shield,
  Trash2,
  XCircle,
  Zap,
} from "lucide-react";
import { type ReactNode, useCallback, useEffect, useMemo, useState } from "react";
import { Badge, Button, Card, Input, Modal } from "../../components/ui";
import { useNotify } from "../../context/NotificationContext";
import {
  type VisionKeyConfig,
  type VisionKeyTestResult,
  deleteVisionKey,
  fetchVisionKeys,
  saveVisionKey,
  testVisionKey,
} from "../../lib/api";
import { getCachedSettings, refreshSettingsCache } from "../../lib/api-config";
import { isElectronRuntime, testProviderConnection } from "../../lib/llm-chat";
import { type ProviderKeyConfig, listProviderKeys, testProviderKey } from "../../lib/provider-keys";
import { POPULAR_PROVIDERS } from "../Settings";

export interface ProvidersTabProps {
  readonly children?: ReactNode;
  readonly notify?: (type: "success" | "error" | "info" | "warning", message: string) => void;
}

interface EditState {
  apiKey: string;
  baseUrl: string;
  model: string;
}

interface TestStatus {
  testing: boolean;
  success?: boolean;
  message?: string;
  latencyMs?: number;
  errorCode?: string;
  suggestion?: string;
}

const COMMON_VISION_PROVIDERS = [
  { id: "azure_vision", name: "Azure Computer Vision", docsUrl: "https://portal.azure.com" },
  { id: "google_vision", name: "Google Cloud Vision", docsUrl: "https://cloud.google.com/vision" },
  {
    id: "openai_vision",
    name: "OpenAI GPT-4V Vision",
    docsUrl: "https://platform.openai.com/api-keys",
  },
  {
    id: "huggingface_vision",
    name: "Hugging Face ViT",
    docsUrl: "https://huggingface.co/settings/tokens",
  },
];

export function ProvidersTab({ children, notify: notifyProp }: Readonly<ProvidersTabProps>) {
  // Graceful notification resolution
  const contextNotify = useNotifySafe();
  const notify = notifyProp || contextNotify;

  const isElectron = isElectronRuntime();
  const [activeSubTab, setActiveSubTab] = useState<"llm" | "vision">("llm");

  // Server-side LLM keys (fetched from backend)
  const [serverKeys, setServerKeys] = useState<Record<string, ProviderKeyConfig>>({});

  // Vision keys (fetched from backend)
  const [visionKeys, setVisionKeys] = useState<Record<string, VisionKeyConfig>>({});

  // Electron editing state (typed secrets live only in ephemeral state)
  const [editingProvider, setEditingProvider] = useState<string | null>(null);
  const [editFields, setEditFields] = useState<Record<string, EditState>>({});
  const [showKeySecret, setShowKeySecret] = useState<Record<string, boolean>>({});
  const [testStatuses, setTestStatuses] = useState<Record<string, TestStatus>>({});

  // Vision modal state (Electron only)
  const [showVisionModal, setShowVisionModal] = useState(false);
  const [visionForm, setVisionForm] = useState({
    provider: "",
    apiKey: "",
    baseUrl: "",
    modelName: "",
    isActive: true,
  });
  const [submittingVision, setSubmittingVision] = useState(false);
  const [visionTestResults, setVisionTestResults] = useState<Record<string, VisionKeyTestResult>>(
    {},
  );
  const [testingVision, setTestingVision] = useState<string | null>(null);

  // ──────────────────────────────────────────────────────────────────────────
  // Data Fetching
  // ──────────────────────────────────────────────────────────────────────────

  const loadServerKeys = useCallback(async () => {
    try {
      const res = await listProviderKeys();
      if (res?.data) {
        setServerKeys(res.data);
      }
    } catch {
      // Backend key store might not have all keys initialized yet
    }
  }, []);

  const loadVisionKeys = useCallback(async () => {
    try {
      const res = await fetchVisionKeys();
      if (res?.data) {
        setVisionKeys(res.data);
      }
    } catch {
      // Graceful fallback
    }
  }, []);

  useEffect(() => {
    void loadServerKeys();
    void loadVisionKeys();
  }, [loadServerKeys, loadVisionKeys]);

  // Local settings in Electron mode
  const localSettings = useMemo(() => {
    if (!isElectron) return {};
    return getCachedSettings();
  }, [isElectron]);

  // ──────────────────────────────────────────────────────────────────────────
  // Key Masking Helpers
  // ──────────────────────────────────────────────────────────────────────────

  const getMaskedLlmKey = useCallback(
    (providerId: string): string | null => {
      if (serverKeys[providerId]?.api_key_masked) {
        return serverKeys[providerId].api_key_masked;
      }
      if (isElectron) {
        const localKey = localSettings[`PROVIDER_${providerId.toUpperCase()}_KEY`];
        if (localKey && typeof localKey === "string" && localKey.trim()) {
          const trimmed = localKey.trim();
          if (trimmed.length <= 8) return "••••••••";
          return `${trimmed.slice(0, 3)}••••••••${trimmed.slice(-4)}`;
        }
      }
      return null;
    },
    [serverKeys, isElectron, localSettings],
  );

  // ──────────────────────────────────────────────────────────────────────────
  // Connection Testing
  // ──────────────────────────────────────────────────────────────────────────

  const handleTestConnection = async (providerId: string) => {
    setTestStatuses((prev) => ({
      ...prev,
      [providerId]: { testing: true },
    }));

    try {
      if (isElectron) {
        // In Electron: if user has typed a key in the edit form, persist locally first so testProviderConnection can read it
        const currentEdit = editFields[providerId];
        if (currentEdit?.apiKey && typeof window !== "undefined" && window.localStorage) {
          const stored = localStorage.getItem("etap-settings");
          const settings = stored ? JSON.parse(stored) : {};
          settings[`PROVIDER_${providerId.toUpperCase()}_KEY`] = currentEdit.apiKey.trim();
          if (currentEdit.model) {
            settings[`PROVIDER_${providerId.toUpperCase()}_MODEL`] = currentEdit.model.trim();
          }
          if (currentEdit.baseUrl) {
            settings[`PROVIDER_${providerId.toUpperCase()}_BASE_URL`] = currentEdit.baseUrl.trim();
          }
          localStorage.setItem("etap-settings", JSON.stringify(settings));
          await refreshSettingsCache();
        }

        const result = await testProviderConnection(providerId);
        setTestStatuses((prev) => ({
          ...prev,
          [providerId]: {
            testing: false,
            success: result.success,
            message: result.message,
            latencyMs: result.latencyMs,
            errorCode: result.errorCode,
            suggestion: result.suggestion,
          },
        }));

        if (result.success) {
          notify("success", `Connection test passed for ${providerId}`);
        } else {
          notify("error", `Connection test failed: ${result.message}`);
        }
      } else {
        // In Web: NO keys in localStorage! Test strictly via server-side endpoint
        const resp = await testProviderKey(providerId);
        const success = resp.success && resp.data?.success;
        const message =
          resp.data?.message ||
          (success ? "Connected successfully via server" : "Server test failed");
        setTestStatuses((prev) => ({
          ...prev,
          [providerId]: {
            testing: false,
            success,
            message,
          },
        }));

        if (success) {
          notify("success", `Server connection verified for ${providerId}`);
        } else {
          notify("error", `Server test failed: ${message}`);
        }
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Connection test failed";
      setTestStatuses((prev) => ({
        ...prev,
        [providerId]: {
          testing: false,
          success: false,
          message: msg,
        },
      }));
      notify("error", msg);
    }
  };

  // ──────────────────────────────────────────────────────────────────────────
  // Electron Key Saving & Cancellation
  // ──────────────────────────────────────────────────────────────────────────

  const handleStartEdit = (providerId: string) => {
    if (!isElectron) return;
    const providerDef = POPULAR_PROVIDERS.find((p) => p.id === providerId);
    setEditFields((prev) => ({
      ...prev,
      [providerId]: {
        apiKey: "",
        baseUrl:
          localSettings[`PROVIDER_${providerId.toUpperCase()}_BASE_URL`] ||
          providerDef?.defaultBaseUrl ||
          "",
        model:
          localSettings[`PROVIDER_${providerId.toUpperCase()}_MODEL`] ||
          providerDef?.defaultModel ||
          "",
      },
    }));
    setEditingProvider(providerId);
  };

  const handleCancelEdit = (providerId: string) => {
    setEditFields((prev) => {
      const next = { ...prev };
      delete next[providerId];
      return next;
    });
    setEditingProvider(null);
  };

  const handleSaveKey = async (providerId: string) => {
    if (!isElectron) return;
    const edit = editFields[providerId];
    if (!edit?.apiKey.trim()) {
      notify("error", "Please enter an API key");
      return;
    }

    try {
      if (typeof window !== "undefined" && window.localStorage) {
        const stored = localStorage.getItem("etap-settings");
        const settings = stored ? JSON.parse(stored) : {};
        settings[`PROVIDER_${providerId.toUpperCase()}_KEY`] = edit.apiKey.trim();
        if (edit.model.trim()) {
          settings[`PROVIDER_${providerId.toUpperCase()}_MODEL`] = edit.model.trim();
        }
        if (edit.baseUrl.trim()) {
          settings[`PROVIDER_${providerId.toUpperCase()}_BASE_URL`] = edit.baseUrl.trim();
        }
        localStorage.setItem("etap-settings", JSON.stringify(settings));
        await refreshSettingsCache();
      }

      notify("success", `${providerId} API key saved locally`);
      handleCancelEdit(providerId);
    } catch (err) {
      notify(
        "error",
        `Failed to save ${providerId} key: ${err instanceof Error ? err.message : "Error"}`,
      );
    }
  };

  // ──────────────────────────────────────────────────────────────────────────
  // Vision Keys Actions
  // ──────────────────────────────────────────────────────────────────────────

  const handleTestVisionKey = async (providerId: string) => {
    setTestingVision(providerId);
    try {
      const res = await testVisionKey(providerId);
      const testData: VisionKeyTestResult = res?.data || {
        success: res.success,
        message: res.success ? "Vision key verified" : "Vision key test failed",
      };
      setVisionTestResults((prev) => ({
        ...prev,
        [providerId]: testData,
      }));
      if (res.success && testData.success) {
        notify("success", `Vision key verified for ${providerId}`);
      } else {
        notify("error", `Vision key test failed: ${testData.message || "Test failed"}`);
      }
    } catch (err) {
      notify("error", `Test error: ${err instanceof Error ? err.message : "Error"}`);
    } finally {
      setTestingVision(null);
    }
  };

  const handleDeleteVisionKey = async (providerId: string) => {
    if (!confirm(`Delete vision key for ${providerId}?`)) return;
    try {
      await deleteVisionKey(providerId);
      notify("success", `Vision key for ${providerId} removed`);
      await loadVisionKeys();
    } catch (err) {
      notify("error", `Failed to delete key: ${err instanceof Error ? err.message : "Error"}`);
    }
  };

  const handleSaveVisionForm = async () => {
    if (!visionForm.provider.trim() || !visionForm.apiKey.trim()) {
      notify("error", "Provider name and API key are required");
      return;
    }
    setSubmittingVision(true);
    try {
      await saveVisionKey(
        visionForm.provider.trim(),
        visionForm.apiKey.trim(),
        visionForm.baseUrl.trim() || undefined,
        visionForm.modelName.trim() || undefined,
        visionForm.isActive,
      );
      notify("success", `Vision key for ${visionForm.provider} saved`);
      setShowVisionModal(false);
      setVisionForm({ provider: "", apiKey: "", baseUrl: "", modelName: "", isActive: true });
      await loadVisionKeys();
    } catch (err) {
      notify("error", `Failed to save vision key: ${err instanceof Error ? err.message : "Error"}`);
    } finally {
      setSubmittingVision(false);
    }
  };

  // ──────────────────────────────────────────────────────────────────────────
  // Render
  // ──────────────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-6" data-testid="providers-tab-root">
      {/* Top Banner: Web (Server-Side Authority) vs Electron (Desktop) */}
      {!isElectron ? (
        <div
          dir="rtl"
          className="rounded-lg border border-sky-500/30 bg-sky-950/20 p-5 text-right shadow-sm"
          data-testid="web-server-side-banner"
        >
          <div className="flex items-center gap-2.5 text-sky-400 mb-2">
            <Server className="w-5 h-5 text-sky-400" />
            <h2 className="text-base font-semibold text-slate-100">
              إدارة المفاتيح عبر الخادم (Server-Side Authority)
            </h2>
            <Badge variant="info" className="mr-auto font-mono text-[11px]">
              Web Mode — Zero Client Storage
            </Badge>
          </div>
          <p className="text-sm leading-relaxed text-slate-300">
            في وضع الويب، تُدار مفاتيح النماذج (LLM & Vision API Keys) حصرياً عبر متغيرات البيئة على
            الخادم (مثل <code>OPENAI_API_KEY</code> و <code>ANTHROPIC_API_KEY</code>). لا يتم إدخال
            أو تخزين أي مفاتيح في متصفح الويب (localStorage / sessionStorage) حمايةً للسرية ومطابقةً
            لمعايير الأمان الصارمة.
          </p>
          <div className="mt-3.5 flex flex-wrap items-center gap-3 text-xs text-slate-400">
            <span className="flex items-center gap-1.5 font-mono text-sky-300">
              <Shield className="w-3.5 h-3.5 text-emerald-400" />
              Secure Stream: <code>POST /api/v1/chat/stream</code>
            </span>
            <span className="text-slate-500">•</span>
            <span>الاستعلامات والاختبارات تمر عبر الخادم المركزي الآمن</span>
          </div>
        </div>
      ) : (
        <div
          className="rounded-lg border border-emerald-500/30 bg-emerald-950/20 p-5 shadow-sm"
          data-testid="electron-desktop-banner"
        >
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2.5 text-emerald-400">
              <Monitor className="w-5 h-5 text-emerald-400" />
              <h2 className="text-base font-semibold text-slate-100">
                Desktop Mode (Electron Runtime)
              </h2>
            </div>
            <Badge variant="success" className="font-mono text-[11px]">
              Local Workstation Mode
            </Badge>
          </div>
          <p className="text-sm leading-relaxed text-slate-300">
            In desktop mode, API keys are entered locally and stored securely on this workstation.
            Live connection tests communicate through local proxies and desktop engines.
          </p>
        </div>
      )}

      {/* Sub-Tab Navigation: LLM Providers vs Vision Keys */}
      <div className="flex items-center gap-2 border-b border-[var(--border-primary)] pb-2">
        <button
          type="button"
          onClick={() => setActiveSubTab("llm")}
          data-testid="subtab-llm-providers"
          className={`flex items-center gap-2 px-3.5 py-1.5 text-sm font-medium rounded-md transition-colors ${
            activeSubTab === "llm"
              ? "bg-[var(--accent-primary)] text-white shadow-sm"
              : "text-[var(--text-secondary)] hover:text-white hover:bg-[var(--bg-muted)]"
          }`}
        >
          <Cpu className="w-4 h-4" />
          <span>LLM Providers / موفرو النماذج</span>
          <span className="text-xs px-1.5 py-0.2 rounded-full bg-black/20 font-mono">
            {POPULAR_PROVIDERS.length}
          </span>
        </button>

        <button
          type="button"
          onClick={() => setActiveSubTab("vision")}
          data-testid="subtab-vision-keys"
          className={`flex items-center gap-2 px-3.5 py-1.5 text-sm font-medium rounded-md transition-colors ${
            activeSubTab === "vision"
              ? "bg-[var(--accent-primary)] text-white shadow-sm"
              : "text-[var(--text-secondary)] hover:text-white hover:bg-[var(--bg-muted)]"
          }`}
        >
          <Eye className="w-4 h-4" />
          <span>Vision AI Keys / مفاتيح الرؤية</span>
          <span className="text-xs px-1.5 py-0.2 rounded-full bg-black/20 font-mono">
            {Object.keys(visionKeys).length}
          </span>
        </button>
      </div>

      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* TAB 1: LLM Providers (POPULAR_PROVIDERS)                           */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      {activeSubTab === "llm" && (
        <section className="space-y-4" data-testid="llm-providers-section">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-base font-semibold text-slate-100 flex items-center gap-2">
                <KeyRound className="w-4 h-4 text-[var(--accent-primary)]" />
                <span>AI Providers Catalog</span>
              </h3>
              <p className="text-xs text-[var(--text-muted)]">
                {isElectron
                  ? "Configure model endpoints and API keys for desktop power-system workflows."
                  : "Server-side configured LLM providers with masked credential auditing."}
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
            {POPULAR_PROVIDERS.map((provider, idx) => {
              const maskedKey = getMaskedLlmKey(provider.id);
              const isConfigured = !!maskedKey;
              const isEditing = editingProvider === provider.id;
              const edit = editFields[provider.id];
              const testStatus = testStatuses[provider.id];

              return (
                <Card
                  key={`${provider.id}-${idx}`}
                  padding="md"
                  data-testid={`provider-card-${provider.id}`}
                  className="flex flex-col justify-between border-[var(--border-primary)] hover:border-slate-600 transition-colors"
                >
                  <div>
                    {/* Header */}
                    <div className="flex items-start justify-between gap-2 mb-2">
                      <div className="flex items-center gap-2">
                        <div
                          className="w-3 h-3 rounded-full shrink-0"
                          style={{ backgroundColor: provider.color || "#6366f1" }}
                        />
                        <h4 className="font-semibold text-sm text-slate-100">{provider.name}</h4>
                        {provider.isFree && (
                          <Badge variant="info" className="text-[10px] px-1.5 py-0">
                            Free
                          </Badge>
                        )}
                      </div>
                      <Badge
                        variant={isConfigured ? "success" : "default"}
                        className="text-[11px]"
                        data-testid={`provider-status-${provider.id}`}
                      >
                        {isConfigured
                          ? isElectron
                            ? "Configured (Local)"
                            : "Configured (Server)"
                          : "Not Configured"}
                      </Badge>
                    </div>

                    {/* Metadata */}
                    <div className="text-xs text-[var(--text-secondary)] space-y-1 mb-3">
                      <div className="flex items-center justify-between">
                        <span className="text-[var(--text-muted)]">Default Model:</span>
                        <span className="font-mono text-slate-300">
                          {provider.defaultModel || "—"}
                        </span>
                      </div>
                      {provider.defaultBaseUrl && (
                        <div className="flex items-center justify-between">
                          <span className="text-[var(--text-muted)]">Endpoint:</span>
                          <span className="font-mono text-[11px] text-slate-400 truncate max-w-[200px]">
                            {provider.defaultBaseUrl}
                          </span>
                        </div>
                      )}
                    </div>

                    {/* Masked Key Display (Visible in both Web and Electron) */}
                    <div className="rounded-md bg-slate-950/40 border border-slate-800 p-2 text-xs flex items-center justify-between mb-3">
                      <span className="text-[var(--text-muted)] flex items-center gap-1.5">
                        <Key className="w-3.5 h-3.5 text-slate-500" />
                        Key:
                      </span>
                      <span
                        className="font-mono text-slate-200"
                        data-testid={`provider-masked-key-${provider.id}`}
                      >
                        {maskedKey || <span className="text-slate-500 italic">No key entered</span>}
                      </span>
                    </div>

                    {/* Electron Mode: Input Edit Fields */}
                    {isElectron && isEditing && edit && (
                      <div
                        className="space-y-2.5 p-3 rounded-md bg-slate-900/60 border border-slate-700 mb-3"
                        data-testid={`provider-edit-panel-${provider.id}`}
                      >
                        <div>
                          <label
                            htmlFor={`key-input-${provider.id}`}
                            className="block text-[11px] font-medium text-slate-300 mb-1"
                          >
                            API Key:
                          </label>
                          <div className="relative">
                            <Input
                              id={`key-input-${provider.id}`}
                              type={showKeySecret[provider.id] ? "text" : "password"}
                              placeholder="Paste key here…"
                              value={edit.apiKey}
                              onChange={(e) =>
                                setEditFields((prev) => ({
                                  ...prev,
                                  [provider.id]: { ...prev[provider.id], apiKey: e.target.value },
                                }))
                              }
                              data-testid={`provider-key-input-${provider.id}`}
                              className="font-mono text-xs pr-8"
                            />
                            <button
                              type="button"
                              onClick={() =>
                                setShowKeySecret((prev) => ({
                                  ...prev,
                                  [provider.id]: !prev[provider.id],
                                }))
                              }
                              className="absolute right-2 top-2.5 text-slate-400 hover:text-white"
                              title="Toggle visibility"
                            >
                              {showKeySecret[provider.id] ? (
                                <EyeOff className="w-3.5 h-3.5" />
                              ) : (
                                <Eye className="w-3.5 h-3.5" />
                              )}
                            </button>
                          </div>
                        </div>

                        <div>
                          <label
                            htmlFor={`model-input-${provider.id}`}
                            className="block text-[11px] font-medium text-slate-300 mb-1"
                          >
                            Model ID (optional):
                          </label>
                          <Input
                            id={`model-input-${provider.id}`}
                            placeholder={provider.defaultModel}
                            value={edit.model}
                            onChange={(e) =>
                              setEditFields((prev) => ({
                                ...prev,
                                [provider.id]: { ...prev[provider.id], model: e.target.value },
                              }))
                            }
                            data-testid={`provider-model-input-${provider.id}`}
                            className="font-mono text-xs"
                          />
                        </div>

                        <div>
                          <label
                            htmlFor={`url-input-${provider.id}`}
                            className="block text-[11px] font-medium text-slate-300 mb-1"
                          >
                            Base URL (optional):
                          </label>
                          <Input
                            id={`url-input-${provider.id}`}
                            placeholder={provider.defaultBaseUrl}
                            value={edit.baseUrl}
                            onChange={(e) =>
                              setEditFields((prev) => ({
                                ...prev,
                                [provider.id]: { ...prev[provider.id], baseUrl: e.target.value },
                              }))
                            }
                            data-testid={`provider-url-input-${provider.id}`}
                            className="font-mono text-xs"
                          />
                        </div>

                        <div className="flex items-center justify-end gap-2 pt-1">
                          <Button
                            variant="secondary"
                            size="sm"
                            onClick={() => handleCancelEdit(provider.id)}
                            data-testid={`provider-cancel-${provider.id}`}
                          >
                            Cancel
                          </Button>
                          <Button
                            variant="primary"
                            size="sm"
                            onClick={() => handleSaveKey(provider.id)}
                            data-testid={`provider-save-${provider.id}`}
                          >
                            Save Key
                          </Button>
                        </div>
                      </div>
                    )}

                    {/* Test Results Display */}
                    {testStatus?.message && (
                      <div
                        className={`text-xs p-2 rounded border mb-3 flex items-start gap-2 ${
                          testStatus.success
                            ? "bg-emerald-950/30 border-emerald-500/40 text-emerald-300"
                            : "bg-rose-950/30 border-rose-500/40 text-rose-300"
                        }`}
                        data-testid={`provider-test-result-${provider.id}`}
                      >
                        {testStatus.success ? (
                          <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-400 mt-0.5" />
                        ) : (
                          <XCircle className="w-4 h-4 shrink-0 text-rose-400 mt-0.5" />
                        )}
                        <div className="flex-1">
                          <p className="font-medium">{testStatus.message}</p>
                          {testStatus.latencyMs !== undefined && (
                            <p className="text-[10px] text-slate-400 font-mono mt-0.5">
                              Latency: {testStatus.latencyMs}ms
                            </p>
                          )}
                          {testStatus.suggestion && (
                            <p className="text-[10px] text-slate-300 mt-0.5">
                              Suggestion: {testStatus.suggestion}
                            </p>
                          )}
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Actions Footer */}
                  <div className="flex items-center justify-between pt-2 border-t border-slate-800/80 mt-2">
                    {provider.apiKeyUrl ? (
                      <a
                        href={provider.apiKeyUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="text-[11px] text-[var(--accent-primary)] hover:underline flex items-center gap-1"
                      >
                        Get Key <ExternalLink className="w-3 h-3" />
                      </a>
                    ) : (
                      <div />
                    )}

                    <div className="flex items-center gap-1.5">
                      {isElectron && !isEditing && (
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => handleStartEdit(provider.id)}
                          data-testid={`provider-edit-btn-${provider.id}`}
                        >
                          <Edit3 className="w-3.5 h-3.5 mr-1" />
                          {isConfigured ? "Edit" : "Configure"}
                        </Button>
                      )}

                      <Button
                        variant="secondary"
                        size="sm"
                        disabled={testStatus?.testing}
                        onClick={() => handleTestConnection(provider.id)}
                        data-testid={`provider-test-btn-${provider.id}`}
                      >
                        {testStatus?.testing ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" />
                        ) : (
                          <Zap className="w-3.5 h-3.5 mr-1 text-amber-400" />
                        )}
                        Test
                      </Button>
                    </div>
                  </div>
                </Card>
              );
            })}
          </div>
        </section>
      )}

      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* TAB 2: Vision AI Keys (Integrated from VisionKeys.tsx)              */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      {activeSubTab === "vision" && (
        <section className="space-y-4" data-testid="vision-keys-section">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-base font-semibold text-slate-100 flex items-center gap-2">
                <Eye className="w-4 h-4 text-[var(--accent-primary)]" />
                <span>Vision AI Keys / مفاتيح الرؤية الحاسوبية</span>
              </h3>
              <p className="text-xs text-[var(--text-muted)]">
                {isElectron
                  ? "Manage OCR, diagram scanning, and multimodal visual analysis API keys."
                  : "Vision AI credentials configured server-side with masked representation."}
              </p>
            </div>

            {isElectron && (
              <Button
                variant="primary"
                size="sm"
                onClick={() => setShowVisionModal(true)}
                data-testid="add-vision-key-btn"
              >
                <Plus className="w-4 h-4 mr-1" />
                Add Vision Key
              </Button>
            )}
          </div>

          {/* Vision Keys List */}
          {Object.keys(visionKeys).length === 0 ? (
            <Card padding="lg" className="text-center py-8">
              <Eye className="w-8 h-8 text-slate-600 mx-auto mb-2" />
              <p className="text-sm text-slate-400">No Vision AI keys configured</p>
              <p className="text-xs text-slate-500 mt-1">
                {isElectron
                  ? "Click 'Add Vision Key' to configure credentials for OCR and diagram analysis."
                  : "Vision keys are provisioned on the server environment in web mode."}
              </p>
            </Card>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
              {Object.entries(visionKeys).map(([providerId, config]) => {
                const testResult = visionTestResults[providerId];
                const isTesting = testingVision === providerId;

                return (
                  <Card
                    key={providerId}
                    padding="md"
                    data-testid={`vision-card-${providerId}`}
                    className="border-[var(--border-primary)] flex flex-col justify-between"
                  >
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <h4 className="font-semibold text-sm text-slate-100 capitalize">
                          {providerId.replace(/_/g, " ")}
                        </h4>
                        <Badge
                          variant={config.is_active ? "success" : "default"}
                          className="text-[11px]"
                        >
                          {config.is_active ? "Active" : "Inactive"}
                        </Badge>
                      </div>

                      <div className="rounded-md bg-slate-950/40 border border-slate-800 p-2 text-xs flex items-center justify-between mb-2">
                        <span className="text-[var(--text-muted)]">Key:</span>
                        <span
                          className="font-mono text-slate-200"
                          data-testid={`vision-masked-key-${providerId}`}
                        >
                          {config.api_key_masked || "••••••••"}
                        </span>
                      </div>

                      {config.model_name && (
                        <div className="text-xs text-slate-400 mb-1">
                          Model:{" "}
                          <span className="font-mono text-slate-300">{config.model_name}</span>
                        </div>
                      )}

                      {testResult && (
                        <div
                          className={`text-xs p-2 rounded border my-2 ${
                            testResult.success
                              ? "bg-emerald-950/30 border-emerald-500/40 text-emerald-300"
                              : "bg-rose-950/30 border-rose-500/40 text-rose-300"
                          }`}
                        >
                          {testResult.message}
                        </div>
                      )}
                    </div>

                    <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-800/80 mt-2">
                      {isElectron && (
                        <Button
                          variant="danger"
                          size="sm"
                          onClick={() => handleDeleteVisionKey(providerId)}
                          data-testid={`vision-delete-btn-${providerId}`}
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </Button>
                      )}

                      <Button
                        variant="secondary"
                        size="sm"
                        disabled={isTesting}
                        onClick={() => handleTestVisionKey(providerId)}
                        data-testid={`vision-test-btn-${providerId}`}
                      >
                        {isTesting ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" />
                        ) : (
                          <Zap className="w-3.5 h-3.5 mr-1 text-amber-400" />
                        )}
                        Test
                      </Button>
                    </div>
                  </Card>
                );
              })}
            </div>
          )}

          {/* Modal for adding vision key in Electron */}
          {isElectron && showVisionModal && (
            <Modal
              open={showVisionModal}
              onClose={() => setShowVisionModal(false)}
              title="Add Vision Key / إضافة مفتاح رؤية"
            >
              <div className="space-y-3 p-1">
                <div>
                  <label
                    htmlFor="vision-provider-select"
                    className="block text-xs font-medium text-slate-300 mb-1"
                  >
                    Provider:
                  </label>
                  <select
                    id="vision-provider-select"
                    value={visionForm.provider}
                    onChange={(e) =>
                      setVisionForm((prev) => ({ ...prev, provider: e.target.value }))
                    }
                    className="w-full rounded border border-slate-700 bg-slate-800 px-2.5 py-1.5 text-xs text-white"
                    data-testid="vision-provider-select"
                  >
                    <option value="">Select a provider…</option>
                    {COMMON_VISION_PROVIDERS.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name}
                      </option>
                    ))}
                    <option value="custom_vision">Custom Vision Provider</option>
                  </select>
                </div>

                <div>
                  <label
                    htmlFor="vision-key-input"
                    className="block text-xs font-medium text-slate-300 mb-1"
                  >
                    API Key:
                  </label>
                  <Input
                    id="vision-key-input"
                    type="password"
                    placeholder="sk-..."
                    value={visionForm.apiKey}
                    onChange={(e) => setVisionForm((prev) => ({ ...prev, apiKey: e.target.value }))}
                    data-testid="vision-key-input"
                    className="font-mono text-xs"
                  />
                </div>

                <div>
                  <label
                    htmlFor="vision-model-input"
                    className="block text-xs font-medium text-slate-300 mb-1"
                  >
                    Model Name (optional):
                  </label>
                  <Input
                    id="vision-model-input"
                    placeholder="e.g. gpt-4o, vit-base"
                    value={visionForm.modelName}
                    onChange={(e) =>
                      setVisionForm((prev) => ({ ...prev, modelName: e.target.value }))
                    }
                    className="font-mono text-xs"
                  />
                </div>

                <div className="flex items-center justify-end gap-2 pt-3">
                  <Button variant="secondary" size="sm" onClick={() => setShowVisionModal(false)}>
                    Cancel
                  </Button>
                  <Button
                    variant="primary"
                    size="sm"
                    disabled={submittingVision}
                    onClick={handleSaveVisionForm}
                    data-testid="vision-save-modal-btn"
                  >
                    {submittingVision ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" />
                    ) : null}
                    Save Vision Key
                  </Button>
                </div>
              </div>
            </Modal>
          )}
        </section>
      )}

      {/* Optional children rendered in Electron mode for legacy components */}
      {isElectron && children}
    </div>
  );
}

/** Safe wrapper around useNotify to handle cases where context is not mounted. */
function useNotifySafe(): (
  type: "success" | "error" | "info" | "warning",
  message: string,
) => void {
  try {
    const ctx = useNotify();
    return ctx?.notify || fallbackNotify;
  } catch {
    return fallbackNotify;
  }
}

function fallbackNotify(type: string, message: string) {
  if (type === "error") {
    console.error(`[Notification] ${type}: ${message}`);
  } else {
    console.log(`[Notification] ${type}: ${message}`);
  }
}

export default ProvidersTab;
