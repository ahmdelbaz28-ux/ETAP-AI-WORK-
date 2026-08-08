/**
 * Shared fetch helper for admin/debug pages.
 *
 * Replaces the per-page `magicFetch` / `mfaFetch` / `otpFetch` /
 * `digestFetch` helpers that were copy-pasted across MagicLinks.tsx,
 * Mfa.tsx, EmailOtp.tsx, EmailDigest.tsx.
 *
 * Differences from the old per-page helpers:
 * - Throws a typed `AdminFetchError` instead of a bare `Error`. The
 *   error carries `status`, `detail` (a composed human-readable
 *   string), and `bodyText` (the raw response body, capped at 200
 *   chars) so callers can branch on HTTP status if needed.
 * - On non-JSON success responses (e.g. HTML preview), the caller
 *   must opt in via the `allowPlainText` option. Previously the
 *   helpers did `return text as unknown as T;` which silently
 *   returned a string where the caller expected a JSON shape, then
 *   `res.success` was `undefined` and the UI showed "Failed" with no
 *   useful message. Now the caller gets a thrown error unless they
 *   explicitly accept a plain-text return.
 *
 * Ref: fix/admin-pages-hardening (#4 + #6)
 */

import { API_BASE_URL } from "./api-config";
import { getAuthToken } from "./tokenStorage";

/**
 * Typed error thrown by `adminFetch` on any non-OK response, or on
 * a JSON-parse failure. The `status` field is `number | null` —
 * `null` means the fetch itself failed (network error) or the
 * response was OK but the body was not JSON and `allowPlainText`
 * was not set.
 */
export class AdminFetchError extends Error {
  readonly status: number | null;
  readonly detail: string;
  readonly bodyText: string;

  constructor(
    message: string,
    opts: { status?: number | null; detail?: string; bodyText?: string } = {},
  ) {
    super(message);
    this.name = "AdminFetchError";
    this.status = opts.status ?? null;
    this.detail = opts.detail ?? message;
    this.bodyText = opts.bodyText ?? "";
  }
}

/**
 * Build the Authorization header from the stored JWT, if any.
 * Exported so callers that need raw `fetch` (e.g. for streaming)
 * can still reuse the same auth logic.
 */
export function authHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const token = getAuthToken();
  return {
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...extra,
  };
}

/**
 * Merge caller-supplied headers (in any of the three RequestInit
 * shapes — Headers, tuple array, or plain object) into a flat
 * Record<string, string>. Used internally by `adminFetch`; exported
 * for callers that need to replicate the merge logic.
 */
export function mergeHeaders(
  callerHeaders: Headers | [string, string][] | Record<string, string> | undefined,
  base: Record<string, string>,
): Record<string, string> {
  const merged: Record<string, string> = { ...base };
  if (callerHeaders instanceof Headers) {
    callerHeaders.forEach((v, k) => {
      merged[k] = v;
    });
  } else if (Array.isArray(callerHeaders)) {
    for (const [k, v] of callerHeaders) {
      merged[k] = v;
    }
  } else if (callerHeaders && typeof callerHeaders === "object") {
    Object.assign(merged, callerHeaders);
  }
  return merged;
}

/**
 * Fetch a JSON (or plain-text, with `allowPlainText`) endpoint from
 * the admin API. Throws `AdminFetchError` on any failure.
 *
 * @param path    Path under API_BASE_URL, e.g. "/api/v1/auth/mfa/totp/setup"
 * @param init    Standard RequestInit (method, body, headers, signal, …)
 * @param opts    Options:
 *                - allowPlainText: if true, return the raw response
 *                  text when the body is not valid JSON. Required for
 *                  endpoints like GET /email-digest/preview/{email}
 *                  that return HTML.
 */
export async function adminFetch<T>(
  path: string,
  init?: RequestInit,
  opts: { allowPlainText?: boolean } = {},
): Promise<T> {
  const baseHeaders: Record<string, string> = {
    "Content-Type": "application/json",
    ...authHeaders(),
  };
  const mergedHeaders = mergeHeaders(init?.headers, baseHeaders);

  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: mergedHeaders,
    });
  } catch (err) {
    // Network error (DNS, offline, CORS preflight failure, …).
    throw new AdminFetchError(err instanceof Error ? err.message : "Network request failed", {
      status: null,
      detail: err instanceof Error ? err.message : "Network request failed",
      bodyText: "",
    });
  }

  const text = await res.text().catch(() => "");

  if (!res.ok) {
    // Try to extract a structured error message from the JSON body.
    let detail = `HTTP ${res.status}`;
    let parsed: unknown = null;
    try {
      parsed = JSON.parse(text);
    } catch {
      // Not JSON — fall through to plain-text handling.
    }
    if (parsed && typeof parsed === "object") {
      const p = parsed as Record<string, unknown>;
      if (typeof p.detail === "string") detail = `${detail}: ${p.detail}`;
      else if (typeof p.message === "string") detail = `${detail}: ${p.message}`;
      else if (typeof p.error === "string") detail = `${detail}: ${p.error}`;
    } else if (text) {
      detail = `${detail}: ${text.slice(0, 200)}`;
    }
    throw new AdminFetchError(detail, {
      status: res.status,
      detail,
      bodyText: text.slice(0, 200),
    });
  }

  // Success — try JSON first.
  try {
    return JSON.parse(text) as T;
  } catch {
    if (opts.allowPlainText) {
      return text as unknown as T;
    }
    // Body is not JSON and the caller did not opt in. This is the
    // path that previously returned `text as unknown as T` silently;
    // now it throws so the caller sees a real error instead of a
    // string-where-object-was-expected.
    throw new AdminFetchError(
      `Response was not valid JSON (length ${text.length}). If this endpoint returns plain text, pass { allowPlainText: true }.`,
      {
        status: res.status,
        detail: `Non-JSON response (length ${text.length})`,
        bodyText: text.slice(0, 200),
      },
    );
  }
}
