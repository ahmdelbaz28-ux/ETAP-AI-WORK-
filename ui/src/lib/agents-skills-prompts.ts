/**
 * Agents / Skills / Prompts API client (P7b)
 * ==========================================
 * Read-only, backend-authoritative visibility over the EXISTING agents API
 * (api/agents.py). NO new endpoints are introduced by P7b and NO mutation
 * calls exist here by design:
 *
 *   - The backend currently provides NO contract for enabling/disabling
 *     agents, activating/deactivating skills, or editing prompts. Per the
 *     P7b security rules, a client-side authorization layer or a parallel
 *     write path MUST NOT be invented. This client is therefore strictly
 *     read-only.
 *
 * Backend contract (pre-existing, verified in api/agents.py):
 *   GET /api/v1/agents                    — canonical agent registry listing
 *                                           (api/shared_handlers.AGENTS)
 *   GET /api/v1/agents/{agent_id}         — single agent detail (404 unknown)
 *   GET /api/v1/agents/info               — orchestrator + prompt integration
 *                                           status + available prompt handles
 *                                           (agents.prompt_loader)
 *   GET /api/v1/agents/ahmed-etap/info    — AhmedETAP orchestration skill
 *                                           metadata
 *
 * SECURITY (P7b):
 *   - All displayed metadata comes from trusted backend responses.
 *   - Prompt CONTENT is never requested or rendered — only handle names and
 *     counts, so privileged system prompts cannot leak through the UI.
 *   - No browser persistence of any configuration data (no localStorage /
 *     sessionStorage); everything is fetched fresh from the backend.
 */

import { request } from "./api";

/** One agent as returned by GET /api/v1/agents and GET /api/v1/agents/{id}. */
export interface BackendAgent {
  id: string;
  name: string;
  description: string;
  standard: string;
  status: string;
  capabilities: string[];
  model: string;
  provider: string;
}

export interface AgentsListResponse {
  success: boolean;
  agents: BackendAgent[];
  trace_id?: string;
}

export interface AgentDetailResponse {
  success: boolean;
  agent: BackendAgent;
  trace_id?: string;
}

/**
 * Prompt-integration metadata as returned by GET /api/v1/agents/info.
 * `available_prompts` contains prompt HANDLE names only — never prompt
 * content (the loader returns sorted unique handles from prompts/).
 */
export interface AgentsInfoResponse {
  success: boolean;
  data: {
    orchestrator: {
      prompt_handle: string;
      prompt_loaded: boolean;
    };
    agents: Record<string, unknown>;
    available_prompts: string[];
    prompt_count: number;
  };
  trace_id?: string;
}

/** AhmedETAP orchestration skill metadata (GET /api/v1/agents/ahmed-etap/info). */
export interface AhmedEtapSkillInfoResponse {
  success: boolean;
  data: {
    name?: string;
    description?: string;
    [key: string]: unknown;
  };
}

/** List the backend-registered agents (canonical registry — backend truth). */
export async function listAgents(): Promise<AgentsListResponse> {
  return request<AgentsListResponse>("/api/v1/agents");
}

/** Fetch one agent's detail. Throws (via request) on 404 / backend errors. */
export async function getAgent(agentId: string): Promise<AgentDetailResponse> {
  return request<AgentDetailResponse>(
    `/api/v1/agents/${encodeURIComponent(agentId)}`,
  );
}

/** Fetch orchestrator + prompt integration metadata (handles only). */
export async function getAgentsInfo(): Promise<AgentsInfoResponse> {
  return request<AgentsInfoResponse>("/api/v1/agents/info");
}

/** Fetch the AhmedETAP orchestration skill metadata. */
export async function getAhmedEtapSkillInfo(): Promise<AhmedEtapSkillInfoResponse> {
  return request<AhmedEtapSkillInfoResponse>("/api/v1/agents/ahmed-etap/info");
}
