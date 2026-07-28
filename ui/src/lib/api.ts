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

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${path}`;
  const token = localStorage.getItem("authToken");

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

// ============ Dual Control (Condition A — life-safety 4-eyes principle) ============
//
// All 5 endpoints require `admin` or `engineer` role (enforced server-side
// via `Depends(require_role("admin","engineer"))` — see hf-space/app.py:999-1113).
// Operator/approver/rejector identity is derived from the JWT, NOT the request
// body, to prevent impersonation attacks on life-safety operations.
//
// The dual-control flow:
//   1. Operator calls createDualControlRequest({action}) → server creates a
//      pending request with a 5-minute auto-reject timeout + QR secret.
//   2. A second engineer (the "approver") sees the pending request in the UI.
//   3. Approver can either:
//      a. Approve via REST (POST /approve/{id}) — optionally with QR secret
//         for mobile 2FA.
//      b. Reject via REST (POST /reject/{id}) — with a reason.
//   4. If 5 minutes elapse with no action, the request auto-expires.
//
// UI: pages/DualControl.tsx

export interface DualControlAction {
  type: string;
  target?: string;
  params?: Record<string, unknown>;
  description?: string;
}

export interface DualControlRequest {
  request_id: string;
  action: DualControlAction;
  requested_by: string;
  status: "pending" | "approved" | "rejected" | "expired";
  approved_by: string | null;
  approved_at: string | null;
  rejected_by: string | null;
  rejected_reason: string | null;
  created_at: string;
  expires_at: number; // unix epoch seconds
  qr_secret: string;
}

export interface DualControlCreateInput {
  action: DualControlAction;
}

export interface DualControlCreateResponse {
  success: boolean;
  data: DualControlRequest;
}

export interface DualControlPendingResponse {
  success: boolean;
  data: DualControlRequest[];
}

export interface DualControlQrResponse {
  success: boolean;
  data: {
    request_id: string;
    qr_secret: string;
  };
}

export interface DualControlApproveRejectResponse {
  success: boolean;
  error?: string;
  request?: DualControlRequest;
}

export async function createDualControlRequest(
  input: DualControlCreateInput,
): Promise<DualControlCreateResponse> {
  return request("/api/v1/dual-control/request", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function approveDualControlRequest(
  requestId: string,
  secret?: string,
): Promise<DualControlApproveRejectResponse> {
  return request(`/api/v1/dual-control/approve/${encodeURIComponent(requestId)}`, {
    method: "POST",
    body: JSON.stringify(secret ? { secret } : {}),
  });
}

export async function rejectDualControlRequest(
  requestId: string,
  reason = "",
): Promise<DualControlApproveRejectResponse> {
  return request(`/api/v1/dual-control/reject/${encodeURIComponent(requestId)}`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  });
}

export async function listPendingDualControlRequests(): Promise<DualControlPendingResponse> {
  return request("/api/v1/dual-control/pending");
}

export async function getDualControlQrSecret(requestId: string): Promise<DualControlQrResponse> {
  return request(`/api/v1/dual-control/qr/${encodeURIComponent(requestId)}`);
}

// ============ End of API client ============
