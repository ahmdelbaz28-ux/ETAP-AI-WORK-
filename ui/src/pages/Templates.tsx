import { getAuthToken } from "../lib/tokenStorage";
import { motion } from "framer-motion";
import { FileText, Plus, Search, Loader2, Trash2, Copy } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { ContextHelpButton } from "../components/help/ContextHelpButton";
import { Badge, Button, Card, Modal } from "../components/ui";
import { useNotify } from "../context/NotificationContext";
import { API_BASE_URL } from "../lib/api-config";

interface Template {
  id: string;
  name: string;
  description: string;
  study_type: string;
  system_config: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  is_default: boolean;
}

export default function Templates() {
  useTranslation();
  const { notify } = useNotify();
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [editTemplate, setEditTemplate] = useState<Template | null>(null);
  const [formData, setFormData] = useState({ name: "", description: "", study_type: "load_flow" });

  const fetchTemplates = async () => {
    setLoading(true);
    try {
      const token = getAuthToken();
      const res = await fetch(`${API_BASE_URL}/api/v1/templates/`, {
        headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setTemplates(data.templates || data || []);
    } catch {
      notify("error", "Failed to load templates");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchTemplates(); }, []);

  const handleCreate = async () => {
    try {
      const token = getAuthToken();
      const res = await fetch(`${API_BASE_URL}/api/v1/templates/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(formData),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      notify("success", "Template created successfully");
      setShowCreate(false);
      setFormData({ name: "", description: "", study_type: "load_flow" });
      fetchTemplates();
    } catch {
      notify("error", "Failed to create template");
    }
  };

  const handleDelete = async (id: string) => {
    try {
      const token = getAuthToken();
      const res = await fetch(`${API_BASE_URL}/api/v1/templates/${id}`, {
        method: "DELETE",
        headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      notify("success", "Template deleted");
      fetchTemplates();
    } catch {
      notify("error", "Failed to delete template");
    }
  };

  const handleApply = async (id: string) => {
    try {
      const token = getAuthToken();
      const res = await fetch(`${API_BASE_URL}/api/v1/templates/${id}/apply`, {
        method: "POST",
        headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      notify("success", "Template applied to current study");
    } catch {
      notify("error", "Failed to apply template");
    }
  };

  const filtered = templates.filter((t) =>
    t.name.toLowerCase().includes(search.toLowerCase()) ||
    t.description.toLowerCase().includes(search.toLowerCase())
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
          <p className="text-[var(--text-muted)]">No templates found. Create your first template to get started.</p>
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
                <Badge>{tpl.study_type}</Badge>
              </div>
              <p className="text-sm text-[var(--text-muted)] line-clamp-2">{tpl.description}</p>
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
                    onClick={() => handleDelete(tpl.id)}
                    className="p-1.5 rounded-md text-[var(--text-muted)] hover:text-red-400 hover:bg-red-500/10 transition-colors"
                    title="Delete template"
                    type="button"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
                <span className="text-xs text-[var(--text-muted)]">
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
          <p className="text-sm text-[var(--text-muted)] mt-1">Manage study templates for quick configuration</p>
        </div>
        <div className="flex items-center gap-3">
          <ContextHelpButton contextId="templates" />
          <Button onClick={() => { setEditTemplate(null); setFormData({ name: "", description: "", study_type: "load_flow" }); setShowCreate(true); }}>
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
              <label htmlFor="tpl-name" className="block text-sm font-medium text-[var(--text-primary)] mb-1">Name</label>
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
              <label htmlFor="tpl-description" className="block text-sm font-medium text-[var(--text-primary)] mb-1">Description</label>
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
              <label htmlFor="tpl-study-type" className="block text-sm font-medium text-[var(--text-primary)] mb-1">Study Type</label>
              <select
                id="tpl-study-type"
                value={formData.study_type}
                onChange={(e) => setFormData({ ...formData, study_type: e.target.value })}
                className="w-full px-3 py-2 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] text-[var(--text-primary)]"
              >
                <option value="load_flow">Load Flow</option>
                <option value="short_circuit">Short Circuit</option>
                <option value="arc_flash">Arc Flash</option>
                <option value="protection_coordination">Protection Coordination</option>
                <option value="motor_starting">Motor Starting</option>
                <option value="harmonic_analysis">Harmonic Analysis</option>
                <option value="optimal_power_flow">Optimal Power Flow</option>
                <option value="transient_stability">Transient Stability</option>
                <option value="cable_sizing">Cable Sizing</option>
                <option value="earth_grid">Earth Grid</option>
                <option value="renewable_integration">Renewable Integration</option>
                <option value="battery_storage">Battery Storage</option>
              </select>
            </div>
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <Button variant="ghost" onClick={() => setShowCreate(false)}>Cancel</Button>
            <Button onClick={handleCreate} disabled={!formData.name.trim()}>
              {editTemplate ? "Update" : "Create"}
            </Button>
          </div>
        </div>
      </Modal>
    </motion.div>
  );
}
