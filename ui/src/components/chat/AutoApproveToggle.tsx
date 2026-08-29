/**
 * AutoApproveToggle — per-session auto-approval reflector.
 *
 * The UI NEVER grants approval itself. This toggle only mirrors the backend
 * decision (PUT /api/v1/session/auto-approve) and demands an explicit
 * confirmation before changing state. A disabled state while the backend
 * request is in flight prevents stale/local flips.
 */
import { AlertTriangle, Loader2, ShieldAlert } from "lucide-react";
import { useCallback, useState } from "react";
import { useChatStore } from "../../store/chatStore";
import { Button } from "../ui/Button";
import { Modal } from "../ui/Modal";
import { Toggle } from "../ui/Toggle";

export function AutoApproveToggle() {
  const { enabled, loading, error } = useChatStore((s) => s.autoApprove);
  const setAutoApprove = useChatStore((s) => s.setAutoApprove);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [pendingValue, setPendingValue] = useState(false);

  const requestChange = useCallback(
    (next: boolean) => {
      setPendingValue(next);
      setConfirmOpen(true);
    },
    [],
  );

  const confirm = useCallback(async () => {
    setConfirmOpen(false);
    await setAutoApprove(pendingValue);
  }, [pendingValue, setAutoApprove]);

  return (
    <div className="flex flex-col gap-1.5" data-testid="auto-approve-toggle">
      <div className="flex items-center gap-2">
        <Toggle
          checked={enabled}
          onChange={requestChange}
          disabled={loading}
          label="Auto-approve session actions"
          description={enabled ? "Backend will auto-approve eligible actions." : "Each action requires explicit approval."}
        />
        {loading && <Loader2 className="w-4 h-4 animate-spin text-[var(--text-muted)]" aria-label="Updating" />}
      </div>

      {error && (
        <p className="text-xs text-red-400 inline-flex items-center gap-1">
          <AlertTriangle className="w-3.5 h-3.5" />
          {error}
        </p>
      )}

      <Modal
        open={confirmOpen}
        onClose={() => setConfirmOpen(false)}
        title="Confirm auto-approve change"
        subtitle={pendingValue ? "Enabling" : "Disabling"}
        footer={
          <>
            <Button variant="secondary" onClick={() => setConfirmOpen(false)}>
              Cancel
            </Button>
            <Button
              variant={pendingValue ? "danger" : "secondary"}
              icon={ShieldAlert}
              onClick={confirm}
              data-testid="confirm-auto-approve"
            >
              Confirm
            </Button>
          </>
        }
      >
        <p className="text-sm text-[var(--text-secondary)]">
          {pendingValue
            ? "Enabling auto-approve delegates eligibility decisions to the backend approval gateway. No approval will be granted client-side."
            : "Disabling auto-approve means every action will require explicit approval again."}
        </p>
      </Modal>
    </div>
  );
}