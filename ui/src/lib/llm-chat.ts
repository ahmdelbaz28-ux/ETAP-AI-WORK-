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

// ─── Proxy helper ────────────────────────────────────────────────
// Routes the request through our Vercel serverless function to bypass CORS.
async function proxyFetch(
  endpoint: string,
  apiKey: string,
  body: Record<string, unknown>,
  customHeaders?: Record<string, string>
): Promise<Response> {
  const proxyUrl = '/api/llm-proxy'
  const proxyBody = {
    endpoint,
    apiKey,
    body,
    headers: customHeaders,
  }
  
  const res = await fetch(proxyUrl, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(proxyBody),
  })
  
  return res
}

// ─── Settings helpers ────────────────────────────────────────────
function getSettings(): Record<string, string> {
  try {
    const stored = localStorage.getItem('etap-settings')
    if (!stored) return {}
    // Parse directly — settings are stored as raw JSON
    return JSON.parse(stored)
  } catch {
    return {}
  }
}

export function getActiveProvider(): ProviderConfig | null {
  const settings = getSettings()

  const activeId = settings.PROVIDER_ACTIVE_PROVIDER_ID || ''

  const providersWithKeys = POPULAR_PROVIDERS.filter(p => {
    const keyName = `PROVIDER_${p.id.toUpperCase()}_KEY`
    return !!settings[keyName]
  })

  if (providersWithKeys.length === 0) return null

  const selected = activeId
    ? providersWithKeys.find(p => p.id === activeId)
    : null
  const provider = selected || providersWithKeys[0]

  const keyName = `PROVIDER_${provider.id.toUpperCase()}_KEY`
  const model = settings[`PROVIDER_${provider.id.toUpperCase()}_MODEL`] || provider.defaultModel
  const apiKey = settings[keyName] || ''

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
    return {
      id: p.id,
      name: p.name,
      model: settings[`PROVIDER_${p.id.toUpperCase()}_MODEL`] || p.defaultModel,
    }
  })
}

// ─── LLM API calls (all through proxy) ───────────────────────────

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

// ─── OpenAI-compatible (uses proxy for CORS) ────────────────────
async function callOpenAICompatible(
  messages: ChatMessage[],
  provider: ProviderConfig
): Promise<ChatResult> {
  const endpoint = `${provider.baseUrl}/chat/completions`
  const res = await proxyFetch(endpoint, provider.apiKey, {
    model: provider.model,
    messages,
    max_tokens: 4096,
    temperature: 0.7,
  })

  if (!res.ok) {
    const text = await res.text().catch(() => 'Unknown error')
    throw new Error(`${provider.name} API error ${res.status}: ${text.slice(0, 200)}`)
  }

  const data = await res.json()
  const content = data.choices?.[0]?.message?.content || ''
  return { content, provider: provider.name, model: provider.model }
}

// ─── Anthropic (uses proxy for CORS) ─────────────────────────────
async function callAnthropic(
  messages: ChatMessage[],
  provider: ProviderConfig
): Promise<ChatResult> {
  const endpoint = `${provider.baseUrl}/messages`
  const systemMsg = messages.find(m => m.role === 'system')?.content || ''
  const chatMessages = messages.filter(m => m.role !== 'system')

  const res = await proxyFetch(endpoint, provider.apiKey, {
    model: provider.model.replace('anthropic/', ''),
    max_tokens: 4096,
    system: systemMsg,
    messages: chatMessages,
  }, {
    'x-api-key': provider.apiKey,
    'anthropic-version': '2023-06-01',
  })

  if (!res.ok) {
    const text = await res.text().catch(() => 'Unknown error')
    throw new Error(`${provider.name} API error ${res.status}: ${text.slice(0, 200)}`)
  }

  const data = await res.json()
  const content = data.content?.[0]?.text || ''
  return { content, provider: provider.name, model: provider.model }
}

// ─── Google Gemini (uses proxy for CORS) ────────────────────────
async function callGemini(
  messages: ChatMessage[],
  provider: ProviderConfig
): Promise<ChatResult> {
  const model = provider.model.replace('google/', '')
  const endpoint = `${provider.baseUrl}/models/${model}:generateContent?key=${provider.apiKey}`

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

  // Gemini uses API key in URL, not in Authorization header
  const res = await fetch('/api/llm-proxy', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      endpoint,
      apiKey: 'gemini-no-auth-header', // Gemini uses ?key= not Bearer
      body,
      headers: {},
    }),
  })

  if (!res.ok) {
    const text = await res.text().catch(() => 'Unknown error')
    throw new Error(`${provider.name} API error ${res.status}: ${text.slice(0, 200)}`)
  }

  const data = await res.json()
  const content = data.candidates?.[0]?.content?.parts?.[0]?.text || ''
  return { content, provider: provider.name, model: provider.model }
}

// ─── Cloudflare Workers AI (uses proxy for CORS) ────────────────
async function callCloudflare(
  messages: ChatMessage[],
  provider: ProviderConfig
): Promise<ChatResult> {
  const settings = getSettings()
  const accountId = settings.PROVIDER_CLOUDFLARE_ACCOUNT_ID || ''
  if (!accountId) {
    throw new Error('Cloudflare requires an Account ID. Please add it in Settings.')
  }

  const url = `${provider.baseUrl}/${accountId}/ai/run/${provider.model}`
  const res = await proxyFetch(url, provider.apiKey, { messages })

  if (!res.ok) {
    const text = await res.text().catch(() => 'Unknown error')
    throw new Error(`${provider.name} API error ${res.status}: ${text.slice(0, 200)}`)
  }

  const data = await res.json()
  const content = data.result?.response || ''
  return { content, provider: provider.name, model: provider.model }
}

// ─── Zhipu AI (uses proxy for CORS) ─────────────────────────────
async function callZhipu(
  messages: ChatMessage[],
  provider: ProviderConfig
): Promise<ChatResult> {
  const endpoint = `${provider.baseUrl}/chat/completions`
  const res = await proxyFetch(endpoint, provider.apiKey, {
    model: provider.model,
    messages,
    max_tokens: 4096,
    temperature: 0.7,
  })

  if (!res.ok) {
    const text = await res.text().catch(() => 'Unknown error')
    throw new Error(`${provider.name} API error ${res.status}: ${text.slice(0, 200)}`)
  }

  const data = await res.json()
  const content = data.choices?.[0]?.message?.content || ''
  return { content, provider: provider.name, model: provider.model }
}

// ─── Cohere (uses proxy for CORS) ───────────────────────────────
async function callCohere(
  messages: ChatMessage[],
  provider: ProviderConfig
): Promise<ChatResult> {
  const endpoint = `${provider.baseUrl}/chat`
  const res = await proxyFetch(endpoint, provider.apiKey, {
    model: provider.model,
    messages,
  })

  if (!res.ok) {
    const text = await res.text().catch(() => 'Unknown error')
    throw new Error(`${provider.name} API error ${res.status}: ${text.slice(0, 200)}`)
  }

  const data = await res.json()
  const content = data.message?.content?.[0]?.text || ''
  return { content, provider: provider.name, model: provider.model }
}

// ─── Provider Connection Test (uses proxy for CORS) ─────────────

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
  const model = settings[`PROVIDER_${providerId.toUpperCase()}_MODEL`] || providerDef.defaultModel
  const apiKey = settings[keyName]

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
    const testMessages: ChatMessage[] = [
      { role: 'user', content: 'Say "OK" in one word.' },
    ]

    // For Anthropic
    if (provider.apiType === 'anthropic') {
      const endpoint = `${provider.baseUrl}/messages`
      const res = await proxyFetch(endpoint, provider.apiKey, {
        model: provider.model.replace('anthropic/', ''),
        max_tokens: 100,
        messages: testMessages,
      }, {
        'x-api-key': provider.apiKey,
        'anthropic-version': '2023-06-01',
      })
      const latencyMs = Date.now() - startTime
      if (!res.ok) return await diagnoseHttpError(res, provider, latencyMs)
      const data = await res.json()
      const content = data.content?.[0]?.text || ''
      return {
        success: true,
        message: `Connection successful! Response: "${content.slice(0, 50)}"`,
        latencyMs,
        details: `Provider: ${provider.name} | Model: ${provider.model} | Latency: ${latencyMs}ms`,
      }
    }

    // For Gemini
    if (provider.apiType === 'gemini') {
      const model = provider.model.replace('google/', '')
      const endpoint = `${provider.baseUrl}/models/${model}:generateContent?key=${provider.apiKey}`
      const res = await fetch('/api/llm-proxy', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          endpoint,
          apiKey: 'gemini',
          body: {
            contents: [{ role: 'user', parts: [{ text: 'Say OK' }] }],
            generationConfig: { maxOutputTokens: 100 },
          },
          headers: {},
        }),
      })
      const latencyMs = Date.now() - startTime
      if (!res.ok) return await diagnoseHttpError(res, provider, latencyMs)
      return {
        success: true,
        message: 'Connection successful! Gemini API responded correctly.',
        latencyMs,
      }
    }

    // Default: OpenAI-compatible (through proxy)
    const endpoint = `${provider.baseUrl}/chat/completions`
    const res = await proxyFetch(endpoint, provider.apiKey, {
      model: provider.model,
      messages: testMessages,
      max_tokens: 100,
    })
    const latencyMs = Date.now() - startTime

    if (!res.ok) return await diagnoseHttpError(res, provider, latencyMs)

    const data = await res.json()
    const content = data.choices?.[0]?.message?.content || '(empty response - model may use reasoning tokens)'
    return {
      success: true,
      message: `Connection successful! Response: "${content.slice(0, 80)}"`,
      latencyMs,
      details: `Provider: ${provider.name} | Model: ${provider.model} | Latency: ${latencyMs}ms`,
    }
  } catch (err) {
    const latencyMs = Date.now() - startTime
    const errMsg = err instanceof Error ? err.message : String(err)
    return {
      success: false,
      message: `Unexpected error: ${errMsg}`,
      errorCode: 'UNKNOWN_ERROR',
      latencyMs,
    }
  }
}

async function diagnoseHttpError(
  res: Response,
  provider: ProviderConfig,
  latencyMs: number
): Promise<TestResult> {
  let errorBody = ''
  try {
    errorBody = await res.text()
  } catch {}

  let errorData: { error?: { message?: string; type?: string } } = {}
  try {
    errorData = JSON.parse(errorBody)
  } catch {}

  const status = res.status
  const errMsg = errorData.error?.message || errorBody.slice(0, 200)
  const errType = errorData.error?.type || ''

  // OpenCode Zen CreditsError
  if (errType === 'CreditsError' || errMsg.includes('No payment method')) {
    return {
      success: false,
      message: 'Your API key is valid but your account has no payment method.',
      errorCode: 'CREDITS_ERROR',
      latencyMs,
      details: errMsg,
      suggestion: 'Add a payment method at the provider\'s billing page, or use a FREE model (look for 🆓 badge in the model dropdown).',
    }
  }

  // Model not supported
  if (errType === 'ModelError' || errMsg.includes('not supported')) {
    return {
      success: false,
      message: `Model "${provider.model}" is not supported by this provider.`,
      errorCode: 'MODEL_NOT_SUPPORTED',
      latencyMs,
      details: errMsg,
      suggestion: 'Select a different model from the dropdown. Look for models with 🆓 badge — those are free.',
    }
  }

  if (status === 401) {
    return {
      success: false,
      message: 'Invalid API key (HTTP 401). The provider rejected your API key.',
      errorCode: 'INVALID_KEY',
      latencyMs,
      details: errMsg,
      suggestion: 'Double-check that you copied the entire key. Get a new key from the provider\'s dashboard.',
    }
  }

  if (status === 403) {
    return {
      success: false,
      message: 'Access forbidden (HTTP 403). Your API key is valid but lacks permission.',
      errorCode: 'FORBIDDEN',
      latencyMs,
      details: errMsg,
    }
  }

  if (status === 429) {
    const isQuota = errMsg.toLowerCase().includes('quota') || errMsg.toLowerCase().includes('billing')
    return {
      success: false,
      message: isQuota ? 'Quota exceeded (HTTP 429). Out of credits.' : 'Rate limited (HTTP 429).',
      errorCode: isQuota ? 'QUOTA_EXCEEDED' : 'RATE_LIMITED',
      latencyMs,
      details: errMsg,
      suggestion: isQuota ? 'Add billing credits or use a FREE model.' : 'Wait 30 seconds and try again.',
    }
  }

  if (status === 404) {
    return {
      success: false,
      message: 'Not found (HTTP 404). Endpoint URL or model ID is incorrect.',
      errorCode: 'NOT_FOUND',
      latencyMs,
      details: errMsg,
    }
  }

  if (status >= 500) {
    return {
      success: false,
      message: `Provider server error (HTTP ${status}).`,
      errorCode: 'SERVER_ERROR',
      latencyMs,
      details: errMsg,
      suggestion: 'Try again in a few minutes.',
    }
  }

  return {
    success: false,
    message: `API request failed (HTTP ${status}). ${errMsg}`,
    errorCode: 'HTTP_ERROR',
    latencyMs,
    details: errorBody.slice(0, 300),
  }
}
