import { motion } from "framer-motion";
import {
  Activity,
  AlertCircle,
  Cable,
  Cpu,
  Eye,
  Filter,
  Loader2,
  Pencil,
  Plus,
  Search,
  Settings2,
  Trash2,
  Wrench,
  Zap,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import ModalBackdrop from "../components/ModalBackdrop";
import ModalHeader from "../components/ModalHeader";
import { ContextHelpButton } from "../components/help/ContextHelpButton";
import { Badge, Button, Card, CardSection, EmptyState } from "../components/ui";
import { useNotify } from "../context/NotificationContext";
import { API_BASE_URL } from "../lib/api-config";
import { cn } from "../utils/helpers";

interface Asset {
  id: string;
  name: string;
  type: string;
  rating: string | null;
  voltage: string | null;
  status: string;
  project_id: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

interface AssetListResponse {
  assets: Asset[];
  total: number;
  page: number;
  page_size: number;
}

const typeIcons: Record<string, React.ReactNode> = {
  Transformer: <Zap className="w-5 h-5" />,
  Generator: <Cpu className="w-5 h-5" />,
  Breaker: <Settings2 className="w-5 h-5" />,
  Motor: <Activity className="w-5 h-5" />,
  Line: <Cable className="w-5 h-5" />,
  Relay: <Settings2 className="w-5 h-5" />,
  Capacitor: <Zap className="w-5 h-5" />,
  Reactor: <Zap className="w-5 h-5" />,
  Bus: <Cpu className="w-5 h-5" />,
  Other: <Cpu className="w-5 h-5" />,
};

const statusConfig: Record<
  string,
  { variant: "success" | "warning" | "danger" | "default"; label: string }
> = {
  active: { variant: "success", label: "Active" },
  maintenance: { variant: "warning", label: "Maintenance" },
  faulted: { variant: "danger", label: "Faulted" },
  offline: { variant: "default", label: "Offline" },
};

const ASSET_TYPES = [
  "Transformer",
  "Generator",
  "Breaker",
  "Motor",
  "Line",
  "Relay",
  "Capacitor",
  "Reactor",
  "Bus",
  "Other",
];
const ASSET_STATUSES = ["active", "maintenance", "faulted", "offline"];

interface AssetFormState {
  name: string;
  type: string;
  rating: string;
  voltage: string;
  status: string;
  notes: string;
}

const EMPTY_FORM: AssetFormState = {
  name: "",
  type: "Transformer",
  rating: "",
  voltage: "",
  status: "active",
  notes: "",
};

function getVariantColor(variant: "success" | "warning" | "danger" | "default"): string {
  if (variant === "success") return "text-green-400";
  if (variant === "warning") return "text-amber-400";
  if (variant === "danger") return "text-red-400";
  return "text-[var(--text-tertiary)]";
}

export default function AssetManagement() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [search, setSearch] = useState("");
  const [filterStatus, setFilterStatus] = useState<string>("all");
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [viewAsset, setViewAsset] = useState<Asset | null>(null);
  const [editAsset, setEditAsset] = useState<Asset | null>(null);
  const [form, setForm] = useState<AssetFormState>(EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [actionInProgress, setActionInProgress] = useState<string | null>(null);
  const { notify } = useNotify();

  // Ref mirror of viewAsset.id so the async View-fetch handler can detect
  // if the user closed the View modal while the fetch was in-flight. Without
  // this guard, the modal would RE-OPEN unexpectedly when the stale fetch
  // completes and calls setViewAsset(freshAsset) on a now-closed modal.
  const viewAssetIdRef = useRef<string | null>(null);
  useEffect(() => {
    viewAssetIdRef.current = viewAsset?.id ?? null;
  }, [viewAsset]);

  const fetchAssets = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const token = localStorage.getItem("authToken");
      const r = await fetch(`${API_BASE_URL}/api/v1/assets?page=1&page_size=100`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        signal: AbortSignal.timeout(8000),
      });
      if (!r.ok) {
        const text = await r.text().catch(() => "Unknown error");
        throw new Error(`API ${r.status}: ${text.substring(0, 100)}`);
      }
      const data: AssetListResponse = await r.json();
      setAssets(data.assets ?? []);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      setError(msg);
      setAssets([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAssets();
  }, [fetchAssets]);

  const handleCreate = useCallback(async () => {
    if (!form.name.trim()) {
      notify("error", "Asset name is required");
      return;
    }
    setSubmitting(true);
    try {
      const token = localStorage.getItem("authToken");
      const r = await fetch(`${API_BASE_URL}/api/v1/assets`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          name: form.name.trim(),
          type: form.type,
          rating: form.rating.trim() || null,
          voltage: form.voltage.trim() || null,
          status: form.status,
          notes: form.notes.trim() || null,
        }),
        signal: AbortSignal.timeout(10000),
      });
      if (!r.ok) {
        const text = await r.text().catch(() => "Unknown error");
        throw new Error(`API ${r.status}: ${text.substring(0, 100)}`);
      }
      notify("success", `Asset "${form.name.trim()}" created`);
      setShowCreateModal(false);
      setForm(EMPTY_FORM);
      await fetchAssets();
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      notify("error", `Failed to create asset: ${msg}`);
    } finally {
      setSubmitting(false);
    }
  }, [form, notify, fetchAssets]);

  const handleDelete = useCallback(
    async (asset: Asset) => {
      if (!confirm(`Delete asset "${asset.name}"? This cannot be undone.`)) return;
      setActionInProgress(asset.id);
      try {
        const token = localStorage.getItem("authToken");
        const r = await fetch(`${API_BASE_URL}/api/v1/assets/${encodeURIComponent(asset.id)}`, {
          method: "DELETE",
          headers: token ? { Authorization: `Bearer ${token}` } : {},
          signal: AbortSignal.timeout(8000),
        });
        if (!r.ok && r.status !== 204) {
          const text = await r.text().catch(() => "Unknown error");
          throw new Error(`API ${r.status}: ${text.substring(0, 100)}`);
        }
        notify("success", `Asset "${asset.name}" deleted`);
        await fetchAssets();
      } catch (e) {
        const msg = e instanceof Error ? e.message : "Unknown error";
        notify("error", `Failed to delete: ${msg}`);
      } finally {
        setActionInProgress(null);
      }
    },
    [notify, fetchAssets],
  );

  // Gap-fill: Read (GET /api/v1/assets/{id}) — fetch full asset detail.
  // The list endpoint already returns all fields, but this gives us a
  // server-side authoritative view (in case the asset changed between
  // list-load and view-click).
  const handleView = useCallback(async (asset: Asset) => {
    setViewAsset(asset); // optimistic — show list data immediately
    setActionInProgress(asset.id);
    try {
      const token = localStorage.getItem("authToken");
      const r = await fetch(`${API_BASE_URL}/api/v1/assets/${encodeURIComponent(asset.id)}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        signal: AbortSignal.timeout(8000),
      });
      // Guard: if the user closed the View modal while the fetch was in-flight,
      // don't update state (would re-open the modal unexpectedly).
      if (viewAssetIdRef.current !== asset.id) return;
      if (r.ok) {
        const fresh: Asset = await r.json();
        // Re-check after await r.json() — the user might have closed during JSON parse.
        if (viewAssetIdRef.current !== asset.id) return;
        setViewAsset(fresh);
      }
      // If r not ok, keep the optimistic list data — view modal still useful.
    } catch {
      // Network/timeout — keep optimistic data, don't surface error to user.
    } finally {
      // Only clear actionInProgress if we're still the active view.
      if (viewAssetIdRef.current === asset.id) {
        setActionInProgress(null);
      }
    }
  }, []);

  // Gap-fill: Update (PUT /api/v1/assets/{id}) — pre-fill form + open edit modal.
  const handleEditClick = useCallback((asset: Asset) => {
    setEditAsset(asset);
    setForm({
      name: asset.name,
      type: asset.type,
      rating: asset.rating ?? "",
      voltage: asset.voltage ?? "",
      status: asset.status,
      notes: asset.notes ?? "",
    });
  }, []);

  const handleUpdate = useCallback(async () => {
    if (!editAsset) return;
    if (!form.name.trim()) {
      notify("error", "Asset name is required");
      return;
    }
    setSubmitting(true);
    try {
      const token = localStorage.getItem("authToken");
      const r = await fetch(`${API_BASE_URL}/api/v1/assets/${encodeURIComponent(editAsset.id)}`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          name: form.name.trim(),
          type: form.type,
          rating: form.rating.trim() || null,
          voltage: form.voltage.trim() || null,
          status: form.status,
          notes: form.notes.trim() || null,
        }),
        signal: AbortSignal.timeout(10000),
      });
      if (!r.ok) {
        const text = await r.text().catch(() => "Unknown error");
        throw new Error(`API ${r.status}: ${text.substring(0, 100)}`);
      }
      notify("success", `Asset "${form.name.trim()}" updated`);
      setEditAsset(null);
      setForm(EMPTY_FORM);
      await fetchAssets();
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      notify("error", `Failed to update asset: ${msg}`);
    } finally {
      setSubmitting(false);
    }
  }, [editAsset, form, notify, fetchAssets]);

  const summaryCards = [
    {
      label: "Active",
      count: assets.filter((a) => a.status === "active").length,
      variant: "success" as const,
      icon: <Activity className="w-4 h-4" />,
    },
    {
      label: "Maintenance",
      count: assets.filter((a) => a.status === "maintenance").length,
      variant: "warning" as const,
      icon: <Wrench className="w-4 h-4" />,
    },
    {
      label: "Faulted",
      count: assets.filter((a) => a.status === "faulted").length,
      variant: "danger" as const,
      icon: <Zap className="w-4 h-4" />,
    },
    {
      label: "Offline",
      count: assets.filter((a) => a.status === "offline").length,
      variant: "default" as const,
      icon: <Cpu className="w-4 h-4" />,
    },
  ];

  const filteredAssets = assets.filter((a) => {
    const matchesSearch =
      search === "" ||
      a.name.toLowerCase().includes(search.toLowerCase()) ||
      a.type.toLowerCase().includes(search.toLowerCase());
    const matchesFilter = filterStatus === "all" || a.status === filterStatus;
    return matchesSearch && matchesFilter;
  });

  return (
    <div className="space-y-6">
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-brand-500/10 border border-brand-500/20">
              <Cpu className="w-5 h-5 text-brand-400" />
            </div>
            <div>
              <h2 className="text-2xl font-bold text-[var(--text-primary)]">Asset Management</h2>
              <div className="flex items-center gap-2">
                <p className="text-sm text-[var(--text-tertiary)]">
                  {assets.length} assets in inventory
                </p>
                <ContextHelpButton contextId="asset-management.overview" />
              </div>
            </div>
          </div>
          <Button variant="primary" size="sm" icon={Plus} onClick={() => setShowCreateModal(true)}>
            Add Asset
          </Button>
        </div>
      </motion.div>

      {/* Summary Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {summaryCards.map((card, i) => {
          const iconColor = getVariantColor(card.variant);
          return (
            <motion.div
              key={card.label}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.05 * i }}
            >
              <Card padding="md" className="text-center">
                <div className="flex items-center justify-center gap-2 mb-2">
                  <span className={cn(iconColor)}>{card.icon}</span>
                  <span className="text-xs text-[var(--text-muted)]">{card.label}</span>
                </div>
                <p className="text-3xl font-bold text-[var(--text-primary)] mono-engineering">
                  {card.count}
                </p>
              </Card>
            </motion.div>
          );
        })}
      </div>

      {/* Search/Filter Bar */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
      >
        <Card padding="sm">
          <div className="flex items-center gap-3">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-muted)]" />
              <input
                type="text"
                placeholder="Search assets..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full pl-9 pr-3 py-2 bg-[var(--bg-input)] border border-[var(--border-primary)] rounded-lg text-[var(--text-primary)] text-sm focus:border-[var(--color-brand-500)] outline-none transition-colors"
              />
            </div>
            <div className="flex items-center gap-1.5">
              <Filter className="w-4 h-4 text-[var(--text-muted)]" />
              {["all", ...ASSET_STATUSES].map((status) => (
                <button
                  key={status}
                  onClick={() => setFilterStatus(status)}
                  className={cn(
                    "px-3 py-1.5 rounded-md text-xs font-medium transition-colors capitalize",
                    filterStatus === status
                      ? "bg-[var(--color-brand-500)] text-white"
                      : "text-[var(--text-tertiary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-elevated)]",
                  )}
                  type="button"
                >
                  {status}
                </button>
              ))}
            </div>
          </div>
        </Card>
      </motion.div>

      {/* Loading State */}
      {loading && (
        <Card padding="lg">
          <div className="flex items-center justify-center py-12 text-[var(--text-muted)]">
            <Loader2 className="w-5 h-5 animate-spin mr-2" />
            Loading assets...
          </div>
        </Card>
      )}

      {/* Error State */}
      {error && !loading && (
        <Card padding="lg">
          <div className="flex items-start gap-3 text-red-400">
            <AlertCircle className="w-5 h-5 mt-0.5 flex-shrink-0" />
            <div>
              <p className="text-sm font-medium">Failed to load assets</p>
              <p className="text-xs text-[var(--text-muted)] mt-1 font-mono">{error}</p>
              <Button variant="ghost" size="sm" className="mt-3" onClick={fetchAssets}>
                Retry
              </Button>
            </div>
          </div>
        </Card>
      )}

      {/* Asset Cards Grid */}
      {!loading && !error && filteredAssets.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredAssets.map((asset, i) => {
            const config = statusConfig[asset.status] || statusConfig.offline;
            return (
              <motion.div
                key={asset.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.05 * i }}
              >
                <Card variant="bordered" padding="md">
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center gap-3">
                      <div className="p-2 rounded-lg bg-brand-500/10 text-brand-400">
                        {typeIcons[asset.type] || <Cpu className="w-5 h-5" />}
                      </div>
                      <div>
                        <h3 className="text-sm font-semibold text-[var(--text-primary)]">
                          {asset.name}
                        </h3>
                        <p className="text-xs text-[var(--text-muted)]">{asset.type}</p>
                      </div>
                    </div>
                    <Badge variant={config.variant} dot size="sm">
                      {config.label}
                    </Badge>
                  </div>
                  <CardSection>
                    <div className="flex items-center justify-between">
                      <div className="grid grid-cols-2 gap-3 text-xs flex-1">
                        <div>
                          <p className="text-[var(--text-muted)]">Rating</p>
                          <p className="text-[var(--text-primary)] font-medium mt-0.5 mono-engineering">
                            {asset.rating || "—"}
                          </p>
                        </div>
                        <div>
                          <p className="text-[var(--text-muted)]">Voltage</p>
                          <p className="text-[var(--text-primary)] font-medium mt-0.5 mono-engineering">
                            {asset.voltage || "—"}
                          </p>
                        </div>
                      </div>
                      <div className="ml-2 flex items-center gap-1">
                        <button
                          onClick={() => handleView(asset)}
                          disabled={actionInProgress === asset.id}
                          title="View asset details"
                          className="p-1.5 rounded text-[var(--text-muted)] hover:text-brand-400 hover:bg-brand-400/10 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                          type="button"
                          aria-label={`View ${asset.name}`}
                        >
                          <Eye className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => handleEditClick(asset)}
                          disabled={actionInProgress === asset.id}
                          title="Edit asset"
                          className="p-1.5 rounded text-[var(--text-muted)] hover:text-brand-300 hover:bg-brand-300/10 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                          type="button"
                          aria-label={`Edit ${asset.name}`}
                        >
                          <Pencil className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => handleDelete(asset)}
                          disabled={actionInProgress === asset.id}
                          title="Delete asset"
                          className="p-1.5 rounded text-[var(--text-muted)] hover:text-red-400 hover:bg-red-400/10 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                          type="button"
                          aria-label={`Delete ${asset.name}`}
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  </CardSection>
                </Card>
              </motion.div>
            );
          })}
        </div>
      )}

      {/* Empty State */}
      {!loading && !error && filteredAssets.length === 0 && (
        <Card padding="lg">
          <EmptyState
            icon={<Cpu className="w-12 h-12" />}
            title={assets.length === 0 ? "No assets yet" : "No assets found"}
            description={
              search ? `No results for "${search}"` : "No assets match the current filter"
            }
            action={
              assets.length === 0 ? (
                <Button
                  variant="primary"
                  size="sm"
                  icon={Plus}
                  onClick={() => setShowCreateModal(true)}
                >
                  Add Asset
                </Button>
              ) : (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setSearch("");
                    setFilterStatus("all");
                  }}
                >
                  Clear filters
                </Button>
              )
            }
          />
        </Card>
      )}

      {/* Create Asset Modal */}
      {showCreateModal && (
        <ModalBackdrop onClose={() => setShowCreateModal(false)} disabled={submitting}>
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            onClick={(e) => e.stopPropagation()}
            className="bg-[var(--bg-elevated)] border border-[var(--border-primary)] rounded-xl w-full max-w-md p-6 shadow-2xl"
          >
            <ModalHeader
              title="Add New Asset"
              onClose={() => setShowCreateModal(false)}
              disabled={submitting}
              icon={Plus}
            />

            <div className="space-y-4">
              <div>
                <label
                  htmlFor="asset-name"
                  className="block text-xs font-medium text-[var(--text-secondary)] mb-1.5"
                >
                  Asset Name <span className="text-red-400">*</span>
                </label>
                <input
                  id="asset-name"
                  type="text"
                  aria-label="Asset Name"
                  value={form.name}
                  onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                  placeholder="e.g., Main Transformer T1"
                  disabled={submitting}
                  className="w-full px-3 py-2 bg-[var(--bg-input)] border border-[var(--border-primary)] rounded-lg text-sm text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 outline-none transition-all disabled:opacity-50"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label
                    htmlFor="asset-type"
                    className="block text-xs font-medium text-[var(--text-secondary)] mb-1.5"
                  >
                    Type
                  </label>
                  <select
                    id="asset-type"
                    aria-label="Type"
                    value={form.type}
                    onChange={(e) => setForm((f) => ({ ...f, type: e.target.value }))}
                    disabled={submitting}
                    className="w-full px-3 py-2 bg-[var(--bg-input)] border border-[var(--border-primary)] rounded-lg text-sm text-[var(--text-primary)] focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 outline-none transition-all disabled:opacity-50"
                  >
                    {ASSET_TYPES.map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label
                    htmlFor="asset-status"
                    className="block text-xs font-medium text-[var(--text-secondary)] mb-1.5"
                  >
                    Status
                  </label>
                  <select
                    id="asset-status"
                    aria-label="Status"
                    value={form.status}
                    onChange={(e) => setForm((f) => ({ ...f, status: e.target.value }))}
                    disabled={submitting}
                    className="w-full px-3 py-2 bg-[var(--bg-input)] border border-[var(--border-primary)] rounded-lg text-sm text-[var(--text-primary)] focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 outline-none transition-all disabled:opacity-50 capitalize"
                  >
                    {ASSET_STATUSES.map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label
                    htmlFor="asset-rating"
                    className="block text-xs font-medium text-[var(--text-secondary)] mb-1.5"
                  >
                    Rating
                  </label>
                  <input
                    id="asset-rating"
                    type="text"
                    aria-label="Rating"
                    value={form.rating}
                    onChange={(e) => setForm((f) => ({ ...f, rating: e.target.value }))}
                    placeholder="e.g., 10 MVA"
                    disabled={submitting}
                    className="w-full px-3 py-2 bg-[var(--bg-input)] border border-[var(--border-primary)] rounded-lg text-sm text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 outline-none transition-all disabled:opacity-50"
                  />
                </div>
                <div>
                  <label
                    htmlFor="asset-voltage"
                    className="block text-xs font-medium text-[var(--text-secondary)] mb-1.5"
                  >
                    Voltage
                  </label>
                  <input
                    id="asset-voltage"
                    type="text"
                    aria-label="Voltage"
                    value={form.voltage}
                    onChange={(e) => setForm((f) => ({ ...f, voltage: e.target.value }))}
                    placeholder="e.g., 13.8 kV"
                    disabled={submitting}
                    className="w-full px-3 py-2 bg-[var(--bg-input)] border border-[var(--border-primary)] rounded-lg text-sm text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 outline-none transition-all disabled:opacity-50"
                  />
                </div>
              </div>
              <div>
                <label
                  htmlFor="asset-notes"
                  className="block text-xs font-medium text-[var(--text-secondary)] mb-1.5"
                >
                  Notes
                </label>
                <textarea
                  id="asset-notes"
                  aria-label="Notes"
                  value={form.notes}
                  onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
                  placeholder="Optional notes about this asset"
                  rows={2}
                  disabled={submitting}
                  className="w-full px-3 py-2 bg-[var(--bg-input)] border border-[var(--border-primary)] rounded-lg text-sm text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 outline-none transition-all disabled:opacity-50 resize-none"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 mt-6">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowCreateModal(false)}
                disabled={submitting}
              >
                Cancel
              </Button>
              <Button
                variant="primary"
                size="sm"
                icon={submitting ? Loader2 : Plus}
                onClick={handleCreate}
                disabled={submitting || !form.name.trim()}
                className={submitting ? "animate-pulse" : ""}
              >
                {submitting ? "Adding..." : "Add Asset"}
              </Button>
            </div>
          </motion.div>
        </ModalBackdrop>
      )}

      {/* View Asset Modal (gap-fill: Read endpoint) */}
      {viewAsset && (
        <ModalBackdrop
          onClose={() => setViewAsset(null)}
          disabled={actionInProgress === viewAsset.id}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            onClick={(e) => e.stopPropagation()}
            className="bg-[var(--bg-elevated)] border border-[var(--border-primary)] rounded-xl w-full max-w-lg p-6 shadow-2xl"
          >
            <ModalHeader
              title="Asset Details"
              onClose={() => setViewAsset(null)}
              disabled={actionInProgress === viewAsset.id}
              icon={Eye}
            />
            <div className="space-y-3">
              <div className="flex items-center gap-3 pb-3 border-b border-[var(--border-secondary)]">
                <div className="p-2 rounded-lg bg-brand-500/10 text-brand-400">
                  {typeIcons[viewAsset.type] || <Cpu className="w-5 h-5" />}
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-[var(--text-primary)]">
                    {viewAsset.name}
                  </h3>
                  <p className="text-xs text-[var(--text-muted)] font-mono">{viewAsset.id}</p>
                </div>
                <Badge
                  variant={statusConfig[viewAsset.status]?.variant ?? "default"}
                  dot
                  size="sm"
                  className="ml-auto"
                >
                  {statusConfig[viewAsset.status]?.label ?? viewAsset.status}
                </Badge>
              </div>
              <div className="grid grid-cols-2 gap-3 text-xs">
                <div>
                  <p className="text-[var(--text-muted)]">Type</p>
                  <p className="text-[var(--text-primary)] font-medium mt-0.5">{viewAsset.type}</p>
                </div>
                <div>
                  <p className="text-[var(--text-muted)]">Rating</p>
                  <p className="text-[var(--text-primary)] font-medium mt-0.5 mono-engineering">
                    {viewAsset.rating || "—"}
                  </p>
                </div>
                <div>
                  <p className="text-[var(--text-muted)]">Voltage</p>
                  <p className="text-[var(--text-primary)] font-medium mt-0.5 mono-engineering">
                    {viewAsset.voltage || "—"}
                  </p>
                </div>
                <div>
                  <p className="text-[var(--text-muted)]">Project ID</p>
                  <p className="text-[var(--text-primary)] font-medium mt-0.5 font-mono">
                    {viewAsset.project_id || "—"}
                  </p>
                </div>
                <div>
                  <p className="text-[var(--text-muted)]">Created</p>
                  <p className="text-[var(--text-primary)] font-medium mt-0.5">
                    {viewAsset.created_at}
                  </p>
                </div>
                <div>
                  <p className="text-[var(--text-muted)]">Updated</p>
                  <p className="text-[var(--text-primary)] font-medium mt-0.5">
                    {viewAsset.updated_at}
                  </p>
                </div>
                {viewAsset.notes && (
                  <div className="col-span-2">
                    <p className="text-[var(--text-muted)]">Notes</p>
                    <p className="text-[var(--text-primary)] mt-0.5 text-sm">{viewAsset.notes}</p>
                  </div>
                )}
              </div>
            </div>
            <div className="flex items-center justify-end gap-2 mt-6">
              <Button
                variant="ghost"
                size="sm"
                icon={Pencil}
                onClick={() => {
                  const a = viewAsset;
                  setViewAsset(null);
                  handleEditClick(a);
                }}
              >
                Edit
              </Button>
              <Button variant="ghost" size="sm" onClick={() => setViewAsset(null)}>
                Close
              </Button>
            </div>
          </motion.div>
        </ModalBackdrop>
      )}

      {/* Edit Asset Modal (gap-fill: Update endpoint) */}
      {editAsset && (
        <ModalBackdrop
          onClose={() => {
            setEditAsset(null);
            setForm(EMPTY_FORM);
          }}
          disabled={submitting}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            onClick={(e) => e.stopPropagation()}
            className="bg-[var(--bg-elevated)] border border-[var(--border-primary)] rounded-xl w-full max-w-md p-6 shadow-2xl"
          >
            <ModalHeader
              title="Edit Asset"
              onClose={() => {
                setEditAsset(null);
                setForm(EMPTY_FORM);
              }}
              disabled={submitting}
              icon={Pencil}
            />
            <div className="space-y-4">
              <div>
                <label
                  htmlFor="edit-asset-name"
                  className="block text-xs font-medium text-[var(--text-secondary)] mb-1.5"
                >
                  Asset Name <span className="text-red-400">*</span>
                </label>
                <input
                  id="edit-asset-name"
                  type="text"
                  aria-label="Asset Name"
                  value={form.name}
                  onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                  disabled={submitting}
                  className="w-full px-3 py-2 bg-[var(--bg-input)] border border-[var(--border-primary)] rounded-lg text-sm text-[var(--text-primary)] focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 outline-none transition-all disabled:opacity-50"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label
                    htmlFor="edit-asset-type"
                    className="block text-xs font-medium text-[var(--text-secondary)] mb-1.5"
                  >
                    Type
                  </label>
                  <select
                    id="edit-asset-type"
                    aria-label="Type"
                    value={form.type}
                    onChange={(e) => setForm((f) => ({ ...f, type: e.target.value }))}
                    disabled={submitting}
                    className="w-full px-3 py-2 bg-[var(--bg-input)] border border-[var(--border-primary)] rounded-lg text-sm text-[var(--text-primary)] focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 outline-none transition-all disabled:opacity-50"
                  >
                    {ASSET_TYPES.map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label
                    htmlFor="edit-asset-status"
                    className="block text-xs font-medium text-[var(--text-secondary)] mb-1.5"
                  >
                    Status
                  </label>
                  <select
                    id="edit-asset-status"
                    aria-label="Status"
                    value={form.status}
                    onChange={(e) => setForm((f) => ({ ...f, status: e.target.value }))}
                    disabled={submitting}
                    className="w-full px-3 py-2 bg-[var(--bg-input)] border border-[var(--border-primary)] rounded-lg text-sm text-[var(--text-primary)] focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 outline-none transition-all disabled:opacity-50 capitalize"
                  >
                    {ASSET_STATUSES.map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label
                    htmlFor="edit-asset-rating"
                    className="block text-xs font-medium text-[var(--text-secondary)] mb-1.5"
                  >
                    Rating
                  </label>
                  <input
                    id="edit-asset-rating"
                    type="text"
                    aria-label="Rating"
                    value={form.rating}
                    onChange={(e) => setForm((f) => ({ ...f, rating: e.target.value }))}
                    placeholder="e.g., 10 MVA"
                    disabled={submitting}
                    className="w-full px-3 py-2 bg-[var(--bg-input)] border border-[var(--border-primary)] rounded-lg text-sm text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 outline-none transition-all disabled:opacity-50"
                  />
                </div>
                <div>
                  <label
                    htmlFor="edit-asset-voltage"
                    className="block text-xs font-medium text-[var(--text-secondary)] mb-1.5"
                  >
                    Voltage
                  </label>
                  <input
                    id="edit-asset-voltage"
                    type="text"
                    aria-label="Voltage"
                    value={form.voltage}
                    onChange={(e) => setForm((f) => ({ ...f, voltage: e.target.value }))}
                    placeholder="e.g., 13.8 kV"
                    disabled={submitting}
                    className="w-full px-3 py-2 bg-[var(--bg-input)] border border-[var(--border-primary)] rounded-lg text-sm text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 outline-none transition-all disabled:opacity-50"
                  />
                </div>
              </div>
              <div>
                <label
                  htmlFor="edit-asset-notes"
                  className="block text-xs font-medium text-[var(--text-secondary)] mb-1.5"
                >
                  Notes
                </label>
                <textarea
                  id="edit-asset-notes"
                  aria-label="Notes"
                  value={form.notes}
                  onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
                  placeholder="Optional notes about this asset"
                  rows={2}
                  disabled={submitting}
                  className="w-full px-3 py-2 bg-[var(--bg-input)] border border-[var(--border-primary)] rounded-lg text-sm text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 outline-none transition-all disabled:opacity-50 resize-none"
                />
              </div>
            </div>
            <div className="flex items-center justify-end gap-2 mt-6">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setEditAsset(null);
                  setForm(EMPTY_FORM);
                }}
                disabled={submitting}
              >
                Cancel
              </Button>
              <Button
                variant="primary"
                size="sm"
                icon={submitting ? Loader2 : Pencil}
                onClick={handleUpdate}
                disabled={submitting || !form.name.trim()}
                className={submitting ? "animate-pulse" : ""}
              >
                {submitting ? "Saving..." : "Save Changes"}
              </Button>
            </div>
          </motion.div>
        </ModalBackdrop>
      )}
    </div>
  );
}
