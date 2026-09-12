import { motion } from "framer-motion";
import {
  Activity,
  Cable,
  CheckCircle,
  Copy,
  Layers,
  Loader2,
  Package,
  Plus,
  Search,
  Settings2,
  ShieldCheck,
  Upload,
  Zap,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import ModalBackdrop from "../components/ModalBackdrop";
import ModalHeader from "../components/ModalHeader";
import { ContextHelpButton } from "../components/help/ContextHelpButton";
import { Badge, Button, Card, EmptyState, Toggle } from "../components/ui";
import { useNotify } from "../context/NotificationContext";
import { API_BASE_URL } from "../lib/api-config";
import { getAuthToken } from "../lib/tokenStorage";
import { cn } from "../utils/helpers";

export interface ComponentItem {
  id: string;
  type: string;
  category: string;
  subcategory?: string | null;
  name: string;
  manufacturer?: string | null;
  model_number?: string | null;
  specs?: Record<string, unknown> | null;
  standards?: string[] | null;
  tags?: string[] | null;
  is_verified: boolean;
  source: string;
  contributor_id?: string | null;
  review_status: string;
  review_notes?: string | null;
  created_at?: string | null;
}

interface TypeCount {
  type: string;
  count: number;
}

interface StandardCount {
  standard: string;
  count: number;
}

const typeIconMap: Record<string, React.ReactNode> = {
  cable: <Cable className="w-5 h-5 text-emerald-400" />,
  transformer: <Zap className="w-5 h-5 text-amber-400" />,
  breaker: <Settings2 className="w-5 h-5 text-blue-400" />,
  relay: <Activity className="w-5 h-5 text-purple-400" />,
  template: <Layers className="w-5 h-5 text-rose-400" />,
};

export default function ComponentLibrary() {
  useTranslation();
  const { notify } = useNotify();

  const [components, setComponents] = useState<ComponentItem[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [types, setTypes] = useState<TypeCount[]>([]);
  const [standards, setStandards] = useState<StandardCount[]>([]);

  // Filters
  const [selectedType, setSelectedType] = useState<string>("all");
  const [selectedStandard, setSelectedStandard] = useState<string>("");
  const [searchQuery, setSearchQuery] = useState("");
  const [verifiedOnly, setVerifiedOnly] = useState(true);

  // Modals & Details
  const [detailComponent, setDetailComponent] = useState<ComponentItem | null>(null);
  const [showContributeModal, setShowContributeModal] = useState(false);
  const [showImportModal, setShowImportModal] = useState(false);
  const [importTab, setImportTab] = useState<"etap" | "json">("etap");
  const [importing, setImporting] = useState(false);

  // Contribute Form State
  const [contribType, setContribType] = useState("cable");
  const [contribCategory, setContribCategory] = useState("LV Power");
  const [contribSubcategory, setContribSubcategory] = useState("");
  const [contribName, setContribName] = useState("");
  const [contribManufacturer, setContribManufacturer] = useState("");
  const [contribModel, setContribModel] = useState("");
  const [contribStandards, setContribStandards] = useState("IEC 60364");
  const [contribTags, setContribTags] = useState("community, standard");
  const [contribSpecsJson, setContribSpecsJson] = useState(
    JSON.stringify({ voltage_kv: 1.0, ampacity_a: 250, r_ohm_km: 0.125 }, null, 2),
  );
  const [contribNotes, setContribNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // Fetch Types & Standards Stats
  const fetchMetadata = useCallback(async () => {
    try {
      const token = getAuthToken();
      const headers: Record<string, string> = {};
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }
      const [resTypes, resStds] = await Promise.all([
        fetch(`${API_BASE_URL}/api/v1/components/types`, { headers }),
        fetch(`${API_BASE_URL}/api/v1/components/standards`, { headers }),
      ]);
      if (resTypes.ok) {
        setTypes(await resTypes.json());
      }
      if (resStds.ok) {
        setStandards(await resStds.json());
      }
    } catch {
      // Non-blocking metadata failure
    }
  }, []);

  // Fetch Components List
  const fetchComponents = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (selectedType !== "all") params.set("type", selectedType);
      if (selectedStandard) params.set("standard", selectedStandard);
      if (searchQuery.trim()) params.set("search", searchQuery.trim());
      if (verifiedOnly) params.set("verified", "true");
      params.set("page_size", "100");

      const token = getAuthToken();
      const headers: Record<string, string> = {};
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }

      const res = await fetch(`${API_BASE_URL}/api/v1/components?${params.toString()}`, { headers });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setComponents(data.components || []);
      setTotalCount(data.total || 0);
    } catch (err) {
      notify("error", "Failed to load component library");
    } finally {
      setLoading(false);
    }
  }, [selectedType, selectedStandard, searchQuery, verifiedOnly, notify]);

  useEffect(() => {
    fetchMetadata();
  }, [fetchMetadata]);

  useEffect(() => {
    fetchComponents();
  }, [fetchComponents]);

  // Handle Community Submission
  const handleContributeSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      let parsedSpecs = {};
      try {
        parsedSpecs = JSON.parse(contribSpecsJson);
      } catch {
        notify("error", "Invalid JSON format in Specs field");
        setSubmitting(false);
        return;
      }

      const payload = {
        type: contribType,
        category: contribCategory,
        subcategory: contribSubcategory || null,
        name: contribName,
        manufacturer: contribManufacturer || null,
        model_number: contribModel || null,
        standards: contribStandards.split(",").map((s) => s.trim()).filter(Boolean),
        tags: contribTags.split(",").map((t) => t.trim()).filter(Boolean),
        specs: parsedSpecs,
        contributor_notes: contribNotes || null,
      };

      const token = getAuthToken();
      if (!token) {
        notify("error", "Please log in to contribute components");
        setSubmitting(false);
        return;
      }
      const res = await fetch(`${API_BASE_URL}/api/v1/components/contribute`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      notify("success", "Component submitted successfully! Pending verification.");
      setShowContributeModal(false);
      setContribName("");
      setContribModel("");
      fetchComponents();
    } catch (err) {
      notify("error", "Failed to submit component");
    } finally {
      setSubmitting(false);
    }
  };

  // Handle File Upload Import
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setImporting(true);
    try {
      const token = getAuthToken();
      if (!token) {
        notify("error", "Please log in to import components");
        setImporting(false);
        return;
      }
      const formData = new FormData();
      formData.append("file", file);

      const endpoint =
        importTab === "etap"
          ? `${API_BASE_URL}/api/v1/components/import/etap`
          : `${API_BASE_URL}/api/v1/components/import/json`;

      const res = await fetch(endpoint, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
        },
        body: formData,
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `HTTP ${res.status}`);
      }

      const imported = await res.json();
      notify("success", `Successfully imported ${imported.length} components!`);
      setShowImportModal(false);
      fetchMetadata();
      fetchComponents();
    } catch (err) {
      notify("error", `Import failed: ${err instanceof Error ? err.message : "Unknown error"}`);
    } finally {
      setImporting(false);
    }
  };

  const copySpecsToClipboard = (specs: Record<string, unknown> | null | undefined) => {
    if (!specs) return;
    navigator.clipboard.writeText(JSON.stringify(specs, null, 2));
    notify("success", "Specs copied to clipboard!");
  };

  return (
    <div className="space-y-6">
      {/* Header Section */}
      <motion.div
        initial={{ opacity: 0, y: 15 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex flex-col md:flex-row md:items-center md:justify-between gap-4"
      >
        <div className="flex items-center gap-3">
          <div className="p-3 rounded-2xl bg-brand-500/10 border border-brand-500/20 text-brand-400">
            <Package className="w-7 h-7" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold text-[var(--text-primary)]">Component Library</h1>
              <Badge variant="brand" size="sm">
                Standardized
              </Badge>
              <ContextHelpButton contextId="component-library.overview" />
            </div>
            <p className="text-sm text-[var(--text-muted)]">
              Multi-standard power system component specifications, ETAP models & community catalog.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Link to="/admin/component-review">
            <Button variant="ghost" size="sm" icon={ShieldCheck}>
              Review Queue
            </Button>
          </Link>
          <Button
            variant="secondary"
            size="sm"
            icon={Upload}
            onClick={() => setShowImportModal(true)}
          >
            Bulk Import
          </Button>
          <Button
            variant="primary"
            size="sm"
            icon={Plus}
            onClick={() => setShowContributeModal(true)}
          >
            Contribute Component
          </Button>
        </div>
      </motion.div>

      {/* Metrics Banner */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="p-4 rounded-xl bg-[var(--bg-secondary)] border border-[var(--border-primary)]">
          <span className="text-xs text-[var(--text-muted)] uppercase tracking-wider font-semibold">
            Total Catalog
          </span>
          <p className="text-2xl font-bold text-[var(--text-primary)] mt-1">{totalCount}</p>
        </div>
        <div className="p-4 rounded-xl bg-[var(--bg-secondary)] border border-[var(--border-primary)]">
          <span className="text-xs text-[var(--text-muted)] uppercase tracking-wider font-semibold">
            Standards Covered
          </span>
          <p className="text-2xl font-bold text-brand-400 mt-1">{standards.length || 6}</p>
        </div>
        <div className="p-4 rounded-xl bg-[var(--bg-secondary)] border border-[var(--border-primary)]">
          <span className="text-xs text-[var(--text-muted)] uppercase tracking-wider font-semibold">
            Component Types
          </span>
          <p className="text-2xl font-bold text-emerald-400 mt-1">{types.length || 5}</p>
        </div>
        <div className="p-4 rounded-xl bg-[var(--bg-secondary)] border border-[var(--border-primary)]">
          <span className="text-xs text-[var(--text-muted)] uppercase tracking-wider font-semibold">
            ETAP Bulk Import
          </span>
          <p className="text-sm font-medium text-[var(--text-secondary)] mt-2 flex items-center gap-1">
            <CheckCircle className="w-4 h-4 text-emerald-400 inline" /> .etp / .etpx XML Ready
          </p>
        </div>
      </div>

      {/* Filter Toolbar */}
      <Card padding="md">
        <div className="space-y-4">
          {/* Type Pills */}
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => setSelectedType("all")}
              className={cn(
                "px-3.5 py-1.5 rounded-lg text-xs font-medium transition-all",
                selectedType === "all"
                  ? "bg-brand-500 text-white shadow-sm"
                  : "bg-[var(--bg-secondary)] text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] border border-[var(--border-primary)]",
              )}
            >
              All Types ({totalCount})
            </button>
            {types.map((t) => (
              <button
                key={t.type}
                type="button"
                onClick={() => setSelectedType(t.type)}
                className={cn(
                  "px-3.5 py-1.5 rounded-lg text-xs font-medium capitalize flex items-center gap-1.5 transition-all",
                  selectedType === t.type
                    ? "bg-brand-500 text-white shadow-sm"
                    : "bg-[var(--bg-secondary)] text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] border border-[var(--border-primary)]",
                )}
              >
                {typeIconMap[t.type] || <Package className="w-3.5 h-3.5" />}
                {t.type}s ({t.count})
              </button>
            ))}
          </div>

          {/* Search, Standard Filter & Verified Toggle */}
          <div className="flex flex-col md:flex-row items-center gap-3">
            <div className="relative flex-1 w-full">
              <Search className="w-4 h-4 text-[var(--text-muted)] absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search by name, manufacturer, model, insulation, or size..."
                className="w-full pl-9 pr-4 py-2 text-sm rounded-lg bg-[var(--bg-input)] border border-[var(--border-primary)] text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none focus:border-brand-500"
              />
            </div>

            <div className="flex items-center gap-3 w-full md:w-auto">
              <select
                value={selectedStandard}
                onChange={(e) => setSelectedStandard(e.target.value)}
                aria-label="Filter by standard"
                className="px-3 py-2 text-sm rounded-lg bg-[var(--bg-input)] border border-[var(--border-primary)] text-[var(--text-primary)] focus:outline-none focus:border-brand-500"
              >
                <option value="">All Standards</option>
                {standards.map((s) => (
                  <option key={s.standard} value={s.standard}>
                    {s.standard} ({s.count})
                  </option>
                ))}
              </select>

              <div className="flex items-center gap-2 whitespace-nowrap">
                <Toggle
                  checked={verifiedOnly}
                  onChange={setVerifiedOnly}
                  label="Verified only"
                  size="sm"
                />
              </div>
            </div>
          </div>
        </div>
      </Card>

      {/* Grid of Components */}
      {loading ? (
        <div className="flex flex-col items-center justify-center py-16 gap-3">
          <Loader2 className="w-8 h-8 text-brand-400 animate-spin" />
          <p className="text-sm text-[var(--text-muted)]">Loading component catalog...</p>
        </div>
      ) : components.length === 0 ? (
        <EmptyState
          icon={<Package className="w-10 h-10 text-[var(--text-muted)]" />}
          title="No components match your search"
          description="Try broadening your filters or contribute a new component definition to the library."
          action={
            <Button
              variant="primary"
              size="sm"
              icon={Plus}
              onClick={() => setShowContributeModal(true)}
            >
              Contribute Component
            </Button>
          }
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {components.map((comp) => (
            <motion.div
              key={comp.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="rounded-xl border border-[var(--border-primary)] bg-[var(--bg-secondary)] hover:border-brand-500/40 transition-all p-5 flex flex-col justify-between shadow-sm hover:shadow-md"
            >
              <div>
                <div className="flex items-start justify-between gap-2 mb-2">
                  <div className="flex items-center gap-2">
                    <div className="p-2 rounded-lg bg-[var(--bg-primary)] border border-[var(--border-primary)]">
                      {typeIconMap[comp.type] || <Package className="w-4 h-4 text-brand-400" />}
                    </div>
                    <div>
                      <span className="text-xs uppercase font-semibold text-[var(--text-muted)]">
                        {comp.type} • {comp.category}
                      </span>
                      <h3 className="text-base font-bold text-[var(--text-primary)] leading-tight">
                        {comp.name}
                      </h3>
                    </div>
                  </div>

                  {comp.is_verified ? (
                    <span
                      title="Standard Verified Specification"
                      className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/20"
                    >
                      <ShieldCheck className="w-3.5 h-3.5" />
                      Verified
                    </span>
                  ) : (
                    <span
                      title="Pending Verification"
                      className="inline-flex items-center gap-1 text-[11px] font-medium text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded-full border border-amber-500/20"
                    >
                      Pending
                    </span>
                  )}
                </div>

                {comp.manufacturer && (
                  <p className="text-xs text-[var(--text-secondary)] mb-3">
                    <span className="text-[var(--text-muted)]">Manufacturer:</span>{" "}
                    {comp.manufacturer}
                    {comp.model_number && ` (${comp.model_number})`}
                  </p>
                )}

                {/* Standards Badges */}
                {comp.standards && comp.standards.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 mb-3">
                    {comp.standards.map((std) => (
                      <span
                        key={std}
                        className="text-[10px] font-mono px-2 py-0.5 rounded bg-[var(--bg-primary)] text-[var(--text-secondary)] border border-[var(--border-primary)]"
                      >
                        {std}
                      </span>
                    ))}
                  </div>
                )}

                {/* Specs Highlights */}
                {comp.specs && (
                  <div className="grid grid-cols-2 gap-2 p-2.5 rounded-lg bg-[var(--bg-primary)] border border-[var(--border-primary)] text-xs mb-3 font-mono">
                    {Object.entries(comp.specs)
                      .slice(0, 4)
                      .map(([k, v]) => (
                        <div key={k} className="truncate">
                          <span className="text-[var(--text-muted)]">{k.replaceAll("_", " ")}: </span>
                          <span className="font-semibold text-[var(--text-primary)]">
                            {String(v)}
                          </span>
                        </div>
                      ))}
                  </div>
                )}
              </div>

              <div className="flex items-center justify-between pt-3 border-t border-[var(--border-primary)] mt-2">
                <span className="text-[11px] text-[var(--text-muted)] capitalize">
                  Src: {comp.source}
                </span>
                <div className="flex items-center gap-1">
                  <Button
                    variant="ghost"
                    size="sm"
                    icon={Copy}
                    onClick={() => copySpecsToClipboard(comp.specs)}
                    title="Copy Specs JSON"
                  />
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => setDetailComponent(comp)}
                  >
                    View Specs
                  </Button>
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      )}

      {/* Component Details Drawer / Modal */}
      {detailComponent && (
        <ModalBackdrop onClose={() => setDetailComponent(null)}>
          <div className="bg-[var(--bg-secondary)] border border-[var(--border-primary)] rounded-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto shadow-2xl p-6">
            <ModalHeader
              title={detailComponent.name}
              icon={Package}
              onClose={() => setDetailComponent(null)}
            />
            <p className="text-xs text-[var(--text-muted)] -mt-2 mb-4">
              {detailComponent.type.toUpperCase()} • {detailComponent.category}{" "}
              {detailComponent.subcategory ? `(${detailComponent.subcategory})` : ""}
            </p>

            <div className="space-y-5 mt-4">
              {/* Metadata strip */}
              <div className="flex flex-wrap items-center gap-3 text-xs text-[var(--text-secondary)]">
                {detailComponent.manufacturer && (
                  <div>
                    <span className="text-[var(--text-muted)]">Manufacturer:</span>{" "}
                    <strong>{detailComponent.manufacturer}</strong>
                  </div>
                )}
                {detailComponent.model_number && (
                  <div>
                    <span className="text-[var(--text-muted)]">Model:</span>{" "}
                    <strong>{detailComponent.model_number}</strong>
                  </div>
                )}
                <div>
                  <span className="text-[var(--text-muted)]">Source:</span>{" "}
                  <Badge variant="default" size="sm">
                    {detailComponent.source}
                  </Badge>
                </div>
                <div>
                  <span className="text-[var(--text-muted)]">Verified:</span>{" "}
                  <Badge
                    variant={detailComponent.is_verified ? "success" : "warning"}
                    size="sm"
                  >
                    {detailComponent.is_verified ? "Yes" : "Pending Review"}
                  </Badge>
                </div>
              </div>

              {/* Standards */}
              {detailComponent.standards && detailComponent.standards.length > 0 && (
                <div>
                  <h4 className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-2">
                    Governing Standards
                  </h4>
                  <div className="flex flex-wrap gap-2">
                    {detailComponent.standards.map((s) => (
                      <Badge key={s} variant="brand">
                        {s}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}

              {/* Full Specs Table */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <h4 className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider">
                    Engineering Parameters & Specifications
                  </h4>
                  <Button
                    variant="ghost"
                    size="sm"
                    icon={Copy}
                    onClick={() => copySpecsToClipboard(detailComponent.specs)}
                  >
                    Copy JSON
                  </Button>
                </div>

                {detailComponent.specs && Object.keys(detailComponent.specs).length > 0 ? (
                  <div className="overflow-x-auto rounded-xl border border-[var(--border-primary)] bg-[var(--bg-primary)]">
                    <table className="w-full text-left text-xs font-mono">
                      <thead className="bg-[var(--bg-secondary)] border-b border-[var(--border-primary)] text-[var(--text-muted)]">
                        <tr>
                          <th className="p-2.5">Parameter</th>
                          <th className="p-2.5">Value</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[var(--border-primary)]">
                        {Object.entries(detailComponent.specs).map(([param, val]) => (
                          <tr key={param} className="hover:bg-[var(--bg-hover)]">
                            <td className="p-2.5 text-[var(--text-secondary)] font-medium">
                              {param}
                            </td>
                            <td className="p-2.5 text-[var(--text-primary)] font-semibold">
                              {typeof val === "object" ? JSON.stringify(val) : String(val)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="text-xs text-[var(--text-muted)] italic">
                    No custom specifications recorded.
                  </p>
                )}
              </div>

              {/* Tags */}
              {detailComponent.tags && detailComponent.tags.length > 0 && (
                <div>
                  <h4 className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-2">
                    Tags
                  </h4>
                  <div className="flex flex-wrap gap-1.5">
                    {detailComponent.tags.map((t) => (
                      <span
                        key={t}
                        className="text-[11px] px-2 py-0.5 rounded-full bg-[var(--bg-hover)] text-[var(--text-secondary)]"
                      >
                        #{t}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Review Notes (if any) */}
              {detailComponent.review_notes && (
                <div className="p-3 rounded-lg bg-[var(--bg-primary)] border border-[var(--border-primary)] text-xs">
                  <span className="font-semibold text-[var(--text-secondary)]">
                    Reviewer Notes:
                  </span>{" "}
                  <p className="text-[var(--text-muted)] mt-1">{detailComponent.review_notes}</p>
                </div>
              )}

              <div className="flex justify-end pt-4 border-t border-[var(--border-primary)]">
                <Button variant="secondary" onClick={() => setDetailComponent(null)}>
                  Close
                </Button>
              </div>
            </div>
          </div>
        </ModalBackdrop>
      )}

      {/* Contribute Modal */}
      {showContributeModal && (
        <ModalBackdrop onClose={() => setShowContributeModal(false)}>
          <div className="bg-[var(--bg-secondary)] border border-[var(--border-primary)] rounded-2xl max-w-xl w-full max-h-[90vh] overflow-y-auto shadow-2xl p-6">
            <ModalHeader
              title="Contribute Standard Component"
              icon={Plus}
              onClose={() => setShowContributeModal(false)}
            />
            <p className="text-xs text-[var(--text-muted)] -mt-2 mb-4">
              Submit a verified component spec to the shared engineering catalog
            </p>

            <form onSubmit={handleContributeSubmit} className="space-y-4 text-xs">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label htmlFor="contrib-type" className="block font-medium text-[var(--text-secondary)] mb-1">
                    Component Type
                  </label>
                  <select
                    id="contrib-type"
                    value={contribType}
                    onChange={(e) => setContribType(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg bg-[var(--bg-input)] border border-[var(--border-primary)] text-[var(--text-primary)]"
                  >
                    <option value="cable">Cable</option>
                    <option value="transformer">Transformer</option>
                    <option value="breaker">Breaker</option>
                    <option value="relay">Relay</option>
                    <option value="template">Coordination Template</option>
                  </select>
                </div>
                <div>
                  <label htmlFor="contrib-category" className="block font-medium text-[var(--text-secondary)] mb-1">
                    Category
                  </label>
                  <input
                    id="contrib-category"
                    type="text"
                    required
                    value={contribCategory}
                    onChange={(e) => setContribCategory(e.target.value)}
                    placeholder="e.g. LV Power, MV Vacuum"
                    className="w-full px-3 py-2 rounded-lg bg-[var(--bg-input)] border border-[var(--border-primary)] text-[var(--text-primary)]"
                  />
                </div>
              </div>

              <div>
                <label htmlFor="contrib-subcategory" className="block font-medium text-[var(--text-secondary)] mb-1">
                  Subcategory (Optional)
                </label>
                <input
                  id="contrib-subcategory"
                  type="text"
                  value={contribSubcategory}
                  onChange={(e) => setContribSubcategory(e.target.value)}
                  placeholder="e.g. Copper XLPE, Oil Immersed"
                  className="w-full px-3 py-2 rounded-lg bg-[var(--bg-input)] border border-[var(--border-primary)] text-[var(--text-primary)]"
                />
              </div>

              <div>
                <label htmlFor="contrib-name" className="block font-medium text-[var(--text-secondary)] mb-1">
                  Component Name
                </label>
                <input
                  id="contrib-name"
                  type="text"
                  required
                  value={contribName}
                  onChange={(e) => setContribName(e.target.value)}
                  placeholder="e.g. 4x240 mm² Cu/XLPE 0.6/1kV"
                  className="w-full px-3 py-2 rounded-lg bg-[var(--bg-input)] border border-[var(--border-primary)] text-[var(--text-primary)]"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label htmlFor="contrib-mfg" className="block font-medium text-[var(--text-secondary)] mb-1">
                    Manufacturer (Optional)
                  </label>
                  <input
                    id="contrib-mfg"
                    type="text"
                    value={contribManufacturer}
                    onChange={(e) => setContribManufacturer(e.target.value)}
                    placeholder="e.g. ABB, Schneider, Prysmian"
                    className="w-full px-3 py-2 rounded-lg bg-[var(--bg-input)] border border-[var(--border-primary)] text-[var(--text-primary)]"
                  />
                </div>
                <div>
                  <label htmlFor="contrib-model" className="block font-medium text-[var(--text-secondary)] mb-1">
                    Model Number (Optional)
                  </label>
                  <input
                    id="contrib-model"
                    type="text"
                    value={contribModel}
                    onChange={(e) => setContribModel(e.target.value)}
                    placeholder="e.g. VD4-12, NSX-250"
                    className="w-full px-3 py-2 rounded-lg bg-[var(--bg-input)] border border-[var(--border-primary)] text-[var(--text-primary)]"
                  />
                </div>
              </div>

              <div>
                <label htmlFor="contrib-standards" className="block font-medium text-[var(--text-secondary)] mb-1">
                  Standards (comma-separated)
                </label>
                <input
                  id="contrib-standards"
                  type="text"
                  value={contribStandards}
                  onChange={(e) => setContribStandards(e.target.value)}
                  placeholder="IEC 60364, IEC 60228"
                  className="w-full px-3 py-2 rounded-lg bg-[var(--bg-input)] border border-[var(--border-primary)] text-[var(--text-primary)]"
                />
              </div>

              <div>
                <label htmlFor="contrib-tags" className="block font-medium text-[var(--text-secondary)] mb-1">
                  Tags (comma-separated)
                </label>
                <input
                  id="contrib-tags"
                  type="text"
                  value={contribTags}
                  onChange={(e) => setContribTags(e.target.value)}
                  placeholder="lv, community, xlpe"
                  className="w-full px-3 py-2 rounded-lg bg-[var(--bg-input)] border border-[var(--border-primary)] text-[var(--text-primary)]"
                />
              </div>

              <div>
                <label htmlFor="contrib-specs" className="block font-medium text-[var(--text-secondary)] mb-1">
                  Technical Specifications (JSON format)
                </label>
                <textarea
                  id="contrib-specs"
                  rows={4}
                  value={contribSpecsJson}
                  onChange={(e) => setContribSpecsJson(e.target.value)}
                  className="w-full px-3 py-2 font-mono text-xs rounded-lg bg-[var(--bg-input)] border border-[var(--border-primary)] text-[var(--text-primary)]"
                />
              </div>

              <div>
                <label htmlFor="contrib-notes" className="block font-medium text-[var(--text-secondary)] mb-1">
                  Notes for Reviewers
                </label>
                <textarea
                  id="contrib-notes"
                  rows={2}
                  value={contribNotes}
                  onChange={(e) => setContribNotes(e.target.value)}
                  placeholder="Reference catalog, page number, or laboratory test cert..."
                  className="w-full px-3 py-2 text-xs rounded-lg bg-[var(--bg-input)] border border-[var(--border-primary)] text-[var(--text-primary)]"
                />
              </div>

              <div className="flex justify-end gap-2 pt-3 border-t border-[var(--border-primary)]">
                <Button
                  variant="ghost"
                  type="button"
                  onClick={() => setShowContributeModal(false)}
                >
                  Cancel
                </Button>
                <Button variant="primary" type="submit" disabled={submitting}>
                  {submitting ? "Submitting..." : "Submit for Verification"}
                </Button>
              </div>
            </form>
          </div>
        </ModalBackdrop>
      )}

      {/* Bulk Import Modal */}
      {showImportModal && (
        <ModalBackdrop onClose={() => setShowImportModal(false)}>
          <div className="bg-[var(--bg-secondary)] border border-[var(--border-primary)] rounded-2xl max-w-lg w-full shadow-2xl p-6">
            <ModalHeader
              title="Bulk Import Components"
              icon={Upload}
              onClose={() => setShowImportModal(false)}
            />
            <p className="text-xs text-[var(--text-muted)] -mt-2 mb-4">
              Extract standardized components from ETAP project or JSON definitions
            </p>

            <div className="space-y-4 mt-4">
              {/* Import Tabs */}
              <div className="flex border-b border-[var(--border-primary)]">
                <button
                  type="button"
                  onClick={() => setImportTab("etap")}
                  className={cn(
                    "pb-2 px-4 text-xs font-semibold border-b-2 transition-all",
                    importTab === "etap"
                      ? "border-brand-500 text-brand-400"
                      : "border-transparent text-[var(--text-muted)] hover:text-[var(--text-primary)]",
                  )}
                >
                  ETAP .etp / .etpx XML
                </button>
                <button
                  type="button"
                  onClick={() => setImportTab("json")}
                  className={cn(
                    "pb-2 px-4 text-xs font-semibold border-b-2 transition-all",
                    importTab === "json"
                      ? "border-brand-500 text-brand-400"
                      : "border-transparent text-[var(--text-muted)] hover:text-[var(--text-primary)]",
                  )}
                >
                  Standard JSON
                </button>
              </div>

              {importTab === "etap" ? (
                <div className="text-xs text-[var(--text-secondary)] space-y-3">
                  <p>
                    Upload an ETAP project export XML file containing <code>&lt;Cable&gt;</code>,{" "}
                    <code>&lt;Transformer&gt;</code>, <code>&lt;Breaker&gt;</code>, or{" "}
                    <code>&lt;Relay&gt;</code> definitions.
                  </p>
                  <p className="text-[var(--text-muted)]">
                    All components are automatically converted into standardized catalog definitions
                    with verified source tracking.
                  </p>
                </div>
              ) : (
                <div className="text-xs text-[var(--text-secondary)] space-y-3">
                  <p>
                    Upload a JSON file containing an array of standardized component definitions
                    matching the catalog schema.
                  </p>
                </div>
              )}

              <div className="p-6 border-2 border-dashed border-[var(--border-primary)] rounded-xl flex flex-col items-center justify-center text-center gap-3">
                <Upload className="w-8 h-8 text-brand-400" />
                <div>
                  <span className="text-xs font-semibold text-[var(--text-primary)]">
                    Choose file to import
                  </span>
                  <p className="text-[11px] text-[var(--text-muted)] mt-0.5">
                    {importTab === "etap" ? ".xml, .etp, .etpx files up to 20MB" : ".json files up to 10MB"}
                  </p>
                </div>
                <label className="cursor-pointer">
                  <span className="px-4 py-1.5 text-xs font-medium rounded-lg bg-brand-500 text-white hover:bg-brand-600 transition-colors inline-block">
                    Browse File
                  </span>
                  <input
                    type="file"
                    accept={importTab === "etap" ? ".xml,.etp,.etpx" : ".json"}
                    onChange={handleFileUpload}
                    className="hidden"
                    disabled={importing}
                  />
                </label>
              </div>

              {importing && (
                <div className="flex items-center justify-center gap-2 text-xs text-brand-400 py-2">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Parsing and importing component specifications...</span>
                </div>
              )}
            </div>
          </div>
        </ModalBackdrop>
      )}
    </div>
  );
}
