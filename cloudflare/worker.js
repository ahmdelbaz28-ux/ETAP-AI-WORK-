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
// Set this via `wrangler secret put ORIGIN_VERIFY_SECRET`
const ORIGIN_VERIFY_SECRET = "REPLACE_WITH_YOUR_SECRET";

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

// Blocked countries (ISO 3166-1 alpha-2). Empty array = no blocking.
// NOSONAR(javascript:S7776): array is intentional for simplicity
const BLOCKED_COUNTRIES = [
  // "CN", "RU", "KP", "IR"
];

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

  entries.push(now);
  rateLimitStore.set(clientIP, entries);
  return true;
}

// ─── Main Handler ────────────────────────────────────────────────────────────

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const path = url.pathname;
//     const method = request.method;
    const clientIP = request.headers.get("CF-Connecting-IP") || "unknown";
    const country = request.headers.get("CF-IPCountry") || "";
    const userAgent = request.headers.get("User-Agent") || "";
    const rayID = request.headers.get("CF-RAY") || crypto.randomUUID();

    // ── 1. Block direct origin access (Host header check) ───────────────
    // This Worker runs on *.workers.dev — requests to the HF Space origin
    // directly should be blocked at the origin (via CLOUDFLARE_ORIGIN_SECRET).

    // ── 2. Geo blocking ─────────────────────────────────────────────────
    if (BLOCKED_COUNTRIES.length > 0 && BLOCKED_COUNTRIES.includes(country)) {
      return new Response(JSON.stringify({
        detail: "This service is not available in your region.",
        cf_ray: rayID,
        country: country,
      }), {
        status: 451,
        headers: { "Content-Type": "application/json", "X-Block-Reason": "geo-block" },
      });
    }

    // ── 3. Block malicious User-Agents ──────────────────────────────────
    for (const pattern of BLOCKED_UA_PATTERNS) {
      if (pattern.test(userAgent)) {
        return new Response(JSON.stringify({
          detail: "Blocked: malicious user agent.",
          cf_ray: rayID,
        }), {
          status: 403,
          headers: { "Content-Type": "application/json", "X-Block-Reason": "bad-ua" },
        });
      }
    }

    // ── 4. Rate limiting ────────────────────────────────────────────────
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
    } else if (path.startsWith("/api/")) {
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

    // ── 5. Block SQL injection patterns in query params ─────────────────
    const queryString = url.search.toLowerCase();
    const sqliPatterns = [
      /union\s+select/,
      /or\s+1\s*=\s*1/,
      /'\s*or\s*'/,
      /drop\s+table/,
      /insert\s+into/,
      /delete\s+from/,
    ];
    for (const pattern of sqliPatterns) {
      if (pattern.test(queryString)) {
        return new Response(JSON.stringify({
          detail: "Blocked: SQL injection pattern detected.",
          cf_ray: rayID,
        }), {
          status: 403,
          headers: { "Content-Type": "application/json", "X-Block-Reason": "sqli" },
        });
      }
    }

    // ── 6. Block XSS patterns in query params ───────────────────────────
    const xssPatterns = [
      /<script/i,
      /javascript:/i,
      /onerror\s*=/i,
      /onload\s*=/i,
      /<iframe/i,
      /document\.cookie/i,
    ];
    for (const pattern of xssPatterns) {
      if (pattern.test(queryString)) {
        return new Response(JSON.stringify({
          detail: "Blocked: XSS pattern detected.",
          cf_ray: rayID,
        }), {
          status: 403,
          headers: { "Content-Type": "application/json", "X-Block-Reason": "xss" },
        });
      }
    }

    // ── 7. Block path traversal ─────────────────────────────────────────
    if (path.includes("../") || path.includes("..\\") || path.includes("%2e%2e")) {
      return new Response(JSON.stringify({
        detail: "Blocked: path traversal detected.",
        cf_ray: rayID,
      }), {
        status: 403,
        headers: { "Content-Type": "application/json", "X-Block-Reason": "path-traversal" },
      });
    }

    // ── 8. Forward request to origin with verification header ───────────
    const originRequest = new Request(ORIGIN_URL + path + url.search, request);

    // Inject the origin verification secret
    originRequest.headers.set("X-Origin-Verify", env.ORIGIN_VERIFY_SECRET || ORIGIN_VERIFY_SECRET);

    // Preserve real client IP (Cloudflare already sets CF-Connecting-IP)
    // The origin middleware will use CF-Connecting-IP

    try {
      const originResponse = await fetch(originRequest, {
        cf: {
          // Don't cache API responses — they're dynamic and user-specific
          cacheEverything: path.startsWith("/assets/") || path.exec(/\.(js|css|png|jpg|svg|woff2?)$/),
          cacheTtl: path.startsWith("/assets/") ? 31536000 : 0,  // 1 year for static assets
        },
      });

      // ── 9. Add security headers to the response ──────────────────────
      const response = new Response(originResponse.body, originResponse);

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

      // Add CF-RAY for correlation
      response.headers.set("CF-RAY", rayID);

      // Cache static assets for 1 year (immutable — Vite uses content-hashed filenames)
      if (path.startsWith("/assets/") || path.exec(/\.(js|css|png|jpg|svg|woff2?)$/)) {
        response.headers.set("Cache-Control", "public, max-age=31536000, immutable");
      }

      // Never cache API responses
      if (path.startsWith("/api/")) {
        response.headers.set("Cache-Control", "no-store, no-cache, must-revalidate, proxy-revalidate");
      }

      return response;

    } catch (err) {
      // Origin unreachable
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
