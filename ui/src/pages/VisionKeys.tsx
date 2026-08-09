import { Eye, EyeOff, Key, Loader2, Plus, TestTube, Trash2 } from "lucide-react";
// NOSONAR(typescript:S3776,typescript:S2004,typescript:S6478,typescript:S6479,typescript:S3358,typescript:S6759,typescript:S6551,typescript:S2486,typescript:S6819): UI components are intentionally complex for feature-rich DX
import { useCallback, useMemo, useState } from "react";
import { Badge, Button, Card, DataTable, EmptyState, Input, Modal, Tag } from "../components/ui";
import { useNotify } from "../context/NotificationContext";
import {
  type VisionKeyConfig,
  type VisionKeyTestResult,
  type VisionKeysResponse,
  deleteVisionKey,
  fetchVisionKeys,
  saveVisionKey,
  testVisionKey,
} from "../lib/api";

interface VisionKeyRow {
  readonly provider: string;
  readonly config: VisionKeyConfig;
}

export default function VisionKeys() {
  const [keys, setKeys] = useState<VisionKeysResponse["data"]>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);
  const [form, setForm] = useState({
    provider: "",
    apiKey: "",
    baseUrl: "",
    modelName: "",
    isActive: true,
  });
  const [submitting, setSubmitting] = useState(false);
  const [testing, setTesting] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<Record<string, VisionKeyTestResult>>({});
  const [showKey, setShowKey] = useState<Record<string, boolean>>({});
  const { notify } = useNotify();

  const loadKeys = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchVisionKeys();
      setKeys(data.data);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useState(() => {
    loadKeys();
  });

  const handleSave = useCallback(
    async (providerId: string) => {
      setSubmitting(true);
      try {
        await saveVisionKey(
          providerId,
          form.apiKey,
          form.baseUrl || undefined,
          form.modelName || undefined,
          form.isActive,
        );
        notify("success", `Vision key for ${providerId} saved`);
        setShowModal(false);
        setEditing(null);
        setForm({ provider: "", apiKey: "", baseUrl: "", modelName: "", isActive: true });
        await loadKeys();
      } catch (e) {
        const msg = e instanceof Error ? e.message : "Unknown error";
        notify("error", `Failed to save key: ${msg}`);
      } finally {
        setSubmitting(false);
      }
    },
    [form, notify, loadKeys],
  );

  const handleDelete = useCallback(
    async (providerId: string) => {
      if (!confirm(`Delete vision key for ${providerId}?`)) return;
      try {
        await deleteVisionKey(providerId);
        notify("success", `Key for ${providerId} deleted`);
        await loadKeys();
      } catch (e) {
        const msg = e instanceof Error ? e.message : "Unknown error";
        notify("error", `Failed to delete: ${msg}`);
      }
    },
    [notify, loadKeys],
  );

  const handleTest = useCallback(
    async (providerId: string) => {
      setTesting(providerId);
      setTestResults((prev) => ({
        ...prev,
        [providerId]: { success: false, message: "Testing..." },
      }));
      try {
        const result = await testVisionKey(providerId);
        setTestResults((prev) => ({ ...prev, [providerId]: result.data }));
        notify(result.data.success ? "success" : "error", result.data.message);
      } catch (e) {
        const msg = e instanceof Error ? e.message : "Unknown error";
        setTestResults((prev) => ({ ...prev, [providerId]: { success: false, message: msg } }));
        notify("error", `Test failed: ${msg}`);
      } finally {
        setTesting(null);
      }
    },
    [notify],
  );

  const startEditing = useCallback((providerId: string, existing?: VisionKeyConfig) => {
    setEditing(providerId);
    setForm({
      provider: providerId,
      apiKey: "",
      baseUrl: existing?.base_url || "",
      modelName: existing?.model_name || "",
      isActive: existing?.is_active ?? true,
    });
    setShowModal(true);
  }, []);

  const cancelEditing = useCallback(() => {
    setShowModal(false);
    setEditing(null);
    setForm({ provider: "", apiKey: "", baseUrl: "", modelName: "", isActive: true });
  }, []);

  const rows: VisionKeyRow[] = useMemo(
    () =>
      Object.entries(keys).map(([provider, config]) => ({
        provider,
        config,
      })),
    [keys],
  );

  const columns = useMemo(
    () => [
      {
        key: "provider",
        label: "Provider",
        render: (row: VisionKeyRow) => (
          <div className="flex items-center gap-2">
            <Key className="w-4 h-4 text-[var(--text-muted)]" />
            <span className="font-medium text-[var(--text-primary)]">{row.provider}</span>
          </div>
        ),
      },
      {
        key: "api_key_masked",
        label: "API Key",
        render: (row: VisionKeyRow) => {
          const visible = showKey[row.provider];
          return (
            <code className="text-xs mono-engineering text-[var(--text-secondary)]">
              {visible ? "••••••••••••" : row.config.api_key_masked || "Not set"}
            </code>
          );
        },
      },
      {
        key: "model_name",
        label: "Model",
        render: (row: VisionKeyRow) => row.config.model_name || "—",
      },
      {
        key: "is_active",
        label: "Status",
        render: (row: VisionKeyRow) => (
          <Badge variant={row.config.is_active ? "success" : "default"} dot>
            {row.config.is_active ? "Active" : "Inactive"}
          </Badge>
        ),
      },
      {
        key: "updated_at",
        label: "Updated",
        render: (row: VisionKeyRow) =>
          row.config.updated_at ? new Date(row.config.updated_at).toLocaleDateString() : "—",
      },
      {
        key: "actions",
        label: "Actions",
        sortable: false,
        render: (row: VisionKeyRow) => (
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="sm"
              icon={TestTube}
              onClick={() => handleTest(row.provider)}
              loading={testing === row.provider}
              title="Test connection"
            />
            <Button
              variant="ghost"
              size="sm"
              icon={showKey[row.provider] ? EyeOff : Eye}
              onClick={() => setShowKey((p) => ({ ...p, [row.provider]: !p[row.provider] }))}
              title="Toggle visibility"
            />
            <Button
              variant="ghost"
              size="sm"
              icon={() => <span className="text-xs font-medium">Edit</span>}
              onClick={() => startEditing(row.provider, row.config)}
              title="Edit"
            />
            <Button
              variant="ghost"
              size="sm"
              icon={Trash2}
              onClick={() => handleDelete(row.provider)}
              className="text-[var(--color-danger)] hover:text-[var(--color-danger)]"
              title="Delete"
            />
          </div>
        ),
      },
    ],
    [showKey, testing, handleTest, handleDelete, startEditing],
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-[var(--text-primary)]">Vision Keys</h1>
          <p className="text-sm text-[var(--text-muted)] mt-1">
            Manage API keys for vision-language model providers
          </p>
        </div>
        <Button
          icon={Plus}
          onClick={() => {
            setEditing(null);
            setForm({ provider: "", apiKey: "", baseUrl: "", modelName: "", isActive: true });
            setShowModal(true);
          }}
        >
          Add Key
        </Button>
      </div>

      {error && (
        <Card padding="md" className="border-[var(--color-danger)]/30 bg-[var(--color-danger)]/5">
          <p className="text-sm text-[var(--color-danger)]">{error}</p>
          <Button variant="ghost" size="sm" onClick={loadKeys} className="mt-2">
            Retry
          </Button>
        </Card>
      )}

      {loading ? (
        <Card padding="lg">
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-6 h-6 animate-spin text-[var(--text-muted)]" />
          </div>
        </Card>
      ) : rows.length === 0 ? (
        <Card padding="lg">
          <EmptyState
            icon={<Key className="w-8 h-8" />}
            title="No vision keys configured"
            description="Add API keys for vision-language providers to enable multimodal AI capabilities."
            action={
              <Button
                icon={Plus}
                onClick={() => {
                  setEditing(null);
                  setForm({ provider: "", apiKey: "", baseUrl: "", modelName: "", isActive: true });
                  setShowModal(true);
                }}
              >
                Add Your First Key
              </Button>
            }
          />
        </Card>
      ) : (
        <Card padding="md">
          <DataTable data={rows} columns={columns} keyExtractor={(r) => r.provider} pageSize={10} />
        </Card>
      )}

      {/* Add/Edit Modal */}
      <Modal
        open={showModal}
        onClose={cancelEditing}
        title={editing ? "Edit Vision Key" : "Add Vision Key"}
        subtitle={editing ? "Update provider configuration" : "Configure a new vision provider"}
        size="md"
      >
        <div className="space-y-4">
          {!editing && (
            <Input
              label="Provider ID"
              value={form.provider}
              onChange={(e) => setForm((p) => ({ ...p, provider: e.target.value }))}
              placeholder="e.g. openai, anthropic, gemini"
              required
            />
          )}
          <Input
            label="API Key"
            type="password"
            value={form.apiKey}
            onChange={(e) => setForm((p) => ({ ...p, apiKey: e.target.value }))}
            placeholder="sk-..."
            required={!editing}
            description={editing ? "Leave blank to keep existing key" : ""}
          />
          <Input
            label="Base URL (optional)"
            value={form.baseUrl}
            onChange={(e) => setForm((p) => ({ ...p, baseUrl: e.target.value }))}
            placeholder="https://api.example.com/v1"
          />
          <Input
            label="Model Name (optional)"
            value={form.modelName}
            onChange={(e) => setForm((p) => ({ ...p, modelName: e.target.value }))}
            placeholder="gpt-4o, claude-3-5-sonnet, etc."
          />
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="isActive"
              checked={form.isActive}
              onChange={(e) => setForm((p) => ({ ...p, isActive: e.target.checked }))}
              className="h-4 w-4 rounded border-[var(--border-primary)] accent-[var(--color-brand-500)]"
            />
            <label htmlFor="isActive" className="text-sm text-[var(--text-secondary)]">
              Active
            </label>
          </div>
          {testing && (
            <div className="flex items-center gap-2 text-xs text-[var(--text-muted)]">
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              Testing connection...
            </div>
          )}
          {testResults[editing || form.provider] && (
            <Tag variant={testResults[editing || form.provider].success ? "success" : "danger"}>
              {testResults[editing || form.provider].message}
            </Tag>
          )}
        </div>
        <div className="flex items-center justify-end gap-2 mt-6">
          <Button variant="ghost" onClick={cancelEditing}>
            Cancel
          </Button>
          <Button
            onClick={() => {
              const pid = editing || form.provider;
              if (!pid) return;
              handleSave(pid);
            }}
            loading={submitting}
            disabled={!editing && !form.provider}
          >
            {editing ? "Save Changes" : "Add Key"}
          </Button>
        </div>
      </Modal>
    </div>
  );
}
