/**
 * chatStore — Chat Workspace state (P6). Frontend state ONLY.
 *
 * Backend contracts:
 *  - chat stream     : POST /api/v1/chat/stream (llm-chat.streamFromServerChat)
 *  - session stream  : POST /api/v1/ws-ticket → WS /ws/sessions/{id}?ticket=...
 *                      events: session_init, token, action_proposed, approval_result,
 *                      job_progress, result_ready, decision_request (seq dedupe on replay)
 *  - approvals       : GET /api/v1/approvals/pending?session_id=...
 *                      POST /api/v1/approvals/{id}/resolve ({ decision })
 *                      PUT /api/v1/session/auto-approve ({ session_id, enabled })
  *  - results         : GET /api/v1/results/{resultId}
 *  - kill switch     : GET /admin/cua/kill-switch, POST /admin/cua/kill-switch/activate ({ reason })
 */
import { create } from "zustand";
import { request } from "../lib/api";
import { API_BASE_URL } from "../lib/api-config";
import { getChatSessionId, streamFromServerChat } from "../lib/llm-chat";
import { generateId } from "../utils/helpers";

export type ChatStreamStatus = "idle" | "connecting" | "streaming" | "completed" | "error";
export type WsConnectionStatus =
  | "connecting"
  | "connected"
  | "reconnecting"
  | "disconnected"
  | "completed"
  | "failed";

export interface ChatMessage {
  readonly id: string;
  readonly role: "user" | "assistant";
  readonly content: string;
  readonly status: "complete" | "streaming" | "error";
  readonly error?: string;
  readonly createdAt: number;
}

/** Event types published on the SessionStream hub (P3 wire contract). */
export type SessionEventType =
  | "session_init"
  | "token"
  | "action_proposed"
  | "approval_result"
  | "job_progress"
  | "result_ready"
  | "decision_request";

export interface SessionEvent<TPayload = Record<string, unknown>> {
  readonly seq: number;
  readonly type: SessionEventType;
  readonly session_id: string;
  readonly ts: string;
  readonly payload: TPayload;
}

/** Pending action returned by the Approval Gateway. */
export interface PendingApproval {
  readonly id: string;
  readonly session_id: string;
  readonly tool: string;
  readonly args_hash?: string | null;
  readonly risk_class: string;
  readonly status: string;
  readonly expires_at?: string | null;
  readonly created_at?: string | null;
  readonly requested_by_user_id?: string | null;
  readonly requested_by_role?: string | null;
  // transient UI state — not part of the wire contract
  readonly resolving?: "approve" | "reject";
  readonly error?: string | null;
}

export interface ActivityProgress {
  readonly execution_id?: string;
  readonly phase: string;
  readonly pct: number;
  readonly tool?: string;
  readonly ts?: string;
}

/** A `result_ready` event optionally enriched with the ResultStore payload. */
export interface ResultEntry {
  readonly resultId: string;
  readonly execution_id?: string;
  readonly tool?: string;
  readonly plan_id?: string;
  readonly ts?: string;
  readonly summary?: Record<string, unknown> | null;
  readonly loading?: boolean;
  readonly loaded?: boolean;
  readonly error?: string | null;
}

export interface ProposedActionEntry {
  readonly seq: number;
  readonly ts: string;
  readonly payload: Record<string, unknown>;
}

export interface ApprovalResultEntry {
  readonly seq: number;
  readonly ts: string;
  readonly tool?: string;
  readonly decision: string;
  readonly reason?: string;
}

export interface DecisionEntry {
  readonly seq: number;
  readonly ts: string;
  readonly payload: Record<string, unknown>;
}

// ─── Module-level mutable refs (store internals — never exposed) ─────────────
const WS_TOKEN_MARKER = "ws_token_";
const MAX_LIST_ITEMS = 50;
const RECONNECT_MAX_ATTEMPTS = 5;

let activeWs: WebSocket | null = null;
let wsClosedByUser = false;
let reconnectAttempt = 0;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
let activeChatAbort: AbortController | null = null;

function wsBaseUrl(): string {
  if (!API_BASE_URL) {
    if (typeof window === "undefined") return "";
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${protocol}//${window.location.host}`;
  }
  return API_BASE_URL.replace(/^http/, "ws");
}

function toErrorMessage(err: unknown, fallback: string): string {
  return err instanceof Error && err.message ? err.message : fallback;
}

function initialAutoApprove(): { enabled: boolean; loading: boolean; error: string | null } {
  return { enabled: false, loading: false, error: null };
}

function initialEmergencyStop(): { active: boolean; activating: boolean; lastResult: "success" | "error" | null; error: string | null } {
  return { active: false, activating: false, lastResult: null, error: null };
}

// @@CHUNK_STORE_CONTINUE@@

export interface ChatWorkspaceState {
  sessionId: string;
  messages: ChatMessage[];
  streamStatus: ChatStreamStatus;
  lastAssistantId: string | null;
  wsStatus: WsConnectionStatus;
  lastSeq: number;
  wsError: string | null;
  activity: ActivityProgress[];
  proposedActions: ProposedActionEntry[];
  approvalResults: ApprovalResultEntry[];
  approvals: PendingApproval[];
  results: ResultEntry[];
  decisions: DecisionEntry[];
  selectedResultId: string | null;
  approvalsError: string | null;
  autoApprove: { enabled: boolean; loading: boolean; error: string | null };
  emergencyStop: { active: boolean; activating: boolean; lastResult: "success" | "error" | null; error: string | null };
  connectSession: () => void;
  disconnectSession: () => void;
  handleSessionEvent: (frame: unknown) => void;
  setWsStatus: (status: WsConnectionStatus, error?: string | null) => void;
  sendMessage: (text: string) => Promise<boolean>;
  setStreamStatus: (status: ChatStreamStatus) => void;
  refreshApprovals: () => Promise<void>;
  resolveApproval: (approvalId: string, decision: "approve" | "reject") => Promise<boolean>;
  setAutoApprove: (enabled: boolean) => Promise<boolean>;
  activateEmergencyStop: (reason?: string) => Promise<boolean>;
  checkEmergencyStop: () => Promise<void>;
  loadResult: (resultId: string) => Promise<void>;
  selectResult: (resultId: string | null) => void;
  clearSessionData: () => void;
}

const scheduleReconnect = (get: () => ChatWorkspaceState) => {
  if (wsClosedByUser) return;
  if (reconnectAttempt >= RECONNECT_MAX_ATTEMPTS) {
    useChatStore.setState({ wsStatus: "failed", wsError: "Session stream reconnect attempts exhausted" });
    return;
  }
  reconnectAttempt += 1;
  const delay = Math.min(1000 * 2 ** reconnectAttempt, 15000);
  if (reconnectTimer) clearTimeout(reconnectTimer);
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    get().connectSession();
  }, delay);
};

export const useChatStore = create<ChatWorkspaceState>()((set, get) => ({
  sessionId: getChatSessionId(),
  messages: [],
  streamStatus: "idle",
  lastAssistantId: null,
  wsStatus: "disconnected",
  lastSeq: 0,
  wsError: null,
  activity: [],
  proposedActions: [],
  approvalResults: [],
  approvals: [],
  results: [],
  decisions: [],
  selectedResultId: null,
  approvalsError: null,
  autoApprove: initialAutoApprove(),
  emergencyStop: initialEmergencyStop(),

  setStreamStatus: (status) => set({ streamStatus: status }),

  setWsStatus: (status, error = null) => {
    set({ wsStatus: status, wsError: error });
  },

  connectSession: () => {
    const { wsStatus } = get();
    if (wsStatus === "connected" || wsStatus === "connecting") return;
    if (typeof WebSocket === "undefined") {
      set({ wsStatus: "failed", wsError: "WebSocket is not available in this environment" });
      return;
    }
    set({ wsStatus: "connecting", wsError: null });
    void (async () => {
      try {
        const res = await request<{ ticket: string; expires_at?: string; ttl_seconds?: number }>(
          "/api/v1/ws-ticket",
          { method: "POST", body: JSON.stringify({ session_id: get().sessionId }) },
        );
        if (!res?.ticket) throw new Error("No session stream ticket returned");
        const resume = get().lastSeq > 0 ? `&after_seq=${get().lastSeq}` : "";
        const url = `${wsBaseUrl()}/ws/sessions/${encodeURIComponent(get().sessionId)}?ticket=${encodeURIComponent(
          res.ticket,
        )}${resume}`;
        const socket = new WebSocket(url);
        activeWs = socket;
        wsClosedByUser = false;
        socket.addEventListener("open", () => {
          reconnectAttempt = 0;
          set({ wsStatus: "connected", wsError: null });
        });
        socket.addEventListener("message", (event) => {
          try {
            get().handleSessionEvent(JSON.parse(String(event.data)));
          } catch {
            // Non-JSON frames (heartbeats/pings) are ignored — never crash.
          }
        });
        socket.addEventListener("error", () => {
          set({ wsStatus: "failed", wsError: "Session stream connection failed" });
        });
        socket.addEventListener("close", () => {
          if (wsClosedByUser || get().wsStatus === "disconnected") {
            set({ wsStatus: "disconnected" });
            return;
          }
          set({ wsStatus: "reconnecting", wsError: "Session stream disconnected — reconnecting" });
          scheduleReconnect(get);
        });
      } catch (err) {
        set({ wsStatus: "failed", wsError: toErrorMessage(err, "Failed to open session stream") });
      }
    })();
  },

  disconnectSession: () => {
    wsClosedByUser = true;
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    if (activeWs) {
      try {
        activeWs.close();
      } catch {
        // ignore — the socket may already be in a closing/closed state
      }
      activeWs = null;
    }
    set({ wsStatus: "disconnected", wsError: null });
  },

  handleSessionEvent: (frame) => {
    if (!frame || typeof frame !== "object") return;
    const evt = frame as Partial<SessionEvent>;
    if (typeof evt.seq !== "number" || typeof evt.type !== "string") return;
    if (typeof evt.session_id === "string" && evt.session_id !== get().sessionId) return;

    // Sequence-deduped replay (resumes after `after_seq=lastSeq`).
    if (evt.seq <= get().lastSeq) return;
    set({ lastSeq: evt.seq });

    const ts = typeof evt.ts === "string" ? evt.ts : new Date().toISOString();
    const payload = (evt.payload ?? {}) as Record<string, unknown>;

    switch (evt.type) {
      case "session_init":
        return;
      case "token": {
        if (typeof payload.delta !== "string" || !payload.delta) return;
        const { messages } = get();
        const last = messages[messages.length - 1];
        if (last && last.role === "assistant" && last.status === "streaming" && last.id.startsWith(WS_TOKEN_MARKER)) {
          set({
            messages: messages.map((m) =>
              m.id === last.id ? { ...m, content: m.content + payload.delta } : m,
            ),
          });
        } else {
          const newId = `${WS_TOKEN_MARKER}${generateId()}`;
          set({
            messages: [
              ...messages,
              { id: newId, role: "assistant", content: payload.delta, status: "streaming", createdAt: Date.now() },
            ],
            lastAssistantId: newId,
            streamStatus: "streaming",
          });
        }
        return;
      }
      case "action_proposed": {
        const entry: ProposedActionEntry = { seq: evt.seq, ts, payload };
        set({ proposedActions: [entry, ...get().proposedActions].slice(0, MAX_LIST_ITEMS) });
        return;
      }
      case "approval_result": {
        const entry: ApprovalResultEntry = {
          seq: evt.seq,
          ts,
          tool: typeof payload.tool === "string" ? payload.tool : undefined,
          decision: typeof payload.decision === "string" ? payload.decision : "unknown",
          reason: typeof payload.reason === "string" ? payload.reason : undefined,
        };
        set({ approvalResults: [entry, ...get().approvalResults].slice(0, MAX_LIST_ITEMS) });
        return;
      }
      case "job_progress": {
        const phase = typeof payload.phase === "string" ? payload.phase : "running";
        const pctNum = typeof payload.pct === "number" ? payload.pct : Number(payload.pct ?? 0);
        const progress: ActivityProgress = {
          execution_id: typeof payload.execution_id === "string" ? payload.execution_id : undefined,
          tool: typeof payload.tool === "string" ? payload.tool : undefined,
          phase,
          pct: Number.isFinite(pctNum) ? Math.max(0, Math.min(100, pctNum)) : 0,
          ts,
        };
        const activity = [...get().activity, progress].slice(-MAX_LIST_ITEMS);
        set({ activity });
        return;
      }
            case "result_ready": {
        // The P3 SessionStream `result_ready` event carries the result id as
        // `result_id` (snake_case). The frontend's wire-facing model uses
        // `resultId` (camelCase) to match the P5 public contract —
        // POST /api/v1/studies/run → StudyResult serialization_alias="resultId".
        const resultId =
          typeof payload.result_id === "string"
            ? payload.result_id
            : typeof payload.execution_id === "string"
              ? payload.execution_id
              : null;
        if (!resultId) return;
        const entry: ResultEntry = {
          resultId,
          execution_id: typeof payload.execution_id === "string" ? payload.execution_id : undefined,
          tool: typeof payload.tool === "string" ? payload.tool : undefined,
          plan_id: typeof payload.plan_id === "string" ? payload.plan_id : undefined,
          ts,
          summary: (payload.summary as Record<string, unknown> | undefined) ?? null,
          // result_ready announces a result whose ResultStore payload is still
          // pending enrichment via loadResult — the entry starts in-flight.
          loading: true,
        };
        const existing = get().results.find((r) => r.resultId === resultId);
        const results = existing
          ? get().results.map((r) => (r.resultId === resultId ? { ...r, ...entry, loading: !r.loaded } : r))
          : [entry, ...get().results].slice(0, MAX_LIST_ITEMS);
        set({ results, selectedResultId: get().selectedResultId ?? resultId });
        return;
      }
      case "decision_request": {
        const entry: DecisionEntry = { seq: evt.seq, ts, payload };
        set({ decisions: [entry, ...get().decisions].slice(0, MAX_LIST_ITEMS) });
        return;
      }
      default:
        return;
    }
  },

  sendMessage: async (text) => {
    const trimmed = (text ?? "").trim();
    if (!trimmed) return false;
    if (activeChatAbort) {
      try { activeChatAbort.abort(); } catch { /* ignore */ }
    }
    const controller = new AbortController();
    activeChatAbort = controller;
    const userMessage: ChatMessage = {
      id: generateId(),
      role: "user",
      content: trimmed,
      status: "complete",
      createdAt: Date.now(),
    };
    set({
      messages: [...get().messages, userMessage],
      streamStatus: "connecting",
    });

    try {
      const history = get().messages
        .filter((m) => m.status !== "error")
        .map((m) => ({ role: m.role, content: m.content }));

      let acc = "";
      for await (const delta of streamFromServerChat(history, controller.signal)) {
        acc += delta;
        const { messages } = get();
        const last = messages[messages.length - 1];
        if (last && last.role === "assistant" && last.id.startsWith(WS_TOKEN_MARKER)) {
          set({
            messages: messages.map((m) =>
              m.id === last.id ? { ...m, content: acc, status: "streaming" } : m,
            ),
            streamStatus: "streaming",
          });
        } else {
          const newId = `${WS_TOKEN_MARKER}${generateId()}`;
          set({
            messages: [
              ...messages,
              { id: newId, role: "assistant", content: acc, status: "streaming", createdAt: Date.now() },
            ],
            lastAssistantId: newId,
            streamStatus: "streaming",
          });
        }
      }
      // Finalize the streaming assistant message.
      const { messages: afterStream } = get();
      const last = afterStream[afterStream.length - 1];
      if (last && last.role === "assistant" && last.id.startsWith(WS_TOKEN_MARKER)) {
        set({
          messages: afterStream.map((m) =>
            m.id === last.id ? { ...m, status: "complete", content: acc || m.content } : m,
          ),
          streamStatus: "completed",
        });
      } else {
        set({ streamStatus: "completed" });
      }
      return true;
    } catch (err) {
      const message = toErrorMessage(err, "Chat stream failed");
      const { messages: errMsgs } = get();
      const last = errMsgs[errMsgs.length - 1];
      if (last && last.role === "assistant" && last.id.startsWith(WS_TOKEN_MARKER) && last.status === "streaming") {
        set({
          messages: errMsgs.map((m) =>
            m.id === last.id ? { ...m, status: "error", error: message } : m,
          ),
          streamStatus: "error",
        });
      } else {
        set({
          messages: [
            ...errMsgs,
            {
              id: generateId(),
              role: "assistant",
              content: message,
              status: "error",
              error: message,
              createdAt: Date.now(),
            },
          ],
          streamStatus: "error",
        });
      }
      return false;
    } finally {
      if (activeChatAbort === controller) activeChatAbort = null;
    }
  },

  clearSessionData: () => {
    if (activeChatAbort) {
      try { activeChatAbort.abort(); } catch { /* ignore */ }
      activeChatAbort = null;
    }
    set({
      messages: [],
      lastAssistantId: null,
      activity: [],
      proposedActions: [],
      approvalResults: [],
      approvals: [],
      results: [],
      decisions: [],
      selectedResultId: null,
      approvalsError: null,
      lastSeq: 0,
      streamStatus: "idle",
    });
  },

  selectResult: (resultId) => {
    set({ selectedResultId: resultId });
  },

  loadResult: async (resultId) => {
    if (!resultId) return;
    const results = get().results.map((r) =>
      r.resultId === resultId ? { ...r, loading: true, error: null } : r,
    );
    set({ results, selectedResultId: resultId });
    try {
      const data = await request<Record<string, unknown>>(`/api/v1/results/${encodeURIComponent(resultId)}`);
      const updated = get().results.map((r) =>
        r.resultId === resultId
          ? { ...r, loading: false, loaded: true, summary: (data?.summary as Record<string, unknown> | undefined) ?? r.summary ?? null }
          : r,
      );
      set({ results: updated });
    } catch (err) {
      const message = toErrorMessage(err, "Failed to load result");
      const updated = get().results.map((r) =>
        r.resultId === resultId ? { ...r, loading: false, error: message } : r,
      );
      set({ results: updated });
    }
  },

  refreshApprovals: async () => {
    try {
      const res = await request<{ data?: PendingApproval[]; items?: PendingApproval[] }>(
        `/api/v1/approvals/pending?session_id=${encodeURIComponent(get().sessionId)}`,
      );
      const list: PendingApproval[] = Array.isArray(res?.data)
        ? res.data
        : Array.isArray(res?.items)
          ? res.items
          : [];
      set({ approvals: list, approvalsError: null });
    } catch (err) {
      set({ approvalsError: toErrorMessage(err, "Failed to load pending approvals") });
    }
  },

  resolveApproval: async (approvalId, decision) => {
    if (!approvalId) return false;
    const next = get().approvals.map((a) =>
      a.id === approvalId ? { ...a, resolving: decision, error: null } : a,
    );
    set({ approvals: next });
    try {
      await request<{ success: boolean }>(`/api/v1/approvals/${encodeURIComponent(approvalId)}/resolve`, {
        method: "POST",
        body: JSON.stringify({ decision, session_id: get().sessionId }),
      });
      set({
        approvals: get().approvals.filter((a) => a.id !== approvalId),
      });
      return true;
    } catch (err) {
      const message = toErrorMessage(err, "Failed to resolve approval");
      set({
        approvals: get().approvals.map((a) =>
          a.id === approvalId ? { ...a, resolving: undefined, error: message } : a,
        ),
      });
      return false;
    }
  },

  setAutoApprove: async (enabled) => {
    set({ autoApprove: { ...get().autoApprove, loading: true, error: null } });
    try {
      const res = await request<{ enabled: boolean; effective_enabled?: boolean }>(
        "/api/v1/session/auto-approve",
        {
          method: "PUT",
          body: JSON.stringify({ session_id: get().sessionId, enabled }),
        },
      );
      const resolved = typeof res?.effective_enabled === "boolean" ? res.effective_enabled : enabled;
      set({ autoApprove: { enabled: resolved, loading: false, error: null } });
      return true;
    } catch (err) {
      set({
        autoApprove: {
          enabled: get().autoApprove.enabled,
          loading: false,
          error: toErrorMessage(err, "Failed to update auto-approve"),
        },
      });
      return false;
    }
  },

  checkEmergencyStop: async () => {
    try {
      const res = await request<{ active?: boolean; enabled?: boolean; is_active?: boolean }>(
        "/admin/cua/kill-switch",
      );
      const active = !!(res?.active ?? res?.enabled ?? res?.is_active);
      set({ emergencyStop: { ...get().emergencyStop, active, error: null } });
    } catch (err) {
      set({
        emergencyStop: {
          ...get().emergencyStop,
          error: toErrorMessage(err, "Failed to read kill-switch state"),
        },
      });
    }
  },

  activateEmergencyStop: async (reason) => {
    set({
      emergencyStop: { ...get().emergencyStop, activating: true, error: null },
    });
    try {
      await request<{ success: boolean }>("/admin/cua/kill-switch/activate", {
        method: "POST",
        body: JSON.stringify({
          reason: reason || "User-triggered emergency stop from ChatWorkspace",
          scope: "session",
          session_id: get().sessionId,
        }),
      });
      set({
        emergencyStop: { active: true, activating: false, lastResult: "success", error: null },
      });
      get().disconnectSession();
      return true;
    } catch (err) {
      set({
        emergencyStop: {
          ...get().emergencyStop,
          activating: false,
          lastResult: "error",
          error: toErrorMessage(err, "Emergency stop activation failed"),
        },
      });
      return false;
    }
  },
}));