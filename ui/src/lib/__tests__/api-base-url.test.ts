/**
 * @vitest-environment jsdom
 *
 * Unit tests for resolveApiBaseUrl and apiUrl in ui/src/lib/api-base-url.ts.
 *
 * Proves the 5 mandatory contract scenarios:
 * 1. Valid Staging URL via VITE_API_URL.
 * 2. Missing VITE_API_URL on Staging host (strict fail-closed rejection of production fallback).
 * 3. Accidental production URL provided to Staging build (fail-closed rejection).
 * 4. Intended production URL in standalone preview (not staging, not localhost).
 * 5. Local development and same-origin behavior (localhost, 127.0.0.1, .hf.space).
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

describe("api-base-url resolution contracts", () => {
  const originalLocation = window.location;
  const originalConsoleError = console.error;

  beforeEach(() => {
    vi.restoreAllMocks();
    console.error = vi.fn();
  });

  afterEach(() => {
    // Restore window.location
    Object.defineProperty(window, "location", {
      value: originalLocation,
      writable: true,
      configurable: true,
    });
    console.error = originalConsoleError;
    vi.unstubAllEnvs();
  });

  function setWindowHostname(hostname: string) {
    Object.defineProperty(window, "location", {
      value: {
        ...originalLocation,
        hostname,
      },
      writable: true,
      configurable: true,
    });
  }

  it("1. resolves to exact Staging URL when VITE_API_URL is configured", async () => {
    vi.stubEnv("MODE", "staging");
    vi.stubEnv("VITE_API_URL", "https://staging-api.example.com");
    setWindowHostname("etap-ai-work-staging.vercel.app");

    const { resolveApiBaseUrl } = await import("../api-base-url");
    const result = resolveApiBaseUrl();

    expect(result).toBe("https://staging-api.example.com");
    expect(console.error).not.toHaveBeenCalled();
  });

  it("2. fails closed (empty string) when running on Staging host without VITE_API_URL", async () => {
    vi.stubEnv("MODE", "staging");
    vi.stubEnv("VITE_API_URL", "");
    setWindowHostname("etap-ai-work-staging.vercel.app");

    const { resolveApiBaseUrl } = await import("../api-base-url");
    const result = resolveApiBaseUrl();

    expect(result).toBe("");
    expect(console.error).toHaveBeenCalledWith(
      expect.stringContaining("[API GUARD] Running on Staging host without explicit VITE_API_URL")
    );
  });

  it("3. rejects accidental production HF Space URL when configured in Staging mode", async () => {
    vi.stubEnv("MODE", "staging");
    vi.stubEnv("VITE_API_URL", "https://ahmdelbaz28-ahmedetap-platform.hf.space");
    setWindowHostname("etap-ai-work-staging.vercel.app");

    const { resolveApiBaseUrl } = await import("../api-base-url");
    const result = resolveApiBaseUrl();

    expect(result).toBe("");
    expect(console.error).toHaveBeenCalledWith(
      expect.stringContaining("[API GUARD] Rejecting production API fallback in Staging deployment")
    );
  });

  it("4. defaults to production HF Space URL for standalone production preview", async () => {
    vi.stubEnv("MODE", "production");
    vi.stubEnv("VITE_API_URL", "");
    setWindowHostname("ahmedetap-platform.vercel.app");

    const { resolveApiBaseUrl } = await import("../api-base-url");
    const result = resolveApiBaseUrl();

    expect(result).toBe("https://ahmdelbaz28-ahmedetap-platform.hf.space");
    expect(console.error).not.toHaveBeenCalled();
  });

  it("5. uses same-origin (empty string) in local dev environments (localhost / 127.0.0.1)", async () => {
    vi.stubEnv("MODE", "development");
    vi.stubEnv("VITE_API_URL", "");

    for (const host of ["localhost", "127.0.0.1", "0.0.0.0", "custom-space.hf.space"]) {
      setWindowHostname(host);
      const { resolveApiBaseUrl } = await import("../api-base-url");
      const result = resolveApiBaseUrl();
      expect(result).toBe("");
    }
  });

  it("6. formats apiUrl correctly with base URL", async () => {
    const { apiUrl } = await import("../api-base-url");
    const path = "/api/v1/healthz";
    const result = apiUrl(path);
    expect(result).toContain("/api/v1/healthz");
  });
});
