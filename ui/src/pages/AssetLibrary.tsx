import { motion } from "framer-motion";
import { Database, Filter, Loader2, Package, Plus, Search, Trash2 } from "lucide-react";
import { type ReactNode, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { ContextHelpButton } from "../components/help/ContextHelpButton";
import { Badge, Button, Card, Modal } from "../components/ui";
import { useNotify } from "../context/NotificationContext";
import { API_BASE_URL } from "../lib/api-config";

interface Asset {
  id: string;
  name: string;
  type: string;
  category: string;
  manufacturer: string;
  model: string;
  rating: string;
  status: "active" | "maintenance" | "retired";
  location: string;
  created_at: string;
  updated_at: string;
}

const statusVariant = (status: Asset["status"]): "success" | "warning" | "default" => {
  if (status === "active") return "success";
  if (status === "maintenance") return "warning";
  return "default";
};

export default function AssetLibrary() {
  useTranslation();
  const { notify } = useNotify();
  const [assets, setAssets] = useState<Asset[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");
  const [showCreate, setShowCreate] = useState(false);
  const [formData, setFormData] = useState({
    name: "",
    type: "transformer",
    category: "",
    manufacturer: "",
    model: "",
    rating: "",
    status: "active" as const,
    location: "",
  });

  const fetchAssets = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem("authToken");
      const res = await fetch(`${API_BASE_URL}/api/v1/assets/`, {
        headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setAssets(data.assets || data || []);
    } catch {
      notify("error", "Failed to load assets");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAssets();
  }, []);

  const handleCreate = async () => {
    try {
      const token = localStorage.getItem("authToken");
      const res = await fetch(`${API_BASE_URL}/api/v1/assets/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(formData),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      notify("success", "Asset created successfully");
      setShowCreate(false);
      setFormData({
        name: "",
        type: "transformer",
        category: "",
        manufacturer: "",
        model: "",
        rating: "",
        status: "active",
        location: "",
      });
      fetchAssets();
    } catch {
      notify("error", "Failed to create asset");
    }
  };

  const handleDelete = async (id: string) => {
    try {
      const token = localStorage.getItem("authToken");
      const res = await fetch(`${API_BASE_URL}/api/v1/assets/${id}`, {
        method: "DELETE",
        headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      notify("success", "Asset deleted");
      fetchAssets();
    } catch {
      notify("error", "Failed to delete asset");
    }
  };

  const assetTypes = [
    "transformer",
    "breaker",
    "cable",
    "bus",
    "generator",
    "load",
    "relay",
    "meter",
    "capacitor",
    "reactor",
    "switch",
    "other",
  ];
  const filtered = assets.filter((a) => {
    const matchesSearch =
      a.name.toLowerCase().includes(search.toLowerCase()) ||
      a.manufacturer.toLowerCase().includes(search.toLowerCase()) ||
      a.model.toLowerCase().includes(search.toLowerCase());
    const matchesType = typeFilter === "all" || a.type === typeFilter;
    return matchesSearch && matchesType;
  });

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
          <Package className="w-12 h-12 text-[var(--text-muted)] mx-auto mb-3" />
          <p className="text-[var(--text-muted)]">
            No assets found. Add your first asset to get started.
          </p>
        </div>
      </Card>
    );
  } else {
    content = (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filtered.map((asset) => (
          <Card key={asset.id} className="hover:border-brand-500/40 transition-colors">
            <div className="p-4 space-y-3">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-2 min-w-0">
                  <Package className="w-5 h-5 text-brand-500 shrink-0" />
                  <h3 className="font-semibold text-[var(--text-primary)] truncate">
                    {asset.name}
                  </h3>
                </div>
                <Badge variant={statusVariant(asset.status)}>{asset.status}</Badge>
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div>
                  <span className="text-[var(--text-muted)]">Type:</span>{" "}
                  <span className="text-[var(--text-primary)]">{asset.type}</span>
                </div>
                <div>
                  <span className="text-[var(--text-muted)]">Rating:</span>{" "}
                  <span className="text-[var(--text-primary)]">{asset.rating}</span>
                </div>
                <div>
                  <span className="text-[var(--text-muted)]">Manufacturer:</span>{" "}
                  <span className="text-[var(--text-primary)]">{asset.manufacturer}</span>
                </div>
                <div>
                  <span className="text-[var(--text-muted)]">Model:</span>{" "}
                  <span className="text-[var(--text-primary)]">{asset.model}</span>
                </div>
              </div>
              <div className="flex items-center justify-between pt-2 border-t border-[var(--border-primary)]">
                <span className="text-xs text-[var(--text-muted)]">{asset.location || "N/A"}</span>
                <button
                  onClick={() => handleDelete(asset.id)}
                  className="p-1.5 rounded-md text-[var(--text-muted)] hover:text-red-400 hover:bg-red-500/10 transition-colors"
                  title="Delete asset"
                  type="button"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
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
            <Database className="w-6 h-6 text-brand-500" />
            Asset Library
          </h1>
          <p className="text-sm text-[var(--text-muted)] mt-1">
            Manage power system equipment and assets
          </p>
        </div>
        <div className="flex items-center gap-3">
          <ContextHelpButton contextId="asset-library" />
          <Button onClick={() => setShowCreate(true)}>
            <Plus className="w-4 h-4" /> New Asset
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
            placeholder="Search by name, manufacturer, or model..."
            className="w-full pl-10 pr-4 py-2.5 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] text-[var(--text-primary)]"
          />
        </div>
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-[var(--text-muted)]" />
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="px-3 py-2.5 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] text-[var(--text-primary)] text-sm"
          >
            <option value="all">All Types</option>
            {assetTypes.map((t) => (
              <option key={t} value={t}>
                {t.charAt(0).toUpperCase() + t.slice(1)}
              </option>
            ))}
          </select>
        </div>
      </div>

      {content}

      <Modal open={showCreate} onClose={() => setShowCreate(false)}>
        <div className="p-6 space-y-4 max-h-[80vh] overflow-y-auto">
          <h2 className="text-lg font-semibold text-[var(--text-primary)]">New Asset</h2>
          <div className="grid grid-cols-2 gap-3">
            <div className="col-span-2">
              <label
                htmlFor="asset-name"
                className="block text-sm font-medium mb-1 text-[var(--text-primary)]"
              >
                Name
              </label>
              <input
                id="asset-name"
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="w-full px-3 py-2 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] text-[var(--text-primary)]"
              />
            </div>
            <div>
              <label
                htmlFor="asset-type"
                className="block text-sm font-medium mb-1 text-[var(--text-primary)]"
              >
                Type
              </label>
              <select
                id="asset-type"
                value={formData.type}
                onChange={(e) => setFormData({ ...formData, type: e.target.value })}
                className="w-full px-3 py-2 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] text-[var(--text-primary)]"
              >
                {assetTypes.map((t) => (
                  <option key={t} value={t}>
                    {t.charAt(0).toUpperCase() + t.slice(1)}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label
                htmlFor="asset-status"
                className="block text-sm font-medium mb-1 text-[var(--text-primary)]"
              >
                Status
              </label>
              <select
                id="asset-status"
                value={formData.status}
                onChange={(e) => setFormData({ ...formData, status: e.target.value as any })}
                className="w-full px-3 py-2 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] text-[var(--text-primary)]"
              >
                <option value="active">Active</option>
                <option value="maintenance">Maintenance</option>
                <option value="retired">Retired</option>
              </select>
            </div>
            <div>
              <label
                htmlFor="asset-manufacturer"
                className="block text-sm font-medium mb-1 text-[var(--text-primary)]"
              >
                Manufacturer
              </label>
              <input
                id="asset-manufacturer"
                type="text"
                value={formData.manufacturer}
                onChange={(e) => setFormData({ ...formData, manufacturer: e.target.value })}
                className="w-full px-3 py-2 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] text-[var(--text-primary)]"
              />
            </div>
            <div>
              <label
                htmlFor="asset-model"
                className="block text-sm font-medium mb-1 text-[var(--text-primary)]"
              >
                Model
              </label>
              <input
                id="asset-model"
                type="text"
                value={formData.model}
                onChange={(e) => setFormData({ ...formData, model: e.target.value })}
                className="w-full px-3 py-2 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] text-[var(--text-primary)]"
              />
            </div>
            <div>
              <label
                htmlFor="asset-rating"
                className="block text-sm font-medium mb-1 text-[var(--text-primary)]"
              >
                Rating
              </label>
              <input
                id="asset-rating"
                type="text"
                value={formData.rating}
                onChange={(e) => setFormData({ ...formData, rating: e.target.value })}
                placeholder="e.g., 100 MVA"
                className="w-full px-3 py-2 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] text-[var(--text-primary)]"
              />
            </div>
            <div>
              <label
                htmlFor="asset-location"
                className="block text-sm font-medium mb-1 text-[var(--text-primary)]"
              >
                Location
              </label>
              <input
                id="asset-location"
                type="text"
                value={formData.location}
                onChange={(e) => setFormData({ ...formData, location: e.target.value })}
                className="w-full px-3 py-2 rounded-lg border border-[var(--border-primary)] bg-[var(--bg-primary)] text-[var(--text-primary)]"
              />
            </div>
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <Button variant="ghost" onClick={() => setShowCreate(false)}>
              Cancel
            </Button>
            <Button onClick={handleCreate} disabled={!formData.name.trim()}>
              Create Asset
            </Button>
          </div>
        </div>
      </Modal>
    </motion.div>
  );
}
