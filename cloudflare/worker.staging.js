/**
 * Cloudflare Worker — Dedicated Staging Reverse Proxy for AhmedETAP Platform
 *
 * Dedicated staging proxy isolating the staging environment on workers.dev.
 * Upstream origin is strictly dynamically configured and validated.
 *
 * Invariants:
 * 1. ZERO production fallback: The production Hugging Face origin is explicitly forbidden.
 * 2. Fail-closed: An unset or invalid ORIGIN_URL returns HTTP 503.
 * 3. Transparent streaming: SSE text/event-stream responses are passed unbuffered.
 * 4. Staging CORS: Handles preflight and attaches CORS for staging Vercel frontend.
 * 5. No caching: All engineering calculations and chat streams are strictly no-store.
 */

// ─── Security Configuration & Origin Validation ─────────────────────────────

const PRODUCTION_HOST_DENYLIST = [
  "ahmdelbaz28-ahmedetap-platform.hf.space",
  "etap-ai-work.vercel.app",
  "ahmdelbaz28.com",
];

const ALLOWED_CORS_ORIGINS = new Set([
  "https://etap-ai-work-staging.vercel.app",
  "http://localhost:5173",
  "http://localhost:3000",
  "http://127.0.0.1:5173",
  "http://127.0.0.1:3000",
]);

function validateOrigin(originUrl) {
  if (!originUrl || typeof originUrl !== "string") {
    return { valid: false, error: "ORIGIN_URL environment variable is missing or empty" };
  }
  const trimmed = originUrl.trim().replace(/\/+$/, "");
  let parsed;
  try {
    parsed = new URL(trimmed);
  } catch {
    return { valid: false, error: `ORIGIN_URL '${originUrl}' is not a valid URL` };
  }

  if (parsed.protocol !== "https:" && parsed.protocol !== "http:") {
    return { valid: false, error: `Invalid protocol '${parsed.protocol}' in ORIGIN_URL` };
  }

  for (const denied of PRODUCTION_HOST_DENYLIST) {
    if (parsed.hostname.toLowerCase() === denied.toLowerCase()) {
      return {
        valid: false,
        error: `SECURITY VIOLATION: ORIGIN_URL points to production host '${denied}'`,
      };
    }
  }

  return { valid: true, cleanUrl: trimmed, hostname: parsed.hostname };
}

// ─── Main Worker Export ─────────────────────────────────────────────────────

export default {
  async fetch(request, env, ctx) {
    const originCheck = validateOrigin(env.ORIGIN_URL);
    if (!originCheck.valid) {
      return new Response(
        JSON.stringify({
          error: "STAGING_ORIGIN_NOT_CONFIGURED",
          message: originCheck.error,
          environment: "staging",
        }),
        {
          status: 503,
          headers: {
            "Content-Type": "application/json",
            "Cache-Control": "no-store, no-cache",
          },
        }
      );
    }

    const clientOrigin = request.headers.get("Origin") || "";
    const isAllowedCors = ALLOWED_CORS_ORIGINS.has(clientOrigin);

    // Handle OPTIONS Preflight
    if (request.method === "OPTIONS") {
      const corsHeaders = {
        "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, PATCH, OPTIONS",
        "Access-Control-Allow-Headers":
          "Authorization, Content-Type, X-User-LLM-Key, X-User-LLM-Provider, X-CSRF-Token, X-API-Key, Accept",
        "Access-Control-Max-Age": "86400",
        "Vary": "Origin",
      };
      if (isAllowedCors) {
        corsHeaders["Access-Control-Allow-Origin"] = clientOrigin;
        corsHeaders["Access-Control-Allow-Credentials"] = "true";
      } else {
        corsHeaders["Access-Control-Allow-Origin"] = "https://etap-ai-work-staging.vercel.app";
      }
      return new Response(null, { status: 204, headers: corsHeaders });
    }

    // Build target upstream URL
    const reqUrl = new URL(request.url);
    const targetUrl = new URL(reqUrl.pathname + reqUrl.search, originCheck.cleanUrl);

    // Forward headers
    const newHeaders = new Headers(request.headers);
    newHeaders.set("Host", originCheck.hostname);
    newHeaders.set("X-Forwarded-Host", reqUrl.host);
    newHeaders.set("X-Forwarded-Proto", reqUrl.protocol.replace(":", ""));
    newHeaders.set("X-Staging-Proxy", "ahmedetap-staging-proxy");

    // Pass request through to upstream
    try {
      const upstreamResp = await fetch(targetUrl.toString(), {
        method: request.method,
        headers: newHeaders,
        body: ["GET", "HEAD"].includes(request.method) ? undefined : request.body,
        redirect: "follow",
      });

      // Assemble downstream response
      const respHeaders = new Headers(upstreamResp.headers);

      // Enforce CORS headers on response
      if (isAllowedCors) {
        respHeaders.set("Access-Control-Allow-Origin", clientOrigin);
        respHeaders.set("Access-Control-Allow-Credentials", "true");
      }
      respHeaders.set("Vary", "Origin");

      // SSE Streaming: Disable proxy buffering
      const contentType = (respHeaders.get("Content-Type") || "").toLowerCase();
      if (contentType.includes("text/event-stream")) {
        respHeaders.set("X-Accel-Buffering", "no");
        respHeaders.set("Cache-Control", "no-cache, no-transform");
        respHeaders.set("Connection", "keep-alive");
      } else {
        respHeaders.set("Cache-Control", "no-store");
      }

      // Security headers
      respHeaders.set("X-Content-Type-Options", "nosniff");
      respHeaders.set("X-Frame-Options", "SAMEORIGIN");
      respHeaders.set("Referrer-Policy", "strict-origin-when-cross-origin");

      return new Response(upstreamResp.body, {
        status: upstreamResp.status,
        statusText: upstreamResp.statusText,
        headers: respHeaders,
      });
    } catch (err) {
      return new Response(
        JSON.stringify({
          error: "STAGING_UPSTREAM_UNREACHABLE",
          message: `Failed to reach staging upstream: ${err.message || String(err)}`,
          upstream: originCheck.cleanUrl,
        }),
        {
          status: 502,
          headers: {
            "Content-Type": "application/json",
            "Cache-Control": "no-store",
          },
        }
      );
    }
  },
};
