/**
 * AhmedETAP Platform — API Client
 *
 * REAL backend only. No demo mode, no mock data, no silent fallback.
 *
 * The API base URL is resolved centrally in ./api-config.ts.
 * See that file for configuration options (VITE_API_URL env var).
 */

import { API_BASE_URL } from './api-config'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${path}`
  const token = localStorage.getItem('authToken')

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options?.headers as Record<string, string> | undefined),
  }

  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const response = await fetch(url, {
    ...options,
    headers,
    signal: options?.signal ?? AbortSignal.timeout(15000),
  })

  if (!response.ok) {
    // Try to extract a structured error from the backend
    let detail = 'Unknown error'
    try {
      const body = await response.json()
      detail = body.detail || body.message || JSON.stringify(body)
    } catch {
      try {
        detail = await response.text()
      } catch {
        detail = `HTTP ${response.status} ${response.statusText}`
      }
    }
    throw new Error(`API ${response.status}: ${detail}`)
  }

  // 204 No Content
  if (response.status === 204) {
    return undefined as unknown as T
  }

  return response.json() as Promise<T>
}

// ============ Types ============

export interface HealthResponse {
  ok?: boolean
  status: string
  version: string
  uptime?: number
  uptime_seconds?: number
  agents?: number
  etap_manuals?: number
  zenon_guides?: number
  standards?: number
  engineeringService?: { configured: boolean; healthy: boolean; latencyMs?: number }
  providers?: Record<string, unknown>
  timestamp?: string
}

export interface AgentMeta {
  id: string
  name: string
  description: string
  capabilities: string[]
  model: string
  provider: string
}

export interface StudyResult {
  study_type: string
  status: string
  results?: Record<string, unknown>
  errors?: string[]
  warnings?: string[]
  duration_ms?: number
  timestamp?: string
}

export interface MetricsResponse {
  requests_total: number
  requests_per_minute: number
  agents_active: number
  studies_run: number
  providers: Record<string, { requests: number; errors: number; latency_ms: number }>
  timestamp: string
}

export interface AuditEntry {
  timestamp: string
  method: string
  path: string
  statusCode: number
  action: string
  latencyMs?: number
  userId?: string
}

// ============ API functions ============

export async function fetchHealth(): Promise<HealthResponse> {
  return request<HealthResponse>('/health')
}

export async function fetchAgents(): Promise<AgentMeta[]> {
  const data = await request<{ agents: AgentMeta[] } | AgentMeta[]>('/api/v1/agents')
  return Array.isArray(data) ? data : data.agents ?? []
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
      system: params.system ?? {
        base_mva: 100,
        buses: [
          { bus_id: 1, bus_type: 'slack', voltage_magnitude: 1.05 },
          { bus_id: 2, bus_type: 'pv', voltage_magnitude: 1.0 },
          { bus_id: 3, bus_type: 'pq', load_power_real: 1, load_power_reactive: 0.3 },
        ],
        lines: [
          { line_id: 1, from_bus_id: 1, to_bus_id: 2, r1: 0.01, x1: 0.05 },
          { line_id: 2, from_bus_id: 2, to_bus_id: 3, r1: 0.015, x1: 0.06 },
        ],
      },
    }),
  })
}

export async function fetchStudies(): Promise<unknown[]> {
  return request<unknown[]>('/api/v1/studies')
}

export async function validateSystem(): Promise<{ valid: boolean; errors?: string[] }> {
  return request<{ valid: boolean; errors?: string[] }>('/api/v1/system/validate', {
    method: 'POST',
  })
}

export async function fetchMetrics(): Promise<MetricsResponse> {
  return request<MetricsResponse>('/metrics')
}

export async function chatWithAgent(
  agentId: string,
  message: string
): Promise<{ response: string; agentId: string }> {
  return request<{ response: string; agentId: string }>('/api/v1/agents/chat', {
    method: 'POST',
    body: JSON.stringify({ agentId, message }),
  })
}

export async function fetchAuditLogs(): Promise<AuditEntry[]> {
  return request<AuditEntry[]>('/api/v1/audit')
}

// ============ Guard Skills API ============

export interface GuardViolation {
  rule_id: string
  rule_name: string
  severity: 'must_fix' | 'should_fix' | 'worth_noting'
  description: string
  location: string
  suggestion: string
  evidence: string
}

export interface GuardReviewResult {
  success: boolean
  guard_results: Record<string, {
    guard_name: string
    mode: string
    passed: boolean
    must_fix: number
    should_fix: number
    worth_noting: number
    violations: GuardViolation[]
  }>
  all_passed: boolean
  must_fix_total: number
  should_fix_total: number
  worth_noting_total: number
  trace_id: string
}

export interface GuardInfo {
  guards: Record<string, {
    name: string
    description: string
    rules_checked: number
    failure_modes?: Array<{
      id: string
      name: string
      severity: string
      description: string
      research_source: string
    }>
  }>
  severity_levels: Record<string, string>
  source: string
}

export async function guardReview(
  source: string,
  guardType: string = 'all',
  language: string = 'python'
): Promise<GuardReviewResult> {
  return request<GuardReviewResult>('/api/v1/guards/review', {
    method: 'POST',
    body: JSON.stringify({ source, guard_type: guardType, language }),
  })
}

export async function fetchGuardInfo(): Promise<GuardInfo> {
  const data = await request<{ success: boolean; data: GuardInfo }>('/api/v1/guards/info')
  return data.data
}

// ============ Vision API Keys (Settings) ============

export interface VisionKeyConfig {
  provider: string
  api_key_masked: string
  api_key_set: boolean
  base_url: string | null
  model_name: string | null
  is_active: boolean
  created_at: string | null
  updated_at: string | null
}

export interface VisionKeysResponse {
  success: boolean
  data: Record<string, VisionKeyConfig>
  providers: string[]
}

export interface VisionKeyTestResult {
  success: boolean
  message: string
  base_url?: string
  model?: string
  sample_models?: string[]
}

export async function fetchVisionKeys(): Promise<VisionKeysResponse> {
  return request<VisionKeysResponse>('/api/v1/settings/keys')
}

export async function saveVisionKey(
  provider: string,
  apiKey: string,
  baseUrl?: string,
  modelName?: string,
  isActive: boolean = true
): Promise<{ success: boolean; data: VisionKeyConfig | null; message: string }> {
  const params = new URLSearchParams({
    api_key: apiKey,
    is_active: String(isActive),
  })
  if (baseUrl) params.set('base_url', baseUrl)
  if (modelName) params.set('model_name', modelName)

  return request(`/api/v1/settings/keys/${provider}?${params.toString()}`, {
    method: 'POST',
  })
}

export async function deleteVisionKey(provider: string): Promise<{ success: boolean; message: string }> {
  return request(`/api/v1/settings/keys/${provider}`, {
    method: 'DELETE',
  })
}

export async function testVisionKey(provider: string): Promise<{ success: boolean; data: VisionKeyTestResult }> {
  return request(`/api/v1/settings/keys/${provider}/test`, {
    method: 'POST',
  })
}

// ============ Backwards-compat stubs (removed) ============
//
// The following functions were demo-mode helpers and have been REMOVED:
//   - isDemoMode()  → always returns false now; components should not gate
//                     behavior on demo mode because there is no demo mode.
//   - setDemoMode() → no-op removed; there is no demo mode to set.
//
// Any component that imported these must be updated to handle real API
// errors directly (try/catch + show error to user).
