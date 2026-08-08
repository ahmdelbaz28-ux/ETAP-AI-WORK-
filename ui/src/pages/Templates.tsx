import { motion } from "framer-motion";
import { Copy, FileText, Loader2, Pencil, Plus, Search, Trash2 } from "lucide-react";
import { type ReactNode, useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { ContextHelpButton } from "../components/help/ContextHelpButton";
import { Badge, Button, Card, Modal } from "../components/ui";
import { useNotify } from "../context/NotificationContext";
import { API_BASE_URL } from "../lib/api-config";
import { getAuthToken } from "../lib/tokenStorage";

interface Template {
  id: string;
  name: string;
  description: string;
  study_type: string;
  system_config: Record<string, unknown>;
  parameters?: Record<string, unknown>;
  tags?: string[];
  is_public?: boolean;
  usage_count?: number;
  created_by?: string;
  created_at: string;
  updated_at: string;
  is_default: boolean;
}

const STUDY_TYPES: { value: string; label: string }[] = [
  { value: "load_flow", label: "Load Flow" },
  { value: "short_circuit", label: "Short Circuit" },
  { value: "arc_flash", label: "Arc Flash" },
  { value: "protection_coordination", label: "Protection Coordination" },
  { value: "motor_starting", label: "Motor Starting" },
  { value: "harmonic_analysis", label: "Harmonic Analysis" },
  { value: "optimal_power_flow", label: "Optimal Power Flow" },
  { value: "transient_stability", label: "Transient Stability" },
  { value: "cable_sizing", label: "Cable Sizing" },
  { value: "earth_grid", label: "Earth Grid" },
  { value: "renewable_integration", label: "Renewable Integration" },
  { value: "battery_storage", label: "Battery Storage" },
];

interface FormState {
  name: string;
  description: string;
  study_type: string;
  parameters: string; // JSON string in textarea
  tags: string; // comma-separated string in textarea
  is_public: boolean;
}

const EMPTY_FORM: FormState = {
  name: "",
  description: "",
  study_type: "load_flow",
  parameters: "{}",
  tags: "",
  is_public: false,
};

function authHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const token = getAuthToken();
  return { ...(token ? { Authorization: `Bearer ${token}` } : {}), ...extra };
}

async function templatesFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: authHeaders({
      "Content-Type": "application/json",
      ...(init?.headers as Record<string, string> | undefined),
    }),
  });
  const text = await res.text().catch(() => "");
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const parsed = JSON.parse(text);
      if (parsed?.detail) detail = `${detail}: ${parsed.detail}`;
      else if (parsed?.message) detail = `${detail}: ${parsed.message}`;
      else if (parsed?.error) detail = `${detail}: ${parsed.error}`;
    } catch {
      if (text) detail = `${detail}: ${text.slice(0, 200)}`;
    }
    throw new Error(detail);
  }
  try {
    return JSON.parse(text) as T;
  } catch {
    return text as unknown as T;
  }
}

export default function Templates() {
  useTranslation();
  const { notify } = useNotify();
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [editTemplate, setEditTemplate] = useState<Template | null>(null);
  const [formData, setFormData] = useState<FormState>(EMPTY_FORM);
  const [formError, setFormError] = useState<string | null>(null);
  const [formSaving, setFormSaving] = useState(false);
  const [loadingDetail, setLoadingDetail] = useState(false);

  const fetchTemplates = useCallback(async () => {
    setLoading(true);
    try {
      const data = await templatesFetch<{ templates: Template[] } | Template[]>(
        "/api/v1/templates/",
      );
      setTemplates(Array.isArray(data) ? data : (data.templates ?? []));
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      notify("error", `Failed to load templates: ${msg}`);
    } finally {
      setLoading(false);
    }
  }, [notify]);

  useEffect(() => {
    fetchTemplates();
  }, [fetchTemplates]);

  const openCreate = () => {
    setEditTemplate(null);
    setFormData(EMPTY_FORM);
    setFormError(null);
    setShowCreate(true);
  };

  const openEdit = async (tpl: Template) => {
    // Fetch full template detail via GET /{id} — list response may have
    // truncated fields (e.g. parameters omitted). The detail endpoint
    // returns the full record.
    setLoadingDetail(true);
    setFormError(null);
    try {
      const detail = await templatesFetch<Template>(`/api/v1/templates/${tpl.id}`);
      setEditTemplate(detail);
      setFormData({
        name: detail.name ?? "",
        description: detail.description ?? "",
        study_type: detail.study_type ?? "load_flow",
        parameters: JSON.stringify(detail.parameters ?? {}, null, 2),
        tags: (detail.tags ?? []).join(", "),
        is_public: detail.is_public ?? false,
      });
      setShowCreate(true);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      notify("error", `Failed to load template detail: ${msg}`);
    } finally {
      setLoadingDetail(false);
    }
  };

  const handleCreateOrUpdate = async () => {
    setFormError(null);
    setFormSaving(true);

    // Parse parameters JSON
    let parameters: Record<string, unknown> = {};
    try {
      parameters = formData.parameters.trim() ? JSON.parse(formData.parameters) : {};
    } catch (err) {
      setFormError(
        `Parameters must be valid JSON: ${err instanceof Error ? err.message : String(err)}`,
      );
      setFormSaving(false);
      return;
    }

    // Parse tags (comma-separated → array)
    const tags = formData.tags
      .split(",")
      .map((t) => t.trim())
      .filter((t) => t.length > 0);

    try {
      if (editTemplate) {
        // PUT /{id} — partial update
        const body = {
          name: formData.name.trim(),
          description: formData.description.trim() || null,
          study_type: formData.study_type,
          parameters,
          tags,
          is_public: formData.is_public,
        };
        await templatesFetch<Template>(`/api/v1/templates/${editTemplate.id}`, {
          method: "PUT",
          body: JSON.stringify(body),
        });
        notify("success", `Template "${body.name}" updated successfully`);
      } else {
        // POST / — create
        const body = {
          name: formData.name.trim(),
          description: formData.description.trim() || null,
          study_type: formData.study_type,
          parameters,
          tags,
          is_public: formData.is_public,
        };
        await templatesFetch<Template>("/api/v1/templates/", {
          method: "POST",
          body: JSON.stringify(body),
        });
        notify("success", "Template created successfully");
      }
      setShowCreate(false);
      setFormData(EMPTY_FORM);
      setEditTemplate(null);
      fetchTemplates();
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setFormError(msg);
      notify("error", `Failed to ${editTemplate ? "update" : "create"} template: ${msg}`);
    } finally {
      setFormSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await templatesFetch(`/api/v1/templates/${id}`, {
        method: "DELETE",
      });
      notify("success", "Template deleted");
      fetchTemplates();
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      notify("error", `Failed to delete template: ${msg}`);
    }
  };

  const handleApply = async (id: string) => {
    try {
      await templatesFetch(`/api/v1/templates/${id}/apply`, {
        method: "POST",
      });
      notify("success", "Template applied to current study");
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      notify("error", `Failed to apply template: ${msg}`);
    }
  };

  const filtered = templates.filter(
    (t) =>
      t.name.toLowerCase().includes(search.toLowerCase()) ||
      (t.description ?? "").toLowerCase().includes(search.toLowerCase()),
  );

  // S3358: render states via if/else instead of a nested ternary chain.
  let content: ReactNode;
  if (loading) {
    content = (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 animate-spin text-brand-500" />
      </div>
    );
  } else if (filtered.length === 0) {
    content = (
      <Card>
        <div className="p-12 text-center">
          <FileText className="w-12 h-12 text-[var(--text-muted)] mx-auto mb-3" />
          <p className="text-[var(--text-muted)]">
            No templates found. Create your first template to get started.
          </p>
        </div>
      </Card>
    );
  } else {
    content = (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filtered.map((tpl) => (
          <Card key={tpl.id} className="hover:border-brand-500/40 transition-colors">
            <div className="p-4 space-y-3">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-2 min-w-0">
                  <FileText className="w-5 h-5 text-brand-500 shrink-0" />
                  <h3 className="font-semibold text-[var(--text-primary)] truncate">{tpl.name}</h3>
                </div>
                <div className="flex items-center gap-1 shrink-0">
                  <Badge>{tpl.study_type}</Badge>
                  {tpl.is_public && <Badge variant="brand">public</Badge>}
                </div>
              </div>
              <p className="text-sm text-[var(--text-muted)] line-clamp-2">
                {tpl.description || "No description"}
              </p>
              {(tpl.tags?.length ?? 0) > 0 && (
                <div className="flex flex-wrap gap-1">
                  {tpl.tags?.slice(0, 4).map((tag) => (
                    <span
                      key={tag}
                      className="px-1.5 py-0.5 text-[10px] rounded-full bg-[var(--bg-elevated)] text-[var(--text-muted)]"
                    >
                      {tag}
                    </span>
                  ))}
                  {(tpl.tags?.length ?? 0) > 4 && (
                    <span className="px-1.5 py-0.5 text-[10px] text-[var(--text-muted)]">
                      +{(tpl.tags?.length ?? 0) - 4} more
                    </span>
                  )}
                </div>
              )}
              <div className="flex items-center justify-between pt-2 border-t border-[var(--border-primary)]">
                <div className="flex gap-1">
                  <button
                    onClick={() => handleApply(tpl.id)}
                    className="p-1.5 rounded-md text-[var(--text-muted)] hover:text-green-400 hover:bg-green-500/10 transition-colors"
                    title="Apply template"
                    type="button"
                  >
                    <Copy className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => openEdit(tpl)}
                    className="p-1.5 rounded-md text-[var(--text-muted)] hover:text-blue-400 hover:bg-blue-500/10 transition-colors"
                    title="Edit template (GET + PUT /{id})"
                    type="button"
                    disabled={loadingDetail}
                  >
                    {loadingDetail ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <Pencil className="w-4 h-4" />
                    )}
                  </button>
                  <button
                    onClick={() => handleDelete(tpl.id)}
                    className="p-1.5 rounded-md text-[var(--text-muted)] hover:text-red-400 hover:bg-red-500/10 transition-colors"
                    title="Delete template"
                    type="button"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
                <span className="text-xs text-[var(--text-muted)]">
                  {tpl.usage_count ? `${tpl.usage_count}× · ` : ""}
                  {new Date(tpl.updated_at).toLocaleDateString()}
                </span>
              </div>
            </div>
          </Card>
        ))}
      </div>
    );
  }

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)] flex items-center gap-2">
            <FileText className="w-6 h-6 text-brand-500" />
            Templates
          </h1>
          <p className="text-sm text-[var(--text-muted)] mt-1">
            Manage study templates for quick configuration
          </p>
        </div>
        <div className="flex items-center gap-3">
          <ContextHelpButton contextId="templates" />
          <Button onClick={openCreate}>
            <Plus className="w-4 h-4" /> New Template
          </Button>
        </div>
      </div>

      <div className="flex gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-muted)]" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search templates..."
            className="w-full pl-10 pr-4 py-2.5 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:ring-2 focus:ring-brand-500/50"
          />
        </div>
      </div>

      {content}

      {/* Create/Edit Modal */}
      <Modal open={showCreate} onClose={() => setShowCreate(false)}>
        <div className="p-6 space-y-4">
          <h2 className="text-lg font-semibold text-[var(--text-primary)]">
            {editTemplate ? "Edit Template" : "Create Template"}
          </h2>
          <div className="space-y-3">
            <div>
              <label
                htmlFor="tpl-name"
                className="block text-sm font-medium text-[var(--text-primary)] mb-1"
              >
                Name
              </label>
              <input
                id="tpl-name"
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="w-full px-3 py-2 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] text-[var(--text-primary)]"
                placeholder="Template name"
              />
            </div>
            <div>
              <label
                htmlFor="tpl-description"
                className="block text-sm font-medium text-[var(--text-primary)] mb-1"
              >
                Description
              </label>
              <textarea
                id="tpl-description"
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                className="w-full px-3 py-2 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] text-[var(--text-primary)]"
                rows={3}
                placeholder="Template description"
              />
            </div>
            <div>
              <label
                htmlFor="tpl-study-type"
                className="block text-sm font-medium text-[var(--text-primary)] mb-1"
              >
                Study Type
              </label>
              <select
                id="tpl-study-type"
                value={formData.study_type}
                onChange={(e) => setFormData({ ...formData, study_type: e.target.value })}
                className="w-full px-3 py-2 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] text-[var(--text-primary)]"
              >
                {STUDY_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label
                htmlFor="tpl-parameters"
                className="block text-sm font-medium text-[var(--text-primary)] mb-1"
              >
                Parameters (JSON)
              </label>
              <textarea
                id="tpl-parameters"
                value={formData.parameters}
                onChange={(e) => setFormData({ ...formData, parameters: e.target.value })}
                className="w-full px-3 py-2 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] text-[var(--text-primary)] font-mono text-xs"
                rows={6}
                placeholder='{"key": "value"}'
              />
              <p className="text-xs text-[var(--text-muted)] mt-1">
                JSON object of study parameters. Defaults to {"{}"}.
              </p>
            </div>
            <div>
              <label
                htmlFor="tpl-tags"
                className="block text-sm font-medium text-[var(--text-primary)] mb-1"
              >
                Tags (comma-separated)
              </label>
              <input
                id="tpl-tags"
                type="text"
                value={formData.tags}
                onChange={(e) => setFormData({ ...formData, tags: e.target.value })}
                className="w-full px-3 py-2 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] text-[var(--text-primary)]"
                placeholder="recommended, production, baseline"
              />
            </div>
            <div className="flex items-center gap-2">
              <input
                id="tpl-is-public"
                type="checkbox"
                checked={formData.is_public}
                onChange={(e) => setFormData({ ...formData, is_public: e.target.checked })}
                className="w-4 h-4 rounded border-[var(--border-primary)] bg-[var(--bg-primary)]"
              />
              <label htmlFor="tpl-is-public" className="text-sm text-[var(--text-primary)]">
                Public (visible to all users, not just creator)
              </label>
            </div>
          </div>

          {formError && (
            <div
              role="alert"
              className="flex items-start gap-2 rounded-md border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300"
            >
              <span className="break-words">{formError}</span>
            </div>
          )}

          <div className="flex justify-end gap-3 pt-2">
            <Button variant="ghost" onClick={() => setShowCreate(false)} disabled={formSaving}>
              Cancel
            </Button>
            <Button onClick={handleCreateOrUpdate} disabled={!formData.name.trim() || formSaving}>
              {formSaving && <Loader2 className="w-4 h-4 animate-spin" />}
              {editTemplate ? "Update" : "Create"}
            </Button>
          </div>
        </div>
      </Modal>
    </motion.div>
  );
}
