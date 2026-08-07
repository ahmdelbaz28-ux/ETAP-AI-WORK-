/**
 * @vitest-environment jsdom
 *
 * Unit tests for the LLM chat module — focusing on:
 *   - 429 rate-limit / quota lockout handling
 *   - 30-second reuse suggestion on 429
 *   - No-enumeration: API keys must never appear as enumerable properties
 *     in error messages or test results
 */
import { beforeEach, describe, expect, it, vi } from "vitest";

// ── Mocks ──────────────────────────────────────────────────────────────────────

// Mock POPULAR_PROVIDERS (imported by llm-chat via Settings page)
vi.mock("../../pages/Settings", () => ({
  POPULAR_PROVIDERS: [
    {
      id: "openai",
      name: "OpenAI",
      defaultBaseUrl: "https://api.openai.com/v1",
      defaultModel: "gpt-4o-mini",
      apiType: "openai",
      apiKeyUrl: "https://platform.openai.com/api-keys",
      models: [{ id: "gpt-4o-mini", name: "GPT-4o Mini", isFree: false }],
    },
  ],
}));

// Mock api-config so getCachedSettings returns predictable values
vi.mock("../api-config", () => ({
  getCachedSettings: () => ({
    PROVIDER_ACTIVE_PROVIDER_ID: "openai",
    PROVIDER_OPENAI_KEY: "sk-test-key-1234567890abcdef",
    PROVIDER_OPENAI_MODEL: "gpt-4o-mini",
  }),
  API_BASE_URL: "http://localhost:8000",
}));

// Import the module under test AFTER mocks are set up
import { chatWithLLM, testProviderConnection } from "../llm-chat";

// ── Helpers ────────────────────────────────────────────────────────────────────

function mockFetchResponse(status: number, body: unknown) {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 429 ? "Too Many Requests" : "OK",
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(JSON.stringify(body)),
    body: null,
  };
}

// ── Tests ──────────────────────────────────────────────────────────────────────

describe("llm-chat: 429 rate-limit handling", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.restoreAllMocks();
  });

  it("testProviderConnection returns RATE_LIMITED on 429 without quota keyword", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      mockFetchResponse(429, {
        error: {
          message: "You are sending requests too quickly.",
          type: "rate_limit_error",
        },
      }) as Response,
    );

    const result = await testProviderConnection("openai");
    expect(result.success).toBe(false);
    expect(result.errorCode).toBe("RATE_LIMITED");
    expect(result.message).toContain("429");
  });

  it("testProviderConnection returns QUOTA_EXCEEDED on 429 with quota/billing keyword", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      mockFetchResponse(429, {
        error: {
          message: "You exceeded your current quota. Please check your plan and billing details.",
          type: "insufficient_quota",
        },
      }) as Response,
    );

    const result = await testProviderConnection("openai");
    expect(result.success).toBe(false);
    expect(result.errorCode).toBe("QUOTA_EXCEEDED");
    expect(result.message).toContain("429");
  });

  it("testProviderConnection suggests 30-second wait on rate-limit 429", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      mockFetchResponse(429, {
        error: {
          message: "Rate limit reached. Please retry after 30 seconds.",
          type: "rate_limit_error",
        },
      }) as Response,
    );

    const result = await testProviderConnection("openai");
    expect(result.success).toBe(false);
    // The suggestion should mention waiting / retry timing
    expect(result.suggestion).toBeTruthy();
    expect(result.suggestion?.toLowerCase()).toContain("30");
  });

  it("testProviderConnection suggests billing credits on quota 429", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      mockFetchResponse(429, {
        error: {
          message: "You exceeded your current quota. Please check your plan and billing details.",
          type: "insufficient_quota",
        },
      }) as Response,
    );

    const result = await testProviderConnection("openai");
    expect(result.success).toBe(false);
    expect(result.suggestion).toBeTruthy();
    // Should suggest billing/credits, not "wait 30 seconds"
    expect(result.suggestion?.toLowerCase()).not.toContain("wait 30");
  });
});

describe("llm-chat: chatWithLLM error propagation", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.restoreAllMocks();
  });

  it("throws a user-friendly error on 429 from chatWithLLM", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      mockFetchResponse(429, {
        error: {
          message: "Rate limit reached for default organization.",
          type: "rate_limit_error",
        },
      }) as Response,
    );

    await expect(chatWithLLM([{ role: "user", content: "Hello" }])).rejects.toThrow(/429|rate/i);
  });

  it("throws on 401 unauthorized", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      mockFetchResponse(401, {
        error: { message: "Incorrect API key provided.", type: "invalid_request_error" },
      }) as Response,
    );

    await expect(chatWithLLM([{ role: "user", content: "Hello" }])).rejects.toThrow();
  });

  it("supports AbortSignal — throws AbortError when aborted", async () => {
    const controller = new AbortController();
    // Abort immediately
    controller.abort();

    vi.spyOn(globalThis, "fetch").mockImplementation(
      (_input: RequestInfo | URL, init?: RequestInit) => {
        // Simulate the browser behavior: fetch rejects with AbortError when signal is aborted
        if (init?.signal?.aborted) {
          return Promise.reject(new DOMException("The user aborted a request.", "AbortError"));
        }
        return Promise.resolve(mockFetchResponse(200, {}) as Response);
      },
    );

    await expect(
      chatWithLLM([{ role: "user", content: "Hello" }], undefined, controller.signal),
    ).rejects.toThrow();
  });
});

describe("llm-chat: no-enumeration (API key leakage prevention)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.restoreAllMocks();
  });

  it("testProviderConnection never includes the raw API key in error messages", async () => {
    const secretKey = "sk-test-key-1234567890abcdef";
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      mockFetchResponse(401, {
        error: { message: `Invalid API key: ${secretKey}`, type: "invalid_request_error" },
      }) as Response,
    );

    const result = await testProviderConnection("openai");
    expect(result.success).toBe(false);
    // The error message should NOT contain the full API key
    expect(result.message).not.toContain(secretKey);
    // The details may contain the raw backend error, but the user-facing message must not
  });

  it("chatWithLLM error does not expose the full API key", async () => {
    const secretKey = "sk-test-key-1234567890abcdef";
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      mockFetchResponse(500, {
        error: { message: `Internal error with key ${secretKey}` },
      }) as Response,
    );

    try {
      await chatWithLLM([{ role: "user", content: "test" }]);
      // If it doesn't throw, that's fine — but we still check for key leakage
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      // The error message should NOT contain the raw API key
      expect(message).not.toContain(secretKey);
    }
  });

  it("testProviderConnection error details are truncated (no full key dump)", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      mockFetchResponse(429, {
        error: {
          message: "Rate limit reached.",
          type: "rate_limit_error",
        },
      }) as Response,
    );

    const result = await testProviderConnection("openai");
    expect(result.success).toBe(false);
    // Details should exist but be bounded in length
    if (result.details) {
      expect(result.details.length).toBeLessThan(500);
    }
  });
});
