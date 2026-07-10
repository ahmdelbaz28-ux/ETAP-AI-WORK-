/**
 * Cloudflare Worker — Secure Reverse Proxy + R2 Storage for AhmedETAP Platform
 *
 * This Worker adds R2 storage capabilities to the proxy:
 *   - /api/v1/storage/upload — upload files to R2
 *   - /api/v1/storage/download/:key — download files from R2
 *   - /api/v1/storage/list — list files in a prefix
 *   - /api/v1/storage/delete/:key — delete a file
 *   - /api/v1/storage/presign/:key — generate a presigned URL
 *
 * Storage routes require JWT authentication (handled by the origin).
 * The Worker passes R2 operations through to the origin's r2_storage.py
 * module which uses the S3-compatible API.
 *
 * For direct R2 access from the Worker (faster, no origin round-trip),
 * bind the R2 bucket to the Worker in wrangler.toml:
 *   [[r2_buckets]]
 *   binding = "STORAGE"
 *   bucket_name = "ahmedetap-storage"
 */

// ─── Configuration ───────────────────────────────────────────────────────────

const ORIGIN_URL = "https://ahmdelbaz28-ahmedetap-platform.hf.space";
const R2_PUBLIC_URL = "https://storage.ahmed.net"; // Set after custom domain is configured

// ─── Main Handler ────────────────────────────────────────────────────────────

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const path = url.pathname;
    const method = request.method;
    const clientIP = request.headers.get("CF-Connecting-IP") || "unknown";
    const country = request.headers.get("CF-IPCountry") || "";
    const userAgent = request.headers.get("User-Agent") || "";
    const rayID = request.headers.get("CF-RAY") || crypto.randomUUID();

    // ── Direct R2 access routes (bypass origin for speed) ──────────────
    // These routes use the Worker's R2 binding directly (no S3 API needed)
    if (path.startsWith("/storage/") && env.STORAGE) {
      return handleR2Request(request, env, path, method, rayID);
    }

    // ── Forward all other requests to origin (existing proxy logic) ────
    return forwardToOrigin(request, env, url, path, rayID, clientIP, country, userAgent);
  },
};

// ─── R2 Direct Access Handler ────────────────────────────────────────────────

async function handleR2Request(request, env, path, method, rayID) {
  // Extract the object key from the path: /storage/<key>
  const key = decodeURIComponent(path.replace("/storage/", ""));

  if (!key) {
    return jsonResponse({ detail: "Missing object key", cf_ray: rayID }, 400);
  }

  try {
    switch (method) {
      case "GET": {
        // Download object from R2
        const object = await env.STORAGE.get(key);
        if (!object) {
          return jsonResponse({ detail: "Object not found", cf_ray: rayID }, 404);
        }
        const headers = new Headers();
        object.writeHttpMetadata(headers);
        headers.set("Cache-Control", "public, max-age=31536000, immutable");
        headers.set("CF-RAY", rayID);
        headers.set("X-Storage-Backend", "cloudflare-r2");
        return new Response(object.body, { headers });
      }

      case "PUT": {
        // Upload object to R2 (max 100MB per Worker)
        const contentType = request.headers.get("Content-Type") || "application/octet-stream";
        const body = await request.arrayBuffer();
        if (body.byteLength > 100 * 1024 * 1024) {
          return jsonResponse({ detail: "File too large (max 100MB)", cf_ray: rayID }, 413);
        }
        await env.STORAGE.put(key, body, {
          httpMetadata: { contentType },
          customMetadata: {
            uploadedAt: new Date().toISOString(),
            uploadedBy: request.headers.get("CF-Connecting-IP") || "unknown",
          },
        });
        return jsonResponse({
          key: key,
          size: body.byteLength,
          contentType: contentType,
          url: `${R2_PUBLIC_URL}/${key}`,
          cf_ray: rayID,
        }, 201);
      }

      case "DELETE": {
        await env.STORAGE.delete(key);
        return jsonResponse({ detail: "Deleted", key: key, cf_ray: rayID }, 200);
      }

      case "HEAD": {
        const object = await env.STORAGE.head(key);
        if (!object) {
          return jsonResponse({ detail: "Object not found", cf_ray: rayID }, 404);
        }
        return new Response(null, {
          headers: {
            "Content-Length": object.size.toString(),
            "Content-Type": object.httpMetadata?.contentType || "application/octet-stream",
            "Last-Modified": object.uploaded?.toUTCString() || "",
            "CF-RAY": rayID,
          },
        });
      }

      default:
        return jsonResponse({ detail: "Method not allowed", cf_ray: rayID }, 405);
    }
  } catch (err) {
    return jsonResponse({
      detail: "R2 operation failed",
      error: err.message,
      cf_ray: rayID,
    }, 500);
  }
}

// ─── Origin Proxy Handler (existing logic) ──────────────────────────────────

async function forwardToOrigin(request, env, url, path, rayID, clientIP, country, userAgent) {
  // Block malicious User-Agents
  const blockedUA = [/sqlmap/i, /nikto/i, /nmap/i, /masscan/i, /dirb/i, /gobuster/i, /wpscan/i, /hydra/i, /burp/i, /acunetix/i, /nessus/i, /zgrab/i];
  for (const pattern of blockedUA) {
    if (pattern.test(userAgent)) {
      return jsonResponse({ detail: "Blocked: malicious user agent.", cf_ray: rayID }, 403);
    }
  }

  // Rate limiting
  const rateLimitStore = forwardToOrigin.rateLimitStore || new Map();
  forwardToOrigin.rateLimitStore = rateLimitStore;

  function checkRateLimit(ip, limit, windowSec) {
    const now = Date.now();
    const windowStart = now - windowSec * 1000;
    let entries = rateLimitStore.get(ip) || [];
    entries = entries.filter(t => t > windowStart);
    if (entries.length >= limit) {
      rateLimitStore.set(ip, entries);
      return false;
    }
    entries.push(now);
    rateLimitStore.set(ip, entries);
    return true;
  }

  if (path.startsWith("/api/v1/auth/")) {
    if (!checkRateLimit(clientIP, 10, 60)) {
      return jsonResponse({ detail: "Too many auth attempts.", cf_ray: rayID }, 429, { "Retry-After": "60" });
    }
  } else if (path.startsWith("/api/")) {
    if (!checkRateLimit(clientIP, 300, 60)) {
      return jsonResponse({ detail: "Rate limit exceeded.", cf_ray: rayID }, 429, { "Retry-After": "60" });
    }
  }

  // SQL injection / XSS / path traversal blocking (existing logic)
  const queryString = url.search.toLowerCase();
  if (/union\s+select|or\s+1\s*=\s*1|'\s*or\s*'|drop\s+table|insert\s+into/.test(queryString)) {
    return jsonResponse({ detail: "Blocked: SQL injection.", cf_ray: rayID }, 403);
  }
  if (/<script|javascript:|onerror\s*=|<iframe|document\.cookie/i.test(queryString)) {
    return jsonResponse({ detail: "Blocked: XSS.", cf_ray: rayID }, 403);
  }
  if (path.includes("../") || path.includes("..\\") || path.includes("%2e%2e")) {
    return jsonResponse({ detail: "Blocked: path traversal.", cf_ray: rayID }, 403);
  }

  // Forward to origin
  const originRequest = new Request(ORIGIN_URL + path + url.search, request);
  originRequest.headers.set("X-Origin-Verify", env.ORIGIN_VERIFY_SECRET);

  try {
    const originResponse = await fetch(originRequest, {
      cf: {
        cacheEverything: path.startsWith("/assets/") || path.match(/\.(js|css|png|jpg|svg|woff2?)$/),
        cacheTtl: path.startsWith("/assets/") ? 31536000 : 0,
      },
    });

    const response = new Response(originResponse.body, originResponse);
    response.headers.set("Strict-Transport-Security", "max-age=31536000; includeSubDomains; preload");
    response.headers.set("X-Content-Type-Options", "nosniff");
    response.headers.set("X-Frame-Options", "SAMEORIGIN");
    response.headers.set("Referrer-Policy", "strict-origin-when-cross-origin");
    response.headers.set("Permissions-Policy", "geolocation=(), microphone=(), camera=(), payment=()");
    response.headers.set("Content-Security-Policy",
      "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net; " +
      "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data: https:; " +
      "font-src 'self' data: https://cdn.jsdelivr.net; connect-src 'self'"
    );
    response.headers.set("CF-RAY", rayID);

    if (path.startsWith("/assets/") || path.match(/\.(js|css|png|jpg|svg|woff2?)$/)) {
      response.headers.set("Cache-Control", "public, max-age=31536000, immutable");
    }
    if (path.startsWith("/api/")) {
      response.headers.set("Cache-Control", "no-store, no-cache, must-revalidate");
    }

    return response;
  } catch (err) {
    return jsonResponse({ detail: "Backend unavailable.", cf_ray: rayID }, 502);
  }
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function jsonResponse(data, status, extraHeaders = {}) {
  return new Response(JSON.stringify(data), {
    status: status,
    headers: {
      "Content-Type": "application/json",
      ...extraHeaders,
    },
  });
}
