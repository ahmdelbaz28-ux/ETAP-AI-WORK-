/**
 * NotificationContext — wires the toast UI to the backend notification system.
 *
 * Backend wiring (TASK-3):
 *   - GET  /api/v1/notifications/            → hydrate initial list on mount
 *   - PUT   /api/v1/notifications/{id}/read  → mark as read on dismiss
 *   - WS    /ws/notifications?token=...      → real-time push
 *
 * Backward-compat: the existing `notify(type, message)` API is preserved
 * for client-side toasts (e.g. "Saved successfully"). These ephemeral
 * toasts are NOT round-tripped to the server — they continue to behave
 * exactly as before. The backend-sourced notifications are surfaced
 * through the same toast container so users see a unified feed.
 *
 * Graceful fallback: if the backend is unreachable on mount, we display a
 * small degraded-mode banner at the top of the toast container so users
 * know real-time push is offline (instead of silently swallowing errors).
 *
 * Ref: TASK-3
 */

import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle, CheckCircle, Info, WifiOff, X, XCircle } from "lucide-react";
import {
  type ReactNode,
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { API_BASE_URL } from "../lib/api-config";
import { getAuthToken } from "../lib/tokenStorage";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ToastNotification {
  id: string;
  type: "success" | "error" | "warning" | "info";
  message: string;
}

interface BackendNotification {
  id: string;
  user_id: string;
  notification_type: string;
  title: string;
  message: string;
  priority: string;
  data: Record<string, unknown> | null;
  is_read: boolean;
  is_archived: boolean;
  created_at: string | null;
  read_at: string | null;
}

interface NotificationListResponse {
  notifications: BackendNotification[];
  total: number;
  unread_count: number;
  page: number;
  page_size: number;
}

interface NotificationContextType {
  notifications: ToastNotification[];
  notify: (type: ToastNotification["type"], message: string) => void;
  dismiss: (id: string) => void;
  /** True when the backend notification feed is reachable; false when degraded. */
  backendReachable: boolean;
}

const NotificationContext = createContext<NotificationContextType>({
  notifications: [],
  notify: () => {},
  dismiss: () => {},
  backendReachable: true,
});

const iconMap = {
  success: CheckCircle,
  error: XCircle,
  warning: AlertTriangle,
  info: Info,
};

const colorMap = {
  success: "bg-green-600/90 border-green-400/30",
  error: "bg-red-600/90 border-red-400/30",
  warning: "bg-amber-600/90 border-amber-400/30",
  info: "bg-brand-600/90 border-brand-400/30",
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function authHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const token = getAuthToken();
  return { ...(token ? { Authorization: `Bearer ${token}` } : {}), ...extra };
}

/**
 * Map a backend notification's `notification_type`/`priority` to a toast
 * type. Falls back to "info" for unknown types.
 */
function backendToToastType(n: BackendNotification): ToastNotification["type"] {
  const t = n.notification_type?.toLowerCase() ?? "";
  if (
    t.includes("error") ||
    t.includes("critical") ||
    n.priority === "critical" ||
    n.priority === "high"
  ) {
    return "error";
  }
  if (t.includes("warning") || t.includes("alert") || n.priority === "medium") {
    return "warning";
  }
  if (t.includes("success") || t.includes("info")) {
    return "success";
  }
  return "info";
}

/**
 * Build the WebSocket URL for the notifications feed. The token is sent
 * as a query parameter because WebSocket headers are limited and the
 * browser API doesn't allow setting Authorization on WS upgrades.
 */
function buildWsUrl(token: string): string {
  // API_BASE_URL may be "" (same-origin on HF Space), a bare host, or a
  // full URL. Normalize to ws(s)://host/ws/notifications?token=...
  const base = API_BASE_URL || "";
  let url: string;
  if (base.startsWith("http://") || base.startsWith("https://")) {
    url = base.replace(/^http/, "ws");
  } else if (base.startsWith("ws://") || base.startsWith("wss://")) {
    url = base;
  } else {
    // Bare host or empty — use the current page's protocol/host
    const proto = globalThis.location?.protocol === "https:" ? "wss:" : "ws:";
    url = `${proto}//${globalThis.location?.host ?? ""}${base}`;
  }
  const sep = url.includes("?") ? "&" : "?";
  return `${url}/ws/notifications${sep}token=${encodeURIComponent(token)}`;
}

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function NotificationProvider({ children }: { readonly children: ReactNode }) {
  const [notifications, setNotifications] = useState<ToastNotification[]>([]);
  const [backendReachable, setBackendReachable] = useState(true);
  // Track which backend notification IDs we've already toasted, so we don't
  // re-toast them after the initial hydration on subsequent WS reconnects.
  const toastedBackendIds = useRef<Set<string>>(new Set());
  // Track the active WebSocket so we can clean it up on unmount.
  const wsRef = useRef<WebSocket | null>(null);
  // Reconnect backoff — doubles on each failure, capped at 30s.
  const reconnectDelayRef = useRef(1000);
  // Track whether the component is mounted, to avoid state updates after unmount.
  const isMountedRef = useRef(true);

  // Add an ephemeral toast (auto-dismiss after 5s). Used by both the
  // public `notify` API and by backend-sourced notifications.
  const pushToast = useCallback(
    (type: ToastNotification["type"], message: string, backendId?: string) => {
      if (!isMountedRef.current) return;
      const id = backendId ?? crypto.randomUUID();
      setNotifications((prev) => [...prev, { id, type, message }]);
      setTimeout(() => {
        if (!isMountedRef.current) return;
        setNotifications((prev) => prev.filter((n) => n.id !== id));
      }, 5000);
    },
    [],
  );

  // Public notify API — client-side toasts. Preserved for backward-compat.
  const notify = useCallback(
    (type: ToastNotification["type"], message: string) => {
      pushToast(type, message);
    },
    [pushToast],
  );

  // Public dismiss — removes the toast locally. If the toast corresponds
  // to a backend notification (i.e. its id is a backend notification id),
  // also fire PUT /api/v1/notifications/{id}/read to mark it read server-side.
  const dismiss = useCallback((id: string) => {
    setNotifications((prev) => prev.filter((n) => n.id !== id));
    // Fire-and-forget the read request; surface failures via console
    // (don't re-toast — that would create a notification loop).
    if (toastedBackendIds.current.has(id)) {
      fetch(`${API_BASE_URL}/api/v1/notifications/${encodeURIComponent(id)}/read`, {
        method: "PUT",
        headers: authHeaders({ "Content-Type": "application/json" }),
      }).catch((err) => {
        // eslint-disable-next-line no-console
        console.warn("Failed to mark notification as read:", err);
      });
    }
  }, []);

  // Connect to the WebSocket with auto-reconnect + exponential backoff.
  const connectWs = useCallback(() => {
    if (!isMountedRef.current) return;
    const token = getAuthToken();
    if (!token) return; // Not logged in yet — skip WS

    let ws: WebSocket;
    try {
      ws = new WebSocket(buildWsUrl(token));
    } catch (err) {
      // eslint-disable-next-line no-console
      console.warn("Failed to construct WebSocket:", err);
      setBackendReachable(false);
      return;
    }
    wsRef.current = ws;

    ws.onopen = () => {
      if (!isMountedRef.current) return;
      setBackendReachable(true);
      reconnectDelayRef.current = 1000; // Reset backoff on success
    };

    ws.onmessage = (event) => {
      if (!isMountedRef.current) return;
      try {
        const data = JSON.parse(event.data) as Partial<BackendNotification> & { type?: string };
        // The WS may send different message shapes. Handle the common case:
        // a full notification object. Skip if missing required fields.
        if (!data.id || !data.message) return;
        // Don't re-toast notifications we've already shown.
        if (toastedBackendIds.current.has(data.id)) return;
        toastedBackendIds.current.add(data.id);
        const toastType = backendToToastType(data as BackendNotification);
        const message = data.title ? `${data.title}: ${data.message}` : data.message;
        pushToast(toastType, message, data.id);
      } catch {
        // Ignore malformed WS messages — don't crash the UI
      }
    };

    ws.onerror = () => {
      if (!isMountedRef.current) return;
      setBackendReachable(false);
    };

    ws.onclose = () => {
      if (!isMountedRef.current) return;
      wsRef.current = null;
      // Schedule a reconnect with exponential backoff (capped at 30s).
      // Don't set backendReachable=false here — a transient close might
      // recover quickly. The onerror handler is responsible for surfacing
      // persistent failures.
      const delay = Math.min(reconnectDelayRef.current, 30000);
      reconnectDelayRef.current = Math.min(reconnectDelayRef.current * 2, 30000);
      setTimeout(() => {
        if (isMountedRef.current) connectWs();
      }, delay);
    };
  }, [pushToast]);

  // On mount: hydrate from REST, then connect WS.
  useEffect(() => {
    isMountedRef.current = true;
    const token = getAuthToken();

    if (token) {
      // Hydrate the initial unread list from the server
      fetch(`${API_BASE_URL}/api/v1/notifications/?page=1&page_size=20&unread_only=true`, {
        headers: authHeaders(),
      })
        .then(async (res) => {
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          const data = (await res.json()) as NotificationListResponse;
          if (!isMountedRef.current) return;
          // Toast each unread notification that we haven't shown yet.
          for (const n of data.notifications ?? []) {
            if (toastedBackendIds.current.has(n.id)) continue;
            toastedBackendIds.current.add(n.id);
            const toastType = backendToToastType(n);
            const message = n.title ? `${n.title}: ${n.message}` : n.message;
            pushToast(toastType, message, n.id);
          }
          setBackendReachable(true);
        })
        .catch(() => {
          if (!isMountedRef.current) return;
          // Backend unreachable — surface as degraded banner.
          setBackendReachable(false);
        });

      // Connect WebSocket for real-time push
      connectWs();
    }

    return () => {
      isMountedRef.current = false;
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connectWs, pushToast]);

  // Memoise the context value so consumers don't re-render unnecessarily.
  const contextValue = useMemo(
    () => ({ notifications, notify, dismiss, backendReachable }),
    [notifications, notify, dismiss, backendReachable],
  );

  return (
    <NotificationContext.Provider value={contextValue}>
      {children}
      {/* Notification container — bottom-right of viewport.
          Uses inline styles for positioning + z-index to avoid Tailwind v4
          utility fallback issues (max-w-sm / z-index var() bugs). */}
      <div
        style={{
          position: "fixed",
          bottom: "16px",
          right: "16px",
          zIndex: 80,
          display: "flex",
          flexDirection: "column",
          gap: "8px",
          width: "min(384px, calc(100vw - 32px))",
          maxWidth: "384px",
          pointerEvents: "none",
        }}
      >
        {/* Degraded-mode banner — shown when the backend notification feed
            is unreachable. Dismissible by clicking or pressing Enter/Space.
            Uses a <button> so keyboard users can dismiss it too. */}
        {!backendReachable && (
          <button
            type="button"
            className="pointer-events-auto px-4 py-2.5 rounded-xl shadow-lg text-sm font-medium flex items-center gap-2 cursor-pointer border backdrop-blur-md bg-amber-600/90 border-amber-400/30 text-white"
            onClick={() => setBackendReachable(true)}
            title="Click to dismiss — real-time push will retry automatically"
          >
            <WifiOff className="w-4 h-4 shrink-0" />
            <span className="flex-1 text-left">Real-time notifications offline — retrying</span>
            <X className="w-3.5 h-3.5 text-white/60 hover:text-white transition-colors shrink-0" />
          </button>
        )}
        <AnimatePresence mode="popLayout">
          {notifications.map((n) => {
            const Icon = iconMap[n.type];
            return (
              <motion.div
                key={n.id}
                layout
                initial={{ opacity: 0, x: 120, scale: 0.9 }}
                animate={{ opacity: 1, x: 0, scale: 1 }}
                exit={{ opacity: 0, x: 120, scale: 0.9 }}
                transition={{ type: "spring", damping: 20, stiffness: 300 }}
                onClick={() => dismiss(n.id)}
                role="alert"
                aria-live="assertive"
                aria-atomic="true"
                className={`pointer-events-auto px-4 py-3 rounded-xl shadow-lg text-sm font-medium flex items-center gap-3 cursor-pointer border backdrop-blur-md ${colorMap[n.type]}`}
                style={{ minWidth: "280px" }}
              >
                <Icon className="w-5 h-5 shrink-0 text-white" />
                <span className="flex-1 text-white">{n.message}</span>
                <X className="w-4 h-4 text-white/60 hover:text-white transition-colors shrink-0" />
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>
    </NotificationContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useNotify() {
  return useContext(NotificationContext);
}
