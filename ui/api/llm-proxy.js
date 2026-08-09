/**
 * Vercel Serverless Function — LLM API Proxy (with streaming support)
 *
 * Two modes:
 *   1. Non-streaming: POST /api/llm-proxy → JSON response
 *   2. Streaming: POST /api/llm-proxy?stream=true → SSE stream
 *
 * Solves CORS: browsers can't directly call LLM APIs because they don't
 * send CORS headers. This proxy forwards server-to-server.
 *
 * SECURITY AUDIT 2026-08-02 (CRITICAL SSRF fix):
 * The previous version accepted ANY `endpoint` URL from the client,
 * including http://169.254.169.254/ (AWS metadata), http://localhost:6379/
 * (internal Redis), etc. This allowed:
 *   - Cloud metadata exfiltration (IMDS)
 *   - Internal network scanning
 *   - API key forwarding to attacker-controlled servers
 *
 * Fix: strict URL allowlist — only known LLM API domains are permitted.
 * All internal/private IPs are blocked.
 */

// ---------------------------------------------------------------------------
// SECURITY: URL allowlist — only these LLM API domains are permitted
// ---------------------------------------------------------------------------
const ALLOWED_LLM_DOMAINS = [
  // OpenAI
  "api.openai.com",
  // Anthropic
  "api.anthropic.com",
  // Google Gemini / Vertex AI
  "generativelanguage.googleapis.com",
  "aiplatform.googleapis.com",
  // Azure OpenAI
  "*.openai.azure.com",
  // Groq
  "api.groq.com",
  // Mistral
  "api.mistral.ai",
  // Cohere
  "api.cohere.ai",
  "api.cohere.com",
  // Together AI
  "api.together.xyz",
  // Fireworks AI
  "api.fireworks.ai",
  // DeepSeek
  "api.deepseek.com",
  // Perplexity
  "api.perplexity.ai",
  // Local development (only in non-production)
  "localhost",
  "127.0.0.1",
];

// Private IP ranges that are ALWAYS blocked (even if allowlisted somehow)
const PRIVATE_IP_PATTERNS = [
  /^10\./, // 10.0.0.0/8
  /^172\.(1[6-9]|2\d|3[0-1])\./, // 172.16.0.0/12
  /^192\.168\./, // 192.168.0.0/16
  /^127\./, // 127.0.0.0/8 (loopback)
  /^169\.254\./, // 169.254.0.0/16 (link-local / AWS IMDS)
  /^0\./, // 0.0.0.0/8
  /^::1$/, // IPv6 loopback
  /^fc/, // IPv6 unique-local
  /^fe80:/, // IPv6 link-local
  /^fd/, // IPv6 unique-local
];

/**
 * Validate the endpoint URL against the allowlist and block private IPs.
 * Returns { valid: true } or { valid: false, reason: string }.
 *
 * SECURITY: This is the core SSRF mitigation. Without it, the proxy
 * accepts ANY URL — including cloud metadata endpoints and internal services.
 */
function validateEndpoint(endpoint) {
  let url;
  try {
    url = new URL(endpoint);
  } catch {
    return { valid: false, reason: "Invalid URL format" };
  }

  // Only HTTPS allowed (HTTP only in non-production for localhost)
  const isProd =
    (process.env.ENVIRONMENT || process.env.ENV || "development").toLowerCase() !== "development";
  if (url.protocol !== "https:") {
    if (
      url.protocol === "http:" &&
      !isProd &&
      (url.hostname === "localhost" || url.hostname === "127.0.0.1")
    ) {
      // Allow http://localhost in development only
    } else {
      return { valid: false, reason: `Only HTTPS is allowed (got ${url.protocol})` };
    }
  }

  // Block private IPs
  const hostname = url.hostname;
  for (const pattern of PRIVATE_IP_PATTERNS) {
    if (pattern.test(hostname)) {
      // Allow localhost/127.0.0.1 in non-production
      if ((hostname === "localhost" || hostname === "127.0.0.1") && !isProd) {
        continue;
      }
      return { valid: false, reason: `Private/internal IP addresses are blocked: ${hostname}` };
    }
  }

  // Check against allowlist
  const isAllowed = ALLOWED_LLM_DOMAINS.some((domain) => {
    if (domain.startsWith("*.")) {
      return hostname.endsWith(domain.slice(2)) || hostname === domain.slice(2);
    }
    return hostname === domain;
  });

  if (!isAllowed) {
    return {
      valid: false,
      reason: `Domain '${hostname}' is not in the allowed LLM API domains list. Allowed: ${ALLOWED_LLM_DOMAINS.join(", ")}`,
    };
  }

  return { valid: true };
}

/**
 * Validate the request body and return a normalized request descriptor,
 * or send an error response and return null if the request is invalid.
 *
 * Extracted from `handler` to keep the main function's cognitive
 * complexity under 15 (SonarCloud S3776).
 */
function parseProxyRequest(req, res) {
  const { endpoint, apiKey, body, headers: customHeaders, stream } = req.body || {};

  if (!endpoint || !apiKey || !body) {
    res.status(400).json({
      error: "Missing required fields: endpoint, apiKey, body",
    });
    return null;
  }

  // SECURITY: Validate endpoint URL against allowlist (SSRF protection)
  const validation = validateEndpoint(endpoint);
  if (!validation.valid) {
    res.status(403).json({
      error: "Endpoint not allowed",
      reason: validation.reason,
    });
    return null;
  }

  const headers = {
    "Content-Type": "application/json",
    ...customHeaders,
  };

  if (!headers.Authorization && !headers.authorization) {
    headers.Authorization = `Bearer ${apiKey}`;
  }

  // Add stream: true to the body if streaming is requested
  const requestBody =
    typeof body === "string"
      ? body
      : JSON.stringify({ ...body, stream: stream ? true : undefined });

  return { endpoint, apiKey, headers, requestBody, stream: !!stream };
}

/**
 * Streaming mode: pipe the upstream SSE response to the client.
 * Extracted from `handler` to reduce cognitive complexity (SonarCloud S3776).
 */
async function handleStreamingMode(res, endpoint, headers, requestBody) {
  res.setHeader("Content-Type", "text/event-stream");
  res.setHeader("Cache-Control", "no-cache");
  res.setHeader("Connection", "keep-alive");
  res.setHeader("X-Accel-Buffering", "no"); // Disable Nginx buffering

  const response = await fetch(endpoint, {
    method: "POST",
    headers,
    body: requestBody,
  });

  if (!response.ok) {
    const errorText = await response.text();
    res.write(
      `data: ${JSON.stringify({ error: true, status: response.status, message: errorText.slice(0, 500) })}\n\n`,
    );
    res.end();
    return;
  }

  // Pipe the stream through
  const reader = response.body.getReader();
  const decoder = new TextDecoder();

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const chunk = decoder.decode(value, { stream: true });
      // Forward each SSE chunk
      res.write(chunk);
    }
  } catch (_streamErr) {
    console.warn(
      "SSE stream error (client may have disconnected):",
      _streamErr instanceof Error ? _streamErr.message : String(_streamErr),
    );
  }

  res.write("data: [DONE]\n\n");
  res.end();
}

/**
 * Non-streaming mode: forward the upstream JSON/text response to the client.
 * Extracted from `handler` to reduce cognitive complexity (SonarCloud S3776).
 */
async function handleNonStreamingMode(res, endpoint, headers, requestBody) {
  const response = await fetch(endpoint, {
    method: "POST",
    headers,
    body: requestBody,
  });

  const responseText = await response.text();

  let responseData;
  try {
    responseData = JSON.parse(responseText);
  } catch {
    responseData = { raw: responseText };
  }

  res.status(response.status).json(responseData);
}

export default async function handler(req, res) {
  // SECURITY: Restrict CORS to same-origin (was "*" — allowed any website to use the proxy)
  const allowedOrigin = process.env.LLM_PROXY_ALLOWED_ORIGIN || "";
  const requestOrigin = req.headers.origin || "";
  // In production, only allow the configured origin. In development, allow all.
  const isProd =
    (process.env.ENVIRONMENT || process.env.ENV || "development").toLowerCase() !== "development";
  if (isProd && allowedOrigin && requestOrigin !== allowedOrigin) {
    res.setHeader("Access-Control-Allow-Origin", allowedOrigin);
  } else {
    res.setHeader("Access-Control-Allow-Origin", "*");
  }
  res.setHeader("Access-Control-Allow-Methods", "POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");

  if (req.method === "OPTIONS") {
    return res.status(200).end();
  }
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  try {
    const parsed = parseProxyRequest(req, res);
    if (!parsed) return; // parseProxyRequest already sent the error response

    const { endpoint, headers, requestBody, stream } = parsed;

    if (stream) {
      await handleStreamingMode(res, endpoint, headers, requestBody);
      return;
    }

    await handleNonStreamingMode(res, endpoint, headers, requestBody);
  } catch (err) {
    console.error("LLM Proxy error:", err);
    return res.status(500).json({
      error: "Proxy request failed",
      message: err.message,
    });
  }
}
