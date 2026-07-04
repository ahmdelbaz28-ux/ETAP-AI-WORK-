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
