/**
 * LLM Chat Module — Direct provider API calls from the browser
 * ============================================================
 *
 * This module reads the user's configured API key from localStorage
 * and calls the AI provider's API directly. No backend required —
 * this is a client-side-only LLM integration (like KiloCode/OpenCode).
 *
 * Supported API types:
 *   - openai:      OpenAI-compatible /v1/chat/completions (OpenAI, DeepSeek, Groq, NVIDIA, Fireworks, Qwen, HuggingFace, OpenCode, KiloCode)
 *   - anthropic:   Anthropic /v1/messages with x-api-key header
 *   - gemini:      Google Gemini /v1beta/models/{model}:generateContent
 *   - cloudflare:  Cloudflare Workers AI /accounts/{account_id}/ai/run/{model}
 *   - zhipu:       Zhipu AI (GLM) OpenAI-compatible /chat/completions
 *   - cohere:      Cohere /v2/chat
 *
 * The active provider is selected via the PROVIDER_ACTIVE_PROVIDER_ID
 * setting in localStorage. If not set, the first provider with a key
 * is used.
 */

import { POPULAR_PROVIDERS } from '../pages/Settings'

// ─── Types ────────────────────────────────────────────────────────
export interface ChatMessage {
  role: 'user' | 'assistant' | 'system'
  content: string
}

export interface ChatResult {
  content: string
  provider: string
  model: string
}

export interface ProviderConfig {
  id: string
  name: string
  apiKey: string
  baseUrl: string
  model: string
  apiType: 'openai' | 'anthropic' | 'gemini' | 'cloudflare' | 'zhipu' | 'cohere'
}

// ─── Settings helpers ────────────────────────────────────────────
function getSettings(): Record<string, string> {
  try {
    const stored = localStorage.getItem('etap-settings')
    if (!stored) return {}
    return JSON.parse(stored)
  } catch {
    return {}
  }
}

export function getActiveProvider(): ProviderConfig | null {
  const settings = getSettings()

  // Check if user explicitly selected an active provider
  const activeId = settings.PROVIDER_ACTIVE_PROVIDER_ID || ''

  // Build list of providers with keys
  const providersWithKeys = POPULAR_PROVIDERS.filter(p => {
    const keyName = `PROVIDER_${p.id.toUpperCase()}_KEY`
    return !!settings[keyName]
  })

  if (providersWithKeys.length === 0) return null

  // Use explicitly selected provider if it has a key, else first available
  const selected = activeId
    ? providersWithKeys.find(p => p.id === activeId)
    : null
  const provider = selected || providersWithKeys[0]

  const keyName = `PROVIDER_${provider.id.toUpperCase()}_KEY`
  const modelName = `PROVIDER_${provider.id.toUpperCase()}_MODEL`
  const apiKey = settings[keyName] || ''
  const model = settings[modelName] || provider.defaultModel

  return {
    id: provider.id,
    name: provider.name,
    apiKey,
    baseUrl: provider.defaultBaseUrl,
    model,
    apiType: provider.apiType,
  }
}

export function getConfiguredProviders(): { id: string; name: string; model: string }[] {
  const settings = getSettings()
  return POPULAR_PROVIDERS.filter(p => {
    const keyName = `PROVIDER_${p.id.toUpperCase()}_KEY`
    return !!settings[keyName]
  }).map(p => {
    const modelName = `PROVIDER_${p.id.toUpperCase()}_MODEL`
    return {
      id: p.id,
      name: p.name,
      model: settings[modelName] || p.defaultModel,
    }
  })
}

// ─── LLM API calls ───────────────────────────────────────────────

export async function chatWithLLM(
  messages: ChatMessage[],
  config?: Partial<ProviderConfig>
): Promise<ChatResult> {
  const provider = config
    ? { ...getActiveProvider()!, ...config }
    : getActiveProvider()

  if (!provider || !provider.apiKey) {
    throw new Error('No API key configured. Go to Settings → AI Providers to connect a provider.')
  }

  switch (provider.apiType) {
    case 'openai':
      return callOpenAICompatible(messages, provider)
    case 'anthropic':
      return callAnthropic(messages, provider)
    case 'gemini':
      return callGemini(messages, provider)
    case 'cloudflare':
      return callCloudflare(messages, provider)
    case 'zhipu':
      return callZhipu(messages, provider)
    case 'cohere':
      return callCohere(messages, provider)
    default:
      throw new Error(`Unsupported provider type: ${provider.apiType}`)
  }
}

// ─── Provider Connection Test ────────────────────────────────────
// Performs a real chat completion request to verify the API key works.
// Returns detailed error information to help the user diagnose issues.

export interface TestResult {
  success: boolean
  message: string
  details?: string
  latencyMs?: number
  errorCode?: string
  suggestion?: string
}

export async function testProviderConnection(
  providerId: string
): Promise<TestResult> {
  const settings = getSettings()
  const providerDef = POPULAR_PROVIDERS.find(p => p.id === providerId)

  // Handle custom OpenAI-compatible provider
  if (providerId === 'custom_openai') {
    const apiKey = settings.CUSTOM_OPENAI_API_KEY || ''
    const baseUrl = settings.CUSTOM_OPENAI_BASE_URL || ''
    const modelId = settings.CUSTOM_OPENAI_MODEL_ID || ''

    if (!apiKey) return { success: false, message: 'API key is required', errorCode: 'MISSING_KEY' }
    if (!baseUrl) return { success: false, message: 'Endpoint URL is required', errorCode: 'MISSING_URL' }
    if (!modelId) return { success: false, message: 'Model ID is required', errorCode: 'MISSING_MODEL' }

    return await performChatTest({
      id: 'custom_openai',
      name: 'Custom (OpenAI-compatible)',
      apiKey,
      baseUrl: baseUrl.replace(/\/$/, ''),
      model: modelId,
      apiType: 'openai',
    })
  }

  if (!providerDef) {
    return { success: false, message: `Unknown provider: ${providerId}`, errorCode: 'UNKNOWN_PROVIDER' }
  }

  const keyName = `PROVIDER_${providerId.toUpperCase()}_KEY`
  const modelName = `PROVIDER_${providerId.toUpperCase()}_MODEL`
  const apiKey = settings[keyName]
  const model = settings[modelName] || providerDef.defaultModel

  if (!apiKey) {
    return {
      success: false,
      message: 'No API key entered. Please paste your API key first.',
      errorCode: 'MISSING_KEY',
      suggestion: `Get your API key from ${providerDef.apiKeyUrl}`,
    }
  }

  return await performChatTest({
    id: providerDef.id,
    name: providerDef.name,
    apiKey,
    baseUrl: providerDef.defaultBaseUrl,
    model,
    apiType: providerDef.apiType,
  })
}

async function performChatTest(provider: ProviderConfig): Promise<TestResult> {
  const startTime = Date.now()

  try {
    // Send a minimal chat request to verify the key works for actual chat
    const testMessages: ChatMessage[] = [
      { role: 'user', content: 'Say "OK" in one word.' },
    ]

    // For Anthropic, we need to use the messages API directly
    if (provider.apiType === 'anthropic') {
      const url = `${provider.baseUrl}/messages`
      const res = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-api-key': provider.apiKey,
          'anthropic-version': '2023-06-01',
        },
        body: JSON.stringify({
          model: provider.model.replace('anthropic/', ''),
          max_tokens: 5,
          messages: testMessages,
        }),
      })
      const latencyMs = Date.now() - startTime

      if (!res.ok) {
        return diagnoseHttpError(res, provider, latencyMs)
      }

      const data = await res.json()
      const content = data.content?.[0]?.text || ''
      return {
        success: true,
        message: `✓ Connection successful! Response: "${content.slice(0, 50)}"`,
        latencyMs,
        details: `Provider: ${provider.name} | Model: ${provider.model} | Latency: ${latencyMs}ms`,
      }
    }

    // For Gemini
    if (provider.apiType === 'gemini') {
      const model = provider.model.replace('google/', '')
      const url = `${provider.baseUrl}/models/${model}:generateContent?key=${provider.apiKey}`
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          contents: [{ role: 'user', parts: [{ text: 'Say OK' }] }],
          generationConfig: { maxOutputTokens: 5 },
        }),
      })
      const latencyMs = Date.now() - startTime

      if (!res.ok) {
        return diagnoseHttpError(res, provider, latencyMs)
      }

      return {
        success: true,
        message: '✓ Connection successful! Gemini API responded correctly.',
        latencyMs,
        details: `Model: ${provider.model} | Latency: ${latencyMs}ms`,
      }
    }

    // For Cloudflare Workers AI — needs account ID
    if (provider.apiType === 'cloudflare') {
      const accountId = settings.PROVIDER_CLOUDFLARE_ACCOUNT_ID || ''
      if (!accountId) {
        return {
          success: false,
          message: 'Cloudflare requires an Account ID. Please add it in Settings.',
          errorCode: 'MISSING_ACCOUNT_ID',
          suggestion: 'Find your Account ID at https://dash.cloudflare.com → Workers & Pages',
        }
      }
      const url = `${provider.baseUrl}/${accountId}/ai/run/${provider.model}`
      const res = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${provider.apiKey}`,
        },
        body: JSON.stringify({ messages: testMessages }),
      })
      const latencyMs = Date.now() - startTime

      if (!res.ok) {
        return diagnoseHttpError(res, provider, latencyMs)
      }
      return {
        success: true,
        message: '✓ Connection successful! Cloudflare Workers AI responded.',
        latencyMs,
      }
    }

    // Default: OpenAI-compatible
    const url = `${provider.baseUrl}/chat/completions`
    const res = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${provider.apiKey}`,
      },
      body: JSON.stringify({
        model: provider.model,
        messages: testMessages,
        max_tokens: 5,
      }),
    })
    const latencyMs = Date.now() - startTime

    if (!res.ok) {
      return diagnoseHttpError(res, provider, latencyMs)
    }

    const data = await res.json()
    const content = data.choices?.[0]?.message?.content || ''
    return {
      success: true,
      message: `✓ Connection successful! Response: "${content.slice(0, 50)}"`,
      latencyMs,
      details: `Provider: ${provider.name} | Model: ${provider.model} | Latency: ${latencyMs}ms`,
    }
  } catch (err) {
    const latencyMs = Date.now() - startTime
    const errMsg = err instanceof Error ? err.message : String(err)

    // Diagnose network/CORS errors
    if (errMsg.includes('Failed to fetch') || errMsg.includes('NetworkError')) {
      return {
        success: false,
        message: 'Cannot reach the API endpoint. This may be due to:',
        errorCode: 'NETWORK_ERROR',
        latencyMs,
        details: errMsg,
        suggestion: '1) Check your internet connection. 2) Verify the endpoint URL is correct. 3) The provider may not allow browser-based requests (CORS) — this is normal for some providers. Your key is still saved and will work when used from a backend.',
      }
    }
    if (errMsg.includes('CORS')) {
      return {
        success: false,
        message: 'CORS error: The provider blocked this browser request.',
        errorCode: 'CORS_ERROR',
        latencyMs,
        suggestion: 'This is a browser security restriction, not a key issue. Your API key is still saved. To use this provider, you may need to route requests through a backend proxy.',
      }
    }
    return {
      success: false,
      message: `Unexpected error: ${errMsg}`,
      errorCode: 'UNKNOWN_ERROR',
      latencyMs,
    }
  }
}

// Helper: diagnose HTTP error responses with specific, helpful messages
async function diagnoseHttpError(
  res: Response,
  provider: ProviderConfig,
  latencyMs: number
): Promise<TestResult> {
  let errorBody = ''
  try {
    errorBody = await res.text()
  } catch {}

  const status = res.status

  // 401 Unauthorized — invalid API key
  if (status === 401) {
    return {
      success: false,
      message: `Invalid API key (HTTP 401). The provider rejected your API key.`,
      errorCode: 'INVALID_KEY',
      latencyMs,
      details: errorBody.slice(0, 300),
      suggestion: `Double-check that you copied the entire key. Get a new key from the provider's dashboard.`,
    }
  }

  // 403 Forbidden — key valid but no permission
  if (status === 403) {
    return {
      success: false,
      message: `Access forbidden (HTTP 403). Your API key is valid but lacks permission for this model.`,
      errorCode: 'FORBIDDEN',
      latencyMs,
      details: errorBody.slice(0, 300),
      suggestion: 'Check that your account has access to this model. Some models require separate enrollment or payment.',
    }
  }

  // 429 Rate limit / Quota exceeded
  if (status === 429) {
    const isQuota = errorBody.toLowerCase().includes('quota') ||
                    errorBody.toLowerCase().includes('limit') ||
                    errorBody.toLowerCase().includes('exceeded') ||
                    errorBody.toLowerCase().includes('billing')
    return {
      success: false,
      message: isQuota
        ? 'Quota exceeded (HTTP 429). Your API key has run out of credits or hit its rate limit.'
        : 'Rate limited (HTTP 429). Too many requests in a short time.',
      errorCode: isQuota ? 'QUOTA_EXCEEDED' : 'RATE_LIMITED',
      latencyMs,
      details: errorBody.slice(0, 300),
      suggestion: isQuota
        ? 'Add billing credits at the provider\'s dashboard, or switch to a free-tier provider like Groq, Gemini, or NVIDIA NIM.'
        : 'Wait 30 seconds and try again. If this keeps happening, upgrade your plan.',
    }
  }

  // 404 Not Found — wrong endpoint or model
  if (status === 404) {
    return {
      success: false,
      message: `Not found (HTTP 404). The endpoint URL or model ID is incorrect.`,
      errorCode: 'NOT_FOUND',
      latencyMs,
      details: errorBody.slice(0, 300),
      suggestion: `Verify:
1. The endpoint URL is correct (e.g., https://api.openai.com/v1)
2. The model ID is spelled correctly (e.g., "gpt-4o-mini", not "gpt4o-mini")
3. The model exists in your account`,
    }
  }

  // 400 Bad Request — usually model not found or malformed
  if (status === 400) {
    return {
      success: false,
      message: `Bad request (HTTP 400). The provider rejected the request.`,
      errorCode: 'BAD_REQUEST',
      latencyMs,
      details: errorBody.slice(0, 300),
      suggestion: 'This usually means the model ID is wrong or not supported. Check the model name spelling.',
    }
  }

  // 5xx Server errors
  if (status >= 500) {
    return {
      success: false,
      message: `Provider server error (HTTP ${status}). The provider is having issues.`,
      errorCode: 'SERVER_ERROR',
      latencyMs,
      details: errorBody.slice(0, 300),
      suggestion: 'Try again in a few minutes. The provider is temporarily unavailable.',
    }
  }

  // Generic fallback
  return {
    success: false,
    message: `API request failed (HTTP ${status}).`,
    errorCode: 'HTTP_ERROR',
    latencyMs,
    details: errorBody.slice(0, 300),
  }
}

// ─── OpenAI-compatible (OpenAI, DeepSeek, Groq, NVIDIA, Fireworks, Qwen, HF, OpenCode, KiloCode) ───
async function callOpenAICompatible(
  messages: ChatMessage[],
  provider: ProviderConfig
): Promise<ChatResult> {
  const url = `${provider.baseUrl}/chat/completions`
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${provider.apiKey}`,
    },
    body: JSON.stringify({
      model: provider.model,
      messages,
      max_tokens: 4096,
      temperature: 0.7,
    }),
  })

  if (!res.ok) {
    const text = await res.text().catch(() => 'Unknown error')
    throw new Error(`${provider.name} API error ${res.status}: ${text.slice(0, 200)}`)
  }

  const data = await res.json()
  const content = data.choices?.[0]?.message?.content || ''
  return { content, provider: provider.name, model: provider.model }
}

// ─── Anthropic (Claude) ──────────────────────────────────────────
async function callAnthropic(
  messages: ChatMessage[],
  provider: ProviderConfig
): Promise<ChatResult> {
  const url = `${provider.baseUrl}/messages`
  // Anthropic requires system message to be separate
  const systemMsg = messages.find(m => m.role === 'system')?.content || ''
  const chatMessages = messages.filter(m => m.role !== 'system')

  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-api-key': provider.apiKey,
      'anthropic-version': '2023-06-01',
    },
    body: JSON.stringify({
      model: provider.model.replace('anthropic/', ''),
      max_tokens: 4096,
      system: systemMsg,
      messages: chatMessages,
    }),
  })

  if (!res.ok) {
    const text = await res.text().catch(() => 'Unknown error')
    throw new Error(`${provider.name} API error ${res.status}: ${text.slice(0, 200)}`)
  }

  const data = await res.json()
  const content = data.content?.[0]?.text || ''
  return { content, provider: provider.name, model: provider.model }
}

// ─── Google Gemini ───────────────────────────────────────────────
async function callGemini(
  messages: ChatMessage[],
  provider: ProviderConfig
): Promise<ChatResult> {
  const model = provider.model.replace('google/', '')
  const url = `${provider.baseUrl}/models/${model}:generateContent?key=${provider.apiKey}`

  const contents = messages
    .filter(m => m.role !== 'system')
    .map(m => ({
      role: m.role === 'assistant' ? 'model' : 'user',
      parts: [{ text: m.content }],
    }))

  const systemInstruction = messages.find(m => m.role === 'system')
  const body: Record<string, unknown> = {
    contents,
    generationConfig: { temperature: 0.7, maxOutputTokens: 4096 },
  }
  if (systemInstruction) {
    body.systemInstruction = { parts: [{ text: systemInstruction.content }] }
  }

  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

  if (!res.ok) {
    const text = await res.text().catch(() => 'Unknown error')
    throw new Error(`${provider.name} API error ${res.status}: ${text.slice(0, 200)}`)
  }

  const data = await res.json()
  const content = data.candidates?.[0]?.content?.parts?.[0]?.text || ''
  return { content, provider: provider.name, model: provider.model }
}

// ─── Cloudflare Workers AI ───────────────────────────────────────
async function callCloudflare(
  messages: ChatMessage[],
  provider: ProviderConfig
): Promise<ChatResult> {
  // Cloudflare requires account_id in the URL. The user stores their
  // account_id in PROVIDER_CLOUDFLARE_ACCOUNT_ID.
  const settings = getSettings()
  const accountId = settings.PROVIDER_CLOUDFLARE_ACCOUNT_ID || ''
  if (!accountId) {
    throw new Error('Cloudflare requires an Account ID. Please set it in Settings.')
  }

  const url = `${provider.baseUrl}/${accountId}/ai/run/${provider.model}`
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${provider.apiKey}`,
    },
    body: JSON.stringify({
      messages,
    }),
  })

  if (!res.ok) {
    const text = await res.text().catch(() => 'Unknown error')
    throw new Error(`${provider.name} API error ${res.status}: ${text.slice(0, 200)}`)
  }

  const data = await res.json()
  const content = data.result?.response || ''
  return { content, provider: provider.name, model: provider.model }
}

// ─── Zhipu AI (GLM) — OpenAI-compatible ─────────────────────────
async function callZhipu(
  messages: ChatMessage[],
  provider: ProviderConfig
): Promise<ChatResult> {
  const url = `${provider.baseUrl}/chat/completions`
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${provider.apiKey}`,
    },
    body: JSON.stringify({
      model: provider.model,
      messages,
      max_tokens: 4096,
      temperature: 0.7,
    }),
  })

  if (!res.ok) {
    const text = await res.text().catch(() => 'Unknown error')
    throw new Error(`${provider.name} API error ${res.status}: ${text.slice(0, 200)}`)
  }

  const data = await res.json()
  const content = data.choices?.[0]?.message?.content || ''
  return { content, provider: provider.name, model: provider.model }
}

// ─── Cohere ──────────────────────────────────────────────────────
async function callCohere(
  messages: ChatMessage[],
  provider: ProviderConfig
): Promise<ChatResult> {
  const url = `${provider.baseUrl}/chat`
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${provider.apiKey}`,
    },
    body: JSON.stringify({
      model: provider.model,
      messages,
    }),
  })

  if (!res.ok) {
    const text = await res.text().catch(() => 'Unknown error')
    throw new Error(`${provider.name} API error ${res.status}: ${text.slice(0, 200)}`)
  }

  const data = await res.json()
  const content = data.message?.content?.[0]?.text || ''
  return { content, provider: provider.name, model: provider.model }
}
