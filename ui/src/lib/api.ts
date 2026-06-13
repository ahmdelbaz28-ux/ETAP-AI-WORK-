/**
 * ETAP AI Platform — API Client
 * Centralized API layer for all backend communication.
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// ---------- Types ----------

export interface HealthResponse {
  ok: boolean
  status: string
  version?: string
  uptime?: number
  engineeringService?: {
    configured: boolean
    healthy: boolean
    latencyMs?: number
  }
  providers?: Record<string, ProviderMetrics>
  timestamp?: string
  [key: string]: unknown
}

export interface ProviderMetrics {
  count: number
  avgMs: number
  failureRate: number
}

export interface MetricsResponse {
  api: Record<string, number>
  providers: Record<string, ProviderMetrics>
  perKey: Record<string, number>
  circuits: Record<string, { state: string; consecutiveFailures: number }>
}

export interface AuditEntry {
  timestamp: string
  method: string
  path: string
  statusCode: number
  action: string
  latencyMs?: number
}

export interface AgentMeta {
  id: string
  name: string
  description?: string
  capabilities: string[]
  model?: string
  provider?: string
}

export interface StudyResult {
  status: 'completed' | 'dry_run' | 'failed' | 'running'
  study_type: string
  data?: Record<string, unknown>
  message?: string
  duration_ms?: number
  timestamp?: string
  [key: string]: unknown
}

// ---------- Helpers ----------

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${path}`
  const token = localStorage.getItem('authToken')

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options?.headers as Record<string, string>),
  }

  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const response = await fetch(url, {
    ...options,
    headers,
    signal: options?.signal ?? AbortSignal.timeout(30000),
  })

  if (!response.ok) {
    const text = await response.text().catch(() => 'Unknown error')
    throw new Error(`API ${response.status}: ${text}`)
  }

  return response.json()
}

// ---------- API Functions ----------

export async function fetchHealth(): Promise<HealthResponse> {
  return request<HealthResponse>('/health')
}

export async function fetchAgents(): Promise<AgentMeta[]> {
  try {
    const data = await request<{ agents: AgentMeta[] } | AgentMeta[]>('/api/v1/agents')
    return Array.isArray(data) ? data : data.agents ?? []
  } catch {
    return []
  }
}

export async function runStudy(
  studyType: string,
  params: Record<string, unknown>,
  dryRun = false
): Promise<StudyResult> {
  return request<StudyResult>('/api/v1/studies/run', {
    method: 'POST',
    body: JSON.stringify({
      study_type: studyType,
      params,
      dry_run: dryRun,
      system: {
        base_mva: 100,
        buses: [
          { bus_id: 1, bus_type: 'slack', voltage_magnitude: 1.05 },
          { bus_id: 2, bus_type: 'pv', voltage_magnitude: 1.0 },
          { bus_id: 3, bus_type: 'pq', load_power_real: 1.0, load_power_reactive: 0.3 },
        ],
        lines: [
          { line_id: 1, from_bus_id: 1, to_bus_id: 2, r1: 0.01, x1: 0.05 },
          { line_id: 2, from_bus_id: 2, to_bus_id: 3, r1: 0.015, x1: 0.06 },
        ],
      },
    }),
  })
}

export async function fetchStudies() {
  try {
    return await request<unknown[]>('/api/v1/studies')
  } catch {
    return []
  }
}

export async function validateSystem() {
  return request<{ valid: boolean; errors?: string[] }>('/api/v1/system/validate', {
    method: 'POST',
  })
}

export async function fetchMetrics(): Promise<MetricsResponse> {
  return request<MetricsResponse>('/metrics')
}

export async function chatWithAgent(agentId: string, message: string): Promise<{ response: string; agentId: string }> {
  return request<{ response: string; agentId: string }>('/api/v1/agents/chat', {
    method: 'POST',
    body: JSON.stringify({ agentId, message }),
  })
}

export async function fetchAuditLogs(): Promise<AuditEntry[]> {
  try {
    return await request<AuditEntry[]>('/api/v1/audit')
  } catch {
    return []
  }
}
