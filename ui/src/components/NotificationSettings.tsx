import { motion } from "framer-motion";
import { AlertTriangle, Bell, Globe, LinkIcon, Mail, Save } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Button, Card, CardHeader, Toggle } from "../components/ui";
import { ContextHelpButton } from "../components/help/ContextHelpButton";
import { useNotify } from "../context/NotificationContext";
import { API_BASE_URL } from "../lib/api-config";
import { getAuthToken } from "../lib/tokenStorage";
import { cn } from "../utils/helpers";

// ─── Types ───────────────────────────────────────────────────────────

interface DigestConfig {
  alert_types: {
    arc_flash: boolean;
    short_circuit: boolean;
    scada_faults: boolean;
    load_flow_violations: boolean;
    protection_coordination: boolean;
    equipment_alarms: boolean;
    system_health: boolean;
  };
  email_digest: {
    enabled: boolean;
    cron_schedule: string;
    recipients: string[];
  };
  webhooks: {
    id: string;
    url: string;
    events: string[];
    enabled: boolean;
  }[];
}

const DEFAULT_CONFIG: DigestConfig = {
  alert_types: {
    arc_flash: true,
    short_circuit: true,
    scada_faults: true,
    load_flow_violations: false,
    protection_coordination: false,
    equipment_alarms: true,
    system_health: false,
  },
  email_digest: {
    enabled: false,
    cron_schedule: "0 9 * * 1-5",
    recipients: [],
  },
  webhooks: [],
};

const ALERT_TYPE_LABELS: Record<string, { label: string; description: string }> = {
  arc_flash: { label: "Arc Flash", description: "Arc flash hazard analysis results" },
  short_circuit: { label: "Short Circuit", description: "Short circuit fault events" },
  scada_faults: { label: "SCADA Faults", description: "Real-time SCADA fault alerts" },
  load_flow_violations: { label: "Load Flow Violations", description: "Bus voltage & line loading violations" },
  protection_coordination: { label: "Protection Coordination", description: "Relay coordination issues" },
  equipment_alarms: { label: "Equipment Alarms", description: "Transformer & motor thermal alarms" },
  system_health: { label: "System Health", description: "Backend service health monitoring" },
};

// ─── Component ───────────────────────────────────────────────────────

export default function NotificationSettings() {
  const { notify } = useNotify();
  const [config, setConfig] = useState<DigestConfig>(DEFAULT_CONFIG);
  const [original, setOriginal] = useState<DigestConfig>(DEFAULT_CONFIG);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [newWebhookUrl, setNewWebhookUrl] = useState("");
  const [newRecipient, setNewRecipient] = useState("");

  // Fetch config
  const fetchConfig = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const token = getAuthToken();
      const r = await fetch(`${API_BASE_URL}/api/v1/notifications/digest/config`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        signal: AbortSignal.timeout(8000),
      });
      if (!r.ok) {
        const text = await r.text().catch(() => "Unknown error");
        throw new Error(`API ${r.status}: ${text.substring(0, 100)}`);
      }
      const data = await r.json();
      const fetched: DigestConfig = {
        alert_types: {
          arc_flash: data.alert_types?.arc_flash ?? DEFAULT_CONFIG.alert_types.arc_flash,
          short_circuit: data.alert_types?.short_circuit ?? DEFAULT_CONFIG.alert_types.short_circuit,
          scada_faults: data.alert_types?.scada_faults ?? DEFAULT_CONFIG.alert_types.scada_faults,
          load_flow_violations: data.alert_types?.load_flow_violations ?? DEFAULT_CONFIG.alert_types.load_flow_violations,
          protection_coordination: data.alert_types?.protection_coordination ?? DEFAULT_CONFIG.alert_types.protection_coordination,
          equipment_alarms: data.alert_types?.equipment_alarms ?? DEFAULT_CONFIG.alert_types.equipment_alarms,
          system_health: data.alert_types?.system_health ?? DEFAULT_CONFIG.alert_types.system_health,
        },
        email_digest: {
          enabled: data.email_digest?.enabled ?? DEFAULT_CONFIG.email_digest.enabled,
          cron_schedule: data.email_digest?.cron_schedule ?? DEFAULT_CONFIG.email_digest.cron_schedule,
          recipients: Array.isArray(data.email_digest?.recipients) ? data.email_digest.recipients : [],
        },
        webhooks: Array.isArray(data.webhooks)
          ? data.webhooks.map((w: Record<string, unknown>) => ({
              id: String(w.id ?? crypto.randomUUID()),
              url: String(w.url ?? ""),
              events: Array.isArray(w.events) ? w.events.map(String) : [],
              enabled: Boolean(w.enabled ?? true),
            }))
          : [],
      };
      setConfig(fetched);
      setOriginal(fetched);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchConfig();
  }, [fetchConfig]);

  // Save config
  const handleSave = async () => {
    setSaving(true);
    try {
      const token = getAuthToken();
      const r = await fetch(`${API_BASE_URL}/api/v1/notifications/digest/config`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(config),
        signal: AbortSignal.timeout(8000),
      });
      if (!r.ok) {
        const text = await r.text().catch(() => "Unknown error");
        throw new Error(`API ${r.status}: ${text.substring(0, 100)}`);
      }
      setOriginal({ ...config });
      notify("success", "Notification settings saved");
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      notify("error", `Failed to save notification settings: ${msg}`);
    } finally {
      setSaving(false);
    }
  };

  // Toggle alert type
  const toggleAlertType = (key: keyof DigestConfig["alert_types"]) => {
    setConfig({
      ...config,
      alert_types: { ...config.alert_types, [key]: !config.alert_types[key] },
    });
  };

  // Add webhook
  const addWebhook = () => {
    if (!newWebhookUrl.trim()) return;
    try {
      new URL(newWebhookUrl);
    } catch {
      notify("error", "Invalid webhook URL");
      return;
    }
    setConfig({
      ...config,
      webhooks: [
        ...config.webhooks,
        { id: crypto.randomUUID(), url: newWebhookUrl.trim(), events: ["*"], enabled: true },
      ],
    });
    setNewWebhookUrl("");
  };

  // Remove webhook
  const removeWebhook = (id: string) => {
    setConfig({ ...config, webhooks: config.webhooks.filter((w) => w.id !== id) });
  };

  // Toggle webhook
  const toggleWebhook = (id: string) => {
    setConfig({
      ...config,
      webhooks: config.webhooks.map((w) => (w.id === id ? { ...w, enabled: !w.enabled } : w)),
    });
  };

  // Add recipient
  const addRecipient = () => {
    if (!newRecipient.trim() || !newRecipient.includes("@")) {
      notify("error", "Invalid email address");
      return;
    }
    setConfig({
      ...config,
      email_digest: {
        ...config.email_digest,
        recipients: [...config.email_digest.recipients, newRecipient.trim()],
      },
    });
    setNewRecipient("");
  };

  // Remove recipient
  const removeRecipient = (email: string) => {
    setConfig({
      ...config,
      email_digest: {
        ...config.email_digest,
        recipients: config.email_digest.recipients.filter((r) => r !== email),
      },
    });
  };

  const hasChanges = JSON.stringify(config) !== JSON.stringify(original);

  // ─── Loading state ────────────────────────────────────────────────
  if (loading && error === null) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-[var(--accent-primary)] border-t-transparent rounded-full animate-spin" />
          <span className="text-sm text-[var(--text-muted)]">Loading notification settings…</span>
        </div>
      </div>
    );
  }

  // ─── Error state ──────────────────────────────────────────────────
  if (error && loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center max-w-md">
          <AlertTriangle className="w-8 h-8 text-red-400 mx-auto mb-3" />
          <p className="text-sm text-[var(--text-secondary)] mb-2">Failed to load notification settings</p>
          <p className="text-xs text-[var(--text-muted)] mb-4 font-mono">{error}</p>
          <Button variant="secondary" size="sm" onClick={fetchConfig}>
            Retry
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between"
      >
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-brand-500/10 border border-brand-500/20">
            <Bell className="w-5 h-5 text-brand-400" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-[var(--text-primary)]">Notification Settings</h2>
            <div className="flex items-center gap-2">
              <p className="text-sm text-[var(--text-tertiary)]">Alert preferences, email digests & webhooks</p>
              <ContextHelpButton contextId="notifications.settings" />
            </div>
          </div>
        </div>
        <Button variant="primary" size="sm" icon={Save} loading={saving} onClick={handleSave} disabled={!hasChanges}>
          Save Changes
        </Button>
      </motion.div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Alert type toggles */}
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
          <Card padding="md">
            <CardHeader
              title="Alert Types"
              subtitle="Choose which alerts to receive"
              icon={<Bell className="w-4 h-4" />}
            />
            <div className="space-y-3">
              {(Object.entries(ALERT_TYPE_LABELS) as [keyof DigestConfig["alert_types"], { label: string; description: string }][]).map(
                ([key, meta]) => (
                  <Toggle
                    key={key}
                    checked={config.alert_types[key]}
                    onChange={() => toggleAlertType(key)}
                    label={meta.label}
                    description={meta.description}
                  />
                ),
              )}
            </div>
          </Card>
        </motion.div>

        {/* Email digest & webhooks */}
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }} className="space-y-6">
          {/* Email digest */}
          <Card padding="md">
            <CardHeader
              title="Email Digest"
              subtitle="Scheduled email summaries"
              icon={<Mail className="w-4 h-4" />}
            />
            <div className="space-y-4">
              <Toggle
                checked={config.email_digest.enabled}
                onChange={(checked) =>
                  setConfig({
                    ...config,
                    email_digest: { ...config.email_digest, enabled: checked },
                  })
                }
                label="Enable Email Digest"
                description="Send periodic email summaries of alerts"
              />

              {config.email_digest.enabled && (
                <>
                  {/* Cron schedule */}
                  <div>
                    <label className="block text-sm font-medium text-[var(--text-secondary)] mb-2">
                      Cron Schedule
                    </label>
                    <input
                      type="text"
                      value={config.email_digest.cron_schedule}
                      onChange={(e) =>
                        setConfig({
                          ...config,
                          email_digest: { ...config.email_digest, cron_schedule: e.target.value },
                        })
                      }
                      placeholder="0 9 * * 1-5"
                      className="w-full px-3 py-2 rounded-lg bg-[var(--bg-primary)] border border-[var(--border-primary)] text-sm text-[var(--text-primary)] font-mono focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
                    />
                    <p className="text-xs text-[var(--text-muted)] mt-1">
                      Default: 0 9 * * 1-5 (9 AM weekdays)
                    </p>
                  </div>

                  {/* Recipients */}
                  <div>
                    <label className="block text-sm font-medium text-[var(--text-secondary)] mb-2">
                      Recipients
                    </label>
                    <div className="flex items-center gap-2">
                      <input
                        type="email"
                        value={newRecipient}
                        onChange={(e) => setNewRecipient(e.target.value)}
                        placeholder="email@example.com"
                        className="flex-1 px-3 py-2 rounded-lg bg-[var(--bg-primary)] border border-[var(--border-primary)] text-sm text-[var(--text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
                        onKeyDown={(e) => { if (e.key === "Enter") addRecipient(); }}
                      />
                      <Button variant="secondary" size="sm" onClick={addRecipient}>
                        Add
                      </Button>
                    </div>
                    {config.email_digest.recipients.length > 0 && (
                      <div className="flex flex-wrap gap-2 mt-2">
                        {config.email_digest.recipients.map((email) => (
                          <span
                            key={email}
                            className="inline-flex items-center gap-1.5 px-2 py-1 rounded-lg bg-[var(--bg-primary)] border border-[var(--border-primary)] text-xs text-[var(--text-secondary)]"
                          >
                            {email}
                            <button
                              type="button"
                              onClick={() => removeRecipient(email)}
                              className="text-[var(--text-muted)] hover:text-red-400 transition-colors"
                            >
                              ×
                            </button>
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </>
              )}
            </div>
          </Card>

          {/* Webhooks */}
          <Card padding="md">
            <CardHeader
              title="Webhooks"
              subtitle="External HTTP endpoints"
              icon={<Globe className="w-4 h-4" />}
            />
            <div className="space-y-4">
              {/* Add webhook */}
              <div className="flex items-center gap-2">
                <input
                  type="url"
                  value={newWebhookUrl}
                  onChange={(e) => setNewWebhookUrl(e.target.value)}
                  placeholder="https://hooks.example.com/notify"
                  className="flex-1 px-3 py-2 rounded-lg bg-[var(--bg-primary)] border border-[var(--border-primary)] text-sm text-[var(--text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--ring)]"
                  onKeyDown={(e) => { if (e.key === "Enter") addWebhook(); }}
                />
                <Button variant="secondary" size="sm" icon={LinkIcon} onClick={addWebhook}>
                  Add
                </Button>
              </div>

              {/* Existing webhooks */}
              {config.webhooks.length === 0 ? (
                <p className="text-xs text-[var(--text-muted)] py-4 text-center">No webhooks configured</p>
              ) : (
                <div className="max-h-48 overflow-y-auto space-y-2 pr-1">
                  {config.webhooks.map((webhook) => (
                    <div
                      key={webhook.id}
                      className="flex items-center justify-between p-2.5 rounded-lg bg-[var(--bg-primary)] border border-[var(--border-primary)]"
                    >
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-mono text-[var(--text-primary)] truncate">{webhook.url}</p>
                        <p className="text-xs text-[var(--text-muted)] mt-0.5">
                          Events: {webhook.events.join(", ")}
                        </p>
                      </div>
                      <div className="flex items-center gap-2 shrink-0 ml-2">
                        <button
                          type="button"
                          role="switch"
                          aria-checked={webhook.enabled}
                          onClick={() => toggleWebhook(webhook.id)}
                          className={cn(
                            "relative rounded-full transition-colors w-8 h-4.5",
                            webhook.enabled ? "bg-brand-500" : "bg-[var(--border-secondary)]",
                          )}
                        >
                          <span
                            className={cn(
                              "absolute top-0.5 bg-white rounded-full shadow-sm transition-transform w-3.5 h-3.5",
                              webhook.enabled ? "translate-x-[14px]" : "translate-x-0.5",
                            )}
                          />
                        </button>
                        <button
                          type="button"
                          onClick={() => removeWebhook(webhook.id)}
                          className="p-1 rounded hover:bg-red-500/10 text-[var(--text-muted)] hover:text-red-400 transition-colors"
                        >
                          <AlertTriangle className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </Card>
        </motion.div>
      </div>

      {/* Unsaved changes indicator */}
      {hasChanges && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="fixed bottom-4 left-1/2 -translate-x-1/2 z-50 flex items-center gap-3 px-4 py-2.5 rounded-xl bg-[var(--bg-card)] border border-[var(--border-primary)] shadow-lg"
        >
          <span className="text-sm text-[var(--text-secondary)]">Unsaved changes</span>
          <Button variant="ghost" size="sm" onClick={() => setConfig({ ...original })}>
            Discard
          </Button>
          <Button variant="primary" size="sm" icon={Save} loading={saving} onClick={handleSave}>
            Save
          </Button>
        </motion.div>
      )}
    </div>
  );
}
