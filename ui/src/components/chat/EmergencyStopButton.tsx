/**
 * EmergencyStopButton — UI reflector for the backend CUA kill-switch.
 *
 * The button performs TWO distinct actions and reports BOTH honestly:
 *
 *   1. LOCAL STREAM ABORT (immediate, client-side):
 *      Calls abortStream() first — cancels the active SSE/fetch stream and
 *      marks all in-progress activity entries as "failed" in the UI.
 *      This always succeeds instantly regardless of server reachability.
 *      NOTE: This does NOT cancel a background Python study — api/studies.py
 *      has no cancel endpoint. A running Python computation continues until
 *      it finishes naturally.
 *
 *   2. SERVER KILL-SWITCH (async, backend-confirmed):
 *      Calls activateEmergencyStop() which POSTs to
 *      POST /admin/cua/kill-switch/activate (agents/life_safety.py file gate).
 *      The CUA Loop will abort on its next action check — this is NOT a
 *      guarantee of immediate cancellation of any already-dispatched study.
 *      Server failure → error is surfaced honestly; "confirmed" is never
 *      shown unless the backend acknowledges the activation.
 *
 * Both results are shown as separate status indicators.
 *
 * Backend contracts (both calls delegated to chatStore.activateEmergencyStop):
 *   GET  /admin/cua/kill-switch          (status check on mount)
 *   POST /admin/cua/kill-switch/activate (activate kill-switch)
 */
import { AlertOctagon, CheckCircle2, Loader2, OctagonX, WifiOff } from "lucide-react";
import { useEffect, useRef } from "react";
import { useChatStore } from "../../store/chatStore";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { cn } from "../../utils/helpers";

export function EmergencyStopButton() {
  const { active, activating, lastResult, error } = useChatStore((s) => s.emergencyStop);
  const activate = useChatStore((s) => s.activateEmergencyStop);
  const checkStatus = useChatStore((s) => s.checkEmergencyStop);

  // Track whether stream was locally aborted (set to true the moment button is pressed,
  // independently of the server outcome).
  const streamAbortedRef = useRef(false);
  const streamAbortedState = useChatStore(
    (s) =>
      s.streamStatus === "idle" ||
      s.streamStatus === "error" ||
      s.streamStatus === "completed",
  );

  // Reflect the backend state on mount (best-effort; backend dictates access).
  useEffect(() => {
    void checkStatus();
  }, [checkStatus]);

  const handleClick = () => {
    streamAbortedRef.current = true;
    void activate("chat_workspace_ui");
  };

  // "Stream locally stopped" is true once the button was pressed AND
  // the streamStatus reflects a non-streaming state.
  const localAbortConfirmed = streamAbortedRef.current && streamAbortedState;

  return (
    <div className="flex flex-col gap-1.5" data-testid="emergency-stop">
      <div className="flex items-center gap-2">
        <Button
          variant={active ? "secondary" : "danger"}
          size="sm"
          loading={activating}
          disabled={active}
          icon={active ? OctagonX : AlertOctagon}
          onClick={handleClick}
          data-testid="emergency-stop-button"
        >
          {active ? "Active" : "Emergency Stop"}
        </Button>
        {active && <Badge variant="danger" dot>Active</Badge>}
      </div>

      {activating && (
        <span className="text-xs text-[var(--text-muted)] inline-flex items-center gap-1">
          <Loader2 className="w-3 h-3 animate-spin" />
          Contacting backend…
        </span>
      )}

      {/* ── Truth 1: Local stream status ── */}
      {localAbortConfirmed && (
        <span
          className="text-xs inline-flex items-center gap-1 text-amber-400"
          data-testid="local-abort-status"
        >
          <CheckCircle2 className="w-3.5 h-3.5" />
          Stream stopped locally (client-side only)
        </span>
      )}

      {/* ── Truth 2: Server kill-switch status ── */}
      {lastResult === "success" && active && (
        <span
          className={cn("text-xs inline-flex items-center gap-1", "text-red-400")}
          data-testid="server-stop-status"
        >
          <CheckCircle2 className="w-3.5 h-3.5" />
          Kill-switch confirmed by server — CUA Loop will abort on next check
        </span>
      )}
      {lastResult === "success" && !active && (
        <span
          className="text-xs inline-flex items-center gap-1 text-green-400"
          data-testid="server-stop-status"
        >
          <CheckCircle2 className="w-3.5 h-3.5" />
          Backend acknowledged the stop request
        </span>
      )}
      {error && (
        <span
          className="text-xs inline-flex items-center gap-1 text-red-400"
          data-testid="server-stop-error"
        >
          <WifiOff className="w-3.5 h-3.5" />
          Server not confirmed: {error}
        </span>
      )}
    </div>
  );
}