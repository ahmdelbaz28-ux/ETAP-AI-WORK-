/**
 * LLM Chat Module — Client-side LLM integration with CORS proxy
 *
 * Browser requests to LLM APIs are blocked by CORS. This module routes
 * ALL requests through our Vercel serverless function at /api/llm-proxy
 * which forwards them server-to-server (no CORS restriction).
 *
 * Supported API types:
 *   - openai:      OpenAI-compatible /v1/chat/completions
 *   - anthropic:   Anthropic /v1/messages with x-api-key header
 *   - gemini:      Google Gemini /v1beta/models/{model}:generateContent
 *   - cloudflare:  Cloudflare Workers AI /accounts/{account_id}/ai/run/{model}
 *   - zhipu:       Zhipu AI (GLM) OpenAI-compatible /chat/completions
 *   - cohere:      Cohere /v2/chat
 */

import { POPULAR_PROVIDERS } from "../pages/Settings";
import { apiUrl, getCachedSettings } from "./api-config";
import { testProviderKey } from "./provider-keys";
import { getAuthToken } from "./tokenStorage";

// --- section ---
export interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
}

export interface ChatResult {
  content: string;
  provider: string;
  model: string;
}

export interface ProviderConfig {
  id: string;
  name: string;
  apiKey: string;
  baseUrl: string;
  model: string;
  apiType: "openai" | "anthropic" | "gemini" | "cloudflare" | "zhipu" | "cohere";
}

// --- section ---
// Routes the request through our Vercel serverless function to bypass CORS.
async function proxyFetch(
  endpoint: string,
  apiKey: string,
  body: Record<string, unknown>,
  customHeaders?: Record<string, string>,
  signal?: AbortSignal,
): Promise<Response> {
  const proxyUrl = "/api/llm-proxy";
  const proxyBody = {
    endpoint,
    apiKey,
    body,
    headers: customHeaders,
  };

  const res = await fetch(proxyUrl, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(proxyBody),
    signal,
  });

  return res;
}

// --- section ---
function getSettings(): Record<string, string> {
  return getCachedSettings();
}

export function getActiveProvider(): ProviderConfig | null {
  const settings = getSettings();
  const activeId = settings.PROVIDER_ACTIVE_PROVIDER_ID || "";

  const hasCustom =
    !!settings.CUSTOM_OPENAI_API_KEY &&
    !!settings.CUSTOM_OPENAI_BASE_URL &&
    !!settings.CUSTOM_OPENAI_MODEL_ID;

  if (activeId === "custom_openai" && hasCustom) {
    return {
      id: "custom_openai",
      name: "Custom (OpenAI-compatible)",
      apiKey: settings.CUSTOM_OPENAI_API_KEY || "",
      baseUrl: (settings.CUSTOM_OPENAI_BASE_URL || "").replace(/\/$/, ""),
      model: settings.CUSTOM_OPENAI_MODEL_ID || "",
      apiType: "openai",
    };
  }

  const providersWithKeys = POPULAR_PROVIDERS.filter((p) => {
    const keyName = `PROVIDER_${p.id.toUpperCase()}_KEY`;
    return !!settings[keyName];
  });

  if (providersWithKeys.length === 0) {
    if (hasCustom) {
      return {
        id: "custom_openai",
        name: "Custom (OpenAI-compatible)",
        apiKey: settings.CUSTOM_OPENAI_API_KEY || "",
        baseUrl: (settings.CUSTOM_OPENAI_BASE_URL || "").replace(/\/$/, ""),
        model: settings.CUSTOM_OPENAI_MODEL_ID || "",
        apiType: "openai",
      };
    }
    return null;
  }

  let provider: (typeof providersWithKeys)[0];
  if (activeId) {
    const selected = providersWithKeys.find((p) => p.id === activeId);
    provider = selected || providersWithKeys[0];
  } else {
    provider = providersWithKeys[0];
  }

  const keyName = `PROVIDER_${provider.id.toUpperCase()}_KEY`;
  const model = settings[`PROVIDER_${provider.id.toUpperCase()}_MODEL`] || provider.defaultModel;
  const apiKey = settings[keyName] || "";

  return {
    id: provider.id,
    name: provider.name,
    apiKey,
    baseUrl: provider.defaultBaseUrl,
    model,
    apiType: provider.apiType,
  };
}

export function getConfiguredProviders(): { id: string; name: string; model: string }[] {
  const settings = getSettings();
  const configured = POPULAR_PROVIDERS.filter((p) => {
    const keyName = `PROVIDER_${p.id.toUpperCase()}_KEY`;
    return !!settings[keyName];
  }).map((p) => {
    return {
      id: p.id,
      name: p.name,
      model: settings[`PROVIDER_${p.id.toUpperCase()}_MODEL`] || p.defaultModel,
    };
  });

  if (
    settings.CUSTOM_OPENAI_API_KEY &&
    settings.CUSTOM_OPENAI_BASE_URL &&
    settings.CUSTOM_OPENAI_MODEL_ID
  ) {
    configured.push({
      id: "custom_openai",
      name: "Custom (OpenAI-compatible)",
      model: settings.CUSTOM_OPENAI_MODEL_ID,
    });
  }

  return configured;
}

// --- section ---

export async function chatWithLLM(
  messages: ChatMessage[],
  config?: Partial<ProviderConfig>,
  signal?: AbortSignal,
): Promise<ChatResult> {
  // SonarCloud typescript:S6582: use optional chain for cleaner null-safe access.
  const activeProvider = getActiveProvider();
  const provider = config && activeProvider ? { ...activeProvider, ...config } : activeProvider;

  if (!provider?.apiKey) {
    throw new Error("No API key configured. Go to Settings → AI Providers to connect a provider.");
  }

  switch (provider.apiType) {
    case "openai":
      return callOpenAICompatible(messages, provider, signal);
    case "anthropic":
      return callAnthropic(messages, provider, signal);
    case "gemini":
      return callGemini(messages, provider, signal);
    case "cloudflare":
      return callCloudflare(messages, provider, signal);
    case "zhipu":
      return callZhipu(messages, provider, signal);
    case "cohere":
      return callCohere(messages, provider, signal);
    default:
      throw new Error(`Unsupported provider type: ${provider.apiType}`);
  }
}

// --- section ---
async function callOpenAICompatible(
  messages: ChatMessage[],
  provider: ProviderConfig,
  signal?: AbortSignal,
): Promise<ChatResult> {
  const endpoint = `${provider.baseUrl}/chat/completions`;
  const res = await proxyFetch(
    endpoint,
    provider.apiKey,
    {
      model: provider.model,
      messages,
      max_tokens: 4096,
      temperature: 0.7,
    },
    undefined,
    signal,
  );

  if (!res.ok) {
    const text = await res.text().catch((error) => {
      console.warn("Failed to read response text:", error);
      return "Unknown error";
    });
    const redactedText = text.slice(0, 200).replace(/sk-[a-zA-Z0-9]+/g, "[REDACTED]");
    throw new Error(`${provider.name} API error ${res.status}: ${redactedText}`);
  }

  const data = await res.json();
  const content = data.choices?.[0]?.message?.content || "";
  return { content, provider: provider.name, model: provider.model };
}

// --- section ---
async function callAnthropic(
  messages: ChatMessage[],
  provider: ProviderConfig,
  signal?: AbortSignal,
): Promise<ChatResult> {
  const endpoint = `${provider.baseUrl}/messages`;
  const systemMsg = messages.find((m) => m.role === "system")?.content || "";
  const chatMessages = messages.filter((m) => m.role !== "system");

  const res = await proxyFetch(
    endpoint,
    provider.apiKey,
    {
      model: provider.model.replace("anthropic/", ""),
      max_tokens: 4096,
      system: systemMsg,
      messages: chatMessages,
    },
    {
      "x-api-key": provider.apiKey,
      "anthropic-version": "2023-06-01",
    },
    signal,
  );

  if (!res.ok) {
    const text = await res.text().catch((error) => {
      console.warn("Failed to read Anthropic response text:", error);
      return "Unknown error";
    });
    const redactedText = text.slice(0, 200).replace(/sk-[a-zA-Z0-9]+/g, "[REDACTED]");
    throw new Error(`${provider.name} API error ${res.status}: ${redactedText}`);
  }

  const data = await res.json();
  const content = data.content?.[0]?.text || "";
  return { content, provider: provider.name, model: provider.model };
}

// --- section ---
async function callGemini(
  messages: ChatMessage[],
  provider: ProviderConfig,
  signal?: AbortSignal,
): Promise<ChatResult> {
  const model = provider.model.replace("google/", "").replace("gemini/", "");
  const endpoint = `${provider.baseUrl}/models/${model}:generateContent`;

  const contents = messages
    .filter((m) => m.role !== "system")
    .map((m) => ({
      role: m.role === "assistant" ? "model" : "user",
      parts: [{ text: m.content }],
    }));

  const systemInstruction = messages.find((m) => m.role === "system");
  const body: Record<string, unknown> = {
    contents,
    generationConfig: { temperature: 0.7, maxOutputTokens: 4096 },
  };
  if (systemInstruction) {
    body.systemInstruction = { parts: [{ text: systemInstruction.content }] };
  }

  // Gemini uses x-goog-api-key header instead of ?key= in URL to avoid URL leakage
  const res = await fetch("/api/llm-proxy", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      endpoint,
      apiKey: provider.apiKey,
      body,
      headers: { "x-goog-api-key": provider.apiKey },
    }),
    signal,
  });

  if (!res.ok) {
    const text = await res.text().catch((error) => {
      console.warn("Failed to read Gemini response text:", error);
      return "Unknown error";
    });
    const redactedText = text.slice(0, 200).replace(/sk-[a-zA-Z0-9]+/g, "[REDACTED]");
    throw new Error(`${provider.name} API error ${res.status}: ${redactedText}`);
  }

  const data = await res.json();
  const content = data.candidates?.[0]?.content?.parts?.[0]?.text || "";
  return { content, provider: provider.name, model: provider.model };
}

// --- section ---
async function callCloudflare(
  messages: ChatMessage[],
  provider: ProviderConfig,
  signal?: AbortSignal,
): Promise<ChatResult> {
  const settings = getSettings();
  const accountId = settings.PROVIDER_CLOUDFLARE_ACCOUNT_ID || "";
  if (!accountId) {
    throw new Error("Cloudflare requires an Account ID. Please add it in Settings.");
  }

  const url = `${provider.baseUrl}/${accountId}/ai/run/${provider.model}`;
  const res = await proxyFetch(url, provider.apiKey, { messages }, undefined, signal);

  if (!res.ok) {
    const text = await res.text().catch((error) => {
      console.warn("Failed to read Cloudflare response text:", error);
      return "Unknown error";
    });
    const redactedText = text.slice(0, 200).replace(/sk-[a-zA-Z0-9]+/g, "[REDACTED]");
    throw new Error(`${provider.name} API error ${res.status}: ${redactedText}`);
  }

  const data = await res.json();
  const content = data.result?.response || "";
  return { content, provider: provider.name, model: provider.model };
}

// --- section ---
// Zhipu uses the same OpenAI-compatible /chat/completions API shape.
async function callZhipu(
  messages: ChatMessage[],
  provider: ProviderConfig,
  signal?: AbortSignal,
): Promise<ChatResult> {
  return callOpenAICompatible(messages, provider, signal);
}

// --- section ---
async function callCohere(
  messages: ChatMessage[],
  provider: ProviderConfig,
  signal?: AbortSignal,
): Promise<ChatResult> {
  const endpoint = `${provider.baseUrl}/chat`;
  const res = await proxyFetch(
    endpoint,
    provider.apiKey,
    {
      model: provider.model,
      messages,
    },
    undefined,
    signal,
  );

  if (!res.ok) {
    const text = await res.text().catch((error) => {
      console.warn("Failed to read Cohere response text:", error);
      return "Unknown error";
    });
    const redactedText = text.slice(0, 200).replace(/sk-[a-zA-Z0-9]+/g, "[REDACTED]");
    throw new Error(`${provider.name} API error ${res.status}: ${redactedText}`);
  }

  const data = await res.json();
  const content = data.message?.content?.[0]?.text || "";
  return { content, provider: provider.name, model: provider.model };
}

// --- section ---

export interface TestResult {
  success: boolean;
  message: string;
  details?: string;
  latencyMs?: number;
  errorCode?: string;
  suggestion?: string;
}

async function testCustomOpenAi(settings: Record<string, any>): Promise<TestResult> {
  const apiKey = settings.CUSTOM_OPENAI_API_KEY || "";
  const baseUrl = settings.CUSTOM_OPENAI_BASE_URL || "";
  const modelId = settings.CUSTOM_OPENAI_MODEL_ID || "";

  if (!apiKey)
    return { success: false, message: "API key is required", errorCode: "MISSING_KEY" };
  if (!baseUrl)
    return { success: false, message: "Endpoint URL is required", errorCode: "MISSING_URL" };
  if (!modelId)
    return { success: false, message: "Model ID is required", errorCode: "MISSING_MODEL" };

  return await performChatTest({
    id: "custom_openai",
    name: "Custom (OpenAI-compatible)",
    apiKey,
    baseUrl: baseUrl.replace(/\/$/, ""),
    model: modelId,
    apiType: "openai",
  });
}

export async function testProviderConnection(providerId: string): Promise<TestResult> {
  if (!isElectronRuntime() && (await isServerChatStreamEnabled())) {
    try {
      const res = await testProviderKey(providerId);
      return {
        success: res.data?.success ?? res.success,
        message: res.data?.message ?? "Provider key verified",
      };
    } catch (err) {
      return {
        success: false,
        message: err instanceof Error ? err.message : "Failed to test provider key via server",
      };
    }
  }

  const settings = getSettings();
  const providerDef = POPULAR_PROVIDERS.find((p) => p.id === providerId);

  // Handle custom OpenAI-compatible provider
  if (providerId === "custom_openai") {
    return await testCustomOpenAi(settings);
  }

  if (!providerDef) {
    return {
      success: false,
      message: `Unknown provider: ${providerId}`,
      errorCode: "UNKNOWN_PROVIDER",
    };
  }

  const keyName = `PROVIDER_${providerId.toUpperCase()}_KEY`;
  const model = settings[`PROVIDER_${providerId.toUpperCase()}_MODEL`] || providerDef.defaultModel;
  const apiKey = settings[keyName];

  if (!apiKey) {
    return {
      success: false,
      message: "No API key entered. Please paste your API key first.",
      errorCode: "MISSING_KEY",
      suggestion: `Get your API key from ${providerDef.apiKeyUrl}`,
    };
  }

  return await performChatTest({
    id: providerDef.id,
    name: providerDef.name,
    apiKey,
    baseUrl: providerDef.defaultBaseUrl,
    model,
    apiType: providerDef.apiType,
  });
}

async function performChatTest(provider: ProviderConfig): Promise<TestResult> {
  const startTime = Date.now();

  try {
    const testMessages: ChatMessage[] = [{ role: "user", content: 'Say "OK" in one word.' }];

    // For Anthropic
    if (provider.apiType === "anthropic") {
      const endpoint = `${provider.baseUrl}/messages`;
      const res = await proxyFetch(
        endpoint,
        provider.apiKey,
        {
          model: provider.model.replace("anthropic/", ""),
          max_tokens: 100,
          messages: testMessages,
        },
        {
          "x-api-key": provider.apiKey,
          "anthropic-version": "2023-06-01",
        },
      );
      const latencyMs = Date.now() - startTime;
      if (!res.ok) return await diagnoseHttpError(res, provider, latencyMs);
      const data = await res.json();
      const content = data.content?.[0]?.text || "";
      return {
        success: true,
        message: `Connection successful! Response: "${content.slice(0, 50)}"`,
        latencyMs,
        details: `Provider: ${provider.name} | Model: ${provider.model} | Latency: ${latencyMs}ms`,
      };
    }

    // For Gemini
    if (provider.apiType === "gemini") {
      const model = provider.model.replace("google/", "").replace("gemini/", "");
      const endpoint = `${provider.baseUrl}/models/${model}:generateContent`;
      const res = await fetch("/api/llm-proxy", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          endpoint,
          apiKey: provider.apiKey,
          headers: { "x-goog-api-key": provider.apiKey },
          body: {
            contents: [{ role: "user", parts: [{ text: "Say OK" }] }],
            generationConfig: { maxOutputTokens: 100 },
          },
        }),
      });
      const latencyMs = Date.now() - startTime;
      if (!res.ok) return await diagnoseHttpError(res, provider, latencyMs);
      return {
        success: true,
        message: "Connection successful! Gemini API responded correctly.",
        latencyMs,
      };
    }

    // Default: OpenAI-compatible (through proxy)
    const endpoint = `${provider.baseUrl}/chat/completions`;
    const res = await proxyFetch(endpoint, provider.apiKey, {
      model: provider.model,
      messages: testMessages,
      max_tokens: 100,
    });
    const latencyMs = Date.now() - startTime;

    if (!res.ok) return await diagnoseHttpError(res, provider, latencyMs);

    const data = await res.json();
    const content =
      data.choices?.[0]?.message?.content || "(empty response - model may use reasoning tokens)";
    return {
      success: true,
      message: `Connection successful! Response: "${content.slice(0, 80)}"`,
      latencyMs,
      details: `Provider: ${provider.name} | Model: ${provider.model} | Latency: ${latencyMs}ms`,
    };
  } catch (err) {
    const latencyMs = Date.now() - startTime;
    const errMsg = err instanceof Error ? err.message : String(err);
    return {
      success: false,
      message: `Unexpected error: ${errMsg}`,
      errorCode: "UNKNOWN_ERROR",
      latencyMs,
    };
  }
}

async function diagnoseHttpError(
  res: Response,
  provider: ProviderConfig,
  latencyMs: number,
): Promise<TestResult> {
  let errorBody = "";
  try {
    errorBody = await res.text();
  } catch (error) {
    console.warn("Failed to read response body during error diagnosis:", error);
    errorBody = "";
  }

  let errorData: { error?: { message?: string; type?: string } } = {};
  try {
    errorData = JSON.parse(errorBody);
  } catch (error) {
    console.warn("Failed to parse error response as JSON:", error);
    errorData = {};
  }

  const status = res.status;
  const errMsg = errorData.error?.message || errorBody.slice(0, 200);
  const errType = errorData.error?.type || "";

  // OpenCode Zen CreditsError
  if (errType === "CreditsError" || errMsg.includes("No payment method")) {
    return {
      success: false,
      message: "Your API key is valid but your account has no payment method.",
      errorCode: "CREDITS_ERROR",
      latencyMs,
      details: errMsg,
      suggestion:
        "Add a payment method at the provider's billing page, or use a FREE model (look for 🆓 badge in the model dropdown).",
    };
  }

  // Model not supported
  if (errType === "ModelError" || errMsg.includes("not supported")) {
    return {
      success: false,
      message: `Model "${provider.model}" is not supported by this provider.`,
      errorCode: "MODEL_NOT_SUPPORTED",
      latencyMs,
      details: errMsg,
      suggestion:
        "Select a different model from the dropdown. Look for models with 🆓 badge — those are free.",
    };
  }

  if (status === 401) {
    return {
      success: false,
      message: "Invalid API key (HTTP 401). The provider rejected your API key.",
      errorCode: "INVALID_KEY",
      latencyMs,
      details: errMsg,
      suggestion:
        "Double-check that you copied the entire key. Get a new key from the provider's dashboard.",
    };
  }

  if (status === 403) {
    return {
      success: false,
      message: "Access forbidden (HTTP 403). Your API key is valid but lacks permission.",
      errorCode: "FORBIDDEN",
      latencyMs,
      details: errMsg,
    };
  }

  if (status === 429) {
    const isQuota =
      errMsg.toLowerCase().includes("quota") || errMsg.toLowerCase().includes("billing");
    return {
      success: false,
      message: isQuota ? "Quota exceeded (HTTP 429). Out of credits." : "Rate limited (HTTP 429).",
      errorCode: isQuota ? "QUOTA_EXCEEDED" : "RATE_LIMITED",
      latencyMs,
      details: errMsg,
      suggestion: isQuota
        ? "Add billing credits or use a FREE model."
        : "Wait 30 seconds and try again.",
    };
  }

  if (status === 404) {
    return {
      success: false,
      message: "Not found (HTTP 404). Endpoint URL or model ID is incorrect.",
      errorCode: "NOT_FOUND",
      latencyMs,
      details: errMsg,
    };
  }

  if (status >= 500) {
    return {
      success: false,
      message: `Provider server error (HTTP ${status}).`,
      errorCode: "SERVER_ERROR",
      latencyMs,
      details: errMsg,
      suggestion: "Try again in a few minutes.",
    };
  }

  return {
    success: false,
    message: `API request failed (HTTP ${status}). ${errMsg}`,
    errorCode: "HTTP_ERROR",
    latencyMs,
    details: errorBody.slice(0, 300),
  };
}

// --- section ---
// Streams the response token-by-token for a typewriter effect.
//
// The main `chatWithLLMStream` is a thin dispatcher that picks the right
// provider-specific streaming helper. Each helper is a small, focused
// async generator so SonarCloud cognitive complexity stays under 15
// (S3776). The original monolithic function was at complexity 94.

async function* streamFromAnthropic(
  provider: ProviderConfig,
  messages: ChatMessage[],
  signal?: AbortSignal,
): AsyncGenerator<string, void, unknown> {
  const endpoint = `${provider.baseUrl}/messages`;
  const systemMsg = messages.find((m) => m.role === "system")?.content || "";
  const chatMessages = messages.filter((m) => m.role !== "system");

  const res = await fetch("/api/llm-proxy?stream=true", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      endpoint,
      apiKey: provider.apiKey,
      body: {
        model: provider.model.replace("anthropic/", ""),
        max_tokens: 4096,
        system: systemMsg,
        messages: chatMessages,
        stream: true,
      },
      headers: {
        "x-api-key": provider.apiKey,
        "anthropic-version": "2023-06-01",
      },
      stream: true,
    }),
    signal,
  });

  if (!res.ok) {
    const text = await res.text().catch((error) => {
      console.warn("Failed to read Anthropic stream response text:", error);
      return "Unknown error";
    });
    const redactedText = text.slice(0, 200).replace(/sk-[a-zA-Z0-9]+/g, "[REDACTED]");
    throw new Error(`${provider.name} API error ${res.status}: ${redactedText}`);
  }

  const reader = res.body?.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  if (!reader) return;
  while (true) {
    if (signal?.aborted) return;
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";
    for (const line of lines) {
      const yielded = yieldFromAnthropicLine(line);
      if (yielded !== undefined) yield yielded;
      if (line.startsWith("data: ") && line.slice(6).trim() === "[DONE]") return;
    }
  }
}

function yieldFromAnthropicLine(line: string): string | undefined {
  if (!line.startsWith("data: ")) return undefined;
  const data = line.slice(6).trim();
  if (data === "[DONE]") return undefined;
  try {
    const parsed = JSON.parse(data);
    if (parsed.type === "content_block_delta" && parsed.delta?.text) {
      return parsed.delta.text;
    }
    if (parsed.choices?.[0]?.delta?.content) {
      return parsed.choices[0].delta.content;
    }
    if (parsed.error) {
      throw new Error(parsed.message || parsed.error.message || "Stream error");
    }
  } catch (error) {
    console.warn("Failed to parse Anthropic stream line:", error, "Line:", line);
    // Skip non-JSON lines
  }
  return undefined;
}

async function* streamFromGemini(
  provider: ProviderConfig,
  messages: ChatMessage[],
  signal?: AbortSignal,
): AsyncGenerator<string, void, unknown> {
  if (!isElectronRuntime() && (await isServerChatStreamEnabled())) {
    yield* streamFromServerChat(messages, signal);
    return;
  }
  // Gemini streaming in Electron — fall back to non-streaming and
  // simulate streaming by yielding word by word.
  const result = await chatWithLLM(messages, provider, signal);
  const words = result.content.split(/(\s+)/);
  for (const word of words) {
    if (signal?.aborted) return;
    yield word;
    await new Promise((r) => setTimeout(r, 20));
  }
}

function buildOpenAIError(provider: ProviderConfig, status: number, text: string): Error {
  try {
    const errorData = JSON.parse(text);
    if (errorData.error?.type === "CreditsError") {
      return new Error(
        "Your API key is valid but your account has no payment method. Use a FREE model (🆓) instead.",
      );
    }
    if (errorData.error?.type === "ModelError") {
      return new Error(
        `Model "${provider.model}" is not supported. Select a different model from the dropdown.`,
      );
    }
    if (errorData.error?.message) {
      return new Error(errorData.error.message);
    }
  } catch (parseErr) {
    if (
      parseErr instanceof Error &&
      (parseErr.message.includes("is not supported") || parseErr.message.includes("payment method"))
    ) {
      return parseErr;
    }
  }
  const redactedText = text.slice(0, 200).replace(/sk-[a-zA-Z0-9]+/g, "[REDACTED]");
  return new Error(`${provider.name} API error ${status}: ${redactedText}`);
}

async function* streamFromOpenAICompatible(
  provider: ProviderConfig,
  messages: ChatMessage[],
  signal?: AbortSignal,
): AsyncGenerator<string, void, unknown> {
  const endpoint = `${provider.baseUrl}/chat/completions`;
  const res = await fetch("/api/llm-proxy?stream=true", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      endpoint,
      apiKey: provider.apiKey,
      body: {
        model: provider.model,
        messages,
        max_tokens: 4096,
        temperature: 0.7,
        stream: true,
      },
      stream: true,
    }),
    signal,
  });

  if (!res.ok) {
    const text = await res.text().catch((error) => {
      console.warn("Failed to read OpenAI-compatible stream response text:", error);
      return "Unknown error";
    });
    throw buildOpenAIError(provider, res.status, text);
  }

  const reader = res.body?.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let gotAnyContent = false;

  if (!reader) return;

  // Read loop: consumeOpenAILine throws on error and returns 'DONE' on
  // sentinel. We only need to check for content (string) here, which
  // keeps the cognitive complexity of this function under 15 (S3776).
  let done = false;
  while (!done) {
    if (signal?.aborted) return;
    const readResult = await reader.read();
    done = readResult.done;
    if (done) break;
    buffer += decoder.decode(readResult.value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";
    for (const line of lines) {
      const result = consumeOpenAILine(line);
      if (!result) continue; // undefined = skip line
      if (result.done) return; // 'DONE' sentinel
      gotAnyContent = true;
      yield result.content;
    }
  }

  // If no content was streamed, throw — the AI Assistant will handle the fallback.
  // DO NOT call chatWithLLM here — that would make a SECOND API call and could
  // cause duplicate responses.
  if (!gotAnyContent) {
    throw new Error("STREAM_NO_CONTENT");
  }
}

/**
 * Parse one SSE line from an OpenAI-compatible stream.
 * Returns:
 *   - 'DONE' if the line is the [DONE] sentinel
 *   - a string if the line yielded content
 *   - undefined if the line should be skipped (non-data, non-JSON, etc.)
 *   - THROWS an Error if the line signalled an error (so the caller's
 *     try/catch around the generator picks it up; this avoids an extra
 *     `if (result instanceof Error)` check at every call site and keeps
 *     the caller's cognitive complexity under 15 — SonarCloud S3776).
 *
 * Note: Some models (deepseek-v4-flash-free, big-pickle) send
 * reasoning_content chunks FIRST (with content:null), then
 * actual content chunks. We skip reasoning and only yield content.
 */
/** Result of consuming one SSE line: either the 'DONE' sentinel, a content
 * string, or undefined if the line is not a data line. */
type ConsumeResult = { done: true } | { done: false; content: string } | undefined;

function consumeOpenAILine(line: string): ConsumeResult {
  if (!line.startsWith("data: ")) return undefined;
  const data = line.slice(6).trim();
  if (data === "[DONE]") return { done: true };
  try {
    const parsed = JSON.parse(data);
    if (parsed.error) {
      throw new Error(parsed.message || parsed.error?.message || "Stream error");
    }
    const delta = parsed.choices?.[0]?.delta;
    if (delta?.content) {
      return { done: false, content: delta.content };
    }
    // reasoning_content with content:null — skip, content will come later.
    return undefined;
  } catch (error) {
    console.warn("Failed to parse OpenAI stream line:", error, "Line:", line);
    if (
      error instanceof Error &&
      (error.message.includes("not supported") || error.message.includes("payment method"))
    ) {
      throw error;
    }
    return undefined;
  }
}

export async function* chatWithLLMStream(
  messages: ChatMessage[],
  config?: Partial<ProviderConfig>,
  signal?: AbortSignal,
): AsyncGenerator<string, void, unknown> {
  // ── P4b: server-side chat stream (web key freeze) ────────────────────────
  // In WEB mode (no Electron shell) with the `chat_first_ui` rollout flag
  // enabled, stream through /api/v1/chat/stream so API keys NEVER reach the
  // browser. Electron keeps the legacy local-storage provider flow below.
  if (!isElectronRuntime() && (await isServerChatStreamEnabled())) {
    yield* streamFromServerChat(messages, signal);
    return;
  }

  // SonarCloud typescript:S6582: use optional chain for cleaner null-safe access.
  const activeProvider = getActiveProvider();
  const provider = config && activeProvider ? { ...activeProvider, ...config } : activeProvider;

  if (!provider?.apiKey) {
    throw new Error("No API key configured. Go to Settings → AI Providers to connect a provider.");
  }

  if (provider.apiType === "anthropic") {
    yield* streamFromAnthropic(provider, messages, signal);
    return;
  }

  if (provider.apiType === "gemini") {
    yield* streamFromGemini(provider, messages, signal);
    return;
  }

  // Default: OpenAI-compatible streaming (OpenCode Zen, OpenAI, DeepSeek, Groq, etc.)
  yield* streamFromOpenAICompatible(provider, messages, signal);
}
// ═══════════════════════════════════════════════════════════════════════════
// ── P4b: server-side chat path ────────────────────────────────────────────
// Consumes the unified SSE envelope from POST /api/v1/chat/stream:
//   event: token  data: {"delta": "..."}
//   event: done   data: {...}
//   event: error  data: {"code": "...", "message": "..."}
// The request body carries NO credentials — keys are resolved on the server.
// ═══════════════════════════════════════════════════════════════════════════

/** True when running inside the Electron shell (legacy local-key mode). */
export function isElectronRuntime(): boolean {
  return (
    typeof window !== "undefined" && !!(window as unknown as { electronAPI?: unknown }).electronAPI
  );
}

let _serverChatFlagCache: boolean | null = null;

/**
 * True when the `chat_first_ui` gradual-rollout flag is effectively enabled
 * for this user (GET /api/v1/feature-flags/chat_first_ui). Any failure —
 * offline, unknown flag, unauthorized — resolves to FALSE, keeping the
 * legacy proxy path as the safe default. Cached for the page lifetime.
 */
export async function isServerChatStreamEnabled(): Promise<boolean> {
  if (_serverChatFlagCache !== null) return _serverChatFlagCache;
  try {
    const token = getAuthToken();
    const res = await fetch(apiUrl("/api/v1/feature-flags/chat_first_ui"), {
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    });
    if (!res.ok) throw new Error(`flag http ${res.status}`);
    const data = await res.json();
    const flag = data?.data ?? data;
    _serverChatFlagCache = !!(flag?.effective_enabled ?? flag?.enabled);
  } catch (error) {
    console.warn("chat_first_ui flag unavailable — using legacy LLM proxy:", error);
    _serverChatFlagCache = false;
  }
  return _serverChatFlagCache;
}

let _chatSessionId: string | null = null;

function generateRandomHex(): string {
  if (typeof crypto !== "undefined") {
    if (typeof crypto.randomUUID === "function") {
      return crypto.randomUUID();
    }
    if (typeof crypto.getRandomValues === "function") {
      const bytes = new Uint8Array(8);
      crypto.getRandomValues(bytes);
      return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
    }
  }
  return `${Date.now().toString(36)}-fallback`;
}

/** Stable chat session id per page load (for correlation on the server). */
export function getChatSessionId(): string {
  if (!_chatSessionId) {
    _chatSessionId = `sess-web-${Date.now().toString(36)}-${generateRandomHex().slice(0, 8)}`;
  }
  return _chatSessionId;
}

interface ServerChatEventData {
  delta?: unknown;
  code?: unknown;
  message?: unknown;
  detail?: unknown;
}

function redactServerMessage(message: string): string {
  return message.slice(0, 300).replace(/sk-[a-zA-Z0-9]+/g, "[REDACTED]");
}

function extractErrorMessage(parsed: ServerChatEventData): string {
  if (typeof parsed.message === "string") return parsed.message;
  if (typeof parsed.detail === "string") return parsed.detail;
  return "LLM stream error";
}

/** Build a user-facing Error for a failed non-SSE response. */
async function buildServerChatHttpError(res: Response): Promise<Error> {
  let text = "";
  try {
    text = await res.text();
  } catch (error) {
    console.warn("Failed to read chat stream error body:", error);
  }
  let detail = redactServerMessage(text || "Unknown error");
  try {
    detail = redactServerMessage(String(JSON.parse(text)?.detail?.message ?? detail));
  } catch {
    /* plain-text/HTML body — keep as-is */
  }
  if (res.status === 503) {
    return new Error(`No LLM provider is configured on the server. ${detail}`);
  }
  if (res.status === 401) {
    return new Error("Your session expired. Please sign in again.");
  }
  if (res.status === 429) {
    return new Error("Too many chat requests. Please wait a moment and retry.");
  }
  return new Error(`Chat service error ${res.status}: ${detail}`);
}

type SseAction =
  | { type: "token"; delta: string }
  | { type: "done" }
  | { type: "error"; error: Error }
  | { type: "none" };

function handleSseLine(line: string, state: { currentEvent: string }): SseAction {
  if (line.startsWith("event: ")) {
    state.currentEvent = line.slice(7).trim();
    return { type: "none" };
  }
  if (!line.startsWith("data: ")) return { type: "none" };
  const dataStr = line.slice(6).trim();

  let parsed: ServerChatEventData | null = null;
  try {
    parsed = JSON.parse(dataStr) as ServerChatEventData;
  } catch {
    state.currentEvent = "";
    return { type: "none" };
  }

  const evt = state.currentEvent;
  state.currentEvent = "";

  if (evt === "token") {
    if (typeof parsed.delta === "string" && parsed.delta) {
      return { type: "token", delta: parsed.delta };
    }
  } else if (evt === "done") {
    return { type: "done" };
  } else if (evt === "error") {
    const rawMessage = extractErrorMessage(parsed);
    return { type: "error", error: new Error(redactServerMessage(rawMessage)) };
  }
  return { type: "none" };
}

/**
 * Stream a reply through the server-side path (/api/v1/chat/stream).
 * SECURITY: the payload contains only session_id + messages + no keys.
 */
export async function* streamFromServerChat(
  messages: ChatMessage[],
  signal?: AbortSignal,
): AsyncGenerator<string, void, unknown> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const token = getAuthToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(apiUrl("/api/v1/chat/stream"), {
    method: "POST",
    headers,
    body: JSON.stringify({ session_id: getChatSessionId(), messages }),
    signal,
  });

  if (!res.ok) {
    throw await buildServerChatHttpError(res);
  }

  const reader = res.body?.getReader();
  if (!reader) return;
  const decoder = new TextDecoder();
  let buffer = "";
  const sseState = { currentEvent: "" };

  while (true) {
    if (signal?.aborted) return;
    const readResult = await reader.read();
    if (readResult.done) break;
    buffer += decoder.decode(readResult.value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      const action = handleSseLine(line, sseState);
      if (action.type === "token") {
        yield action.delta;
      } else if (action.type === "done") {
        return;
      } else if (action.type === "error") {
        throw action.error;
      }
    }
  }
}
