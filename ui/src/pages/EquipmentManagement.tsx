/**
 * Equipment Management Page — CRUD UI for the equipment library.
 *
 * Wires to all 12 endpoints in api/equipment.py (prefix /api/v1/equipment):
 *   GET    /categories                       — list categories
 *   POST   /categories                       — create category
 *   PUT    /categories/{category_id}         — update category
 *   DELETE /categories/{category_id}         — delete category
 *   GET    /                                 — list equipment (paginated, filterable)
 *   POST   /                                 — create equipment
 *   GET    /{equipment_id}                   — get single equipment
 *   PUT    /{equipment_id}                   — update equipment
 *   DELETE /{equipment_id}                   — delete equipment
 *   GET    /search?query=...                 — search equipment
 *   POST   /import                           — import from JSON/CSV
 *   GET    /export                           — export to JSON/CSV
 *
 * Ref: TASK-2
 */

import { motion } from "framer-motion";
import {
  AlertTriangle,
  Boxes,
  Download,
  Loader2,
  Package,
  Pencil,
  Plus,
  Search,
  Trash2,
  Upload,
} from "lucide-react";
import { type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Badge, Button, Card, EmptyState, Modal, Tabs } from "../components/ui";
import { useNotify } from "../context/NotificationContext";
import { API_BASE_URL } from "../lib/api-config";
import { getAuthToken } from "../lib/tokenStorage";

// ---------------------------------------------------------------------------
// Types — mirror api/equipment.py Pydantic schemas
// ---------------------------------------------------------------------------

interface Category {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  icon: string | null;
  display_order: number;
  equipment_count: number;
  created_at: string | null;
  updated_at: string | null;
}

interface CategoryListResponse {
  categories: Category[];
  total: number;
}

interface CategoryCreatePayload {
  name: string;
  slug: string;
  description?: string | null;
  icon?: string | null;
  display_order?: number;
}

interface Equipment {
  id: string;
  category_id: string;
  category_name: string;
  name: string;
  manufacturer: string | null;
  model_number: string | null;
  serial_number: string | null;
  specs: Record<string, unknown> | null;
  weight_kg: number | null;
  dimensions: string | null;
  standards: Record<string, string> | null;
  tags: string[] | null;
  is_active: boolean;
  notes: string | null;
  created_by: string;
  created_at: string | null;
  updated_at: string | null;
}

interface EquipmentListResponse {
  equipment: Equipment[];
  total: number;
  page: number;
  page_size: number;
}

interface EquipmentCreatePayload {
  category_id: string;
  name: string;
  manufacturer?: string | null;
  model_number?: string | null;
  serial_number?: string | null;
  specs?: Record<string, unknown> | null;
  weight_kg?: number | null;
  dimensions?: string | null;
  standards?: Record<string, string> | null;
  tags?: string[] | null;
  notes?: string | null;
}

type TabId = "equipment" | "categories";

// ---------------------------------------------------------------------------
// Fetch helpers
// ---------------------------------------------------------------------------

function authHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const token = getAuthToken();
  return { ...(token ? { Authorization: `Bearer ${token}` } : {}), ...extra };
}

async function equipFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const callerHeaders = init?.headers;
  const mergedHeaders: Record<string, string> = {};
  if (callerHeaders instanceof Headers) {
    callerHeaders.forEach((value, key) => {
      mergedHeaders[key] = value;
    });
  } else if (Array.isArray(callerHeaders)) {
    for (const [key, value] of callerHeaders) {
      mergedHeaders[key] = value;
    }
  } else if (callerHeaders && typeof callerHeaders === "object") {
    for (const [key, value] of Object.entries(callerHeaders)) {
      mergedHeaders[key] = value;
    }
  }
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: authHeaders(mergedHeaders),
  });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      if (body?.detail) {
        detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
      }
    } catch {
      /* ignore — non-JSON error body */
    }
    throw new Error(detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

function buildQuery(params: Record<string, string | number | boolean | undefined>): string {
  const usp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "") continue;
    usp.set(k, String(v));
  }
  const s = usp.toString();
  return s ? `?${s}` : "";
}

// ---------------------------------------------------------------------------
// Equipment create/edit modal
// ---------------------------------------------------------------------------

interface EquipmentModalProps {
  readonly open: boolean;
  readonly onClose: () => void;
  readonly onSaved: () => void;
  readonly categories: Category[];
  readonly editingEquipment: Equipment | null;
}

interface EquipmentFormState {
  category_id: string;
  name: string;
  manufacturer: string;
  model_number: string;
  serial_number: string;
  weight_kg: string;
  dimensions: string;
  notes: string;
  tags: string;
}

function emptyEquipmentForm(categories: Category[]): EquipmentFormState {
  return {
    category_id: categories[0]?.id ?? "",
    name: "",
    manufacturer: "",
    model_number: "",
    serial_number: "",
    weight_kg: "",
    dimensions: "",
    notes: "",
    tags: "",
  };
}

function EquipmentModal({
  open,
  onClose,
  onSaved,
  categories,
  editingEquipment,
}: EquipmentModalProps) {
  const { notify } = useNotify();
  const [form, setForm] = useState<EquipmentFormState>(emptyEquipmentForm(categories));
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    if (editingEquipment) {
      setForm({
        category_id: editingEquipment.category_id,
        name: editingEquipment.name,
        manufacturer: editingEquipment.manufacturer ?? "",
        model_number: editingEquipment.model_number ?? "",
        serial_number: editingEquipment.serial_number ?? "",
        weight_kg: editingEquipment.weight_kg?.toString() ?? "",
        dimensions: editingEquipment.dimensions ?? "",
        notes: editingEquipment.notes ?? "",
        tags: (editingEquipment.tags ?? []).join(", "),
      });
    } else {
      setForm(emptyEquipmentForm(categories));
    }
  }, [open, editingEquipment, categories]);

  const handleSave = async () => {
    if (!form.category_id) {
      notify(
        "warning",
        "Please select a category first. Create one in the Categories tab if none exist.",
      );
      return;
    }
    if (!form.name.trim()) {
      notify("warning", "Equipment name is required");
      return;
    }
    setSaving(true);
    try {
      const tags = form.tags
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean);
      const weight = form.weight_kg.trim() ? Number.parseFloat(form.weight_kg) : null;
      const payload: EquipmentCreatePayload = {
        category_id: form.category_id,
        name: form.name.trim(),
        manufacturer: form.manufacturer.trim() || null,
        model_number: form.model_number.trim() || null,
        serial_number: form.serial_number.trim() || null,
        weight_kg: Number.isFinite(weight) ? weight : null,
        dimensions: form.dimensions.trim() || null,
        tags: tags.length > 0 ? tags : null,
        notes: form.notes.trim() || null,
      };
      if (editingEquipment) {
        await equipFetch(`/api/v1/equipment/${editingEquipment.id}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
        notify("success", `Equipment "${payload.name}" updated`);
      } else {
        await equipFetch("/api/v1/equipment/", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        notify("success", `Equipment "${payload.name}" created`);
      }
      onSaved();
      onClose();
    } catch (err) {
      notify(
        "error",
        `Failed to save equipment: ${err instanceof Error ? err.message : "unknown"}`,
      );
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={editingEquipment ? "Edit Equipment" : "Create Equipment"}
      subtitle={
        editingEquipment ? `Updating ${editingEquipment.name}` : "Add a new piece of equipment"
      }
      size="lg"
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button
            onClick={handleSave}
            loading={saving}
            disabled={!form.name.trim() || !form.category_id}
          >
            {editingEquipment ? "Update Equipment" : "Create Equipment"}
          </Button>
        </div>
      }
    >
      <div className="space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label
              htmlFor="eq-category"
              className="block text-sm font-medium text-[var(--text-primary)] mb-1"
            >
              Category
            </label>
            <select
              id="eq-category"
              value={form.category_id}
              onChange={(e) => setForm({ ...form, category_id: e.target.value })}
              className="w-full px-3 py-2 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] text-[var(--text-primary)]"
            >
              {categories.length === 0 ? (
                <option value="">No categories — create one first</option>
              ) : (
                categories.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))
              )}
            </select>
          </div>
          <div>
            <label
              htmlFor="eq-name"
              className="block text-sm font-medium text-[var(--text-primary)] mb-1"
            >
              Name
            </label>
            <input
              id="eq-name"
              type="text"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="e.g. 100kVA Transformer"
              className="w-full px-3 py-2 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] text-[var(--text-primary)]"
            />
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div>
            <label
              htmlFor="eq-manufacturer"
              className="block text-sm font-medium text-[var(--text-primary)] mb-1"
            >
              Manufacturer
            </label>
            <input
              id="eq-manufacturer"
              type="text"
              value={form.manufacturer}
              onChange={(e) => setForm({ ...form, manufacturer: e.target.value })}
              placeholder="e.g. ABB"
              className="w-full px-3 py-2 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] text-[var(--text-primary)]"
            />
          </div>
          <div>
            <label
              htmlFor="eq-model"
              className="block text-sm font-medium text-[var(--text-primary)] mb-1"
            >
              Model Number
            </label>
            <input
              id="eq-model"
              type="text"
              value={form.model_number}
              onChange={(e) => setForm({ ...form, model_number: e.target.value })}
              placeholder="e.g. TX-100-3P"
              className="w-full px-3 py-2 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] text-[var(--text-primary)]"
            />
          </div>
          <div>
            <label
              htmlFor="eq-serial"
              className="block text-sm font-medium text-[var(--text-primary)] mb-1"
            >
              Serial Number
            </label>
            <input
              id="eq-serial"
              type="text"
              value={form.serial_number}
              onChange={(e) => setForm({ ...form, serial_number: e.target.value })}
              placeholder="e.g. SN-2024-001"
              className="w-full px-3 py-2 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] text-[var(--text-primary)]"
            />
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label
              htmlFor="eq-weight"
              className="block text-sm font-medium text-[var(--text-primary)] mb-1"
            >
              Weight (kg)
            </label>
            <input
              id="eq-weight"
              type="number"
              step="0.01"
              min="0"
              value={form.weight_kg}
              onChange={(e) => setForm({ ...form, weight_kg: e.target.value })}
              placeholder="e.g. 1250.5"
              className="w-full px-3 py-2 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] text-[var(--text-primary)]"
            />
          </div>
          <div>
            <label
              htmlFor="eq-dimensions"
              className="block text-sm font-medium text-[var(--text-primary)] mb-1"
            >
              Dimensions
            </label>
            <input
              id="eq-dimensions"
              type="text"
              value={form.dimensions}
              onChange={(e) => setForm({ ...form, dimensions: e.target.value })}
              placeholder="e.g. 1200x800x600 mm"
              className="w-full px-3 py-2 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] text-[var(--text-primary)]"
            />
          </div>
        </div>

        <div>
          <label
            htmlFor="eq-tags"
            className="block text-sm font-medium text-[var(--text-primary)] mb-1"
          >
            Tags (comma-separated)
          </label>
          <input
            id="eq-tags"
            type="text"
            value={form.tags}
            onChange={(e) => setForm({ ...form, tags: e.target.value })}
            placeholder="e.g. high-voltage, indoor,三年保修"
            className="w-full px-3 py-2 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] text-[var(--text-primary)]"
          />
        </div>

        <div>
          <label
            htmlFor="eq-notes"
            className="block text-sm font-medium text-[var(--text-primary)] mb-1"
          >
            Notes
          </label>
          <textarea
            id="eq-notes"
            value={form.notes}
            onChange={(e) => setForm({ ...form, notes: e.target.value })}
            rows={3}
            placeholder="Maintenance notes, installation requirements, etc."
            className="w-full px-3 py-2 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] text-[var(--text-primary)]"
          />
        </div>
      </div>
    </Modal>
  );
}

// ---------------------------------------------------------------------------
// Category create/edit modal
// ---------------------------------------------------------------------------

interface CategoryModalProps {
  readonly open: boolean;
  readonly onClose: () => void;
  readonly onSaved: () => void;
  readonly editingCategory: Category | null;
}

interface CategoryFormState {
  name: string;
  slug: string;
  description: string;
  icon: string;
  display_order: string;
}

function CategoryModal({ open, onClose, onSaved, editingCategory }: CategoryModalProps) {
  const { notify } = useNotify();
  const [form, setForm] = useState<CategoryFormState>({
    name: "",
    slug: "",
    description: "",
    icon: "",
    display_order: "0",
  });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    if (editingCategory) {
      setForm({
        name: editingCategory.name,
        slug: editingCategory.slug,
        description: editingCategory.description ?? "",
        icon: editingCategory.icon ?? "",
        display_order: editingCategory.display_order.toString(),
      });
    } else {
      setForm({ name: "", slug: "", description: "", icon: "", display_order: "0" });
    }
  }, [open, editingCategory]);

  // Auto-generate slug from name (only on create, not edit) — convenience
  // that avoids users having to hand-write a slug.
  const autoSlug = (name: string): string =>
    name
      .toLowerCase()
      .trim()
      .replace(/[^a-z0-9_-]+/g, "-")
      .replace(/^-+|-+$/g, "");

  const handleSave = async () => {
    if (!form.name.trim()) {
      notify("warning", "Category name is required");
      return;
    }
    const slug = form.slug.trim() || autoSlug(form.name);
    if (!/^[a-z0-9_-]+$/.test(slug)) {
      notify("warning", "Slug must be lowercase letters, numbers, hyphens, or underscores only");
      return;
    }
    setSaving(true);
    try {
      const payload: CategoryCreatePayload = {
        name: form.name.trim(),
        slug,
        description: form.description.trim() || null,
        icon: form.icon.trim() || null,
        display_order: Number.parseInt(form.display_order || "0", 10) || 0,
      };
      if (editingCategory) {
        await equipFetch(`/api/v1/equipment/categories/${editingCategory.id}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
        notify("success", `Category "${payload.name}" updated`);
      } else {
        await equipFetch("/api/v1/equipment/categories", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        notify("success", `Category "${payload.name}" created`);
      }
      onSaved();
      onClose();
    } catch (err) {
      notify("error", `Failed to save category: ${err instanceof Error ? err.message : "unknown"}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={editingCategory ? "Edit Category" : "Create Category"}
      size="md"
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button onClick={handleSave} loading={saving} disabled={!form.name.trim()}>
            {editingCategory ? "Update Category" : "Create Category"}
          </Button>
        </div>
      }
    >
      <div className="space-y-3">
        <div>
          <label
            htmlFor="cat-name"
            className="block text-sm font-medium text-[var(--text-primary)] mb-1"
          >
            Name
          </label>
          <input
            id="cat-name"
            type="text"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder="e.g. Transformers"
            className="w-full px-3 py-2 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] text-[var(--text-primary)]"
          />
        </div>
        <div>
          <label
            htmlFor="cat-slug"
            className="block text-sm font-medium text-[var(--text-primary)] mb-1"
          >
            Slug
          </label>
          <input
            id="cat-slug"
            type="text"
            value={form.slug}
            onChange={(e) => setForm({ ...form, slug: e.target.value })}
            placeholder="auto-generated from name if blank"
            pattern="^[a-z0-9_-]+$"
            className="w-full px-3 py-2 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] text-[var(--text-primary)]"
          />
          <p className="text-xs text-[var(--text-muted)] mt-1">
            Lowercase letters, numbers, hyphens, underscores only.
          </p>
        </div>
        <div>
          <label
            htmlFor="cat-description"
            className="block text-sm font-medium text-[var(--text-primary)] mb-1"
          >
            Description
          </label>
          <input
            id="cat-description"
            type="text"
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            placeholder="Short description"
            className="w-full px-3 py-2 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] text-[var(--text-primary)]"
          />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label
              htmlFor="cat-icon"
              className="block text-sm font-medium text-[var(--text-primary)] mb-1"
            >
              Icon name (optional)
            </label>
            <input
              id="cat-icon"
              type="text"
              value={form.icon}
              onChange={(e) => setForm({ ...form, icon: e.target.value })}
              placeholder="e.g. Zap"
              className="w-full px-3 py-2 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] text-[var(--text-primary)]"
            />
          </div>
          <div>
            <label
              htmlFor="cat-order"
              className="block text-sm font-medium text-[var(--text-primary)] mb-1"
            >
              Display order
            </label>
            <input
              id="cat-order"
              type="number"
              min="0"
              value={form.display_order}
              onChange={(e) => setForm({ ...form, display_order: e.target.value })}
              className="w-full px-3 py-2 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] text-[var(--text-primary)]"
            />
          </div>
        </div>
      </div>
    </Modal>
  );
}

// ---------------------------------------------------------------------------
// Equipment tab — searchable table + create/edit + bulk delete
// ---------------------------------------------------------------------------

interface EquipmentTabProps {
  readonly equipment: Equipment[];
  readonly categories: Category[];
  readonly loading: boolean;
  readonly error: string | null;
  readonly total: number;
  readonly page: number;
  readonly pageSize: number;
  readonly onReload: () => void;
  readonly onPageChange: (page: number) => void;
  readonly onSearch: (query: string) => void;
  readonly onCategoryFilter: (categoryId: string) => void;
  readonly onManufacturerFilter: (mfr: string) => void;
  readonly onEdit: (eq: Equipment) => void;
  readonly onCreate: () => void;
  readonly onDeleted: () => void;
  readonly searchQuery: string;
  readonly categoryFilter: string;
  readonly manufacturerFilter: string;
}

function EquipmentTab({
  equipment,
  categories,
  loading,
  error,
  total,
  page,
  pageSize,
  onReload,
  onPageChange,
  onSearch,
  onCategoryFilter,
  onManufacturerFilter,
  onEdit,
  onCreate,
  onDeleted,
  searchQuery,
  categoryFilter,
  manufacturerFilter,
}: EquipmentTabProps) {
  const { notify } = useNotify();
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [confirmDelete, setConfirmDelete] = useState<Equipment | null>(null);
  const [confirmBulkDelete, setConfirmBulkDelete] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [bulkDeleting, setBulkDeleting] = useState(false);
  const searchInputRef = useRef<HTMLInputElement>(null);

  const catLookup = useMemo(() => {
    const m = new Map<string, Category>();
    for (const c of categories) m.set(c.id, c);
    return m;
  }, [categories]);

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selectedIds.size === equipment.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(equipment.map((e) => e.id)));
    }
  };

  const handleDelete = async (eq: Equipment) => {
    setDeletingId(eq.id);
    try {
      await equipFetch(`/api/v1/equipment/${eq.id}`, { method: "DELETE" });
      notify("success", `Equipment "${eq.name}" deleted`);
      onDeleted();
      setConfirmDelete(null);
    } catch (err) {
      notify("error", `Failed to delete: ${err instanceof Error ? err.message : "unknown"}`);
    } finally {
      setDeletingId(null);
    }
  };

  const handleBulkDelete = async () => {
    setBulkDeleting(true);
    let ok = 0;
    let fail = 0;
    for (const id of selectedIds) {
      try {
        await equipFetch(`/api/v1/equipment/${id}`, { method: "DELETE" });
        ok++;
      } catch {
        fail++;
      }
    }
    setSelectedIds(new Set());
    setConfirmBulkDelete(false);
    setBulkDeleting(false);
    if (ok > 0) notify("success", `Deleted ${ok} equipment${fail > 0 ? ` (${fail} failed)` : ""}`);
    else if (fail > 0) notify("error", `Failed to delete ${fail} equipment`);
    onDeleted();
  };

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  let content: ReactNode;
  if (loading) {
    content = (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 animate-spin text-brand-500" />
      </div>
    );
  } else if (error) {
    content = (
      <Card>
        <EmptyState
          icon={<AlertTriangle className="w-10 h-10" />}
          title="Failed to load equipment"
          description={error}
          action={<Button onClick={onReload}>Retry</Button>}
        />
      </Card>
    );
  } else if (equipment.length === 0) {
    content = (
      <Card>
        <EmptyState
          icon={<Package className="w-10 h-10" />}
          title={
            searchQuery || categoryFilter || manufacturerFilter
              ? "No equipment matches your filters"
              : "No equipment yet"
          }
          description={
            searchQuery || categoryFilter || manufacturerFilter
              ? "Try clearing filters or using a different search term."
              : "Add your first piece of equipment to start building the library."
          }
          action={
            !searchQuery && !categoryFilter && !manufacturerFilter ? (
              <Button onClick={onCreate}>
                <Plus className="w-4 h-4" /> New Equipment
              </Button>
            ) : undefined
          }
        />
      </Card>
    );
  } else {
    content = (
      <Card padding="none">
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left text-[var(--text-secondary)]">
            <thead className="text-[11px] uppercase tracking-wider text-[var(--text-muted)] border-b border-[var(--border-primary)]">
              <tr>
                <th className="py-3 px-3 w-10">
                  <input
                    type="checkbox"
                    checked={selectedIds.size === equipment.length && equipment.length > 0}
                    onChange={toggleSelectAll}
                    aria-label="Select all equipment on this page"
                    className="w-4 h-4 rounded"
                  />
                </th>
                <th className="py-3 px-4">Name</th>
                <th className="py-3 px-4">Category</th>
                <th className="py-3 px-4">Manufacturer</th>
                <th className="py-3 px-4">Model</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border-primary)]">
              {equipment.map((eq) => {
                const cat = catLookup.get(eq.category_id);
                return (
                  <tr
                    key={eq.id}
                    className={`hover:bg-[var(--bg-elevated)] transition-colors ${
                      selectedIds.has(eq.id) ? "bg-brand-500/5" : ""
                    }`}
                  >
                    <td className="py-3 px-3">
                      <input
                        type="checkbox"
                        checked={selectedIds.has(eq.id)}
                        onChange={() => toggleSelect(eq.id)}
                        aria-label={`Select ${eq.name}`}
                        className="w-4 h-4 rounded"
                      />
                    </td>
                    <td className="py-3 px-4 font-medium text-[var(--text-primary)]">
                      <div className="flex items-center gap-2">
                        <Package className="w-4 h-4 text-brand-400 shrink-0" />
                        {eq.name}
                      </div>
                      {eq.tags && eq.tags.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-1">
                          {eq.tags.slice(0, 3).map((t) => (
                            <Badge key={t} variant="neutral" size="sm">
                              {t}
                            </Badge>
                          ))}
                        </div>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      <Badge variant="info" size="sm">
                        {cat?.name ?? eq.category_name ?? "—"}
                      </Badge>
                    </td>
                    <td className="py-3 px-4 text-[var(--text-muted)]">{eq.manufacturer || "—"}</td>
                    <td className="py-3 px-4 font-mono text-xs text-[var(--text-muted)]">
                      {eq.model_number || "—"}
                    </td>
                    <td className="py-3 px-4">
                      {eq.is_active ? (
                        <Badge variant="success" size="sm">
                          active
                        </Badge>
                      ) : (
                        <Badge variant="default" size="sm">
                          inactive
                        </Badge>
                      )}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <div className="flex justify-end gap-1">
                        <button
                          type="button"
                          onClick={() => onEdit(eq)}
                          className="p-1.5 rounded-md text-[var(--text-muted)] hover:text-brand-400 hover:bg-brand-500/10 transition-colors"
                          title="Edit equipment"
                          aria-label={`Edit ${eq.name}`}
                        >
                          <Pencil className="w-4 h-4" />
                        </button>
                        <button
                          type="button"
                          onClick={() => setConfirmDelete(eq)}
                          disabled={deletingId === eq.id}
                          className="p-1.5 rounded-md text-[var(--text-muted)] hover:text-red-400 hover:bg-red-500/10 transition-colors disabled:opacity-40"
                          title="Delete equipment"
                          aria-label={`Delete ${eq.name}`}
                        >
                          {deletingId === eq.id ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                          ) : (
                            <Trash2 className="w-4 h-4" />
                          )}
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div className="flex items-center justify-between px-4 py-3 border-t border-[var(--border-primary)] text-xs text-[var(--text-muted)]">
          <div>
            {selectedIds.size > 0 ? (
              <span>
                {selectedIds.size} selected ·{" "}
                <button
                  type="button"
                  onClick={() => setConfirmBulkDelete(true)}
                  className="text-red-400 hover:text-red-300 underline"
                >
                  Delete selected
                </button>
              </span>
            ) : (
              <span>
                Showing {equipment.length} of {total} total
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onPageChange(Math.max(1, page - 1))}
              disabled={page <= 1}
            >
              Previous
            </Button>
            <span>
              Page {page} of {totalPages}
            </span>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onPageChange(Math.min(totalPages, page + 1))}
              disabled={page >= totalPages}
            >
              Next
            </Button>
          </div>
        </div>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-muted)]" />
          <input
            ref={searchInputRef}
            type="text"
            value={searchQuery}
            onChange={(e) => onSearch(e.target.value)}
            placeholder="Search by name, model, or manufacturer..."
            className="w-full pl-10 pr-4 py-2.5 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:ring-2 focus:ring-brand-500/50"
          />
        </div>
        <select
          value={categoryFilter}
          onChange={(e) => onCategoryFilter(e.target.value)}
          className="px-3 py-2.5 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] text-[var(--text-primary)]"
          aria-label="Filter by category"
        >
          <option value="">All categories</option>
          {categories.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
        <input
          type="text"
          value={manufacturerFilter}
          onChange={(e) => onManufacturerFilter(e.target.value)}
          placeholder="Manufacturer..."
          className="px-3 py-2.5 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] text-[var(--text-primary)] w-40"
          aria-label="Filter by manufacturer"
        />
        <Button onClick={onCreate}>
          <Plus className="w-4 h-4" /> New Equipment
        </Button>
      </div>
      {content}

      {/* Single delete confirmation */}
      <Modal
        open={confirmDelete !== null}
        onClose={() => setConfirmDelete(null)}
        title="Delete Equipment"
        size="sm"
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setConfirmDelete(null)}>
              Cancel
            </Button>
            <Button
              variant="danger"
              loading={deletingId === confirmDelete?.id}
              onClick={() => confirmDelete && handleDelete(confirmDelete)}
            >
              Delete
            </Button>
          </div>
        }
      >
        <p className="text-sm text-[var(--text-secondary)]">
          Are you sure you want to delete{" "}
          <span className="font-semibold text-[var(--text-primary)]">{confirmDelete?.name}</span>?
          This cannot be undone.
        </p>
      </Modal>

      {/* Bulk delete confirmation */}
      <Modal
        open={confirmBulkDelete}
        onClose={() => setConfirmBulkDelete(false)}
        title="Delete Selected Equipment"
        size="sm"
        footer={
          <div className="flex justify-end gap-2">
            <Button
              variant="ghost"
              onClick={() => setConfirmBulkDelete(false)}
              disabled={bulkDeleting}
            >
              Cancel
            </Button>
            <Button variant="danger" loading={bulkDeleting} onClick={handleBulkDelete}>
              Delete {selectedIds.size} {selectedIds.size === 1 ? "item" : "items"}
            </Button>
          </div>
        }
      >
        <p className="text-sm text-[var(--text-secondary)]">
          You are about to delete{" "}
          <span className="font-semibold text-[var(--text-primary)]">{selectedIds.size}</span>{" "}
          equipment {selectedIds.size === 1 ? "item" : "items"}. This cannot be undone.
        </p>
      </Modal>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Categories tab
// ---------------------------------------------------------------------------

interface CategoriesTabProps {
  readonly categories: Category[];
  readonly loading: boolean;
  readonly error: string | null;
  readonly onReload: () => void;
  readonly onCreate: () => void;
  readonly onEdit: (cat: Category) => void;
  readonly onDeleted: () => void;
}

function CategoriesTab({
  categories,
  loading,
  error,
  onReload,
  onCreate,
  onEdit,
  onDeleted,
}: CategoriesTabProps) {
  const { notify } = useNotify();
  const [confirmDelete, setConfirmDelete] = useState<Category | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const handleDelete = async (cat: Category) => {
    setDeletingId(cat.id);
    try {
      await equipFetch(`/api/v1/equipment/categories/${cat.id}`, { method: "DELETE" });
      notify("success", `Category "${cat.name}" deleted`);
      onDeleted();
      setConfirmDelete(null);
    } catch (err) {
      notify("error", `Failed to delete: ${err instanceof Error ? err.message : "unknown"}`);
    } finally {
      setDeletingId(null);
    }
  };

  let content: ReactNode;
  if (loading) {
    content = (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 animate-spin text-brand-500" />
      </div>
    );
  } else if (error) {
    content = (
      <Card>
        <EmptyState
          icon={<AlertTriangle className="w-10 h-10" />}
          title="Failed to load categories"
          description={error}
          action={<Button onClick={onReload}>Retry</Button>}
        />
      </Card>
    );
  } else if (categories.length === 0) {
    content = (
      <Card>
        <EmptyState
          icon={<Boxes className="w-10 h-10" />}
          title="No categories yet"
          description="Create your first equipment category to start organizing the library."
          action={
            <Button onClick={onCreate}>
              <Plus className="w-4 h-4" /> New Category
            </Button>
          }
        />
      </Card>
    );
  } else {
    content = (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {categories.map((cat) => (
          <Card key={cat.id} padding="md" className="hover:border-brand-500/40 transition-colors">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-2 min-w-0">
                <Boxes className="w-5 h-5 text-brand-400 shrink-0" />
                <h3 className="font-semibold text-[var(--text-primary)] truncate">{cat.name}</h3>
              </div>
              <Badge variant="brand" size="sm">
                {cat.equipment_count}
              </Badge>
            </div>
            <p className="text-xs font-mono text-[var(--text-muted)] mt-1">{cat.slug}</p>
            {cat.description && (
              <p className="text-sm text-[var(--text-secondary)] mt-2 line-clamp-2">
                {cat.description}
              </p>
            )}
            <div className="flex justify-end gap-1 pt-3 mt-3 border-t border-[var(--border-primary)]">
              <button
                type="button"
                onClick={() => onEdit(cat)}
                className="p-1.5 rounded-md text-[var(--text-muted)] hover:text-brand-400 hover:bg-brand-500/10 transition-colors"
                title="Edit category"
                aria-label={`Edit ${cat.name}`}
              >
                <Pencil className="w-4 h-4" />
              </button>
              <button
                type="button"
                onClick={() => setConfirmDelete(cat)}
                disabled={deletingId === cat.id || cat.equipment_count > 0}
                className="p-1.5 rounded-md text-[var(--text-muted)] hover:text-red-400 hover:bg-red-500/10 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                title={
                  cat.equipment_count > 0
                    ? "Cannot delete — category has equipment"
                    : "Delete category"
                }
                aria-label={`Delete ${cat.name}`}
              >
                {deletingId === cat.id ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Trash2 className="w-4 h-4" />
                )}
              </button>
            </div>
          </Card>
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-[var(--text-muted)]">
          {categories.length} {categories.length === 1 ? "category" : "categories"}
        </p>
        <Button onClick={onCreate}>
          <Plus className="w-4 h-4" /> New Category
        </Button>
      </div>
      {content}

      <Modal
        open={confirmDelete !== null}
        onClose={() => setConfirmDelete(null)}
        title="Delete Category"
        size="sm"
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setConfirmDelete(null)}>
              Cancel
            </Button>
            <Button
              variant="danger"
              loading={deletingId === confirmDelete?.id}
              onClick={() => confirmDelete && handleDelete(confirmDelete)}
            >
              Delete
            </Button>
          </div>
        }
      >
        <p className="text-sm text-[var(--text-secondary)]">
          Delete category{" "}
          <span className="font-semibold text-[var(--text-primary)]">{confirmDelete?.name}</span>?
          Equipment in this category will remain but become uncategorized.
        </p>
      </Modal>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main EquipmentManagement page
// ---------------------------------------------------------------------------

export default function EquipmentManagement() {
  const { notify } = useNotify();
  const [activeTab, setActiveTab] = useState<TabId>("equipment");

  // Equipment state
  const [equipment, setEquipment] = useState<Equipment[]>([]);
  const [equipmentLoading, setEquipmentLoading] = useState(true);
  const [equipmentError, setEquipmentError] = useState<string | null>(null);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const pageSize = 25;
  const [searchQuery, setSearchQuery] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [manufacturerFilter, setManufacturerFilter] = useState("");

  // Categories state
  const [categories, setCategories] = useState<Category[]>([]);
  const [categoriesLoading, setCategoriesLoading] = useState(true);
  const [categoriesError, setCategoriesError] = useState<string | null>(null);

  // Modal state
  const [equipmentModalOpen, setEquipmentModalOpen] = useState(false);
  const [editingEquipment, setEditingEquipment] = useState<Equipment | null>(null);
  const [categoryModalOpen, setCategoryModalOpen] = useState(false);
  const [editingCategory, setEditingCategory] = useState<Category | null>(null);

  // Debounced search — avoids hammering the API on every keystroke.
  const [debouncedSearch, setDebouncedSearch] = useState("");
  useEffect(() => {
    const t = setTimeout(() => {
      setDebouncedSearch(searchQuery);
      setPage(1);
    }, 300);
    return () => clearTimeout(t);
  }, [searchQuery]);

  const fetchEquipment = useCallback(async () => {
    setEquipmentLoading(true);
    setEquipmentError(null);
    try {
      const params: Record<string, string | number | boolean | undefined> = {
        page,
        page_size: pageSize,
      };
      if (debouncedSearch) params.search = debouncedSearch;
      if (categoryFilter) params.category_id = categoryFilter;
      if (manufacturerFilter) params.manufacturer = manufacturerFilter;
      const data = await equipFetch<EquipmentListResponse>(
        `/api/v1/equipment/${buildQuery(params)}`,
      );
      setEquipment(data.equipment ?? []);
      setTotal(data.total ?? 0);
    } catch (err) {
      setEquipmentError(err instanceof Error ? err.message : "unknown error");
    } finally {
      setEquipmentLoading(false);
    }
  }, [page, debouncedSearch, categoryFilter, manufacturerFilter]);

  const fetchCategories = useCallback(async () => {
    setCategoriesLoading(true);
    setCategoriesError(null);
    try {
      const data = await equipFetch<CategoryListResponse>("/api/v1/equipment/categories");
      setCategories(data.categories ?? []);
    } catch (err) {
      setCategoriesError(err instanceof Error ? err.message : "unknown error");
    } finally {
      setCategoriesLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchEquipment();
  }, [fetchEquipment]);

  useEffect(() => {
    fetchCategories();
  }, [fetchCategories]);

  // Export handler — calls GET /api/v1/equipment/export and triggers a download.
  const handleExport = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/equipment/export`, {
        headers: authHeaders(),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `equipment-export-${Date.now()}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      notify("success", "Equipment exported");
    } catch (err) {
      notify("error", `Export failed: ${err instanceof Error ? err.message : "unknown"}`);
    }
  };

  // Import handler — POSTs a JSON file to /api/v1/equipment/import.
  const fileInputRef = useRef<HTMLInputElement>(null);
  const handleImportClick = () => fileInputRef.current?.click();
  const handleImportFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const formData = new FormData();
      formData.append("file", file);
      const token = getAuthToken();
      const res = await fetch(`${API_BASE_URL}/api/v1/equipment/import`, {
        method: "POST",
        headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        body: formData,
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      const imported = (data as { imported?: number }).imported ?? 0;
      notify("success", `Imported ${imported} equipment`);
      fetchEquipment();
      fetchCategories();
    } catch (err) {
      notify("error", `Import failed: ${err instanceof Error ? err.message : "unknown"}`);
    } finally {
      // Reset input so the same file can be selected again
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)] flex items-center gap-2">
            <Package className="w-6 h-6 text-brand-500" />
            Equipment Management
          </h1>
          <p className="text-sm text-[var(--text-muted)] mt-1">
            Manage the equipment library: categories, manufacturers, models, and specs
          </p>
        </div>
        <div className="flex items-center gap-2">
          <input
            ref={fileInputRef}
            type="file"
            accept=".json,.csv"
            onChange={handleImportFile}
            className="hidden"
            aria-label="Import equipment file"
          />
          <Button variant="ghost" size="sm" onClick={handleImportClick}>
            <Upload className="w-4 h-4" /> Import
          </Button>
          <Button variant="ghost" size="sm" onClick={handleExport}>
            <Download className="w-4 h-4" /> Export
          </Button>
        </div>
      </div>

      {/* Tabs */}
      <Tabs
        tabs={[
          { id: "equipment", label: "Equipment", badge: total },
          { id: "categories", label: "Categories", badge: categories.length },
        ]}
        activeTab={activeTab}
        onChange={(id) => setActiveTab(id as TabId)}
      />

      {activeTab === "equipment" && (
        <EquipmentTab
          equipment={equipment}
          categories={categories}
          loading={equipmentLoading}
          error={equipmentError}
          total={total}
          page={page}
          pageSize={pageSize}
          onReload={fetchEquipment}
          onPageChange={setPage}
          onSearch={setSearchQuery}
          onCategoryFilter={(id) => {
            setCategoryFilter(id);
            setPage(1);
          }}
          onManufacturerFilter={(mfr) => {
            setManufacturerFilter(mfr);
            setPage(1);
          }}
          onEdit={(eq) => {
            setEditingEquipment(eq);
            setEquipmentModalOpen(true);
          }}
          onCreate={() => {
            setEditingEquipment(null);
            setEquipmentModalOpen(true);
          }}
          onDeleted={fetchEquipment}
          searchQuery={searchQuery}
          categoryFilter={categoryFilter}
          manufacturerFilter={manufacturerFilter}
        />
      )}

      {activeTab === "categories" && (
        <CategoriesTab
          categories={categories}
          loading={categoriesLoading}
          error={categoriesError}
          onReload={fetchCategories}
          onCreate={() => {
            setEditingCategory(null);
            setCategoryModalOpen(true);
          }}
          onEdit={(cat) => {
            setEditingCategory(cat);
            setCategoryModalOpen(true);
          }}
          onDeleted={fetchCategories}
        />
      )}

      <EquipmentModal
        open={equipmentModalOpen}
        onClose={() => setEquipmentModalOpen(false)}
        onSaved={() => {
          fetchEquipment();
          fetchCategories();
        }}
        categories={categories}
        editingEquipment={editingEquipment}
      />
      <CategoryModal
        open={categoryModalOpen}
        onClose={() => setCategoryModalOpen(false)}
        onSaved={fetchCategories}
        editingCategory={editingCategory}
      />
    </motion.div>
  );
}
