/**
 * EmergencyStopButton — UI reflector for the backend CUA kill-switch.
 *
 * The button calls the EXISTING backend contract:
 *   GET  /admin/cua/kill-switch          (status)
 *   POST /admin/cua/kill-switch/activate (activate)
 *
 * It never claims a client-side cancellation stopped anything — success is
 * only reported after the backend acknowledges activation.
 */
import { AlertOctagon, CheckCircle2, Loader2, OctagonX } from "lucide-react";
import { useEffect } from "react";
import { useChatStore } from "../../store/chatStore";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { cn } from "../../utils/helpers";

export function EmergencyStopButton() {
  const { active, activating, lastResult, error } = useChatStore((s) => s.emergencyStop);
  const activate = useChatStore((s) => s.activateEmergencyStop);
  const checkStatus = useChatStore((s) => s.checkEmergencyStop);

  // Reflect the backend state on mount (best-effort; backend dictates access).
  useEffect(() => {
    void checkStatus();
  }, [checkStatus]);

  return (
    <div className="flex flex-col gap-1.5" data-testid="emergency-stop">
      <div className="flex items-center gap-2">
        <Button
          variant={active ? "secondary" : "danger"}
          size="sm"
          loading={activating}
          disabled={active}
          icon={active ? OctagonX : AlertOctagon}
          onClick={() => void activate("chat_workspace_ui")}
          data-testid="emergency-stop-button"
        >
          {active ? "Active" : "Emergency Stop"}
        </Button>
        {active && <Badge variant="danger" dot>Active</Badge>}
        {lastResult === "success" && !active && (
          <Badge variant="success" dot>Confirmed by backend</Badge>
        )}
      </div>

      {activating && (
        <span className="text-xs text-[var(--text-muted)] inline-flex items-center gap-1">
          <Loader2 className="w-3 h-3 animate-spin" />
          Contacting backend…
        </span>
      )}
      {lastResult === "success" && (
        <span className={cn("text-xs inline-flex items-center gap-1", active ? "text-red-400" : "text-green-400")}>
          <CheckCircle2 className="w-3.5 h-3.5" />
          {active ? "Emergency stop activated by backend." : "Backend acknowledged the stop request."}
        </span>
      )}
      {error && <span className="text-xs text-red-400">{error}</span>}
    </div>
  );
}