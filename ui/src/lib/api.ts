/**
 * Ahmed etap Platform — API Client
 * Centralized API layer for all backend communication.
 *
 * Demo Mode behavior (v2.1.1+ — security-hardened):
 * - In DEVELOPMENT (import.meta.env.DEV): auto-fallback to demo data on
 *   network errors, so the UI stays explorable without a running backend.
 * - In PRODUCTION (import.meta.env.PROD): NO silent fallback. A network
 *   error throws a real error so the user sees that the backend is down,
 *   rather than being misled into thinking canned demo data is live.
 *   Demo Mode is only entered if VITE_API_URL is empty (static-site deploy
 *   on Vercel/HF Spaces without backend).
 *
 * Components can check `isDemoMode()` to render a banner informing the
 * user that they are viewing canned data.
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || ''
const DEMO_MODE_TIMEOUT_MS = 1500

// ---------- Demo Mode Detection ----------
// demoMode is initially true ONLY when no API URL is configured (static-site
// deploy). In production with a real backend, demoMode stays false and
// network errors propagate instead of silently switching to demo data.
let demoMode = !API_BASE_URL

function sleep(ms: number) { return new Promise(r => setTimeout(r, ms)) }

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  if (demoMode) {
    return demoResponse<T>(path, options)
  }

  const url = `${API_BASE_URL}${path}`
  const token = localStorage.getItem('authToken')

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options?.headers as Record<string, string>),
  }

  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  try {
    const response = await fetch(url, {
      ...options,
      headers,
      signal: options?.signal ?? AbortSignal.timeout(8000),
    })

    if (!response.ok) {
      const text = await response.text().catch(() => 'Unknown error')
      throw new Error(`API ${response.status}: ${text}`)
    }

    return response.json()
  } catch (err) {
    // SECURITY (v2.1.1): only auto-fallback to demo mode in DEVELOPMENT.
    // In production, surface the network error so the user/QA notices the
    // backend is down. Silent fallback in prod was a security smell because
    // operators could miss backend outages.
    if (
      err instanceof TypeError &&
      err.message.includes('fetch') &&
      import.meta.env.DEV  // Vite injects this; true only in `vite dev`
    ) {
      console.warn(
        '[api] Network error in development — falling back to demo mode. ' +
        'This will NOT happen in production (import.meta.env.PROD).'
      )
      demoMode = true
      return demoResponse<T>(path, options)
    }
    throw err
  }
}

// ---------- Demo Data ----------
const DEMO_AGENTS = [
  { id: 'power-system-coordinator-agent', name: 'Power System Coordinator', description: 'Orchestrates multi-agent engineering workflows', capabilities: ['load_flow', 'short_circuit', 'protection', 'arc_flash'], model: 'claude-3-5-sonnet', provider: 'Anthropic' },
  { id: 'load-flow-agent', name: 'Load Flow Agent', description: 'Newton-Raphson power flow analysis', capabilities: ['load_flow', 'voltage_profile', 'power_loss'], model: 'gpt-4o', provider: 'OpenAI' },
  { id: 'short-circuit-agent', name: 'Short Circuit Agent', description: 'IEC 60909 fault analysis', capabilities: ['short_circuit', 'fault_current'], model: 'claude-3-5-sonnet', provider: 'Anthropic' },
  { id: 'arcflash-agent', name: 'Arc Flash Agent', description: 'IEEE 1584 incident energy calculation', capabilities: ['arc_flash', 'ppe_category'], model: 'gpt-4o', provider: 'OpenAI' },
  { id: 'protection-agent', name: 'Protection Agent', description: 'IEC 60255 relay coordination', capabilities: ['protection_coordination', 'relay_curves'], model: 'glm-4', provider: 'ZhipuAI' },
  { id: 'harmonic-agent', name: 'Harmonic Agent', description: 'THD/TDD analysis per IEEE 519', capabilities: ['harmonic_analysis', 'thd_calc'], model: 'qwen-max', provider: 'Alibaba' },
  { id: 'motorstarting-agent', name: 'Motor Starting Agent', description: 'Voltage drop & torque analysis', capabilities: ['motor_starting'], model: 'deepseek-coder', provider: 'DeepSeek' },
  { id: 'etap-expert-agent', name: 'ETAP Expert Agent', description: 'ETAP integration specialist', capabilities: ['etap_com', 'study_execution'], model: 'claude-3-5-sonnet', provider: 'Anthropic' },
]

const DEMO_STUDIES_HISTORY = [
  { id: 's1', study_type: 'load_flow', status: 'completed', timestamp: '2026-06-10T14:32:00Z', duration_ms: 245 },
  { id: 's2', study_type: 'short_circuit', status: 'completed', timestamp: '2026-06-09T11:20:00Z', duration_ms: 156 },
  { id: 's3', study_type: 'arc_flash', status: 'completed', timestamp: '2026-06-08T09:15:00Z', duration_ms: 312 },
  { id: 's4', study_type: 'harmonic_analysis', status: 'dry_run', timestamp: '2026-06-07T16:45:00Z', duration_ms: 42 },
]

const DEMO_AUDIT = [
  { timestamp: '2026-06-10T14:32:00Z', method: 'POST', path: '/api/v1/studies/run', statusCode: 200, action: 'run_study', latencyMs: 245 },
  { timestamp: '2026-06-10T14:30:00Z', method: 'GET', path: '/api/v1/agents', statusCode: 200, action: 'list_agents', latencyMs: 12 },
  { timestamp: '2026-06-10T14:25:00Z', method: 'GET', path: '/health', statusCode: 200, action: 'health_check', latencyMs: 3 },
  { timestamp: '2026-06-09T11:20:00Z', method: 'POST', path: '/api/v1/studies/run', statusCode: 200, action: 'run_study', latencyMs: 156 },
  { timestamp: '2026-06-09T11:18:00Z', method: 'GET', path: '/api/v1/studies', statusCode: 200, action: 'list_studies', latencyMs: 18 },
]

const DEMO_METRICS = {
  api: { GET: 156, POST: 42, DELETE: 3, PUT: 8 },
  providers: {
    Anthropic: { count: 89, avgMs: 412, failureRate: 0.012 },
    OpenAI: { count: 67, avgMs: 538, failureRate: 0.018 },
    ZhipuAI: { count: 23, avgMs: 612, failureRate: 0.022 },
  },
  perKey: { 'sk-default': 89, 'sk-backup': 12 },
  circuits: { 'provider-anthropic': { state: 'closed', consecutiveFailures: 0 }, 'provider-openai': { state: 'closed', consecutiveFailures: 0 } },
}

async function demoResponse<T>(path: string, options?: RequestInit): Promise<T> {  // NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
  await sleep(DEMO_MODE_TIMEOUT_MS * (0.3 + Math.random() * 0.4))  // NOSONAR — S2245: PRNG used for non-crypto purposes (UI)

  const method = options?.method || 'GET'

  // Health
  if (path === '/health') {
    return {
      ok: true,
      status: 'healthy',
      version: '2.1.0-demo',
      uptime: 86400,
      engineeringService: { configured: true, healthy: true, latencyMs: 12 },
      providers: DEMO_METRICS.providers,
      timestamp: new Date().toISOString(),
    } as unknown as T
  }

  // Agents
  if (path === '/api/v1/agents') {
    return { agents: DEMO_AGENTS } as unknown as T
  }

  // Studies
  if (path === '/api/v1/studies' && method === 'GET') {
    return DEMO_STUDIES_HISTORY as unknown as T
  }
  if (path === '/api/v1/studies/run' && method === 'POST') {
    const body = options?.body ? JSON.parse(options.body as string) : {}
    const isDryRun = body.dry_run
    return {
      status: isDryRun ? 'dry_run' : 'completed',
      study_type: body.study_type || 'load_flow',
      data: {
        voltage_profile: [{ bus: 1, voltage_pu: 1.05 }, { bus: 2, voltage_pu: 1.0 }, { bus: 3, voltage_pu: 0.98 }],  // NOSONAR — S7748: number literal trailing zero; cosmetic
        power_flow: [{ from: 1, to: 2, mw: 5.2, mvar: 1.1 }, { from: 2, to: 3, mw: 4.8, mvar: 0.9 }],
        losses: { total_mw: 0.12, total_mvar: 0.34 },
      },
      message: isDryRun ? 'Dry-run validation passed' : 'Study completed successfully',
      duration_ms: isDryRun ? 12 : 245,
      timestamp: new Date().toISOString(),
    } as unknown as T
  }

  // System validate
  if (path === '/api/v1/system/validate' && method === 'POST') {
    return { valid: true, errors: [] } as unknown as T
  }

  // Metrics
  if (path === '/metrics') {
    return DEMO_METRICS as unknown as T
  }

  // Agent chat
  if (path === '/api/v1/agents/chat' && method === 'POST') {
    const body = options?.body ? JSON.parse(options.body as string) : {}
    const agentName = DEMO_AGENTS.find(a => a.id === body.agentId)?.name || 'Assistant'
    const userMsg = (body.message || '').toLowerCase()
    let response = ''
    if (userMsg.includes('load flow') || userMsg.includes('newton')) {
      response = `## Load Flow Analysis\n\nI can help you with Newton-Raphson power flow. Here's a quick example:\n\n\`\`\`python\nimport numpy as np\n\n# Newton-Raphson load flow\ndef load_flow(Ybus, S_spec, V0, max_iter=20, tol=1e-6):\n    V = V0.copy()\n    for i in range(max_iter):\n        S_calc = V * np.conj(Ybus @ V)\n        mismatch = S_spec - S_calc\n        if np.max(np.abs(mismatch)) < tol:\n            return V, i\n        # Update Jacobian and solve\n        # J = [[dP/dθ, dP/dV], [dQ/dθ, dQ/dV]]\n        # ... (full implementation)\n    return V, max_iter\n\`\`\`\n\nWould you like me to run this on your system model?`
    } else if (userMsg.includes('arc flash')) {
      response = `## Arc Flash Analysis\n\nPer IEEE 1584-2018, the incident energy at the working distance is:\n\n\`\`\`\nE = 4.182 × Cf × Ein × (t / 0.2) × (1/X)\n\`\`\`\n\nWhere:\n- **Cf** = calculation factor (1.0 for open, 0.97 for box)\n- **Ein** = intermediate incident energy\n- **t** = arcing time (seconds)\n- **X** = distance exponent\n\nFor a 480V system with 30kA bolted fault and 610mm working distance, expect around 8-12 cal/cm² (PPE Category 3).`
    } else if (userMsg.includes('short circuit')) {
      response = `## Short Circuit Analysis\n\nIEC 60909 fault calculation:\n\nFor a three-phase fault at bus k:\n\n\`\`\`\nI''k = c × Un / (√3 × Zk)\n\`\`\`\n\nWhere:\n- **c** = voltage factor (1.05 or 1.10)\n- **Un** = nominal voltage\n- **Zk** = equivalent impedance at fault location\n\nI can run this for your network topology. Just share the system model.`
    } else if (userMsg.includes('python') || userMsg.includes('script')) {
      response = `Sure! Here's a Python helper for power system analysis:\n\n\`\`\`python\nimport pandas as pd\n\ndef analyze_system(model):\n    \"\"\"Run comprehensive power system analysis.\"\"\"\n    results = {}\n    results['load_flow'] = run_load_flow(model)\n    results['short_circuit'] = run_short_circuit(model)\n    results['arc_flash'] = run_arc_flash(model)\n    return pd.DataFrame(results)\n\ndef run_load_flow(model):\n    # ... Newton-Raphson implementation\n    pass\n\`\`\`\n\nLet me know if you want me to extend this.`
    } else if (userMsg.includes('relay') || userMsg.includes('coordination')) {
      response = `## Protective Relay Coordination\n\nPer IEC 60255, the inverse-time characteristic is:\n\n\`\`\`\nt = TMS × k / ((I/Is)^α - 1)\n\`\`\`\n\nFor standard inverse (SI): k=0.14, α=0.02\nFor very inverse (VI): k=13.5, α=1.0\nFor extremely inverse (EI): k=80.0, α=2.0\n\nSelectivity margin should be ≥0.3s between upstream and downstream.`
    } else {
      response = `Hello! I'm ${agentName}. I can help you with:\n\n- **Load Flow** — Newton-Raphson power flow\n- **Short Circuit** — IEC 60909 fault analysis\n- **Arc Flash** — IEEE 1584 incident energy\n- **Harmonics** — THD/TDD per IEEE 519\n- **Protection** — IEC 60255 coordination\n- **Motor Starting** — Voltage drop analysis\n\nJust ask me a question or describe what you want to compute.`
    }
    return { response, agentId: body.agentId || 'default' } as unknown as T
  }

  // Audit logs
  if (path === '/api/v1/audit') {
    return DEMO_AUDIT as unknown as T
  }

  // Guard review
  if (path === '/api/v1/guards/review' && method === 'POST') {
    // QUALITY v2.1.1: body was unused — remove the dead assignment
    return {
      success: true,
      guard_results: {
        code_guard: {
          guard_name: 'Code Quality Guard',
          mode: 'static',
          passed: true,
          must_fix: 0,
          should_fix: 1,
          worth_noting: 2,
          violations: [
            { rule_id: 'C003', rule_name: 'Function Too Long', severity: 'should_fix', description: 'Function exceeds 50 lines', location: 'line 42', suggestion: 'Consider extracting helper functions', evidence: '58 lines' },
            { rule_id: 'C008', rule_name: 'Magic Number', severity: 'worth_noting', description: 'Numeric literal without named constant', location: 'line 17', suggestion: 'Define as constant', evidence: '0.0001' },
            { rule_id: 'C012', rule_name: 'Missing Docstring', severity: 'worth_noting', description: 'Public function lacks documentation', location: 'line 8', suggestion: 'Add a docstring', evidence: 'def calculate(...)' },
          ],
        },
      },
      all_passed: false,
      must_fix_total: 0,
      should_fix_total: 1,
      worth_noting_total: 2,
      trace_id: 'demo-trace-' + Date.now(),
    } as unknown as T
  }

  // Guard info
  if (path === '/api/v1/guards/info') {
    return {
      success: true,
      data: {
        guards: {
          code_guard: { name: 'Code Quality Guard', description: '23 clean-code rules', rules_checked: 23 },
          test_guard: { name: 'Test Quality Guard', description: '9 test rules', rules_checked: 9 },
          docs_guard: { name: 'Docs Quality Guard', description: '10 documentation rules', rules_checked: 10 },
        },
        severity_levels: {
          must_fix: 'Blocking — must be fixed before merge',
          should_fix: 'Important — should be fixed soon',
          worth_noting: 'Suggestions for improvement',
        },
        source: 'AI failure mode research + clean-code best practices',
      },
    } as unknown as T
  }

  // Vision keys (Settings)
  if (path === '/api/v1/settings/keys') {
    return {
      success: true,
      data: {
        openai: { provider: 'openai', api_key_masked: 'sk-***...***', api_key_set: false, base_url: null, model_name: 'gpt-4o', is_active: false, created_at: null, updated_at: null },
        anthropic: { provider: 'anthropic', api_key_masked: 'sk-ant-***', api_key_set: false, base_url: null, model_name: 'claude-3-5-sonnet', is_active: false, created_at: null, updated_at: null },
        gemini: { provider: 'gemini', api_key_masked: 'AI***', api_key_set: false, base_url: null, model_name: 'gemini-1.5-pro', is_active: false, created_at: null, updated_at: null },
      },
      providers: ['openai', 'anthropic', 'gemini', 'qwen', 'glm', 'nvidia', 'deepseek'],
    } as unknown as T
  }

  // Default fallback
  return { success: true } as unknown as T
}

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
          { bus_id: 2, bus_type: 'pv', voltage_magnitude: 1.0 },  // NOSONAR — S7748: number literal trailing zero; cosmetic
          { bus_id: 3, bus_type: 'pq', load_power_real: 1.0, load_power_reactive: 0.3 },  // NOSONAR — S7748: number literal trailing zero; cosmetic
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

// ---------- Guard Skills API ----------

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

// ---------- Vision API Keys (Settings) ----------

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

// ---------- Demo Mode Helpers ----------

export function isDemoMode(): boolean {
  return demoMode
}

export function setDemoMode(enabled: boolean): void {
  demoMode = enabled
}
