/**
 * P6 feature flag gateway for `chat_first_ui`.
 *
 * Uses existing project conventions only:
 *  - backend flag list   : GET /api/v1/feature-flags (api.fetchFeatureFlags)
 *  - build-time override : VITE_CHAT_FIRST_UI (Vite env convention, default OFF)
 *
 * Default is OFF (fail-closed): any error opening the flag list or a missing /
 * disabled `chat_first_ui` entry keeps the legacy UI. The backend remains the
 * authority for flags and rollout — the frontend only mirrors the effective
 * state it receives.
 */
import { useEffect, useState } from "react";
import { fetchFeatureFlags } from "./api";

export const CHAT_FIRST_UI_KEY = "chat_first_ui";

function isEnvOverride(): boolean {
  const env = (import.meta as unknown as { env?: Record<string, string | undefined> }).env;
  return env?.VITE_CHAT_FIRST_UI === "true";
}

/** Resolve the effective ChatWorkspace state. FAIL CLOSED → OFF by default. */
export async function isChatFirstUiEnabled(): Promise<boolean> {
  if (isEnvOverride()) return true;
  try {
    const res = await fetchFeatureFlags();
    const flag = (res?.data ?? []).find((f) => f.key === CHAT_FIRST_UI_KEY);
    return flag?.effective_enabled === true;
  } catch {
    // Offline, router not mounted, malformed payload — always keep legacy UI.
    return false;
  }
}

export interface ChatFirstUiState {
  readonly ready: boolean;
  readonly enabled: boolean;
  /** Session-scoped exit that restores the legacy UI until the next load. */
  readonly exitToLegacy: () => void;
}

export function useChatFirstUi(): ChatFirstUiState {
  const [resolved, setResolved] = useState<boolean | null>(null);
  const [optedOut, setOptedOut] = useState(false);

  useEffect(() => {
    let alive = true;
    void isChatFirstUiEnabled().then((enabled) => {
      if (alive) setResolved(enabled);
    });
    return () => {
      alive = false;
    };
  }, []);

  return {
    ready: resolved !== null,
    enabled: resolved === true && !optedOut,
    exitToLegacy: () => setOptedOut(true),
  };
}