import { Globe, Plus, Radio, RefreshCw, Send, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Badge, Button, Card, CardHeader, Modal } from "../components/ui";
import { useNotify } from "../context/NotificationContext";
import { request } from "../lib/api";

export interface WebhookConfig {
  id: string;
  url: string;
  event_types: string[];
  secret: string;
  is_active: boolean;
  created_at?: string;
}

const AVAILABLE_EVENTS = [
  "email.sent",
  "email.delivered",
  "email.bounced",
  "email.opened",
  "email.clicked",
  "email.complained",
];

export default function EmailWebhooks() {
  const { notify } = useNotify();

  const [webhooks, setWebhooks] = useState<WebhookConfig[]>([]);
  const [loading, setLoading] = useState(true);

  // Modal
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [targetUrl, setTargetUrl] = useState("");
  const [selectedEvents, setSelectedEvents] = useState<string[]>([
    "email.delivered",
    "email.bounced",
  ]);
  const [autoSecret, setAutoSecret] = useState("");

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await request<{ webhooks?: WebhookConfig[]; items?: WebhookConfig[] }>(
        "/api/v1/email/webhooks/",
      );
      setWebhooks(res.webhooks || res.items || []);
    } catch (err: any) {
      notify("error", err?.message || "Failed to load webhook endpoints");
    } finally {
      setLoading(false);
    }
  }, [notify]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleOpenCreate = () => {
    setTargetUrl("");
    setSelectedEvents(["email.delivered", "email.bounced"]);
    setAutoSecret(`whsec_${crypto.randomUUID().replaceAll("-", "")}`);
    setIsModalOpen(true);
  };

  const handleSave = async () => {
    if (!targetUrl.trim()) {
      notify("error", "Webhook URL is required");
      return;
    }
    if (selectedEvents.length === 0) {
      notify("error", "Select at least one event type");
      return;
    }

    try {
      await request("/api/v1/email/webhooks/", {
        method: "POST",
        body: JSON.stringify({
          url: targetUrl.trim(),
          event_types: selectedEvents,
          secret: autoSecret,
        }),
      });
      notify("success", "Webhook endpoint registered successfully");
      setIsModalOpen(false);
      loadData();
    } catch (err: any) {
      notify("error", err?.message || "Failed to register webhook");
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Are you sure you want to delete this webhook endpoint?")) return;
    try {
      await request(`/api/v1/email/webhooks/${id}`, { method: "DELETE" });
      notify("success", "Webhook endpoint removed");
      loadData();
    } catch (err: any) {
      notify("error", err?.message || "Failed to delete webhook");
    }
  };

  const handleTestPing = async (id: string) => {
    try {
      await request(`/api/v1/email/webhooks/${id}/test`, { method: "POST" });
      notify("success", "Test event ping sent successfully");
    } catch (err: any) {
      notify("error", err?.message || "Test ping failed");
    }
  };

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-100 flex items-center gap-2">
            <Radio className="h-7 w-7 text-indigo-400" />
            Email Webhook Subscriptions
          </h1>
          <p className="text-sm text-slate-400">
            Configure real-time webhooks for delivery notifications, bounces, and engagements.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button variant="secondary" onClick={loadData} disabled={loading}>
            <RefreshCw className={`h-4 w-4 mr-2 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
          <Button variant="primary" onClick={handleOpenCreate}>
            <Plus className="h-4 w-4 mr-2" />
            Add Webhook Endpoint
          </Button>
        </div>
      </div>

      {/* Webhooks Table */}
      <Card variant="glass">
        <CardHeader title="Configured Endpoints" />
        <div className="p-4 overflow-x-auto">
          {loading ? (
            <div className="flex items-center justify-center p-12 text-slate-400">
              <RefreshCw className="h-8 w-8 animate-spin text-indigo-400 mr-3" />
              <span>Loading webhooks...</span>
            </div>
          ) : webhooks.length === 0 ? (
            <div className="text-center py-12 text-slate-400">
              <Radio className="h-12 w-12 mx-auto mb-3 opacity-40" />
              <p className="text-base font-medium">No webhook endpoints configured</p>
              <p className="text-xs text-slate-500 mt-1">
                Register a URL to receive real-time email event payloads.
              </p>
            </div>
          ) : (
            <table className="w-full text-left text-sm text-slate-300">
              <thead className="bg-slate-800/60 text-slate-400 text-xs uppercase tracking-wider">
                <tr>
                  <th className="px-4 py-3 rounded-l-md">Target URL</th>
                  <th className="px-4 py-3">Subscribed Events</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3 text-right rounded-r-md">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {webhooks.map((wh) => (
                  <tr key={wh.id} className="hover:bg-slate-800/40 transition-colors">
                    <td className="px-4 py-3 font-mono text-xs text-slate-100">
                      <div className="flex items-center gap-2">
                        <Globe className="h-4 w-4 text-indigo-400 shrink-0" />
                        <span className="truncate max-w-md">{wh.url}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-1">
                        {(wh.event_types || []).map((ev) => (
                          <span
                            key={ev}
                            className="px-2 py-0.5 rounded text-[11px] font-mono bg-indigo-950/60 text-indigo-300 border border-indigo-800/40"
                          >
                            {ev}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant={wh.is_active ? "success" : "neutral"}>
                        {wh.is_active ? "Active" : "Disabled"}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <Button
                          variant="secondary"
                          className="px-2 py-1 text-xs"
                          onClick={() => handleTestPing(wh.id)}
                        >
                          <Send className="h-3.5 w-3.5 mr-1" /> Test Ping
                        </Button>
                        <Button
                          variant="danger"
                          className="px-2 py-1 text-xs"
                          onClick={() => handleDelete(wh.id)}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </Card>

      {/* Create Modal */}
      <Modal
        open={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title="Register Webhook Endpoint"
      >
        <div className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1">
              Target Endpoint URL *
            </label>
            <input
              type="url"
              placeholder="https://api.yourcompany.com/webhooks/email"
              value={targetUrl}
              onChange={(e) => setTargetUrl(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 rounded-md px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-300 mb-2">
              Event Subscriptions
            </label>
            <div className="grid grid-cols-2 gap-2 p-3 bg-slate-900/80 rounded border border-slate-800">
              {AVAILABLE_EVENTS.map((ev) => {
                const isSelected = selectedEvents.includes(ev);
                return (
                  <label
                    key={ev}
                    className="flex items-center gap-2 cursor-pointer text-xs text-slate-300"
                  >
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setSelectedEvents([...selectedEvents, ev]);
                        } else {
                          setSelectedEvents(selectedEvents.filter((item) => item !== ev));
                        }
                      }}
                      className="rounded bg-slate-800 border-slate-700 text-indigo-600"
                    />
                    <span className="font-mono">{ev}</span>
                  </label>
                );
              })}
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1">
              Signing Secret (Auto-Generated)
            </label>
            <input
              type="text"
              readOnly
              value={autoSecret}
              className="w-full bg-slate-950 border border-slate-800 rounded-md px-3 py-2 text-xs font-mono text-slate-400"
            />
          </div>

          <div className="flex justify-end gap-3 pt-3">
            <Button variant="secondary" onClick={() => setIsModalOpen(false)}>
              Cancel
            </Button>
            <Button variant="primary" onClick={handleSave}>
              Save Webhook
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
