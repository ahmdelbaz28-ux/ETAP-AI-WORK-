/**
 * External Services Integration & Connectivity Probes
 *
 * Dedicated descriptors and network probes for verifying third-party integrations:
 * LangWatch, Smithery MCP, Hugging Face, GitHub, and Vercel.
 */

export type TestStatus = "idle" | "testing" | "ok" | "fail";

export interface ServiceField {
  key: string;
  label: string;
  placeholder: string;
  required: boolean;
  type?: "text" | "password";
}

export interface ServiceDescriptor {
  id: "langwatch" | "smithery" | "huggingface" | "github" | "vercel";
  name: string;
  description: string;
  dashboardUrl: string;
  color: string;
  fields: ServiceField[];
  testConnection: (
    settings: Record<string, string>,
  ) => Promise<{ ok: boolean; detail: string }> | null;
}

export const EXTERNAL_SERVICES: ServiceDescriptor[] = [
  {
    id: "langwatch",
    name: "LangWatch",
    description: "LLM observability & tracing dashboard",
    dashboardUrl: "https://app.langwatch.ai",
    color: "#6366f1",
    fields: [
      {
        key: "LANGWATCH_API_KEY",
        label: "API Key",
        placeholder: "sk-lw-...",
        required: true,
        type: "password",
      },
      { key: "LANGWATCH_PROJECT", label: "Project Name", placeholder: "AhmedETAP", required: true },
      {
        key: "LANGWATCH_ENDPOINT",
        label: "Endpoint",
        placeholder: "https://app.langwatch.ai",
        required: true,
      },
    ],
    testConnection: (s) => {
      const apiKey = s.LANGWATCH_API_KEY?.trim();
      const endpoint = s.LANGWATCH_ENDPOINT?.trim() || "https://app.langwatch.ai";
      if (!apiKey) return null;
      // LangWatch has CORS restrictions on browser fetches. We use a no-cors mode
      // probe to verify the server is reachable.
      const tryNormal = fetch(`${endpoint}/api/v1/projects`, {
        method: "GET",
        headers: { "X-Auth-Token": apiKey, Accept: "application/json" },
      }).then(async (r) => {
        if (r.ok) return { ok: true, detail: "Connected — project list reachable" };
        if (r.status === 401 || r.status === 403)
          return { ok: false, detail: "Invalid API key (401/403)" };
        if (r.status === 404)
          return { ok: true, detail: "Endpoint reachable (path 404 is normal)" };
        return { ok: false, detail: `HTTP ${r.status}` };
      });

      // If normal fetch throws (CORS), try no-cors probe as fallback
      return tryNormal.catch(() =>
        fetch(`${endpoint}/api/v1/projects`, {
          method: "GET",
          mode: "no-cors",
          headers: { "X-Auth-Token": apiKey },
        })
          .then(() => ({ ok: true, detail: "Endpoint reachable (no-cors probe OK)" }))
          .catch((e) => ({ ok: false, detail: `Network error: ${e.message}` })),
      );
    },
  },
  {
    id: "smithery",
    name: "Smithery MCP",
    description: "Model Context Protocol server registry",
    dashboardUrl: "https://smithery.ai/console/api-keys",
    color: "#10b981",
    fields: [
      {
        key: "SMITHERY_API_KEY",
        label: "API Key",
        placeholder: "UUID-format key",
        required: true,
        type: "password",
      },
      {
        key: "SMITHERY_BASE_URL",
        label: "Base URL",
        placeholder: "https://api.smithery.ai",
        required: true,
      },
    ],
    testConnection: (s) => {
      const apiKey = s.SMITHERY_API_KEY?.trim();
      const baseUrl = s.SMITHERY_BASE_URL?.trim() || "https://api.smithery.ai";
      if (!apiKey) return null;
      // Smithery exposes /v1/servers as a public listing endpoint
      return fetch(`${baseUrl}/v1/servers?limit=1`, {
        method: "GET",
        headers: { Authorization: `Bearer ${apiKey}`, Accept: "application/json" },
      })
        .then(async (r) => {
          if (r.ok) return { ok: true, detail: "Connected — server registry reachable" };
          if (r.status === 401 || r.status === 403) return { ok: false, detail: "Invalid API key" };
          // Try alternative endpoint
          return fetch(`${baseUrl}/servers?limit=1`, {
            method: "GET",
            headers: { Authorization: `Bearer ${apiKey}` },
          }).then((r2) =>
            r2.ok
              ? { ok: true, detail: "Connected (alt path)" }
              : { ok: false, detail: `HTTP ${r.status} / ${r2.status}` },
          );
        })
        .catch((e) => ({ ok: false, detail: `Network error: ${e.message}` }));
    },
  },
  {
    id: "huggingface",
    name: "Hugging Face",
    description: "Model hub & Spaces deployment",
    dashboardUrl: "https://huggingface.co/settings/tokens",
    color: "#ffd21e",
    fields: [
      {
        key: "HF_TOKEN",
        label: "Access Token",
        placeholder: "hf_...",
        required: true,
        type: "password",
      },
      {
        key: "HF_SPACE_NAME",
        label: "Space Name",
        placeholder: "username/space-name",
        required: true,
      },
      {
        key: "HF_REPO_URL",
        label: "Space URL",
        placeholder: "https://huggingface.co/spaces/...",
        required: false,
      },
    ],
    testConnection: (s) => {
      const token = s.HF_TOKEN?.trim();
      if (!token) return null;
      // HuggingFace exposes /api/whoami-v2 which validates the token
      return fetch("https://huggingface.co/api/whoami-v2", {
        method: "GET",
        headers: { Authorization: `Bearer ${token}`, Accept: "application/json" },
      })
        .then(async (r) => {
          if (r.ok) {
            try {
              const data = await r.json();
              const username = data.name || data.user?.name || "unknown";
              return { ok: true, detail: `Connected as @${username}` };
            } catch {
              return { ok: true, detail: "Connected (token valid)" };
            }
          }
          if (r.status === 401) return { ok: false, detail: "Invalid or expired token" };
          return { ok: false, detail: `HTTP ${r.status}` };
        })
        .catch((e) => ({ ok: false, detail: `Network error: ${e.message}` }));
    },
  },
  {
    id: "github",
    name: "GitHub",
    description: "Repository access & CI/CD",
    dashboardUrl: "https://github.com/settings/tokens",
    color: "#6e7681",
    fields: [
      {
        key: "GITHUB_TOKEN",
        label: "Personal Access Token",
        placeholder: "github_pat_... or ghp_...",
        required: true,
        type: "password",
      },
      { key: "GITHUB_REPO", label: "Repository", placeholder: "owner/repo-name", required: true },
    ],
    testConnection: (s) => {
      const token = s.GITHUB_TOKEN?.trim();
      if (!token) return null;
      return fetch("https://api.github.com/user", {
        method: "GET",
        headers: { Authorization: `Bearer ${token}`, Accept: "application/vnd.github+json" },
      })
        .then(async (r) => {
          if (r.ok) {
            try {
              const data = await r.json();
              return { ok: true, detail: `Connected as @${data.login}` };
            } catch {
              return { ok: true, detail: "Connected (token valid)" };
            }
          }
          if (r.status === 401) return { ok: false, detail: "Invalid token" };
          if (r.status === 403) return { ok: false, detail: "Rate-limited or forbidden" };
          return { ok: false, detail: `HTTP ${r.status}` };
        })
        .catch((e) => ({ ok: false, detail: `Network error: ${e.message}` }));
    },
  },
  {
    id: "vercel",
    name: "Vercel",
    description: "Frontend deployment & preview",
    dashboardUrl: "https://vercel.com/account/tokens",
    color: "#000000",
    fields: [
      { key: "VERCEL_PROJECT_ID", label: "Project ID", placeholder: "prj_...", required: true },
      {
        key: "VERCEL_ACCESS_TOKEN",
        label: "Access Token",
        placeholder: "vcp_...",
        required: true,
        type: "password",
      },
    ],
    testConnection: (s) => {
      const token = s.VERCEL_ACCESS_TOKEN?.trim();
      const projectId = s.VERCEL_PROJECT_ID?.trim();
      if (!token || !projectId) return null;
      // Vercel API: GET /v9/projects/{id}
      return fetch(`https://api.vercel.com/v9/projects/${projectId}`, {
        method: "GET",
        headers: { Authorization: `Bearer ${token}`, Accept: "application/json" },
      })
        .then(async (r) => {
          if (r.ok) {
            try {
              const data = await r.json();
              return { ok: true, detail: `Connected — project "${data.name}"` };
            } catch {
              return { ok: true, detail: "Connected (project reachable)" };
            }
          }
          if (r.status === 401) return { ok: false, detail: "Invalid access token" };
          if (r.status === 404) return { ok: false, detail: "Project not found (bad project ID?)" };
          return { ok: false, detail: `HTTP ${r.status}` };
        })
        .catch((e) => ({ ok: false, detail: `Network error: ${e.message}` }));
    },
  },
];
