import { useCallback, useEffect, useState } from "react";
import { API_BASE_URL } from "../lib/api-config";

export type ServerStatus = "online" | "offline" | "checking";

export interface TelemetryState {
  serverStatus: ServerStatus;
  latency: number | null;
  activeAgents: number | null;
  backendVersion: string | null;
}

export function useHealthCheck(pollIntervalMs: number = 5000) {
  const [telemetry, setTelemetry] = useState<TelemetryState>({
    serverStatus: "checking",
    latency: null,
    activeAgents: null,
    backendVersion: null,
  });

  const checkHealth = useCallback(async () => {
    const start = performance.now();
    try {
      const res = await fetch(`${API_BASE_URL}/health`, {
        signal: AbortSignal.timeout(3000),
      });
      const end = performance.now();
      if (res.ok) {
        let version: string | null = null;
        let agentCount: number | null = null;

        try {
          const infoRes = await fetch(`${API_BASE_URL}/info`, {
            signal: AbortSignal.timeout(3000),
          });
          if (infoRes.ok) {
            const data = await infoRes.json();
            if (data.version) version = data.version;
            if (data.agent_count) agentCount = data.agent_count;
          }
        } catch {
          // Keep defaults if info fails
        }

        setTelemetry({
          serverStatus: "online",
          latency: Math.round(end - start),
          activeAgents: agentCount,
          backendVersion: version,
        });
      } else {
        setTelemetry({
          serverStatus: "offline",
          latency: null,
          activeAgents: null,
          backendVersion: null,
        });
      }
    } catch {
      setTelemetry({
        serverStatus: "offline",
        latency: null,
        activeAgents: null,
        backendVersion: null,
      });
    }
  }, []);

  useEffect(() => {
    checkHealth();
    const timer = setInterval(checkHealth, pollIntervalMs);
    return () => clearInterval(timer);
  }, [checkHealth, pollIntervalMs]);

  return {
    ...telemetry,
    refetch: checkHealth,
  };
}
