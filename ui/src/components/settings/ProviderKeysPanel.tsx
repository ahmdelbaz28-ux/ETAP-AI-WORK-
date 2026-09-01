/**
 * ProviderKeysPanel (P7a — Providers & API Keys)
 * ==============================================
 * Settings tab panel for managing LLM provider API keys through the
 * EXISTING backend settings API (server-side AES-256-GCM encrypted store).
 *
 * SECURITY DESIGN (P7a):
 *   - Server-side authority: keys are stored encrypted on the backend; the
 *     browser only ever receives MASKED representations (api_key_masked).
 *   - No persistence: typed keys live only in ephemeral component state
 *     while the user is editing and are cleared immediately after save.
 *     Nothing is written to localStorage / sessionStorage / Zustand.
 *   - Masked display: after save the UI shows "sk-***...xyz" from the
 *     backend — the full secret is never rendered again.
 *   - Backend-controlled validation: "Test Connection" calls the backend,
 *     which performs the minimal provider API call. The browser never
 *     contacts provider APIs directly.
 *   - No secrets in URLs, logs, data-testid values, or error messages.
 *
 * The provider registry below MUST stay in sync with
 * `services/api_key_store.py :: APIKeyStore.SUPPORTED_PROVIDERS` (the
 * backend is the authority — unsupported providers are never offered).
 */

import {
  CheckCircle2,
  ExternalLink,
  Info,
  Key,
  KeyRound,
  Loader2,
  Save,
  Trash2,
  XCircle,
  Zap,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import {
  type ProviderKeyConfig,
  activateProviderKey,
  deleteProviderKey,
  listProviderKeys,
  saveProviderKey,
  testProviderKey,
} from "../../lib/provider-keys";
import { Button, Card, CardHeader } from "../ui";

type NotifyType = "success" | "error" | "info" | "warning";

interface ProviderKeysPanelProps {
  readonly notify: (type: NotifyType, message: string) => void;
}

interface ProviderMeta {
  id: string;
  name: string;
  description: string;
  defaultBaseUrl: string;
  defaultModel: string;
  docsUrl: string;
}

/**
 * Mirror of APIKeyStore.SUPPORTED_PROVIDERS (backend authority) with display
 * metadata. Keep in sync — providers absent from the backend set must NOT
 * be added here.
 */
export const SERVER_KEY_STORE_PROVIDERS: readonly ProviderMeta[] = [
  {
    id: "openai",
    name: "OpenAI",
    description: "OpenAI and OpenAI-compatible endpoints (Azure, Together AI, Groq, ...).",
    defaultBaseUrl: "https://api.openai.com/v1",
    defaultModel: "gpt-4o",
    docsUrl: "https://platform.openai.com/api-keys",
  },
  {
    id: "anthropic",
    name: "Anthropic",
    description: "Claude models via the Anthropic API.",
    defaultBaseUrl: "https://api.anthropic.com",
    defaultModel: "claude-sonnet-4-5",
    docsUrl: "https://console.anthropic.com/settings/keys",
  },
  {
    id: "gemini",
    name: "Google Gemini",
    description: "Google AI Studio Gemini models.",
    defaultBaseUrl: "",
    defaultModel: "gemini-2.0-flash",
    docsUrl: "https://aistudio.google.com/app/apikey",
  },
  {
    id: "opencode",
    name: "OpenCode Zen",
    description: "OpenCode Zen coding-agent platform (OpenAI-compatible).",
    defaultBaseUrl: "https://opencode.ai/zen/v1",
    defaultModel: "deepseek-v4-flash-free",
    docsUrl: "https://opencode.ai/auth",
  },
  {
    id: "kilocode",
    name: "KiloCode",
    description: "KiloCode coding-agent platform (OpenAI-compatible).",
    defaultBaseUrl: "https://api.kilocode.ai/v1",
    defaultModel: "kilocode-coder-v1",
    docsUrl: "https://kilocode.ai/keys",
  },
  {
    id: "claudecode",
    name: "Claude Code",
    description: "Claude Code platform via the Anthropic API.",
    defaultBaseUrl: "https://api.anthropic.com/v1",
    defaultModel: "claude-3-5-sonnet-latest",
    docsUrl: "https://console.anthropic.com/settings/keys",
  },
  {
    id: "deepseek",
    name: "DeepSeek",
    description: "DeepSeek API (OpenAI-compatible).",
    defaultBaseUrl: "https://api.deepseek.com/v1",
    defaultModel: "deepseek-chat",
    docsUrl: "https://platform.deepseek.com/api_keys",
  },
  {
    id: "groq",
    name: "Groq",
    description: "Groq fast-inference API (OpenAI-compatible).",
    defaultBaseUrl: "https://api.groq.com/openai/v1",
    defaultModel: "llama-3.3-70b-versatile",
    docsUrl: "https://console.groq.com/keys",
  },
  {
    id: "fireworks",
    name: "Fireworks AI",
    description: "Fireworks AI inference platform (OpenAI-compatible).",
    defaultBaseUrl: "https://api.fireworks.ai/inference/v1",
    defaultModel: "",
    docsUrl: "https://fireworks.ai/account/api-keys",
  },
  {
    id: "cloudflare",
    name: "Cloudflare Workers AI",
    description: "Cloudflare Workers AI models.",
    defaultBaseUrl: "",
    defaultModel: "",
    docsUrl: "https://developers.cloudflare.com/workers-ai/",
  },
  {
    id: "zhipu",
    name: "Zhipu (GLM)",
    description: "Zhipu AI GLM models (OpenAI-compatible).",
    defaultBaseUrl: "https://open.bigmodel.cn/api/paas/v4",
    defaultModel: "glm-4-plus",
    docsUrl: "https://open.bigmodel.cn/usercenter/apikeys",
  },
  {
    id: "cohere",
    name: "Cohere",
    description: "Cohere Command models.",
    defaultBaseUrl: "https://api.cohere.com/compatibility/v1",
    defaultModel: "command-r-plus",
    docsUrl: "https://dashboard.cohere.com/api-keys",
  },
  {
    id: "huggingface",
    name: "Hugging Face",
    description: "Hugging Face Inference API.",
    defaultBaseUrl: "https://router.huggingface.co/v1",
    defaultModel: "",
    docsUrl: "https://huggingface.co/settings/tokens",
  },
  {
    id: "nvidia",
    name: "NVIDIA NIM",
    description: "NVIDIA NIM microservices (OpenAI-compatible).",
    defaultBaseUrl: "https://integrate.api.nvidia.com/v1",
    defaultModel: "",
    docsUrl: "https://build.nvidia.com/",
  },
  {
    id: "qwen",
    name: "Qwen (DashScope)",
    description: "Alibaba Qwen models via DashScope (OpenAI-compatible).",
    defaultBaseUrl: "https://dashscope.aliyuncs.com/compatible-mode/v1",
    defaultModel: "qwen-plus",
    docsUrl: "https://dashscope.console.aliyun.com/apiKey",
  },
];

interface EditState {
  apiKey: string;
  baseUrl: string;
  modelName: string;
}

/** Extract a safe, user-facing message from an unknown error. */
function toErrorMessage(err: unknown): string {
  return err instanceof Error ? err.message : "Unknown error";
}

function statusBadgeClass(isActive: boolean): string {
  return isActive
    ? "px-2 py-0.5 text-xs rounded-full bg-green-500/20 text-green-400 border border-green-500/30"
    : "px-2 py-0.5 text-xs rounded-full bg-[var(--bg-primary)] text-[var(--text-muted)] border border-[var(--border-primary)]";
}

export function ProviderKeysPanel({ notify }: ProviderKeysPanelProps) {
  const [keys, setKeys] = useState<Record<string, ProviderKeyConfig>>({});
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<Record<string, EditState>>({});
  const [savingProvider, setSavingProvider] = useState<string | null>(null);
  const [testingProvider, setTestingProvider] = useState<string | null>(null);
  const [activatingProvider, setActivatingProvider] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<
    Record<string, { success: boolean; message: string }>
  >({});

  const loadKeys = useCallback(async () => {
    setLoading(true);
    try {
      const resp = await listProviderKeys();
      setKeys(resp.data || {});
    } catch (err) {
      notify("error", `Failed to load provider keys: ${toErrorMessage(err)}`);
    } finally {
      setLoading(false);
    }
  }, [notify]);

  useEffect(() => {
    loadKeys();
  }, [loadKeys]);

  const startEditing = (providerId: string, existing?: ProviderKeyConfig) => {
    setTestResults((prev) => {
      const next = { ...prev };
      delete next[providerId];
      return next;
    });
    setEditing((prev) => ({
      ...prev,
      [providerId]: {
        // The stored (masked) value is never reused — a fresh key must be typed.
        apiKey: "",
        baseUrl:
          existing?.base_url ||
          SERVER_KEY_STORE_PROVIDERS.find((p) => p.id === providerId)?.defaultBaseUrl ||
          "",
        modelName:
          existing?.model_name ||
          SERVER_KEY_STORE_PROVIDERS.find((p) => p.id === providerId)?.defaultModel ||
          "",
      },
    }));
  };

  const cancelEditing = (providerId: string) => {
    // Drop the typed secret immediately — do not keep it in state.
    setEditing((prev) => {
      const next = { ...prev };
      delete next[providerId];
      return next;
    });
  };

  const handleSave = async (providerId: string) => {
    const edit = editing[providerId];
    if (!edit?.apiKey.trim()) {
      notify("error", "Please enter an API key");
      return;
    }
    setSavingProvider(providerId);
    try {
      await saveProviderKey(providerId, {
        api_key: edit.apiKey.trim(),
        base_url: edit.baseUrl.trim() || undefined,
        model_name: edit.modelName.trim() || undefined,
        is_active: true,
      });
      notify("success", `${providerId} API key saved (encrypted server-side)`);
    } catch (err) {
      notify("error", `Failed to save ${providerId} key: ${toErrorMessage(err)}`);
    } finally {
      // Clear the typed secret in every path (success or failure) and
      // refresh the masked list from the backend.
      cancelEditing(providerId);
      setSavingProvider(null);
      await loadKeys();
    }
  };

  const handleTest = async (providerId: string) => {
    setTestingProvider(providerId);
    setTestResults((prev) => ({
      ...prev,
      [providerId]: { success: false, message: "Testing..." },
    }));
    try {
      const resp = await testProviderKey(providerId);
      const result = resp.data;
      setTestResults((prev) => ({
        ...prev,
        [providerId]: { success: result.success, message: result.message },
      }));
      notify(result.success ? "success" : "warning", result.message);
    } catch (err) {
      const msg = toErrorMessage(err);
      setTestResults((prev) => ({ ...prev, [providerId]: { success: false, message: msg } }));
      notify("error", `Test failed: ${msg}`);
    } finally {
      setTestingProvider(null);
    }
  };

  const handleActivate = async (providerId: string, isActive: boolean) => {
    setActivatingProvider(providerId);
    try {
      const resp = await activateProviderKey(providerId, isActive);
      notify(resp.success ? "success" : "warning", resp.message);
      await loadKeys();
    } catch (err) {
      notify("error", `Failed to update ${providerId}: ${toErrorMessage(err)}`);
    } finally {
      setActivatingProvider(null);
    }
  };

  const handleDelete = async (providerId: string) => {
    if (!window.confirm(`Delete the ${providerId} API key? This cannot be undone.`)) return;
    try {
      await deleteProviderKey(providerId);
      notify("info", `${providerId} API key deleted`);
      await loadKeys();
    } catch (err) {
      notify("error", `Failed to delete ${providerId} key: ${toErrorMessage(err)}`);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-[var(--accent-primary)]" />
        <span className="ml-3 text-[var(--text-muted)]">Loading provider keys...</span>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Card padding="md">
        <CardHeader
          title="Providers & API Keys"
          subtitle="Manage LLM provider API keys. Keys are encrypted (AES-256-GCM) and stored server-side — the browser never stores or re-displays them."
          icon={<KeyRound className="w-5 h-5" />}
        />
        <div className="mt-4 p-3 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border-primary)]">
          <div className="flex items-start gap-2">
            <Info className="w-4 h-4 text-[var(--accent-primary)] mt-0.5 flex-shrink-0" />
            <div className="text-sm text-[var(--text-secondary)]">
              <p className="font-medium mb-1">How it works:</p>
              <ul className="list-disc list-inside space-y-1 text-xs">
                <li>
                  Keys are <strong>encrypted server-side</strong> (AES-256-GCM) — never stored in
                  your browser
                </li>
                <li>
                  Keys are shown <strong>masked only</strong> (sk-***) — the full value is never
                  displayed again after saving
                </li>
                <li>
                  <strong>Test Connection</strong> runs on the backend — your key is never sent to
                  any provider from the browser
                </li>
                <li>
                  Saving a new key replaces the previous one; deactivating keeps it but stops
                  using it
                </li>
              </ul>
            </div>
          </div>
        </div>
      </Card>

      {SERVER_KEY_STORE_PROVIDERS.map((provider) => {
        const existing = keys[provider.id];
        const isEditing = !!editing[provider.id];
        const edit = editing[provider.id];
        const testResult = testResults[provider.id];
        const isSaving = savingProvider === provider.id;
        const isTesting = testingProvider === provider.id;
        const isActivating = activatingProvider === provider.id;

        return (
          <Card key={provider.id} padding="md">
            <CardHeader
              title={
                <div className="flex items-center gap-2">
                  <Key className="w-4 h-4" />
                  <span>{provider.name}</span>
                  {existing && (
                    <span
                      className={statusBadgeClass(existing.is_active)}
                      data-testid={`provider-status-${provider.id}`}
                    >
                      {existing.is_active ? "Active" : "Inactive"}
                    </span>
                  )}
                </div>
              }
              subtitle={provider.description}
              icon={null}
            />

            <div className="mt-4 space-y-4">
              {/* Existing key display (masked only) */}
              {existing && !isEditing && (
                <div className="space-y-3">
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                    <div>
                      <span className="text-xs text-[var(--text-muted)]">API Key (masked)</span>
                      <div
                        className="font-mono text-sm text-[var(--text-secondary)] bg-[var(--bg-secondary)] px-3 py-2 rounded-md border border-[var(--border-primary)]"
                        data-testid={`provider-masked-key-${provider.id}`}
                      >
                        {existing.api_key_masked}
                      </div>
                    </div>
                    {existing.base_url && (
                      <div>
                        <span className="text-xs text-[var(--text-muted)]">Base URL</span>
                        <div className="text-sm text-[var(--text-secondary)] bg-[var(--bg-secondary)] px-3 py-2 rounded-md border border-[var(--border-primary)] break-all">
                          {existing.base_url}
                        </div>
                      </div>
                    )}
                    {existing.model_name && (
                      <div>
                        <span className="text-xs text-[var(--text-muted)]">Model</span>
                        <div className="text-sm text-[var(--text-secondary)] bg-[var(--bg-secondary)] px-3 py-2 rounded-md border border-[var(--border-primary)]">
                          {existing.model_name}
                        </div>
                      </div>
                    )}
                  </div>
                  {existing.updated_at && (
                    <p className="text-xs text-[var(--text-muted)]">
                      Last updated: {existing.updated_at}
                    </p>
                  )}
                  <div className="flex flex-wrap items-center gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      icon={isTesting ? Loader2 : Zap}
                      onClick={() => handleTest(provider.id)}
                      disabled={isTesting}
                      data-testid={`provider-test-${provider.id}`}
                    >
                      {isTesting ? "Testing..." : "Test Connection"}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleActivate(provider.id, !existing.is_active)}
                      disabled={isActivating}
                      data-testid={`provider-activate-${provider.id}`}
                    >
                      {existing.is_active ? "Deactivate" : "Activate"}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      icon={Trash2}
                      onClick={() => handleDelete(provider.id)}
                      className="text-red-400 hover:text-red-300"
                      data-testid={`provider-delete-${provider.id}`}
                    >
                      Delete
                    </Button>
                    <Button
                      variant="primary"
                      size="sm"
                      onClick={() => startEditing(provider.id, existing)}
                      data-testid={`provider-replace-${provider.id}`}
                    >
                      Replace Key
                    </Button>
                  </div>
                  {testResult && (
                    <div
                      className={`flex items-center gap-2 text-xs px-3 py-2 rounded-md border ${
                        testResult.success
                          ? "bg-green-500/10 border-green-500/20 text-green-300"
                          : "bg-red-500/10 border-red-500/20 text-red-300"
                      }`}
                      data-testid={`provider-test-result-${provider.id}`}
                    >
                      {testResult.success ? (
                        <CheckCircle2 className="w-3.5 h-3.5 flex-shrink-0" />
                      ) : (
                        <XCircle className="w-3.5 h-3.5 flex-shrink-0" />
                      )}
                      <span className={testResult.success ? "" : "break-all"}>
                        {testResult.message}
                      </span>
                    </div>
                  )}
                </div>
              )}

              {/* Editing form — typed key is password-masked and cleared on save/cancel */}
              {isEditing && edit && (
                <div className="space-y-3">
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                    <div>
                      <label
                        htmlFor={`provider-${provider.id}-key`}
                        className="text-xs text-[var(--text-muted)] mb-1 block"
                      >
                        API Key
                      </label>
                      <input
                        id={`provider-${provider.id}-key`}
                        type="password"
                        autoComplete="new-password"
                        value={edit.apiKey}
                        onChange={(e) =>
                          setEditing((prev) => ({
                            ...prev,
                            [provider.id]: { ...edit, apiKey: e.target.value },
                          }))
                        }
                        placeholder="Paste your API key"
                        className="w-full px-3 py-2 rounded-md bg-[var(--bg-secondary)] border border-[var(--border-primary)] text-[var(--text-primary)] text-sm focus:outline-none focus:border-[var(--accent-primary)]"
                        data-testid={`provider-key-input-${provider.id}`}
                      />
                    </div>
                    <div>
                      <label
                        htmlFor={`provider-${provider.id}-baseurl`}
                        className="text-xs text-[var(--text-muted)] mb-1 block"
                      >
                        Base URL (optional)
                      </label>
                      <input
                        id={`provider-${provider.id}-baseurl`}
                        type="text"
                        autoComplete="off"
                        value={edit.baseUrl}
                        onChange={(e) =>
                          setEditing((prev) => ({
                            ...prev,
                            [provider.id]: { ...edit, baseUrl: e.target.value },
                          }))
                        }
                        placeholder={provider.defaultBaseUrl || "Default endpoint"}
                        className="w-full px-3 py-2 rounded-md bg-[var(--bg-secondary)] border border-[var(--border-primary)] text-[var(--text-primary)] text-sm focus:outline-none focus:border-[var(--accent-primary)]"
                      />
                    </div>
                    <div>
                      <label
                        htmlFor={`provider-${provider.id}-model`}
                        className="text-xs text-[var(--text-muted)] mb-1 block"
                      >
                        Model (optional)
                      </label>
                      <input
                        id={`provider-${provider.id}-model`}
                        type="text"
                        autoComplete="off"
                        value={edit.modelName}
                        onChange={(e) =>
                          setEditing((prev) => ({
                            ...prev,
                            [provider.id]: { ...edit, modelName: e.target.value },
                          }))
                        }
                        placeholder={provider.defaultModel || "Provider default"}
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
                      data-testid={`provider-save-${provider.id}`}
                    >
                      {isSaving ? "Saving..." : "Save Key"}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => cancelEditing(provider.id)}
                      data-testid={`provider-cancel-${provider.id}`}
                    >
                      Cancel
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

              {/* No key + not editing → "Add Key" */}
              {!existing && !isEditing && (
                <div className="flex items-center gap-3">
                  <p className="text-sm text-[var(--text-muted)]">
                    No key configured on the server
                  </p>
                  <Button
                    variant="ghost"
                    size="sm"
                    icon={Key}
                    onClick={() => startEditing(provider.id)}
                    data-testid={`provider-add-${provider.id}`}
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

export default ProviderKeysPanel;


