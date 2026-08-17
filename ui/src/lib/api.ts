// UI components are intentionally complex for feature-rich DX
/**
 * AhmedETAP Platform — API Client
 *
 * REAL backend only. No demo mode, no mock data, no silent fallback.
 *
 * The API base URL is resolved centrally in ./api-config.ts.
 * See that file for configuration options (VITE_API_URL env var).
 */

import { authHeaders } from "./admin-fetch";
import { API_BASE_URL, getCachedSettings } from "./api-config";
import { getAuthToken } from "./tokenStorage";

// Forward user's active provider key/model to backend dynamically.
// Extracted to a helper to keep request() below SonarCloud's cognitive
// complexity threshold (S3776).
function buildProviderHeaders(settings: Record<string, string>): Record<string, string> {
  const headers: Record<string, string> = {};
  const activeProviderId = settings.PROVIDER_ACTIVE_PROVIDER_ID || "openai";
  headers["x-active-provider"] = activeProviderId;

  if (activeProviderId === "custom_openai") {
    if (settings.CUSTOM_OPENAI_API_KEY) headers["x-active-key"] = settings.CUSTOM_OPENAI_API_KEY;
    if (settings.CUSTOM_OPENAI_BASE_URL) headers["x-active-url"] = settings.CUSTOM_OPENAI_BASE_URL;
    if (settings.CUSTOM_OPENAI_MODEL_ID)
      headers["x-active-model"] = settings.CUSTOM_OPENAI_MODEL_ID;
    return headers;
  }

  const upper = activeProviderId.toUpperCase();
  const keyName = `PROVIDER_${upper}_KEY`;
  const modelName = `PROVIDER_${upper}_MODEL`;
  if (settings[keyName]) headers["x-active-key"] = settings[keyName];
  if (settings[modelName]) headers["x-active-model"] = settings[modelName];
  return headers;
}

// Extract a user-facing error detail from a non-OK HTTP response.
// Tries JSON first (structured backend error), then plain text, then a
// generic HTTP status fallback.
async function extractErrorDetail(response: Response): Promise<string> {
  try {
    const body = await response.json();
    return body.detail || body.message || JSON.stringify(body);
  } catch {
    try {
      return await response.text();
    } catch {
      return `HTTP ${response.status} ${response.statusText}`;
    }
  }
}

export async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${path}`;
  // SECURITY FIX: Use sessionStorage instead of localStorage for auth tokens.
  // localStorage persists across sessions and is more vulnerable to XSS.
  const token = getAuthToken();

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options?.headers as Record<string, string> | undefined),
  };

  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  // Use a cached settings snapshot to avoid async overhead on every request.
  // The cache is populated on first call and refreshed periodically.
  Object.assign(headers, buildProviderHeaders(getCachedSettings()));

  const response = await fetch(url, {
    ...options,
    headers,
    signal: options?.signal ?? AbortSignal.timeout(15000),
  });

  if (!response.ok) {
    const detail = await extractErrorDetail(response);
    throw new Error(`API ${response.status}: ${detail}`);
  }

  // 204 No Content
  if (response.status === 204) {
    return undefined as unknown as T;
  }

  return response.json() as Promise<T>;
}

// ============ Types ============

export interface HealthResponse {
  ok?: boolean;
  status: string;
  version: string;
  uptime?: number;
  uptime_seconds?: number;
  agents?: number;
  etap_manuals?: number;
  zenon_guides?: number;
  standards?: number;
  engineeringService?: { configured: boolean; healthy: boolean; latencyMs?: number };
  providers?: Record<string, unknown>;
  timestamp?: string;
}

export interface AgentMeta {
  id: string;
  name: string;
  description: string;
  capabilities: string[];
  model: string;
  provider: string;
}

export interface StudyResult {
  study_type: string;
  status: string;
  results?: Record<string, unknown>;
  errors?: string[];
  warnings?: string[];
  duration_ms?: number;
  timestamp?: string;
}

export interface MetricsResponse {
  requests_total: number;
  requests_per_minute: number;
  agents_active: number;
  studies_run: number;
  providers: Record<string, { requests: number; errors: number; latency_ms: number }>;
  timestamp: string;
}

export interface AuditEntry {
  timestamp: string;
  method: string;
  path: string;
  statusCode: number;
  action: string;
  latencyMs?: number;
  userId?: string;
}

// ============ API functions ============

export async function fetchHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/health");
}

export async function fetchAgents(): Promise<AgentMeta[]> {
  const data = await request<{ agents: AgentMeta[] } | AgentMeta[]>("/api/v1/agents");
  return Array.isArray(data) ? data : (data.agents ?? []);
}

export async function runStudy(
  studyType: string,
  params: Record<string, unknown>,
  dryRun = false,
): Promise<StudyResult> {
  if (!params.system) {
    throw new Error("System configuration is required. Please provide a valid power system model.");
  }
  return request<StudyResult>("/api/v1/studies/run", {
    method: "POST",
    body: JSON.stringify({
      study_type: studyType,
      params,
      dry_run: dryRun,
      system: params.system,
    }),
  });
}

export async function fetchStudies(): Promise<unknown[]> {
  return request<unknown[]>("/api/v1/studies");
}

export interface StudyTypesResponse {
  study_types: string[];
  disabled_studies: Array<{ study_type: string; status: string; description: string }>;
}

export async function fetchStudyTypes(): Promise<StudyTypesResponse> {
  return request<StudyTypesResponse>("/api/v1/studies/types");
}

export async function validateSystem(): Promise<{ valid: boolean; errors?: string[] }> {
  return request<{ valid: boolean; errors?: string[] }>("/api/v1/system/validate", {
    method: "POST",
  });
}

export async function fetchMetrics(): Promise<MetricsResponse> {
  return request<MetricsResponse>("/metrics");
}

export async function chatWithAgent(
  agentId: string,
  message: string,
): Promise<{ response: string; agentId: string }> {
  return request<{ response: string; agentId: string }>("/api/v1/agents/chat", {
    method: "POST",
    body: JSON.stringify({ agentId, message }),
  });
}

export async function fetchAuditLogs(): Promise<AuditEntry[]> {
  return request<AuditEntry[]>("/api/v1/audit");
}

// ============ Guard Skills API ============

export interface GuardViolation {
  rule_id: string;
  rule_name: string;
  severity: "must_fix" | "should_fix" | "worth_noting";
  description: string;
  location: string;
  suggestion: string;
  evidence: string;
}

export interface GuardReviewResult {
  success: boolean;
  guard_results: Record<
    string,
    {
      guard_name: string;
      mode: string;
      passed: boolean;
      must_fix: number;
      should_fix: number;
      worth_noting: number;
      violations: GuardViolation[];
    }
  >;
  all_passed: boolean;
  must_fix_total: number;
  should_fix_total: number;
  worth_noting_total: number;
  trace_id: string;
}

export interface GuardInfo {
  guards: Record<
    string,
    {
      name: string;
      description: string;
      rules_checked: number;
      failure_modes?: Array<{
        id: string;
        name: string;
        severity: string;
        description: string;
        research_source: string;
      }>;
    }
  >;
  severity_levels: Record<string, string>;
  source: string;
}

export async function guardReview(
  source: string,
  guardType = "all",
  language = "python",
): Promise<GuardReviewResult> {
  return request<GuardReviewResult>("/api/v1/guards/review", {
    method: "POST",
    body: JSON.stringify({ source, guard_type: guardType, language }),
  });
}

export async function fetchGuardInfo(): Promise<GuardInfo> {
  const data = await request<{ success: boolean; data: GuardInfo }>("/api/v1/guards/info");
  return data.data;
}

// ============ Vision API Keys (Settings) ============

export interface VisionKeyConfig {
  provider: string;
  api_key_masked: string;
  api_key_set: boolean;
  base_url: string | null;
  model_name: string | null;
  is_active: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface VisionKeysResponse {
  success: boolean;
  data: Record<string, VisionKeyConfig>;
  providers: string[];
}

export interface VisionKeyTestResult {
  success: boolean;
  message: string;
  base_url?: string;
  model?: string;
  sample_models?: string[];
}

export async function fetchVisionKeys(): Promise<VisionKeysResponse> {
  return request<VisionKeysResponse>("/api/v1/settings/keys");
}

export async function saveVisionKey(
  provider: string,
  apiKey: string,
  baseUrl?: string,
  modelName?: string,
  isActive = true,
): Promise<{ success: boolean; data: VisionKeyConfig | null; message: string }> {
  const params = new URLSearchParams({
    api_key: apiKey,
    is_active: String(isActive),
  });
  if (baseUrl) params.set("base_url", baseUrl);
  if (modelName) params.set("model_name", modelName);

  return request(`/api/v1/settings/keys/${provider}?${params.toString()}`, {
    method: "POST",
  });
}

export async function deleteVisionKey(
  provider: string,
): Promise<{ success: boolean; message: string }> {
  return request(`/api/v1/settings/keys/${provider}`, {
    method: "DELETE",
  });
}

export async function testVisionKey(
  provider: string,
): Promise<{ success: boolean; data: VisionKeyTestResult }> {
  return request(`/api/v1/settings/keys/${provider}/test`, {
    method: "POST",
  });
}

// ============ MCP Servers ============

export interface McpServerInfo {
  id: string;
  name: string;
  type: string;
  command: string;
  args: string[];
  env_keys: string[];
  env_redacted: Record<string, string>;
  status: string;
}

export interface McpServersResponse {
  success: boolean;
  data: {
    servers: McpServerInfo[];
    total: number;
    config_path?: string;
    message?: string;
  };
  trace_id?: string;
}

export async function fetchMcpServers(): Promise<McpServersResponse> {
  return request<McpServersResponse>("/api/v1/agents/mcp-servers");
}

// ============ Feature Flags ============

export interface FeatureFlag {
  key: string;
  enabled: boolean;
  status: string;
  description: string;
  effective_enabled: boolean;
}

export interface FeatureFlagListResponse {
  success: boolean;
  data: FeatureFlag[];
  total: number;
  env: string;
  trace_id?: string;
}

export interface FeatureFlagPatchResponse {
  success: boolean;
  data: FeatureFlag & { previous_enabled: boolean; env: string };
  trace_id?: string;
}

export async function fetchFeatureFlags(): Promise<FeatureFlagListResponse> {
  return request<FeatureFlagListResponse>("/api/v1/feature-flags");
}

export async function patchFeatureFlag(
  key: string,
  enabled: boolean,
): Promise<FeatureFlagPatchResponse> {
  return request<FeatureFlagPatchResponse>(`/api/v1/feature-flags/${key}`, {
    method: "PATCH",
    body: JSON.stringify({ enabled }),
    headers: { "Content-Type": "application/json" },
  });
}

// ============ AI/ML Playground ============

export interface AiMlResult {
  success: boolean;
  data?: unknown;
  errors?: string[];
  trace_id?: string;
  rate_limit?: {
    remaining?: number;
    reset_at?: string;
    limit?: number;
  };
}

export type AiMlCapability =
  | "predict/load"
  | "predict/fault"
  | "predict/anomaly"
  | "gnn/predict"
  | "rag/query";

export interface AiMlCapabilityInfo {
  id: AiMlCapability;
  label: string;
  method: "POST";
  path: string;
  description: string;
  inputSchema: Record<string, unknown>;
  sampleInput: unknown;
}

export const AI_ML_CAPABILITIES: AiMlCapabilityInfo[] = [
  {
    id: "predict/load",
    label: "Load Forecast",
    method: "POST",
    path: "/api/v1/predict/load",
    description:
      "Predict future load using Prophet / LSTM / Linear LoadForecaster. Pass historical_data array + horizon_hours (1–168).",
    inputSchema: {
      type: "object",
      required: ["historical_data"],
      properties: {
        historical_data: { type: "array", items: { type: "number" }, maxItems: 10000 },
        horizon_hours: { type: "integer", minimum: 1, maximum: 168, default: 24 },
        method: { type: "string", enum: ["auto", "prophet", "lstm", "linear"], default: "auto" },
      },
    },
    sampleInput: {
      historical_data: [120, 132, 145, 158, 162, 170, 168, 175, 182, 190, 188, 195],
      horizon_hours: 6,
      method: "auto",
    },
  },
  {
    id: "predict/fault",
    label: "Fault Prediction",
    method: "POST",
    path: "/api/v1/predict/fault",
    description:
      "Predict fault probability using XGBoost with SHAP explanations. Pass features object + optional model_version.",
    inputSchema: {
      type: "object",
      required: ["features"],
      properties: {
        features: { type: "object" },
        model_version: { type: "string" },
      },
    },
    sampleInput: {
      features: {
        voltage_pu: 0.94,
        current_a: 410,
        power_factor: 0.85,
        temperature_c: 78,
        harmonic_thd: 0.08,
        load_pct: 0.92,
      },
    },
  },
  {
    id: "predict/anomaly",
    label: "Anomaly Detection",
    method: "POST",
    path: "/api/v1/predict/anomaly",
    description:
      "Detect anomalies using Isolation Forest / PyOD. Pass data array + method + contamination.",
    inputSchema: {
      type: "object",
      required: ["data"],
      properties: {
        data: { type: "array", items: { type: "number" }, maxItems: 10000 },
        method: {
          type: "string",
          enum: ["iforest", "pyod_iforest", "pyod_knn", "pyod_autoencoder"],
          default: "iforest",
        },
        contamination: { type: "number", minimum: 0.01, maximum: 0.5, default: 0.05 },
      },
    },
    sampleInput: {
      data: [10, 12, 11, 13, 12, 14, 11, 50, 12, 13, 11, 12, 75, 12, 13, 11],
      method: "iforest",
      contamination: 0.1,
    },
  },
  {
    id: "gnn/predict",
    label: "GNN Power Grid",
    method: "POST",
    path: "/api/v1/gnn/predict",
    description:
      "Run Graph Neural Network analysis on the power grid topology. Pass nodes + edges.",
    inputSchema: {
      type: "object",
      required: ["nodes"],
      properties: {
        nodes: { type: "array" },
        edges: { type: "array" },
        target: { type: "string" },
      },
    },
    sampleInput: {
      nodes: [
        { id: "bus1", type: "bus", voltage_pu: 1.0 },
        { id: "bus2", type: "bus", voltage_pu: 0.98 },
        { id: "line1", type: "line" },
      ],
      edges: [
        { source: "bus1", target: "line1" },
        { source: "line1", target: "bus2" },
      ],
      target: "voltage_stability",
    },
  },
  {
    id: "rag/query",
    label: "RAG Query",
    method: "POST",
    path: "/api/v1/rag/query",
    description: "Run Retrieval-Augmented Generation query against the ETAP knowledge base.",
    inputSchema: {
      type: "object",
      required: ["query"],
      properties: {
        query: { type: "string", maxLength: 1000 },
        top_k: { type: "integer", minimum: 1, maximum: 20, default: 5 },
        filter_tags: { type: "array", items: { type: "string" } },
      },
    },
    sampleInput: {
      query: "What is the IEEE 519 harmonic limit for voltage distortion?",
      top_k: 3,
    },
  },
];

export async function callAiMlEndpoint(path: string, body: unknown): Promise<AiMlResult> {
  return request<AiMlResult>(path, {
    method: "POST",
    body: JSON.stringify(body),
    headers: { "Content-Type": "application/json" },
  });
}

// ============ Projects ============

export interface Project {
  id: string;
  name: string;
  description: string;
  system_config: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
  created_by: string | null;
  status: "active" | "archived" | "deleted";
}

export interface ProjectListResponse {
  projects: Project[];
  total: number;
  page: number;
  page_size: number;
}

export interface ProjectCreateInput {
  name: string;
  description: string;
  system_config?: Record<string, unknown>;
}

export async function listProjects(
  statusFilter?: "active" | "archived",
  page = 1,
  pageSize = 50,
): Promise<ProjectListResponse> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });
  if (statusFilter) params.set("status", statusFilter);
  return request(`/api/v1/projects/?${params.toString()}`);
}

export async function getProject(projectId: string): Promise<Project> {
  return request(`/api/v1/projects/${encodeURIComponent(projectId)}`);
}

export async function createProject(input: ProjectCreateInput): Promise<Project> {
  return request("/api/v1/projects/", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function updateProject(
  projectId: string,
  input: Partial<ProjectCreateInput> & { status?: "active" | "archived" },
): Promise<Project> {
  return request(`/api/v1/projects/${encodeURIComponent(projectId)}`, {
    method: "PUT",
    body: JSON.stringify(input),
  });
}

export async function deleteProject(projectId: string): Promise<void> {
  await request(`/api/v1/projects/${encodeURIComponent(projectId)}`, {
    method: "DELETE",
  });
}

// ============ Solver Parameters API ============

export interface SolverParameters {
  convergence_tolerance: number;
  max_iterations: number;
  acceleration_factor: number;
  zbus_calculation_enabled: boolean;
  zbus_iteration_limit: number;
  zbus_voltage_threshold: number;
}

export async function fetchSolverParameters(): Promise<SolverParameters> {
  return request<SolverParameters>("/api/v1/studies/parameters");
}

export async function updateSolverParameters(
  params: Partial<SolverParameters>,
): Promise<SolverParameters> {
  return request<SolverParameters>("/api/v1/studies/parameters", {
    method: "PUT",
    body: JSON.stringify(params),
  });
}

// ============ Copilot Config API ============

export interface CopilotConfig {
  primary_model: string;
  llm_temperature: number;
  max_tokens: number;
  fallback_chain: string[];
  fallback_notification_enabled: boolean;
}

export async function fetchCopilotConfig(): Promise<CopilotConfig> {
  return request<CopilotConfig>("/api/v1/copilot/config");
}

export async function updateCopilotConfig(config: Partial<CopilotConfig>): Promise<CopilotConfig> {
  return request<CopilotConfig>("/api/v1/copilot/config", {
    method: "PUT",
    body: JSON.stringify(config),
  });
}

// ============ Storage Management API ============

export interface StorageMetrics {
  total_size_bytes: number;
  total_objects: number;
  by_prefix: Record<string, { count: number; size_bytes: number }>;
  retention_days: number;
}

export async function fetchStorageMetrics(): Promise<StorageMetrics> {
  return request<StorageMetrics>("/api/v1/storage/metrics");
}

export async function purgeStorage(options?: {
  prefix?: string;
  older_than_days?: number;
  dry_run?: boolean;
  confirm?: boolean;
}): Promise<{ deleted_count: number; freed_bytes: number; dry_run: boolean }> {
  return request("/api/v1/storage/purge", {
    method: "POST",
    body: JSON.stringify(options ?? { dry_run: true }),
  });
}

export async function clearCADArtifacts(): Promise<{
  deleted_count: number;
  freed_bytes: number;
  dry_run: boolean;
}> {
  return request("/api/v1/storage/artifacts/cad", {
    method: "DELETE",
    body: JSON.stringify({ dry_run: false, confirm: true }),
  });
}

// ============ Notification Config API ============

export interface NotificationConfig {
  digest: {
    period: string;
    schedule_time: string;
    timezone: string;
    enabled: boolean;
  };
  alerts: Array<{
    alert_type: string;
    enabled: boolean;
    severity_threshold: string;
  }>;
  webhooks: Array<{
    id: string;
    url: string;
    events: string[];
    enabled: boolean;
  }>;
}

export async function fetchNotificationConfig(): Promise<NotificationConfig> {
  return request<NotificationConfig>("/api/v1/notifications/digest/config");
}

export async function updateNotificationConfig(
  config: Partial<NotificationConfig>,
): Promise<NotificationConfig> {
  return request<NotificationConfig>("/api/v1/notifications/digest/config", {
    method: "PUT",
    body: JSON.stringify(config),
  });
}

// ============ Autodesk Connector API ============

export interface ConnectorStatus {
  connector_type: string;
  connected: boolean;
  host: string;
  port: number;
  last_check: string | null;
  error: string | null;
}

export interface ConnectorHealthResponse {
  autocad_status: ConnectorStatus;
  revit_status: ConnectorStatus;
  overall_healthy: boolean;
}

export async function fetchConnectorHealth(): Promise<ConnectorHealthResponse> {
  return request<ConnectorHealthResponse>("/api/v1/connectors/autodesk/status");
}

export async function testConnectorConnection(
  connectorType: "autocad" | "revit",
  timeoutSeconds = 5,
): Promise<{ success: boolean; latency_ms: number; error: string | null; connector_type: string }> {
  return request("/api/v1/connectors/autodesk/test-connection", {
    method: "POST",
    body: JSON.stringify({ connector_type: connectorType, timeout_seconds: timeoutSeconds }),
  });
}

// ============ ZIP Load & Generator Config API ============

export interface ZIPLoadConfig {
  id: string;
  name: string;
  p0: number;
  q0: number;
  aZ: number;
  aI: number;
  aP: number;
  bZ: number;
  bI: number;
  bP: number;
  preset: string | null;
}

export interface ZIPPreset {
  name: string;
  aZ: number;
  aI: number;
  aP: number;
  bZ: number;
  bI: number;
  bP: number;
}

export async function fetchZIPLoads(): Promise<{ loads: ZIPLoadConfig[] }> {
  return request("/api/v1/equipment/zip-generators/zip-loads");
}

export async function fetchZIPPrests(): Promise<{ presets: ZIPPreset[] }> {
  return request("/api/v1/equipment/zip-generators/zip-presets");
}

export async function createZIPLoad(load: Omit<ZIPLoadConfig, "id">): Promise<ZIPLoadConfig> {
  return request("/api/v1/equipment/zip-generators/zip-loads", {
    method: "POST",
    body: JSON.stringify(load),
  });
}

export async function updateZIPLoad(
  loadId: string,
  load: Partial<ZIPLoadConfig>,
): Promise<ZIPLoadConfig> {
  return request(`/api/v1/equipment/zip-generators/zip-loads/${encodeURIComponent(loadId)}`, {
    method: "PUT",
    body: JSON.stringify(load),
  });
}

export async function deleteZIPLoad(loadId: string): Promise<void> {
  await request(`/api/v1/equipment/zip-generators/zip-loads/${encodeURIComponent(loadId)}`, {
    method: "DELETE",
  });
}

export async function previewZIPLoad(
  loadId: string,
  voltage: number,
): Promise<{ P: number; Q: number; voltage: number }> {
  return request(
    `/api/v1/equipment/zip-generators/zip-loads/${encodeURIComponent(loadId)}/preview`,
    {
      method: "POST",
      body: JSON.stringify({ voltage }),
    },
  );
}

// ============ Demo mode ============

/** Check if the API client is running in demo mode (no real backend). */
export function isDemoMode(): boolean {
  return !API_BASE_URL || API_BASE_URL === "";
}

// ============ Dual Control ============

export type DualControlAction = "approve" | "reject";

export interface DualControlActionDetail {
  type: string;
  target?: string;
  description?: string;
}

export interface DualControlRequest {
  request_id: string;
  action: DualControlActionDetail;
  requested_by: string;
  status: "pending" | "approved" | "rejected" | "expired";
  created_at: string;
  expires_at: number;
  approved_by: string | null;
  approved_at: string | null;
  rejected_by: string | null;
  rejected_reason: string | null;
  qr_secret: string;
}

export interface DualControlResponse {
  success: boolean;
  error?: string;
  request?: DualControlRequest;
}

/** Approve a pending dual-control request. */
export async function approveDualControlRequest(
  requestId: string,
  secret?: string,
): Promise<DualControlResponse> {
  const res = await fetch(`${API_BASE_URL}/dual-control/approve/${requestId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ secret }),
  });
  return res.json();
}

/** Reject a pending dual-control request. */
export async function rejectDualControlRequest(
  requestId: string,
  reason: string,
): Promise<DualControlResponse> {
  const res = await fetch(`${API_BASE_URL}/dual-control/reject/${requestId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ reason }),
  });
  return res.json();
}

/** Create a new dual-control approval request. */
export async function createDualControlRequest(
  action: DualControlAction,
  target: string,
  description: string,
): Promise<{ success: boolean; data: DualControlRequest }> {
  const res = await fetch(`${API_BASE_URL}/dual-control/request`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ action: { type: action, target, description } }),
  });
  return res.json();
}

/** List pending dual-control requests. */
export async function listPendingDualControlRequests(): Promise<{
  success: boolean;
  data: DualControlRequest[];
}> {
  const res = await fetch(`${API_BASE_URL}/dual-control/pending`, {
    headers: authHeaders(),
  });
  return res.json();
}

/** Get QR secret for a dual-control request. */
export async function getDualControlQrSecret(
  requestId: string,
): Promise<{ success: boolean; data: { request_id: string; qr_secret: string } }> {
  const res = await fetch(`${API_BASE_URL}/dual-control/qr/${requestId}`, {
    headers: authHeaders(),
  });
  return res.json();
}

// ============ End of API client ============
