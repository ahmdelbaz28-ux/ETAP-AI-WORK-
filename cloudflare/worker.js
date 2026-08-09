/**
 * Cloudflare Worker — Secure Reverse Proxy for AhmedETAP Platform
 *
 * This Worker sits between the user and the HF Space origin, adding:
 *   - Origin verification (X-Origin-Verify header with shared secret)
 *   - Security headers (HSTS, CSP, X-Frame-Options, etc.)
 *   - Rate limiting (per IP, per endpoint)
 *   - Bot detection (User-Agent blocking, challenge suspicious traffic)
 *   - Geo blocking (optional)
 *   - Request/response logging (via Cloudflare Analytics)
 *
 * Deploy with: `wrangler deploy`
 * The Worker runs on *.workers.dev (free, no custom domain needed).
 */

// ─── Configuration ───────────────────────────────────────────────────────────

// The HF Space origin (backend API + UI)
const ORIGIN_URL = "https://ahmdelbaz28-ahmedetap-platform.hf.space";

// Shared secret — must match CLOUDFLARE_ORIGIN_SECRET on the HF Space
// SECURITY: Do NOT hardcode here. Set via: wrangler secret put ORIGIN_VERIFY_SECRET
const ORIGIN_VERIFY_SECRET = undefined; // Fallback only — use env.ORIGIN_VERIFY_SECRET

// Rate limiting: max requests per window per IP
const RATE_LIMIT_AUTH = 10;      // /api/v1/auth/* — 10 req/min
const RATE_LIMIT_API = 300;      // /api/* — 300 req/min
const RATE_LIMIT_WINDOW = 60;    // 60 seconds

// Blocked user agents (malicious tools)
const BLOCKED_UA_PATTERNS = [
  /sqlmap/i,
  /nikto/i,
  /nmap/i,
  /masscan/i,
  /dirb/i,
  /gobuster/i,
  /wpscan/i,
  /hydra/i,
  /burp/i,
  /acunetix/i,
  /nessus/i,
  /zgrab/i,
  /semrushbot/i,    // Uncomment to block SEO bots
];

// Blocked countries (ISO 3166-1 alpha-2). Empty set = no blocking.
// SonarCloud javascript:S7776: a Set is the right shape for an existence
// check (`BLOCKED_COUNTRIES.has(country)` is O(1) and self-documenting).
const BLOCKED_COUNTRIES = new Set([
  // "CN", "RU", "KP", "IR"
]);

// ─── Rate Limiting (in-memory per Worker isolate) ────────────────────────────

const rateLimitStore = new Map();

function checkRateLimit(clientIP, limit, windowSec) {
  const now = Date.now();
  const windowStart = now - windowSec * 1000;

  let entries = rateLimitStore.get(clientIP) || [];
  entries = entries.filter(t => t > windowStart);

  if (entries.length >= limit) {
    rateLimitStore.set(clientIP, entries);
    return false;
  }

  // Record this request and store
  entries.push(now);
  rateLimitStore.set(clientIP, entries);
  return true;
}

// Periodic cleanup of stale rate-limit entries (every 5 min)
let lastCleanup = Date.now();
function maybeCleanupRateLimitStore() {
  const now = Date.now();
  if (now - lastCleanup < 300_000) return; // 5 minutes
  lastCleanup = now;
  const cutoff = now - RATE_LIMIT_WINDOW * 1000;
  for (const [ip, entries] of rateLimitStore) {
    const filtered = entries.filter(t => t > cutoff);
    if (filtered.length === 0) {
      rateLimitStore.delete(ip);
    } else {
      rateLimitStore.set(ip, filtered);
    }
  }
}

// ─── Pre-forward guards (module scope so the main fetch handler stays
// below SonarCloud javascript:S3776 cognitive-complexity threshold) ────────

// SQL-injection signatures checked against the lower-cased query string.
const SQLI_PATTERNS = [
  /union\s+select/,
  /or\s+1\s*=\s*1/,
  /'\s*or\s*'/,
  /drop\s+table/,
  /insert\s+into/,
  /delete\s+from/,
];

// XSS signatures checked against the lower-cased query string.
const XSS_PATTERNS = [
  /<script/i,
  /javascript:/i,
  /onerror\s*=/i,
  /onload\s*=/i,
  /<iframe/i,
  /document\.cookie/i,
];

// Regex for static asset file extensions (used for caching).
const STATIC_ASSET_PATTERN = /\.(js|css|png|jpg|svg|woff2?)$/;

/**
 * Build a small JSON "block" response. Centralised so the main fetch
 * handler doesn't repeat the Response boilerplate for every guard.
 */
function blockResponse(detail, status, rayID, reason) {
  return new Response(JSON.stringify({ detail, cf_ray: rayID }), {
    status,
    headers: { "Content-Type": "application/json", "X-Block-Reason": reason },
  });
}

function blockIfGeoBlocked(country, rayID) {
  if (BLOCKED_COUNTRIES.size > 0 && BLOCKED_COUNTRIES.has(country)) {
    return new Response(JSON.stringify({
      detail: "This service is not available in your region.",
      cf_ray: rayID,
      country: country,
    }), {
      status: 451,
      headers: { "Content-Type": "application/json", "X-Block-Reason": "geo-block" },
    });
  }
  return null;
}

function blockIfMaliciousUA(userAgent, rayID) {
  for (const pattern of BLOCKED_UA_PATTERNS) {
    if (pattern.test(userAgent)) {
      return blockResponse("Blocked: malicious user agent.", 403, rayID, "bad-ua");
    }
  }
  return null;
}

function enforceRateLimit(path, clientIP, rayID) {
  if (path.startsWith("/api/v1/auth/")) {
    if (!checkRateLimit(clientIP, RATE_LIMIT_AUTH, RATE_LIMIT_WINDOW)) {
      return new Response(JSON.stringify({
        detail: "Too many authentication attempts. Please try again later.",
        cf_ray: rayID,
      }), {
        status: 429,
        headers: {
          "Content-Type": "application/json",
          "Retry-After": String(RATE_LIMIT_WINDOW),
          "X-Block-Reason": "rate-limit-auth",
        },
      });
    }
    return null;
  }
  if (path.startsWith("/api/")) {
    if (!checkRateLimit(clientIP, RATE_LIMIT_API, RATE_LIMIT_WINDOW)) {
      return new Response(JSON.stringify({
        detail: "Rate limit exceeded. Please slow down.",
        cf_ray: rayID,
      }), {
        status: 429,
        headers: {
          "Content-Type": "application/json",
          "Retry-After": String(RATE_LIMIT_WINDOW),
          "X-Block-Reason": "rate-limit-api",
        },
      });
    }
  }
  return null;
}

function blockIfMaliciousQuery(queryString, path, rayID) {
  for (const pattern of SQLI_PATTERNS) {
    if (pattern.test(queryString)) {
      return blockResponse("Blocked: SQL injection pattern detected.", 403, rayID, "sqli");
    }
  }
  for (const pattern of XSS_PATTERNS) {
    if (pattern.test(queryString)) {
      return blockResponse("Blocked: XSS pattern detected.", 403, rayID, "xss");
    }
  }
  if (path.includes("../") || path.includes("..\\") || path.includes("%2e%2e")) {
    return blockResponse("Blocked: path traversal detected.", 403, rayID, "path-traversal");
  }
  return null;
}

function applySecurityHeaders(response, rayID) {
  response.headers.set("Strict-Transport-Security", "max-age=31536000; includeSubDomains; preload");
  response.headers.set("X-Content-Type-Options", "nosniff");
  response.headers.set("X-Frame-Options", "SAMEORIGIN");
  response.headers.set("Referrer-Policy", "strict-origin-when-cross-origin");
  response.headers.set("Permissions-Policy", "geolocation=(), microphone=(), camera=(), payment=()");
  response.headers.set("Content-Security-Policy",
    "default-src 'self'; " +
    "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net; " +
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; " +
    "img-src 'self' data: https:; " +
    "font-src 'self' data: https://cdn.jsdelivr.net; " +
    "connect-src 'self'"
  );
  response.headers.set("CF-RAY", rayID);
  return response;
}

// ─── Main Handler ────────────────────────────────────────────────────────────

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const path = url.pathname;
    const clientIP = request.headers.get("CF-Connecting-IP") || "unknown";
    const country = request.headers.get("CF-IPCountry") || "";
    const userAgent = request.headers.get("User-Agent") || "";
    const rayID = request.headers.get("CF-RAY") || crypto.randomUUID();

    // ── 1. Block direct origin access (Host header check) ───────────────
    // This Worker runs on *.workers.dev — requests to the HF Space origin
    // directly should be blocked at the origin (via CLOUDFLARE_ORIGIN_SECRET).

    // ── 2. Geo blocking ─────────────────────────────────────────────────
    const geoBlock = blockIfGeoBlocked(country, rayID);
    if (geoBlock) return geoBlock;

    // ── 3. Block malicious User-Agents ──────────────────────────────────
    const uaBlock = blockIfMaliciousUA(userAgent, rayID);
    if (uaBlock) return uaBlock;

    // ── 4. Rate limiting ────────────────────────────────────────────────
    maybeCleanupRateLimitStore();
    const rateLimitBlock = enforceRateLimit(path, clientIP, rayID);
    if (rateLimitBlock) return rateLimitBlock;

    // ── 5-7. Block SQL injection / XSS / path traversal ─────────────────
    const maliciousBlock = blockIfMaliciousQuery(url.search.toLowerCase(), path, rayID);
    if (maliciousBlock) return maliciousBlock;

    // ── 8. Forward request to origin with verification header ───────────
    const originRequest = new Request(ORIGIN_URL + path + url.search, request);
    originRequest.headers.set("X-Origin-Verify", env.ORIGIN_VERIFY_SECRET || ORIGIN_VERIFY_SECRET);

    try {
      const originResponse = await fetch(originRequest, {
        cf: {
          // Don't cache API responses — they're dynamic and user-specific
          cacheEverything: path.startsWith("/assets/") || STATIC_ASSET_PATTERN.test(path),
          cacheTtl: path.startsWith("/assets/") ? 31536000 : 0,  // 1 year for static assets
        },
      });

      // ── 9. Add security headers to the response ──────────────────────
      const response = new Response(originResponse.body, originResponse);
      applySecurityHeaders(response, rayID);

      // Cache static assets for 1 year (immutable — Vite uses content-hashed filenames)
      if (path.startsWith("/assets/") || STATIC_ASSET_PATTERN.test(path)) {
        response.headers.set("Cache-Control", "public, max-age=31536000, immutable");
      }

      // Never cache API responses
      if (path.startsWith("/api/")) {
        response.headers.set("Cache-Control", "no-store, no-cache, must-revalidate, proxy-revalidate");
      }

      return response;

    } catch (err) {
      // SonarCloud javascript:S2486: surface the backend error in the Worker
      // logs (the client response is still the generic 502 so we don't leak
      // origin internals to attackers).
      console.error(`[worker] origin fetch failed (cf_ray=${rayID}):`, err?.message || err);
      return new Response(JSON.stringify({
        detail: "Backend service temporarily unavailable.",
        cf_ray: rayID,
      }), {
        status: 502,
        headers: { "Content-Type": "application/json", "X-Block-Reason": "origin-unreachable" },
      });
    }
  },
};
