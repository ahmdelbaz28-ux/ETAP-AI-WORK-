// UI components are intentionally complex for feature-rich DX
/**
 * AhmedETAP Platform — API Client
 *
 * REAL backend only. No demo mode, no mock data, no silent fallback.
 *
 * The API base URL is resolved centrally in ./api-config.ts.
 * See that file for configuration options (VITE_API_URL env var).
 */

import { API_BASE_URL, getCachedSettings } from "./api-config";
import { getAuthToken } from "./tokenStorage";

// Forward user's active provider key/model to backend dynamically.
// Extracted to a helper to keep request() below SonarCloud's cognitive
// complexity threshold (S3776).
function buildProviderHeaders(
  settings: Record<string, string>,
): Record<string, string> {
  const headers: Record<string, string> = {};
  const activeProviderId = settings.PROVIDER_ACTIVE_PROVIDER_ID || "openai";
  headers["x-active-provider"] = activeProviderId;

  if (activeProviderId === "custom_openai") {
    if (settings.CUSTOM_OPENAI_API_KEY) headers["x-active-key"] = settings.CUSTOM_OPENAI_API_KEY;
    if (settings.CUSTOM_OPENAI_BASE_URL) headers["x-active-url"] = settings.CUSTOM_OPENAI_BASE_URL;
    if (settings.CUSTOM_OPENAI_MODEL_ID) headers["x-active-model"] = settings.CUSTOM_OPENAI_MODEL_ID;
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

async function request<T>(path: string, options?: RequestInit): Promise<T> {
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

export async function updateCopilotConfig(
  config: Partial<CopilotConfig>,
): Promise<CopilotConfig> {
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

// ============ Audit Logs API ============

export interface AuditLogEntry {
  id: string;
  timestamp: string;
  severity: string;
  action: string;
  user: string;
  ip_address: string;
  resource: string;
  details: string;
  trace_id: string;
}

export interface AuditLogListResponse {
  entries: AuditLogEntry[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export async function fetchAuditLogs(params?: {
  page?: number;
  page_size?: number;
  severity?: string;
  action?: string;
  user?: string;
  search?: string;
  start_date?: string;
  end_date?: string;
}): Promise<AuditLogListResponse> {
  const searchParams = new URLSearchParams();
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined) searchParams.set(k, String(v));
    });
  }
  const qs = searchParams.toString();
  return request<AuditLogListResponse>(`/api/v1/security/audit-logs${qs ? `?${qs}` : ""}`);
}

// ============ Feature Flags API ============

export interface FeatureFlag {
  flag_id: string;
  enabled: boolean;
  status: string;
  description: string;
}

export async function fetchFeatureFlags(): Promise<{
  flags: FeatureFlag[];
  total: number;
  enabled_count: number;
}> {
  return request("/api/v1/feature-flags");
}

export async function updateFeatureFlag(
  flagId: string,
  update: { enabled?: boolean; status?: string; description?: string },
): Promise<FeatureFlag> {
  return request(`/api/v1/feature-flags/${encodeURIComponent(flagId)}`, {
    method: "PUT",
    body: JSON.stringify(update),
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

export async function createZIPLoad(
  load: Omit<ZIPLoadConfig, "id">,
): Promise<ZIPLoadConfig> {
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
  return request(`/api/v1/equipment/zip-generators/zip-loads/${encodeURIComponent(loadId)}/preview`, {
    method: "POST",
    body: JSON.stringify({ voltage }),
  });
}

// ============ End of API client ============
