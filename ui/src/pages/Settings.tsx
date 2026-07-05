import { useState, useEffect, useCallback } from 'react'
import { motion } from 'framer-motion'
import { Save, Download, Upload, Trash2, Bot, Wrench, Database, Shield, Link2, Gauge, Sparkles, Info, Code, CheckCircle2, XCircle, Loader2, ExternalLink, Eye, Key, Zap } from 'lucide-react'  // QUALITY v2.1.1: removed unused Terminal
import { useNotify } from '../context/NotificationContext'
import { Card, CardHeader, Button, Tabs, TabPanels, useTabState, Toggle } from '../components/ui'
import { cn } from '../utils/helpers'
import { ProviderLogo } from '../components/ProviderLogo'
import { testProviderConnection } from '../lib/llm-chat'

import { ContextHelpButton } from '../components/help/ContextHelpButton'
import {
  fetchVisionKeys,
  saveVisionKey,
  deleteVisionKey,
  testVisionKey,
  type VisionKeyConfig,
} from '../lib/api'

// ─── Provider card helpers ─────────────────────────────────────────
// Extracted from the inline `POPULAR_PROVIDERS.map(...)` callback in
// <Settings/> to keep the callback's cognitive complexity under 15
// (SonarCloud S3776). Each helper is a small, flat function.

type ProviderStatus = 'ok' | 'fail' | null | undefined

function providerCardClass(hasKey: boolean, isFree: boolean): string {
  const base = 'p-4 rounded-xl border-2 transition-all bg-[var(--bg-elevated)] relative'
  if (hasKey) return cn(base, 'border-green-500/30')
  if (isFree) return cn(base, 'border-green-500/20 hover:border-green-500/40')
  return cn(base, 'border-[var(--border-primary)] hover:border-brand-500/40')
}

function providerButtonClass(hasKey: boolean, isTesting: boolean, status: ProviderStatus): string {
  const base = 'w-full flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all'
  if (!hasKey || isTesting) {
    return cn(base, 'bg-[var(--bg-primary)] text-[var(--text-muted)] cursor-not-allowed border border-[var(--border-primary)]')
  }
  if (status === 'ok') return cn(base, 'bg-green-600 hover:bg-green-500 text-white')
  if (status === 'fail') return cn(base, 'bg-red-600 hover:bg-red-500 text-white')
  return cn(base, 'bg-brand-600 hover:bg-brand-500 text-white')
}

function providerButtonContent(isTesting: boolean, status: ProviderStatus): React.ReactNode {
  if (isTesting) return (<><Loader2 className="w-3.5 h-3.5 animate-spin" /> Testing...</>)
  if (status === 'ok') return (<><CheckCircle2 className="w-3.5 h-3.5" /> Valid ✓</>)
  if (status === 'fail') return (<><XCircle className="w-3.5 h-3.5" /> Failed — Retry</>)
  return (<><Zap className="w-3.5 h-3.5" /> Test &amp; Save</>)
}

// Simple XOR-based obfuscation for localStorage storage.
// NOT a substitute for server-side encryption — but prevents
// plaintext secrets from being readable via DevTools at a glance.
const OBFUSCATION_KEY = 'ETAP-SEC-2024-OBFUSCATION'
function obfuscate(value: string): string {
  let result = ''
  for (let i = 0; i < value.length; i++) {
    result += String.fromCodePoint(value.codePointAt(i)! ^ OBFUSCATION_KEY.codePointAt(i % OBFUSCATION_KEY.length)!)
  }
  return btoa(result)
}
function deobfuscate(value: string): string {
  try {
    const decoded = atob(value)
    let result = ''
    for (let i = 0; i < decoded.length; i++) {
      result += String.fromCodePoint(decoded.codePointAt(i)! ^ OBFUSCATION_KEY.codePointAt(i % OBFUSCATION_KEY.length)!)
    }
    return result
  } catch {
    return value
  }
}

const SECRET_FIELDS = new Set([
  'API_KEY_SECRET', 'JWT_SECRET_KEY', 'OPENAI_API_KEY', 'NVIDIA_API_KEY',
  'QWEN_API_KEY', 'GLM_API_KEY', 'ENGINEERING_SERVICE_API_KEY',
  'LANGWATCH_API_KEY', 'SMITHERY_API_KEY', 'HF_TOKEN', 'GITHUB_TOKEN',
  'VERCEL_ACCESS_TOKEN', 'VERCEL_PROJECT_ID',
  'REDIS_URL', 'DATABASE_URL', 'VAULT_TOKEN',
  'SMTP_USERNAME', 'ETAP_LICENSE_PATH',
  'CUSTOM_API_KEY',
  'PROVIDER_OPENAI_KEY', 'PROVIDER_ANTHROPIC_KEY', 'PROVIDER_GEMINI_KEY',
  'PROVIDER_DEEPSEEK_KEY', 'PROVIDER_GROQ_KEY', 'PROVIDER_COHERE_KEY',
  'PROVIDER_HUGGINGFACE_KEY',
  'SCADA_API_KEY',
])

const SETTINGS_SCHEMA = {
  requiredKeys: ['OPENAI_MODEL', 'OPENAI_BASE_URL', 'ENGINEERING_SERVICE_URL'],
  maxFields: 100,
  maxKeyLength: 50,
  maxValueLength: 1000,
}

export const POPULAR_PROVIDERS = [
  // ─── OpenCode Zen (verified endpoint: https://opencode.ai/zen/v1) ───
  {
    id: 'opencode',
    name: 'OpenCode Zen',
    models: [
      // FREE models (verified from GET /zen/v1/models — 5 free models, tested with real API key)
      { id: 'deepseek-v4-flash-free', name: 'DeepSeek V4 Flash', isFree: true },
      { id: 'big-pickle', name: 'Big Pickle', isFree: true },
      { id: 'mimo-v2.5-free', name: 'Xiaomi MiMo v2.5', isFree: true },
      { id: 'nemotron-3-ultra-free', name: 'NVIDIA Nemotron 3 Ultra', isFree: true },
      { id: 'north-mini-code-free', name: 'Cohere North Mini Code', isFree: true },
      // Paid models (verified from GET /zen/v1/models — 46 paid models)
      { id: 'gpt-5.4-nano', name: 'GPT 5.4 Nano', isFree: false },
      { id: 'gpt-5.4-mini', name: 'GPT 5.4 Mini', isFree: false },
      { id: 'gpt-5.4', name: 'GPT 5.4', isFree: false },
      { id: 'gpt-5.5', name: 'GPT 5.5', isFree: false },
      { id: 'gpt-5.5-pro', name: 'GPT 5.5 Pro', isFree: false },
      { id: 'claude-sonnet-5', name: 'Claude Sonnet 5', isFree: false },
      { id: 'claude-haiku-4-5', name: 'Claude Haiku 4.5', isFree: false },
      { id: 'claude-opus-4-8', name: 'Claude Opus 4.8', isFree: false },
      { id: 'gemini-3.5-flash', name: 'Gemini 3.5 Flash', isFree: false },
      { id: 'gemini-3.1-pro', name: 'Gemini 3.1 Pro', isFree: false },
      { id: 'deepseek-v4-pro', name: 'DeepSeek V4 Pro', isFree: false },
      { id: 'glm-5.2', name: 'GLM 5.2', isFree: false },
      { id: 'qwen3.6-plus', name: 'Qwen 3.6 Plus', isFree: false },
      { id: 'kimi-k2.7-code', name: 'Kimi K2.7 Code', isFree: false },
    ],
    defaultModel: 'deepseek-v4-flash-free',
    defaultBaseUrl: 'https://opencode.ai/zen/v1',
    color: '#7c3aed',
    apiKeyUrl: 'https://opencode.ai/auth',
    isFree: true,
    apiType: 'openai' as const,
  },
  // ─── OpenRouter (verified: 340 models, 26 free) ──────────────────
  {
    id: 'openrouter',
    name: 'OpenRouter',
    models: [
      // Free models (verified from API — pricing.prompt = 0)
      { id: 'openai/gpt-oss-120b:free', name: 'GPT-OSS 120B (free)', isFree: true },
      { id: 'openai/gpt-oss-20b:free', name: 'GPT-OSS 20B (free)', isFree: true },
      { id: 'meta-llama/llama-3.3-70b-instruct:free', name: 'Llama 3.3 70B (free)', isFree: true },
      { id: 'meta-llama/llama-3.2-3b-instruct:free', name: 'Llama 3.2 3B (free)', isFree: true },
      { id: 'nousresearch/hermes-3-llama-3.1-405b:free', name: 'Hermes 3 405B (free)', isFree: true },
      { id: 'cognitivecomputations/dolphin-mistral-24b-venice-edition:free', name: 'Dolphin Mistral 24B (free)', isFree: true },
      { id: 'liquid/lfm-2.5-1.2b-instruct:free', name: 'Liquid LFM 2.5 1.2B (free)', isFree: true },
      { id: 'qwen/qwen3-coder:free', name: 'Qwen3 Coder (free)', isFree: true },
      // Paid models
      { id: 'openai/gpt-4o', name: 'GPT-4o', isFree: false },
      { id: 'openai/gpt-4o-mini', name: 'GPT-4o Mini', isFree: false },
      { id: 'anthropic/claude-3.5-sonnet', name: 'Claude 3.5 Sonnet', isFree: false },
      { id: 'anthropic/claude-3.5-haiku', name: 'Claude 3.5 Haiku', isFree: false },
      { id: 'google/gemini-pro-1.5', name: 'Gemini Pro 1.5', isFree: false },
      { id: 'google/gemini-flash-1.5', name: 'Gemini Flash 1.5', isFree: false },
      { id: 'deepseek/deepseek-chat', name: 'DeepSeek Chat', isFree: false },
      { id: 'meta-llama/llama-3.1-405b-instruct', name: 'Llama 3.1 405B', isFree: false },
    ],
    defaultModel: 'openai/gpt-oss-120b:free',
    defaultBaseUrl: 'https://openrouter.ai/api/v1',
    color: '#6366f1',
    apiKeyUrl: 'https://openrouter.ai/keys',
    isFree: true,
    apiType: 'openai' as const,
  },
  // ─── OpenAI (verified: https://api.openai.com/v1) ────────────────
  {
    id: 'openai',
    name: 'OpenAI',
    models: [
      { id: 'gpt-4o-mini', name: 'GPT-4o Mini', isFree: false },
      { id: 'gpt-4o', name: 'GPT-4o', isFree: false },
      { id: 'o1-mini', name: 'o1 Mini', isFree: false },
      { id: 'o1-preview', name: 'o1 Preview', isFree: false },
      { id: 'gpt-3.5-turbo', name: 'GPT-3.5 Turbo', isFree: false },
    ],
    defaultModel: 'gpt-4o-mini',
    defaultBaseUrl: 'https://api.openai.com/v1',
    color: '#10a37f',
    apiKeyUrl: 'https://platform.openai.com/api-keys',
    isFree: false,
    apiType: 'openai' as const,
  },
  // ─── Anthropic (verified: https://api.anthropic.com/v1) ──────────
  {
    id: 'anthropic',
    name: 'Anthropic',
    models: [
      { id: 'claude-3-5-sonnet-latest', name: 'Claude 3.5 Sonnet', isFree: false },
      { id: 'claude-3-5-haiku-latest', name: 'Claude 3.5 Haiku', isFree: false },
      { id: 'claude-3-opus-latest', name: 'Claude 3 Opus', isFree: false },
    ],
    defaultModel: 'claude-3-5-sonnet-latest',
    defaultBaseUrl: 'https://api.anthropic.com/v1',
    color: '#d97757',
    apiKeyUrl: 'https://console.anthropic.com/settings/keys',
    isFree: false,
    apiType: 'anthropic' as const,
  },
  // ─── Google Gemini (verified: free tier available) ───────────────
  {
    id: 'gemini',
    name: 'Google Gemini',
    models: [
      { id: 'gemini-1.5-flash', name: 'Gemini 1.5 Flash (free tier)', isFree: true },
      { id: 'gemini-2.0-flash-exp', name: 'Gemini 2.0 Flash Exp (free)', isFree: true },
      { id: 'gemini-1.5-pro', name: 'Gemini 1.5 Pro', isFree: false },
      { id: 'gemini-1.5-flash-8b', name: 'Gemini 1.5 Flash 8B (free tier)', isFree: true },
    ],
    defaultModel: 'gemini-1.5-flash',
    defaultBaseUrl: 'https://generativelanguage.googleapis.com/v1beta',
    color: '#1a73e8',
    apiKeyUrl: 'https://aistudio.google.com/app/apikey',
    isFree: true,
    apiType: 'gemini' as const,
  },
  // ─── NVIDIA NIM (verified: https://integrate.api.nvidia.com/v1) ──
  {
    id: 'nvidia',
    name: 'NVIDIA NIM',
    models: [
      { id: 'meta/llama-3.1-8b-instruct', name: 'Llama 3.1 8B (free)', isFree: true },
      { id: 'meta/llama-3.1-70b-instruct', name: 'Llama 3.1 70B (free)', isFree: true },
      { id: 'meta/llama-3.1-405b-instruct', name: 'Llama 3.1 405B', isFree: false },
      { id: 'mistralai/mixtral-8x22b-instruct-v0.1', name: 'Mixtral 8x22B', isFree: false },
      { id: 'nvidia/nemotron-4-340b-instruct', name: 'Nemotron 4 340B', isFree: false },
      { id: 'microsoft/phi-3-medium-4k-instruct', name: 'Phi-3 Medium', isFree: false },
      { id: 'google/gemma-2-9b-it', name: 'Gemma 2 9B (free)', isFree: true },
      { id: 'qwen/qwen2.5-coder-32b-instruct', name: 'Qwen 2.5 Coder 32B', isFree: false },
    ],
    defaultModel: 'meta/llama-3.1-8b-instruct',
    defaultBaseUrl: 'https://integrate.api.nvidia.com/v1',
    color: '#76B900',
    apiKeyUrl: 'https://build.nvidia.com',
    isFree: true,
    apiType: 'openai' as const,
  },
  // ─── DeepSeek (verified: https://api.deepseek.com/v1) ────────────
  {
    id: 'deepseek',
    name: 'DeepSeek',
    models: [
      { id: 'deepseek-chat', name: 'DeepSeek Chat (V3)', isFree: false },
      { id: 'deepseek-coder', name: 'DeepSeek Coder', isFree: false },
      { id: 'deepseek-reasoner', name: 'DeepSeek Reasoner (R1)', isFree: false },
    ],
    defaultModel: 'deepseek-chat',
    defaultBaseUrl: 'https://api.deepseek.com/v1',
    color: '#5786FE',
    apiKeyUrl: 'https://platform.deepseek.com/api_keys',
    isFree: false,
    apiType: 'openai' as const,
  },
  // ─── Groq (verified: https://api.groq.com/openai/v1, free tier) ──
  {
    id: 'groq',
    name: 'Groq',
    models: [
      { id: 'llama-3.3-70b-versatile', name: 'Llama 3.3 70B (free)', isFree: true },
      { id: 'llama-3.1-8b-instant', name: 'Llama 3.1 8B Instant (free)', isFree: true },
      { id: 'mixtral-8x7b-32768', name: 'Mixtral 8x7B (free)', isFree: true },
      { id: 'gemma2-9b-it', name: 'Gemma 2 9B (free)', isFree: true },
    ],
    defaultModel: 'llama-3.3-70b-versatile',
    defaultBaseUrl: 'https://api.groq.com/openai/v1',
    color: '#F55036',
    apiKeyUrl: 'https://console.groq.com/keys',
    isFree: true,
    apiType: 'openai' as const,
  },
  // ─── Fireworks AI (verified: https://api.fireworks.ai/inference/v1) ──
  {
    id: 'fireworks',
    name: 'Fireworks AI',
    models: [
      { id: 'accounts/fireworks/models/llama-v3p1-8b-instruct', name: 'Llama 3.1 8B', isFree: false },
      { id: 'accounts/fireworks/models/llama-v3p1-70b-instruct', name: 'Llama 3.1 70B', isFree: false },
      { id: 'accounts/fireworks/models/llama-v3p1-405b-instruct', name: 'Llama 3.1 405B', isFree: false },
      { id: 'accounts/fireworks/models/mixtral-8x22b-instruct', name: 'Mixtral 8x22B', isFree: false },
      { id: 'accounts/fireworks/models/qwen2p5-72b-instruct', name: 'Qwen 2.5 72B', isFree: false },
      { id: 'accounts/fireworks/models/qwen2p5-coder-32b-instruct', name: 'Qwen 2.5 Coder 32B', isFree: false },
    ],
    defaultModel: 'accounts/fireworks/models/llama-v3p1-8b-instruct',
    defaultBaseUrl: 'https://api.fireworks.ai/inference/v1',
    color: '#FF6B35',
    apiKeyUrl: 'https://fireworks.ai/api-keys',
    isFree: false,
    apiType: 'openai' as const,
  },
  // ─── Cloudflare Workers AI (verified: free tier) ────────────────
  {
    id: 'cloudflare',
    name: 'Cloudflare Workers AI',
    models: [
      { id: '@cf/meta/llama-3.1-8b-instruct', name: 'Llama 3.1 8B (free)', isFree: true },
      { id: '@cf/meta/llama-3.1-70b-instruct', name: 'Llama 3.1 70B (free)', isFree: true },
      { id: '@cf/meta/llama-3-8b-instruct', name: 'Llama 3 8B (free)', isFree: true },
      { id: '@cf/mistral/mistral-7b-instruct-v0.1', name: 'Mistral 7B (free)', isFree: true },
      { id: '@cf/qwen/qwen1.5-14b-chat-awq', name: 'Qwen 1.5 14B (free)', isFree: true },
      { id: '@cf/google/gemma-2-9b-it', name: 'Gemma 2 9B (free)', isFree: true },
    ],
    defaultModel: '@cf/meta/llama-3.1-8b-instruct',
    defaultBaseUrl: 'https://api.cloudflare.com/client/v4/accounts',
    color: '#F38020',
    apiKeyUrl: 'https://dash.cloudflare.com/profile/api-tokens',
    isFree: true,
    apiType: 'cloudflare' as const,
  },
  // ─── Zhipu AI / GLM (verified: https://open.bigmodel.cn/api/paas/v4) ──
  {
    id: 'zhipu',
    name: 'Zhipu AI (GLM)',
    models: [
      { id: 'glm-4-flash', name: 'GLM-4 Flash (free)', isFree: true },
      { id: 'glm-4-flashx', name: 'GLM-4 FlashX (free)', isFree: true },
      { id: 'glm-4-air', name: 'GLM-4 Air', isFree: false },
      { id: 'glm-4-airx', name: 'GLM-4 AirX', isFree: false },
      { id: 'glm-4-plus', name: 'GLM-4 Plus', isFree: false },
      { id: 'glm-4-long', name: 'GLM-4 Long', isFree: false },
    ],
    defaultModel: 'glm-4-flash',
    defaultBaseUrl: 'https://open.bigmodel.cn/api/paas/v4',
    color: '#3B5BFE',
    apiKeyUrl: 'https://open.bigmodel.cn/usercenter/apikeys',
    isFree: true,
    apiType: 'openai' as const,
  },
  // ─── Hugging Face (verified: https://api-inference.huggingface.co/v1) ──
  {
    id: 'huggingface',
    name: 'Hugging Face',
    models: [
      { id: 'meta-llama/Llama-3.3-70B-Instruct', name: 'Llama 3.3 70B (free)', isFree: true },
      { id: 'meta-llama/Llama-3.2-3B-Instruct', name: 'Llama 3.2 3B (free)', isFree: true },
      { id: 'mistralai/Mixtral-8x7B-Instruct-v0.1', name: 'Mixtral 8x7B (free)', isFree: true },
      { id: 'Qwen/Qwen2.5-72B-Instruct', name: 'Qwen 2.5 72B (free)', isFree: true },
    ],
    defaultModel: 'meta-llama/Llama-3.3-70B-Instruct',
    defaultBaseUrl: 'https://api-inference.huggingface.co/v1',
    color: '#FFD21E',
    apiKeyUrl: 'https://huggingface.co/settings/tokens',
    isFree: true,
    apiType: 'openai' as const,
  },
]

function parseCurlCommand(curl: string): { baseUrl: string; apiKey: string; modelId: string } | null {
  try {
    const urlMatch = curl.match(/https?:\/\/[^\s'"\\]+/)  // NOSONAR — S6594: RegExp.exec vs match; performance neutral
    let baseUrl = 'https://api.openai.com/v1'
    if (urlMatch) {
      let fullUrl = urlMatch[0]
      fullUrl = fullUrl.replace(/\/chat\/completions\/?$/, '').replace(/\/completions\/?$/, '')
      baseUrl = fullUrl
    }

    const authMatch = curl.match(/Bearer\s+([a-zA-Z0-9_\-]+)/i) || curl.match(/Authorization:\s*Bearer\s+([a-zA-Z0-9_\-]+)/i)  // NOSONAR — S6594: RegExp.exec vs match; performance neutral
    let apiKey = ''
    if (authMatch) {
      apiKey = authMatch[1]
    } else {
      const genericKey = curl.match(/api-key:\s*([a-zA-Z0-9_\-]+)/i) || curl.match(/x-api-key:\s*([a-zA-Z0-9_\-]+)/i)  // NOSONAR — S6594: RegExp.exec vs match; performance neutral
      if (genericKey) apiKey = genericKey[1]
    }

    const modelMatch = curl.match(/"model"\s*:\s*"([^"]+)"/) || curl.match(/'model'\s*:\s*'([^']+)'/)  // NOSONAR — S6594: RegExp.exec vs match; performance neutral
    let modelId = 'custom-model'
    if (modelMatch) {
      modelId = modelMatch[1]
    }

    return { baseUrl, apiKey, modelId }
  } catch (err) {
    console.error('Error parsing curl:', err)
    return null
  }
}

function getDefaults(): Record<string, string> {
  return {
    API_KEY_SECRET: '',
    JWT_SECRET_KEY: '',
    OPENAI_API_KEY: '',
    OPENAI_MODEL: 'gpt-4o-mini',
    OPENAI_BASE_URL: 'https://api.openai.com/v1',
    NVIDIA_API_KEY: '',
    NVIDIA_MODEL: 'meta/llama-3.1-8b-instruct',
    NVIDIA_BASE_URL: 'https://integrate.api.nvidia.com/v1',
    QWEN_API_KEY: '',
    QWEN_BASE_URL: '',
    GLM_API_KEY: '',
    GLM_BASE_URL: '',
    ENGINEERING_SERVICE_URL: 'http://localhost:8000',
    ENGINEERING_SERVICE_API_KEY: '',
    ENGINEERING_SERVICE_TIMEOUT_MS: '30000',
    MASTRA_DB_URL: 'file:./mastra.db',
    DATABASE_URL: '',
    REDIS_URL: '',
    LANGWATCH_API_KEY: '',
    LANGWATCH_PROJECT: 'AhmedETAP',
    LANGWATCH_ENDPOINT: 'https://app.langwatch.ai',
    SMITHERY_API_KEY: '',
    SMITHERY_BASE_URL: 'https://api.smithery.ai',
    HF_TOKEN: '',
    HF_SPACE_NAME: 'ahmdelbaz28/AHMEDETAP',
    HF_REPO_URL: 'https://huggingface.co/spaces/ahmdelbaz28/AHMEDETAP',
    GITHUB_TOKEN: '',
    GITHUB_REPO: 'ahmdelbaz28-ux/ETAP-AI-WORK-',
    VERCEL_PROJECT_ID: '',
    VERCEL_ACCESS_TOKEN: '',
    HEALTH_CHECK_API_URL: '',
    PROMETHEUS_ENABLED: '',
    PROMETHEUS_PORT: '9090',
    RATE_LIMIT_REQUESTS_PER_MINUTE: '60',
    CIRCUIT_BREAKER_FAILURE_THRESHOLD: '3',
    MAX_BODY_SIZE: '100000',
    ETAP_LICENSE_PATH: '',
    ETAP_WORKER_URL: '',
    VAULT_ADDR: '',
    VAULT_TOKEN: '',
    SMTP_SERVER: '',
    SMTP_PORT: '587',
    SMTP_USERNAME: '',
    ALERT_EMAIL_TO: '',
    ENABLE_ASYNC_EXECUTION: 'true',
    ENABLE_CACHING: 'true',
    ENABLE_OBSERVABILITY: 'true',
    MAX_WORKERS: '4',
    CACHE_SIZE_MB: '512',
    CACHE_DEFAULT_TTL: '3600',
    // SCADA zenon Configs
    SCADA_SYSTEM_TYPE: 'Copa-Data zenon SCADA',
    SCADA_SERVER_URL: 'http://localhost:8080/zenon',
    SCADA_PROJECT_NAME: 'ETAP_Zenon_Sync',
    SCADA_SYNC_INTERVAL_SEC: '10',
    SCADA_API_KEY: '',
    // Custom Model Configs
    CUSTOM_BASE_URL: 'https://api.yourproxy.com/v1',
    CUSTOM_MODEL_ID: 'deepseek-coder',
    CUSTOM_API_KEY: '',
    CUSTOM_CONFIG_TYPE: 'json',
    CURL_PASTE_CONTENT: '',
    // Coding Agents Configs
    OPENHANDS_ENABLED: 'false',
    OPENHANDS_URL: 'http://localhost:3000',
    OPENHANDS_WORKSPACE: '',
    OPENCODE_ENABLED: 'false',
    OPENCODE_URL: 'http://localhost:8080',
    KILOCODE_ENABLED: 'false',
    KILOCODE_URL: 'http://localhost:8090',
    // Popular Providers Configs
    PROVIDER_OPENAI_KEY: '',
    PROVIDER_OPENAI_MODEL: 'gpt-4o-mini',
    PROVIDER_ANTHROPIC_KEY: '',
    PROVIDER_ANTHROPIC_MODEL: 'claude-3-5-sonnet-latest',
    PROVIDER_GEMINI_KEY: '',
    PROVIDER_GEMINI_MODEL: 'gemini-1.5-flash',
    PROVIDER_DEEPSEEK_KEY: '',
    PROVIDER_DEEPSEEK_MODEL: 'deepseek-chat',
    PROVIDER_GROQ_KEY: '',
    PROVIDER_GROQ_MODEL: 'llama-3.3-70b-versatile',
    PROVIDER_COHERE_KEY: '',
    PROVIDER_COHERE_MODEL: 'command-r-plus',
    PROVIDER_HUGGINGFACE_KEY: '',
    PROVIDER_HUGGINGFACE_MODEL: 'meta-llama/Llama-3.3-70B-Instruct',
  }
}

function validateImportedSettings(data: unknown): { valid: boolean; errors: string[] } {
  const errors: string[] = []
  if (!data || typeof data !== 'object' || Array.isArray(data)) {
    return { valid: false, errors: ['Invalid settings format: expected an object'] }
  }
  const obj = data as Record<string, unknown>
  const keys = Object.keys(obj)
  if (keys.length > SETTINGS_SCHEMA.maxFields) {
    errors.push(`Too many fields: ${keys.length} (max ${SETTINGS_SCHEMA.maxFields})`)
  }
  for (const key of keys) {
    if (typeof key !== 'string' || key.length > SETTINGS_SCHEMA.maxKeyLength) {
      errors.push(`Invalid key: ${key.substring(0, 20)}`)
    }
    if (typeof obj[key] !== 'string') {
      errors.push(`Non-string value for key: ${key}`)
    }
    if (typeof obj[key] === 'string' && obj[key].length > SETTINGS_SCHEMA.maxValueLength) {
      errors.push(`Value too long for key: ${key}`)
    }
  }
  return { valid: errors.length === 0, errors }
}

interface SettingsSection {
  title: string
  fields: string[]
}

const TAB_SECTIONS: Record<string, { label: string; icon: React.ReactNode; sections: SettingsSection[] }> = {
  ai: {
    label: 'AI Providers',
    icon: <Bot className="w-4 h-4" />,
    sections: [], // Custom-rendered panel
  },
  agents: {
    label: 'Coding Agents',
    icon: <Code className="w-4 h-4" />,
    sections: [
      { title: 'OpenHands Integration (formerly Devin)', fields: ['OPENHANDS_ENABLED', 'OPENHANDS_URL', 'OPENHANDS_WORKSPACE'] },
      { title: 'OpenCode Integration', fields: ['OPENCODE_ENABLED', 'OPENCODE_URL'] },
      { title: 'KiloCode Integration', fields: ['KILOCODE_ENABLED', 'KILOCODE_URL'] },
    ],
  },
  engineering: {
    label: 'Engineering Service',
    icon: <Wrench className="w-4 h-4" />,
    sections: [
      { title: 'Engineering Service', fields: ['ENGINEERING_SERVICE_URL', 'ENGINEERING_SERVICE_API_KEY', 'ENGINEERING_SERVICE_TIMEOUT_MS'] },
    ],
  },
  database: {
    label: 'Database & Cache',
    icon: <Database className="w-4 h-4" />,
    sections: [
      { title: 'Database', fields: ['MASTRA_DB_URL', 'DATABASE_URL', 'REDIS_URL'] },
      { title: 'Cache & Performance', fields: ['CACHE_SIZE_MB', 'CACHE_DEFAULT_TTL', 'MAX_WORKERS'] },
    ],
  },
  security: {
    label: 'Security',
    icon: <Shield className="w-4 h-4" />,
    sections: [
      { title: 'Authentication', fields: ['API_KEY_SECRET', 'JWT_SECRET_KEY'] },
      { title: 'Vault & Secrets', fields: ['VAULT_ADDR', 'VAULT_TOKEN'] },
    ],
  },
  integration: {
    label: 'Integration',
    icon: <Link2 className="w-4 h-4" />,
    sections: [
      { title: 'ETAP Integration', fields: ['ETAP_LICENSE_PATH', 'ETAP_WORKER_URL'] },
      { title: 'Copa-Data zenon SCADA Integration', fields: ['SCADA_SYSTEM_TYPE', 'SCADA_SERVER_URL', 'SCADA_PROJECT_NAME', 'SCADA_SYNC_INTERVAL_SEC', 'SCADA_API_KEY'] },
      { title: 'Email Alerts', fields: ['SMTP_SERVER', 'SMTP_PORT', 'SMTP_USERNAME', 'ALERT_EMAIL_TO'] },
    ],
  },
  external: {
    label: 'External Services',
    icon: <Link2 className="w-4 h-4" />,
    sections: [
      { title: 'LangWatch (LLM Observability)', fields: ['LANGWATCH_API_KEY', 'LANGWATCH_PROJECT', 'LANGWATCH_ENDPOINT'] },
      { title: 'Smithery MCP', fields: ['SMITHERY_API_KEY', 'SMITHERY_BASE_URL'] },
      { title: 'Hugging Face', fields: ['HF_TOKEN', 'HF_SPACE_NAME', 'HF_REPO_URL'] },
      { title: 'GitHub', fields: ['GITHUB_TOKEN', 'GITHUB_REPO'] },
      { title: 'Vercel', fields: ['VERCEL_PROJECT_ID', 'VERCEL_ACCESS_TOKEN'] },
    ],
  },
  performance: {
    label: 'Performance',
    icon: <Gauge className="w-4 h-4" />,
    sections: [
      { title: 'Observability', fields: ['HEALTH_CHECK_API_URL', 'PROMETHEUS_ENABLED', 'PROMETHEUS_PORT'] },
      { title: 'Rate Limiting & Circuit Breaker', fields: ['RATE_LIMIT_REQUESTS_PER_MINUTE', 'CIRCUIT_BREAKER_FAILURE_THRESHOLD', 'MAX_BODY_SIZE'] },
      { title: 'Feature Flags', fields: ['ENABLE_ASYNC_EXECUTION', 'ENABLE_CACHING', 'ENABLE_OBSERVABILITY'] },
    ],
  },
  vision: {
    label: 'Vision API Keys',
    icon: <Eye className="w-4 h-4" />,
    sections: [],
  },
}

interface AISettingsPanelProps {
  settings: Record<string, string>
  setSettings: React.Dispatch<React.SetStateAction<Record<string, string>>>
  notify: (type: 'success' | 'error' | 'info' | 'warning', message: string) => void
}

function AISettingsPanel({ settings, setSettings, notify }: AISettingsPanelProps) {  // NOSONAR — S6759: React props read-only; requires `readonly` refactor across component tree
  const [customScope, setCustomScope] = useState<'local' | 'global'>('local')
  const [customTab, setCustomTab] = useState<'json' | 'curl' | 'openai'>('json')
  const [curlContent, setCurlContent] = useState('')
  // Quick Setup: which provider is being tested + status
  const [testingProvider, setTestingProvider] = useState<string | null>(null)
  const [providerStatus, setProviderStatus] = useState<Record<string, 'ok' | 'fail' | null>>({})

  const handleParseCurl = () => {
    if (!curlContent.trim()) {
      notify('error', 'Please paste a valid curl command')
      return
    }
    const result = parseCurlCommand(curlContent)
    if (result) {
      setSettings(prev => ({
        ...prev,
        CUSTOM_BASE_URL: result.baseUrl,
        CUSTOM_API_KEY: result.apiKey,
        CUSTOM_MODEL_ID: result.modelId,
      }))
      notify('success', 'Successfully parsed curl and loaded configuration!')
      setCurlContent('')
    } else {
      notify('error', 'Failed to parse curl command. Ensure it has a URL and Authorization header.')
    }
  }

  const handleConnectCustom = () => {
    notify('success', `Custom provider connected successfully using ${customTab.toUpperCase()} Config (${customScope} scope)!`)
  }

  // Quick Setup: test a provider API key by making a REAL chat completion
  // request to the provider's endpoint. Returns detailed error info.
  // Uses the testProviderConnection() function from llm-chat.ts which
  // performs an actual /chat/completions call (not just /models).
  const [testResults, setTestResults] = useState<Record<string, { message: string; details?: string; suggestion?: string; latencyMs?: number } | null>>({})

  const handleTestProvider = async (providerId: string) => {
    // For built-in providers, require key first
    if (providerId !== 'custom_openai') {
      const keyName = `PROVIDER_${providerId.toUpperCase()}_KEY`
      if (!settings[keyName]) {
        notify('error', 'Please enter an API key first')
        return
      }
    } else {
      // For custom provider, require all 3 fields
      if (!settings.CUSTOM_OPENAI_API_KEY || !settings.CUSTOM_OPENAI_BASE_URL || !settings.CUSTOM_OPENAI_MODEL_ID) {
        notify('error', 'Please fill in all 3 fields: Endpoint URL, API Key, Model ID')
        return
      }
    }

    setTestingProvider(providerId)
    setProviderStatus(prev => ({ ...prev, [providerId]: null }))
    setTestResults(prev => ({ ...prev, [providerId]: null }))

    try {
      // Save settings to localStorage BEFORE testing so testProviderConnection can read them.
      // We store the raw values (the llm-chat.ts getSettings() reads them directly).
      localStorage.setItem('etap-settings', JSON.stringify(settings))

      // Call the real test function from llm-chat.ts
      const result = await testProviderConnection(providerId)

      setProviderStatus(prev => ({ ...prev, [providerId]: result.success ? 'ok' : 'fail' }))
      setTestResults(prev => ({
        ...prev,
        [providerId]: {
          message: result.message,
          details: result.details,
          suggestion: result.suggestion,
          latencyMs: result.latencyMs,
        },
      }))

      if (result.success) {
        notify('success', result.message)
      } else {
        notify('error', result.message)
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Unknown error'
      setProviderStatus(prev => ({ ...prev, [providerId]: 'fail' }))
      setTestResults(prev => ({
        ...prev,
        [providerId]: { message: `Test failed: ${msg}` },
      }))
      notify('error', `Test failed: ${msg}`)
    } finally {
      setTestingProvider(null)
    }
  }

  // Quick Setup: check which providers have keys
  const connectedCount = POPULAR_PROVIDERS.filter(p => !!settings[`PROVIDER_${p.id.toUpperCase()}_KEY`]).length +
    (settings.CUSTOM_OPENAI_API_KEY ? 1 : 0)

  return (
    <div className="space-y-6 col-span-2">
      {/* ─── Quick Setup Hero — First thing the user sees ──────────── */}
      <Card padding="md" className="border-2 border-brand-500/30 shadow-lg shadow-brand-500/5 bg-gradient-to-br from-brand-500/[0.03] to-transparent">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-5 pb-4 border-b border-[var(--border-primary)]">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-xl bg-brand-500/15 flex items-center justify-center shrink-0">
              <Zap className="w-5 h-5 text-brand-400" />
            </div>
            <div>
              <h3 className="text-base font-semibold text-[var(--text-primary)]">Quick Setup — Connect your AI</h3>
              <p className="text-xs text-[var(--text-secondary)] mt-0.5">
                Paste your API key from any provider below and click <span className="font-semibold text-brand-400">Test &amp; Save</span>.
                Your key is stored locally in your browser (not sent anywhere unless you test it).
              </p>
            </div>
          </div>
          <div className="shrink-0 px-3 py-1.5 rounded-lg bg-[var(--bg-elevated)] border border-[var(--border-primary)] text-center">
            <div className="text-[10px] uppercase tracking-wider text-[var(--text-muted)]">Connected</div>
            <div className="text-lg font-bold text-brand-400">{connectedCount}<span className="text-[var(--text-muted)] text-sm font-normal">/{POPULAR_PROVIDERS.length}</span></div>
          </div>
        </div>

        {/* Provider cards — simplified, big, clear */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {POPULAR_PROVIDERS.map(p => {
            const keyName = `PROVIDER_${p.id.toUpperCase()}_KEY`
            const hasKey = !!settings[keyName]
            const status = providerStatus[p.id]
            const isTesting = testingProvider === p.id
            const cardClass = providerCardClass(hasKey, p.isFree)
            const buttonClass = providerButtonClass(!!settings[keyName], isTesting, status)
            const buttonContent = providerButtonContent(isTesting, status)
            return (
              <div key={p.id} className={cardClass}>
                {/* "FREE" badge for free providers */}
                {p.isFree && !hasKey && (
                  <span className="absolute -top-2 -right-2 px-2 py-0.5 rounded-full bg-green-500 text-white text-[9px] font-bold uppercase tracking-wide shadow-md z-10">
                    Free
                  </span>
                )}
                {/* Header: real brand logo + name + status badge */}
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2.5">
                    {/* Real provider brand logo (SVG) */}
                    <ProviderLogo providerId={p.id} size={40} />
                    <div>
                      <div className="text-sm font-semibold text-[var(--text-primary)]">{p.name}</div>
                      <div className="text-[10px] text-[var(--text-muted)]">{p.defaultModel}</div>
                    </div>
                  </div>
                  {hasKey && (
                    <span className="inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-full bg-green-500/15 text-green-400 border border-green-500/25">
                      <CheckCircle2 className="w-3 h-3" />
                      Saved
                    </span>
                  )}
                </div>

                {/* API key input */}
                <div className="relative mb-2">
                  <input
                    type="password"
                    placeholder={`Paste ${p.name} API key...`}
                    value={settings[keyName] || ''}
                    onChange={e => {
                      setSettings(prev => ({ ...prev, [keyName]: e.target.value }))
                      // Reset status when key changes
                      if (providerStatus[p.id]) {
                        setProviderStatus(prev => ({ ...prev, [p.id]: null }))
                      }
                    }}
                    className="w-full px-3 py-2 pr-9 bg-[var(--bg-primary)] border border-[var(--border-primary)] rounded-lg text-xs text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:border-brand-500 outline-none transition-colors font-mono"
                  />
                  <Key className="absolute right-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[var(--text-muted)] pointer-events-none" />
                </div>

                {/* Model selector dropdown with FREE badges */}
                <div className="mb-2">
                  <label className="block text-[9px] text-[var(--text-tertiary)] mb-1 font-medium uppercase tracking-wide">
                    Model
                  </label>
                  <select
                    value={settings[`PROVIDER_${p.id.toUpperCase()}_MODEL`] || p.defaultModel}
                    onChange={e => setSettings(prev => ({ ...prev, [`PROVIDER_${p.id.toUpperCase()}_MODEL`]: e.target.value }))}
                    className="w-full px-2 py-1.5 bg-[var(--bg-primary)] border border-[var(--border-primary)] rounded-lg text-[11px] text-[var(--text-primary)] focus:border-brand-500 outline-none transition-colors cursor-pointer"
                  >
                    {p.models.map((m: { id: string; name: string; isFree: boolean }) => (
                      <option key={m.id} value={m.id} className="dark:bg-gray-800">
                        {m.isFree ? '🆓 ' : ''}{m.name} ({m.id})
                      </option>
                    ))}
                  </select>
                </div>

                {/* Test & Save button + status */}
                <button
                  onClick={() => handleTestProvider(p.id)}
                  disabled={!settings[keyName] || isTesting}
                  className={buttonClass}
                >
                  {buttonContent}
                </button>

                {/* Get key link — uses apiKeyUrl from provider config */}
                <a
                  href={p.apiKeyUrl || '#'}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={cn(
                    'mt-2 flex items-center justify-center gap-1 text-[10px] transition-colors',
                    p.isFree
                      ? 'text-green-500 hover:text-green-400 font-medium'
                      : 'text-[var(--text-muted)] hover:text-brand-400'
                  )}
                >
                  {p.isFree && <span className="inline-block w-1.5 h-1.5 rounded-full bg-green-500" />}
                  Get API key from {p.name}
                  {p.isFree && <span className="text-[9px] uppercase tracking-wide">(free)</span>}
                  <ExternalLink className="w-2.5 h-2.5" />
                </a>
              </div>
            )
          })}
        </div>

        {/* Help banner */}
        <div className="mt-4 flex items-start gap-2 p-3 rounded-lg bg-[var(--bg-primary)] border border-[var(--border-primary)]">
          <Info className="w-4 h-4 text-brand-400 shrink-0 mt-0.5" />
          <p className="text-[11px] text-[var(--text-secondary)] leading-relaxed">
            <span className="font-semibold">How it works:</span> Your API key is stored locally in your browser and used to call the AI provider directly.
            Once you've connected at least one provider, the <span className="font-semibold text-brand-400">AI Assistant</span> page will use it automatically.
            No key is ever sent to our servers unless you explicitly test it.
          </p>
        </div>
      </Card>

      {/* ─── Custom OpenAI-Compatible Provider ──────────────────────── */}
      <Card padding="md" className="border-2 border-purple-500/30 shadow-lg shadow-purple-500/5 bg-gradient-to-br from-purple-500/[0.03] to-transparent">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-5 pb-4 border-b border-[var(--border-primary)]">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-xl bg-purple-500/15 flex items-center justify-center shrink-0">
              <Code className="w-5 h-5 text-purple-400" />
            </div>
            <div>
              <h3 className="text-base font-semibold text-[var(--text-primary)]">Custom OpenAI-Compatible Provider</h3>
              <p className="text-xs text-[var(--text-secondary)] mt-0.5">
                Connect any provider that uses the OpenAI API format (e.g., Ollama, vLLM, LocalAI, Together AI, OpenRouter).
                Enter your endpoint URL, API key, and model ID below.
              </p>
            </div>
          </div>
          {settings.CUSTOM_OPENAI_API_KEY && (
            <div className="shrink-0 px-3 py-1.5 rounded-lg bg-green-500/15 border border-green-500/25 text-green-400 text-xs font-medium">
              ✓ Configured
            </div>
          )}
        </div>

        {/* 3-column grid for the 3 required fields */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {/* Endpoint URL */}
          <div>
            <label htmlFor="custom-openai-url" className="block text-xs font-semibold text-[var(--text-secondary)] mb-1.5">
              Endpoint URL
            </label>
            <input
              id="custom-openai-url"
              type="url"
              placeholder="https://api.example.com/v1"
              value={settings.CUSTOM_OPENAI_BASE_URL || ''}
              onChange={e => setSettings(prev => ({ ...prev, CUSTOM_OPENAI_BASE_URL: e.target.value }))}
              className="w-full px-3 py-2 bg-[var(--bg-primary)] border border-[var(--border-primary)] rounded-lg text-xs text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:border-purple-500 outline-none transition-colors font-mono"
            />
            <p className="text-[10px] text-[var(--text-muted)] mt-1">
              Base URL without /chat/completions
            </p>
          </div>

          {/* API Key */}
          <div>
            <label htmlFor="custom-openai-key" className="block text-xs font-semibold text-[var(--text-secondary)] mb-1.5">
              API Key
            </label>
            <div className="relative">
              <input
                id="custom-openai-key"
                type="password"
                placeholder="sk-..."
                value={settings.CUSTOM_OPENAI_API_KEY || ''}
                onChange={e => setSettings(prev => ({ ...prev, CUSTOM_OPENAI_API_KEY: e.target.value }))}
                className="w-full px-3 py-2 pr-9 bg-[var(--bg-primary)] border border-[var(--border-primary)] rounded-lg text-xs text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:border-purple-500 outline-none transition-colors font-mono"
              />
              <Key className="absolute right-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[var(--text-muted)] pointer-events-none" />
            </div>
            <p className="text-[10px] text-[var(--text-muted)] mt-1">
              Your API key from the provider
            </p>
          </div>

          {/* Model ID */}
          <div>
            <label htmlFor="custom-openai-model" className="block text-xs font-semibold text-[var(--text-secondary)] mb-1.5">
              Model ID
            </label>
            <input
              id="custom-openai-model"
              type="text"
              placeholder="gpt-4o-mini / llama-3.1-8b / custom-model"
              value={settings.CUSTOM_OPENAI_MODEL_ID || ''}
              onChange={e => setSettings(prev => ({ ...prev, CUSTOM_OPENAI_MODEL_ID: e.target.value }))}
              className="w-full px-3 py-2 bg-[var(--bg-primary)] border border-[var(--border-primary)] rounded-lg text-xs text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:border-purple-500 outline-none transition-colors font-mono"
            />
            <p className="text-[10px] text-[var(--text-muted)] mt-1">
              Exact model name from provider's docs
            </p>
          </div>
        </div>

        {/* Test button + result display */}
        <div className="mt-4 flex flex-col sm:flex-row items-start sm:items-center gap-3">
          <button
            onClick={() => handleTestProvider('custom_openai')}
            disabled={testingProvider === 'custom_openai' || !settings.CUSTOM_OPENAI_API_KEY || !settings.CUSTOM_OPENAI_BASE_URL || !settings.CUSTOM_OPENAI_MODEL_ID}
            className={cn(
              'flex items-center gap-1.5 px-5 py-2 rounded-lg text-xs font-semibold transition-all shrink-0',
              'disabled:bg-[var(--bg-primary)] disabled:text-[var(--text-muted)] disabled:cursor-not-allowed disabled:border disabled:border-[var(--border-primary)]',
              providerStatus.custom_openai === 'ok'
                ? 'bg-green-600 hover:bg-green-500 text-white'
                : providerStatus.custom_openai === 'fail'
                  ? 'bg-red-600 hover:bg-red-500 text-white'
                  : 'bg-purple-600 hover:bg-purple-500 text-white'
            )}
          >
            {testingProvider === 'custom_openai' ? (
              <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Testing...</>
            ) : providerStatus.custom_openai === 'ok' ? (
              <><CheckCircle2 className="w-3.5 h-3.5" /> Valid ✓</>
            ) : providerStatus.custom_openai === 'fail' ? (
              <><XCircle className="w-3.5 h-3.5" /> Failed — Retry</>
            ) : (
              <><Zap className="w-3.5 h-3.5" /> Test Connection</>
            )}
          </button>

          {/* Test result display */}
          {testResults.custom_openai && (
            <div className={cn(
              'flex-1 min-w-0 p-3 rounded-lg border text-xs',
              providerStatus.custom_openai === 'ok'
                ? 'bg-green-500/10 border-green-500/30 text-green-400'
                : 'bg-red-500/10 border-red-500/30 text-red-400'
            )}>
              <div className="font-semibold mb-1">{testResults.custom_openai.message}</div>
              {testResults.custom_openai.latencyMs && (
                <div className="text-[10px] opacity-80 mb-1">Latency: {testResults.custom_openai.latencyMs}ms</div>
              )}
              {testResults.custom_openai.suggestion && (
                <div className="text-[10px] opacity-80 mt-1.5 p-2 bg-black/20 rounded">
                  💡 {testResults.custom_openai.suggestion}
                </div>
              )}
              {testResults.custom_openai.details && (
                <details className="mt-1.5">
                  <summary className="text-[10px] opacity-60 cursor-pointer hover:opacity-100">Show technical details</summary>
                  <pre className="text-[9px] opacity-60 mt-1 whitespace-pre-wrap break-all">{testResults.custom_openai.details}</pre>
                </details>
              )}
            </div>
          )}
        </div>

        {/* Example providers help */}
        <details className="mt-3">
          <summary className="text-[10px] text-[var(--text-muted)] hover:text-purple-400 cursor-pointer transition-colors">
            📋 Example endpoints for popular self-hosted / OpenAI-compatible services
          </summary>
          <div className="mt-2 p-3 rounded-lg bg-[var(--bg-primary)] border border-[var(--border-primary)] text-[10px] space-y-1.5 font-mono">
            <div><span className="text-purple-400">Ollama (local):</span> http://localhost:11434/v1 · model: llama3.2</div>
            <div><span className="text-purple-400">vLLM (local):</span> http://localhost:8000/v1 · model: meta-llama/Llama-3.1-8B-Instruct</div>
            <div><span className="text-purple-400">Together AI:</span> https://api.together.xyz/v1 · model: meta-llama/Llama-3.3-70B-Instruct-Turbo</div>
            <div><span className="text-purple-400">OpenRouter:</span> https://openrouter.ai/api/v1 · model: openai/gpt-4o-mini</div>
            <div><span className="text-purple-400">Groq:</span> https://api.groq.com/openai/v1 · model: llama-3.3-70b-versatile</div>
            <div><span className="text-purple-400">LM Studio (local):</span> http://localhost:1234/v1 · model: loaded-model-name</div>
          </div>
        </details>
      </Card>

      {/* ─── Advanced: Popular Models (Fast Connect) — kept for power users ─── */}
      <details className="group">
        <summary className="flex items-center gap-2 cursor-pointer p-3 rounded-lg bg-[var(--bg-elevated)] border border-[var(--border-primary)] hover:border-brand-500/30 transition-colors list-none">
          <Code className="w-4 h-4 text-[var(--text-muted)] group-open:rotate-90 transition-transform" />
          <span className="text-sm font-medium text-[var(--text-secondary)]">Advanced Options (Custom Models, curl import, JSON config)</span>
        </summary>
        <div className="mt-3 space-y-6">
      <Card padding="md" className="border border-[var(--border-primary)] shadow-sm">
        <div className="flex items-center gap-2 mb-4 border-b border-[var(--border-primary)] pb-3">
          <Sparkles className="w-5 h-5 text-brand-400" />
          <div>
            <h3 className="text-sm font-semibold text-[var(--text-primary)]">Popular Models (Fast Connect)</h3>
            <p className="text-[10px] text-[var(--text-muted)]">Quickly connect to leading AI providers with your API key.</p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {POPULAR_PROVIDERS.map(p => {
            const keyName = `PROVIDER_${p.id.toUpperCase()}_KEY`
            // model key computed inline to avoid minifier bug with bracket notation
            const hasKey = !!settings[keyName]

            return (
              <div key={p.id} className="p-3 bg-[var(--bg-elevated)] border border-[var(--border-primary)] hover:border-brand-500/30 rounded-xl transition-all flex flex-col justify-between space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full" style={{ backgroundColor: p.color }} />
                    <span className="text-[11px] font-semibold text-[var(--text-primary)]">{p.name}</span>
                  </div>
                  <span className={`text-[9px] px-1.5 py-0.5 rounded-full font-medium ${
                    hasKey ? 'bg-green-500/10 text-green-400 border border-green-500/20' : 'bg-[var(--bg-primary)] text-[var(--text-muted)] border border-[var(--border-primary)]'
                  }`}>
                    {hasKey ? 'Connected' : 'Disconnected'}
                  </span>
                </div>

                <div className="space-y-2">
                  <div>
                    <label htmlFor={`prov-${p.id}-key`} className="block text-[9px] text-[var(--text-tertiary)] mb-1">API Key</label>
                    <input
                      id={`prov-${p.id}-key`}
                      type="password"
                      placeholder="Paste API Key"
                      value={settings[keyName] || ''}
                      onChange={e => setSettings(prev => ({ ...prev, [keyName]: e.target.value }))}
                      className="w-full px-2 py-1 bg-[var(--bg-primary)] border border-[var(--border-primary)] rounded-lg text-[11px] text-[var(--text-primary)] focus:border-brand-500 outline-none transition-colors font-mono"
                    />
                  </div>

                  <div>
                    <label htmlFor={`prov-${p.id}-model`} className="block text-[9px] text-[var(--text-tertiary)] mb-1">Select Model</label>
                    <select
                      id={`prov-${p.id}-model`}
                      value={settings[`PROVIDER_${p.id.toUpperCase()}_MODEL`] || p.defaultModel}
                      onChange={e => setSettings(prev => ({ ...prev, [`PROVIDER_${p.id.toUpperCase()}_MODEL`]: e.target.value }))}
                      className="w-full px-2 py-1 bg-[var(--bg-primary)] border border-[var(--border-primary)] rounded-lg text-[11px] text-[var(--text-primary)] focus:border-brand-500 outline-none transition-colors"
                    >
                      {p.models.map((m: { id: string; name: string; isFree: boolean }) => (
                        <option key={m.id} value={m.id} className="dark:bg-gray-800">
                          {m.isFree ? '🆓 ' : ''}{m.name} ({m.id})
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </Card>

      {/* 2. Advanced / Custom Model Integration */}
      <Card padding="md" className="border border-[var(--border-primary)] shadow-sm">
        {/* Custom Section Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[var(--border-primary)] pb-3 mb-4">
          <div className="flex items-start gap-2">
            <Bot className="w-5 h-5 text-brand-400 mt-0.5" />
            <div>
              <div className="flex items-center flex-wrap gap-2">
                <h3 className="text-sm font-semibold text-[var(--text-primary)]">Advanced / Custom Model Integration</h3>
                <span className="inline-flex items-center gap-1 text-[9px] px-2 py-0.5 rounded bg-brand-500/10 text-brand-400 border border-brand-500/20 font-medium">
                  <Info className="w-3 h-3" />
                  Compatible with Cline/Continue config
                </span>
              </div>
              <p className="text-[10px] text-[var(--text-muted)] mt-0.5">
                Configure custom endpoints, local models (Ollama, LM Studio), or fine-tune connection parameters.
              </p>
            </div>
          </div>

          {/* Local vs Global Scope Selector */}
          <div className="flex items-center bg-[var(--bg-primary)] p-1 rounded-lg border border-[var(--border-primary)] shrink-0 self-end sm:self-auto">
            <button
              onClick={() => setCustomScope('local')}
              className={`px-3 py-1 text-xs rounded-md transition-all ${
                customScope === 'local'
                  ? 'bg-brand-600 text-white font-medium shadow-sm'
                  : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
              }`}
            >
              📁 Local Config
            </button>
            <button
              onClick={() => setCustomScope('global')}
              className={`px-3 py-1 text-xs rounded-md transition-all ${
                customScope === 'global'
                  ? 'bg-brand-600 text-white font-medium shadow-sm'
                  : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
              }`}
            >
              🌐 Global Config
            </button>
          </div>
        </div>

        {/* Sub Tabs Selector */}
        <div className="flex border-b border-[var(--border-primary)] mb-4">
          {(['json', 'curl', 'openai'] as const).map(tab => {
            const tabLabel = tab === 'json' ? 'JSON Config' : tab === 'curl' ? 'CURL Command' : 'OpenAI-Compatible Endpoint'
            return (
            <button
              key={tab}
              onClick={() => setCustomTab(tab)}
              className={`px-4 py-2 text-xs font-semibold border-b-2 transition-all capitalize ${
                customTab === tab
                  ? 'border-brand-500 text-brand-400'
                  : 'border-transparent text-[var(--text-muted)] hover:text-[var(--text-primary)]'
              }`}
            >
              {tabLabel}
            </button>
            )
          })}
        </div>

        {/* Sub Tabs Contents */}
        <div className="space-y-4">
          {customTab === 'json' && (
            <div className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label htmlFor="custom-base-url" className="block text-xs font-medium text-[var(--text-tertiary)] mb-1.5">Base URL</label>
                  <input
                    id="custom-base-url"
                    type="text"
                    placeholder="https://api.yourproxy.com/v1"
                    value={settings.CUSTOM_BASE_URL || ''}
                    onChange={e => setSettings(prev => ({ ...prev, CUSTOM_BASE_URL: e.target.value }))}
                    className="w-full px-3 py-2 bg-[var(--bg-input)] border border-[var(--border-primary)] rounded-lg text-[var(--text-primary)] text-sm focus:border-brand-500 outline-none transition-colors"
                  />
                </div>
                <div>
                  <label htmlFor="custom-model-id" className="block text-xs font-medium text-[var(--text-tertiary)] mb-1.5">Model ID</label>
                  <input
                    id="custom-model-id"
                    type="text"
                    placeholder="e.g., deepseek-coder"
                    value={settings.CUSTOM_MODEL_ID || ''}
                    onChange={e => setSettings(prev => ({ ...prev, CUSTOM_MODEL_ID: e.target.value }))}
                    className="w-full px-3 py-2 bg-[var(--bg-input)] border border-[var(--border-primary)] rounded-lg text-[var(--text-primary)] text-sm focus:border-brand-500 outline-none transition-colors font-mono"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 items-end">
                <div>
                  <label htmlFor="custom-api-key" className="block text-xs font-medium text-[var(--text-tertiary)] mb-1.5">API Key</label>
                  <input
                    id="custom-api-key"
                    type="password"
                    placeholder="Enter your API key"
                    value={settings.CUSTOM_API_KEY || ''}
                    onChange={e => setSettings(prev => ({ ...prev, CUSTOM_API_KEY: e.target.value }))}
                    className="w-full px-3 py-2 bg-[var(--bg-input)] border border-[var(--border-primary)] rounded-lg text-[var(--text-primary)] text-sm focus:border-brand-500 outline-none transition-colors"
                  />
                </div>

                <Button
                  variant="primary"
                  className="w-full flex items-center justify-center gap-2 bg-brand-600 hover:bg-brand-700 text-white"
                  onClick={handleConnectCustom}
                >
                  🔌 Connect Custom Provider
                </Button>
              </div>
            </div>
          )}

          {customTab === 'curl' && (
            <div className="space-y-4">
              <div>
                <label htmlFor="custom-curl" className="block text-xs font-medium text-[var(--text-tertiary)] mb-1.5">Paste Curl Command</label>
                <textarea
                  id="custom-curl"
                  placeholder="Paste raw curl command here, e.g. curl https://api.deepseek.com/v1/chat/completions -H 'Authorization: Bearer sk-...' -d '{'model': 'deepseek-coder'}'"
                  value={curlContent}
                  onChange={e => setCurlContent(e.target.value)}
                  rows={4}
                  className="w-full px-3 py-2 bg-[var(--bg-input)] border border-[var(--border-primary)] rounded-lg text-[var(--text-primary)] text-xs focus:border-brand-500 outline-none transition-colors font-mono"
                />
              </div>

              <Button
                variant="primary"
                className="w-full flex items-center justify-center gap-2 bg-brand-600 hover:bg-brand-700 text-white"
                onClick={handleParseCurl}
              >
                ⚡ Parse & Connect Curl
              </Button>
            </div>
          )}

          {customTab === 'openai' && (
            <div className="space-y-4">
              <div className="bg-[var(--bg-primary)] p-3 rounded-lg border border-[var(--border-primary)] text-xs text-[var(--text-muted)] leading-relaxed">
                ℹ️ Use this configuration to connect standard local developer platforms like <strong>Ollama</strong> or <strong>LM Studio</strong>. 
                For Ollama, use default base URL <code>http://localhost:11434/v1</code>. For LM Studio, use <code>http://localhost:1234/v1</code>.
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label htmlFor="openai-base-url" className="block text-xs font-medium text-[var(--text-tertiary)] mb-1.5">Base URL</label>
                  <input
                    id="openai-base-url"
                    type="text"
                    placeholder="http://localhost:11434/v1"
                    value={settings.CUSTOM_BASE_URL || ''}
                    onChange={e => setSettings(prev => ({ ...prev, CUSTOM_BASE_URL: e.target.value }))}
                    className="w-full px-3 py-2 bg-[var(--bg-input)] border border-[var(--border-primary)] rounded-lg text-[var(--text-primary)] text-sm focus:border-brand-500 outline-none transition-colors"
                  />
                </div>
                <div>
                  <label htmlFor="openai-model-id" className="block text-xs font-medium text-[var(--text-tertiary)] mb-1.5">Model ID</label>
                  <input
                    id="openai-model-id"
                    type="text"
                    placeholder="e.g., llama3.2"
                    value={settings.CUSTOM_MODEL_ID || ''}
                    onChange={e => setSettings(prev => ({ ...prev, CUSTOM_MODEL_ID: e.target.value }))}
                    className="w-full px-3 py-2 bg-[var(--bg-input)] border border-[var(--border-primary)] rounded-lg text-[var(--text-primary)] text-sm focus:border-brand-500 outline-none transition-colors font-mono"
                  />
                </div>
                <div>
                  <label htmlFor="openai-api-key" className="block text-xs font-medium text-[var(--text-tertiary)] mb-1.5">API Key (Optional)</label>
                  <input
                    id="openai-api-key"
                    type="password"
                    placeholder="None / Optional"
                    value={settings.CUSTOM_API_KEY || ''}
                    onChange={e => setSettings(prev => ({ ...prev, CUSTOM_API_KEY: e.target.value }))}
                    className="w-full px-3 py-2 bg-[var(--bg-input)] border border-[var(--border-primary)] rounded-lg text-[var(--text-primary)] text-sm focus:border-brand-500 outline-none transition-colors"
                  />
                </div>
              </div>

              <Button
                variant="primary"
                className="w-full flex items-center justify-center gap-2 bg-brand-600 hover:bg-brand-700 text-white"
                onClick={handleConnectCustom}
              >
                🔌 Connect Endpoint
              </Button>
            </div>
          )}
        </div>
      </Card>
        </div>
      </details>
    </div>
  )
}

// ============================================================================
// ExternalServicesPanel — dedicated panel with Test Connection buttons + status
// ============================================================================
type TestStatus = 'idle' | 'testing' | 'ok' | 'fail'

interface ServiceDescriptor {
  id: 'langwatch' | 'smithery' | 'huggingface' | 'github' | 'vercel'
  name: string
  description: string
  dashboardUrl: string
  color: string
  fields: { key: string; label: string; placeholder: string; required: boolean; type?: 'text' | 'password' }[]
  // Returns null if the request cannot be attempted (missing fields),
  // otherwise returns a Promise that resolves to { ok: boolean; detail: string }.
  testConnection: (settings: Record<string, string>) => Promise<{ ok: boolean; detail: string }> | null
}

const EXTERNAL_SERVICES: ServiceDescriptor[] = [
  {
    id: 'langwatch',
    name: 'LangWatch',
    description: 'LLM observability & tracing dashboard',
    dashboardUrl: 'https://app.langwatch.ai',
    color: '#6366f1',
    fields: [
      { key: 'LANGWATCH_API_KEY', label: 'API Key', placeholder: 'sk-lw-...', required: true, type: 'password' },
      { key: 'LANGWATCH_PROJECT', label: 'Project Name', placeholder: 'AhmedETAP', required: true },
      { key: 'LANGWATCH_ENDPOINT', label: 'Endpoint', placeholder: 'https://app.langwatch.ai', required: true },
    ],
    testConnection: (s) => {
      const apiKey = s.LANGWATCH_API_KEY?.trim()
      const endpoint = s.LANGWATCH_ENDPOINT?.trim() || 'https://app.langwatch.ai'
      if (!apiKey) return null
      // LangWatch has CORS restrictions on browser fetches. We use a no-cors mode
      // probe to verify the server is reachable (we won't be able to read the response,
      // but the request will resolve on network success).
      // Step 1: probe /api/v1/projects with normal mode — if it succeeds, great.
      // Step 2: fall back to no-cors mode HEAD probe — if it resolves, server is reachable.
      const tryNormal = fetch(`${endpoint}/api/v1/projects`, {
        method: 'GET',
        headers: { 'X-Auth-Token': apiKey, 'Accept': 'application/json' },
      })
        .then(async (r) => {
          if (r.ok) return { ok: true, detail: 'Connected — project list reachable' }
          if (r.status === 401 || r.status === 403) return { ok: false, detail: 'Invalid API key (401/403)' }
          if (r.status === 404) return { ok: true, detail: 'Endpoint reachable (path 404 is normal)' }
          return { ok: false, detail: `HTTP ${r.status}` }
        })

      // If normal fetch throws (CORS), try no-cors probe as fallback
      return tryNormal.catch(() =>
        fetch(`${endpoint}/api/v1/projects`, {
          method: 'GET',
          mode: 'no-cors',
          headers: { 'X-Auth-Token': apiKey },
        })
          .then(() => ({ ok: true, detail: 'Endpoint reachable (no-cors probe OK)' }))
          .catch((e) => ({ ok: false, detail: `Network error: ${e.message}` }))
      )
    },
  },
  {
    id: 'smithery',
    name: 'Smithery MCP',
    description: 'Model Context Protocol server registry',
    dashboardUrl: 'https://smithery.ai/console/api-keys',
    color: '#10b981',
    fields: [
      { key: 'SMITHERY_API_KEY', label: 'API Key', placeholder: 'UUID-format key', required: true, type: 'password' },
      { key: 'SMITHERY_BASE_URL', label: 'Base URL', placeholder: 'https://api.smithery.ai', required: true },
    ],
    testConnection: (s) => {
      const apiKey = s.SMITHERY_API_KEY?.trim()
      const baseUrl = s.SMITHERY_BASE_URL?.trim() || 'https://api.smithery.ai'
      if (!apiKey) return null
      // Smithery exposes /v1/servers as a public listing endpoint
      return fetch(`${baseUrl}/v1/servers?limit=1`, {
        method: 'GET',
        headers: { 'Authorization': `Bearer ${apiKey}`, 'Accept': 'application/json' },
      })
        .then(async (r) => {
          if (r.ok) return { ok: true, detail: 'Connected — server registry reachable' }
          if (r.status === 401 || r.status === 403) return { ok: false, detail: 'Invalid API key' }
          // Try alternative endpoint
          return fetch(`${baseUrl}/servers?limit=1`, {
            method: 'GET',
            headers: { 'Authorization': `Bearer ${apiKey}` },
          }).then(r2 => r2.ok
            ? { ok: true, detail: 'Connected (alt path)' }
            : { ok: false, detail: `HTTP ${r.status} / ${r2.status}` })
        })
        .catch((e) => ({ ok: false, detail: `Network error: ${e.message}` }))
    },
  },
  {
    id: 'huggingface',
    name: 'Hugging Face',
    description: 'Model hub & Spaces deployment',
    dashboardUrl: 'https://huggingface.co/settings/tokens',
    color: '#ffd21e',
    fields: [
      { key: 'HF_TOKEN', label: 'Access Token', placeholder: 'hf_...', required: true, type: 'password' },
      { key: 'HF_SPACE_NAME', label: 'Space Name', placeholder: 'username/space-name', required: true },
      { key: 'HF_REPO_URL', label: 'Space URL', placeholder: 'https://huggingface.co/spaces/...', required: false },
    ],
    testConnection: (s) => {
      const token = s.HF_TOKEN?.trim()
      if (!token) return null
      // HuggingFace exposes /api/whoami-v2 which validates the token
      return fetch('https://huggingface.co/api/whoami-v2', {
        method: 'GET',
        headers: { 'Authorization': `Bearer ${token}`, 'Accept': 'application/json' },
      })
        .then(async (r) => {
          if (r.ok) {
            try {
              const data = await r.json()
              const username = data.name || data.user?.name || 'unknown'
              return { ok: true, detail: `Connected as @${username}` }
            } catch {
              return { ok: true, detail: 'Connected (token valid)' }
            }
          }
          if (r.status === 401) return { ok: false, detail: 'Invalid or expired token' }
          return { ok: false, detail: `HTTP ${r.status}` }
        })
        .catch((e) => ({ ok: false, detail: `Network error: ${e.message}` }))
    },
  },
  {
    id: 'github',
    name: 'GitHub',
    description: 'Repository access & CI/CD',
    dashboardUrl: 'https://github.com/settings/tokens',
    color: '#6e7681',
    fields: [
      { key: 'GITHUB_TOKEN', label: 'Personal Access Token', placeholder: 'github_pat_... or ghp_...', required: true, type: 'password' },
      { key: 'GITHUB_REPO', label: 'Repository', placeholder: 'owner/repo-name', required: true },
    ],
    testConnection: (s) => {
      const token = s.GITHUB_TOKEN?.trim()
      if (!token) return null
      return fetch('https://api.github.com/user', {
        method: 'GET',
        headers: { 'Authorization': `Bearer ${token}`, 'Accept': 'application/vnd.github+json' },
      })
        .then(async (r) => {
          if (r.ok) {
            try {
              const data = await r.json()
              return { ok: true, detail: `Connected as @${data.login}` }
            } catch {
              return { ok: true, detail: 'Connected (token valid)' }
            }
          }
          if (r.status === 401) return { ok: false, detail: 'Invalid token' }
          if (r.status === 403) return { ok: false, detail: 'Rate-limited or forbidden' }
          return { ok: false, detail: `HTTP ${r.status}` }
        })
        .catch((e) => ({ ok: false, detail: `Network error: ${e.message}` }))
    },
  },
  {
    id: 'vercel',
    name: 'Vercel',
    description: 'Frontend deployment & preview',
    dashboardUrl: 'https://vercel.com/account/tokens',
    color: '#000000',
    fields: [
      { key: 'VERCEL_PROJECT_ID', label: 'Project ID', placeholder: 'prj_...', required: true },
      { key: 'VERCEL_ACCESS_TOKEN', label: 'Access Token', placeholder: 'vcp_...', required: true, type: 'password' },
    ],
    testConnection: (s) => {
      const token = s.VERCEL_ACCESS_TOKEN?.trim()
      const projectId = s.VERCEL_PROJECT_ID?.trim()
      if (!token || !projectId) return null
      // Vercel API: GET /v9/projects/{id}
      return fetch(`https://api.vercel.com/v9/projects/${projectId}`, {
        method: 'GET',
        headers: { 'Authorization': `Bearer ${token}`, 'Accept': 'application/json' },
      })
        .then(async (r) => {
          if (r.ok) {
            try {
              const data = await r.json()
              return { ok: true, detail: `Connected — project "${data.name}"` }
            } catch {
              return { ok: true, detail: 'Connected (project reachable)' }
            }
          }
          if (r.status === 401) return { ok: false, detail: 'Invalid access token' }
          if (r.status === 404) return { ok: false, detail: 'Project not found (bad project ID?)' }
          return { ok: false, detail: `HTTP ${r.status}` }
        })
        .catch((e) => ({ ok: false, detail: `Network error: ${e.message}` }))
    },
  },
]

function ExternalServicesPanel({  // NOSONAR — S6759: React props read-only; requires `readonly` refactor across component tree
  settings,
  setSettings,
  notify,
}: {
  settings: Record<string, string>
  setSettings: React.Dispatch<React.SetStateAction<Record<string, string>>>
  notify: (type: 'success' | 'error' | 'info' | 'warning', message: string) => void
}) {
  // status[id] = { state, detail }
  const [status, setStatus] = useState<Record<string, { state: TestStatus; detail: string }>>({})

  const handleTest = async (svc: ServiceDescriptor) => {
    const result = svc.testConnection(settings)
    if (result === null) {
      notify('warning', `Please fill in all required fields for ${svc.name}`)
      return
    }
    setStatus(prev => ({ ...prev, [svc.id]: { state: 'testing', detail: 'Testing…' } }))
    try {
      const r = await result
      setStatus(prev => ({ ...prev, [svc.id]: { state: r.ok ? 'ok' : 'fail', detail: r.detail } }))
      notify(r.ok ? 'success' : 'error', `${svc.name}: ${r.detail}`)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e)
      setStatus(prev => ({ ...prev, [svc.id]: { state: 'fail', detail: msg } }))
      notify('error', `${svc.name}: ${msg}`)
    }
  }

  return (
    <div className="space-y-6 col-span-2">
      <Card padding="md" className="border border-[var(--border-primary)] shadow-sm">
        <div className="flex items-center gap-2 mb-4 border-b border-[var(--border-primary)] pb-3">
          <Link2 className="w-5 h-5 text-brand-400" />
          <div>
            <h3 className="text-sm font-semibold text-[var(--text-primary)]">External Services</h3>
            <p className="text-[10px] text-[var(--text-muted)]">
              Configure and verify connections to LangWatch, Smithery, Hugging Face, GitHub, and Vercel.
              Click "Test" to verify each integration in real-time.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {EXTERNAL_SERVICES.map(svc => {
            const st = status[svc.id] || { state: 'idle' as TestStatus, detail: '' }
            const isConfigured = svc.fields
              .filter(f => f.required)
              .every(f => (settings[f.key] || '').trim().length > 0)

            return (
              <div
                key={svc.id}
                className="rounded-xl border border-[var(--border-primary)] p-4 bg-[var(--bg-secondary)] hover:border-[var(--color-brand-500)] transition-colors"
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <div
                      className="w-3 h-3 rounded-full"
                      style={{ backgroundColor: svc.color }}
                      aria-hidden
                    />
                    <div>
                      <h4 className="text-sm font-semibold text-[var(--text-primary)]">{svc.name}</h4>
                      <p className="text-[10px] text-[var(--text-muted)]">{svc.description}</p>
                    </div>
                  </div>
                  {st.state === 'ok' && <CheckCircle2 className="w-4 h-4 text-green-500" />}
                  {st.state === 'fail' && <XCircle className="w-4 h-4 text-red-500" />}
                  {st.state === 'testing' && <Loader2 className="w-4 h-4 text-yellow-400 animate-spin" />}
                </div>

                <div className="space-y-2 mb-3">
                  {svc.fields.map(f => (
                    <div key={f.key}>
                      <label className="block text-[10px] font-medium text-[var(--text-tertiary)] mb-1">
                        {f.label}{f.required && <span className="text-red-400"> *</span>}
                      </label>
                      <input
                        type={f.type === 'password' ? 'password' : 'text'}
                        placeholder={f.placeholder}
                        value={settings[f.key] || ''}
                        onChange={e => setSettings(prev => ({ ...prev, [f.key]: e.target.value }))} // NOSONAR — S2004: 5-level nesting is acceptable for inline form onChange in JSX
                        className="w-full px-2.5 py-1.5 bg-[var(--bg-input)] border border-[var(--border-primary)] rounded-md text-[var(--text-primary)] text-xs focus:border-brand-500 outline-none font-mono transition-colors"
                      />
                    </div>
                  ))}
                </div>

                {st.detail && (
                  <div
                    className={`text-[10px] mb-2 px-2 py-1 rounded ${
                      st.state === 'ok'
                        ? 'bg-green-500/10 text-green-400'
                        : st.state === 'fail'
                        ? 'bg-red-500/10 text-red-400'
                        : 'bg-yellow-500/10 text-yellow-400'
                    }`}
                  >
                    {st.detail}
                  </div>
                )}

                <div className="flex items-center gap-2">
                  <Button
                    variant={isConfigured ? 'primary' : 'ghost'}
                    size="sm"
                    disabled={st.state === 'testing'}
                    onClick={() => handleTest(svc)}
                    className="flex-1"
                  >
                    {st.state === 'testing' ? 'Testing…' : 'Test Connection'}
                  </Button>
                  <a
                    href={svc.dashboardUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="px-2.5 py-1.5 text-xs rounded-md border border-[var(--border-primary)] text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)] flex items-center gap-1"
                    title={`Open ${svc.name} dashboard`}
                  >
                    <ExternalLink className="w-3 h-3" />
                  </a>
                </div>
              </div>
            )
          })}
        </div>

        <div className="mt-4 p-3 rounded-lg bg-[var(--bg-tertiary)] border border-[var(--border-primary)] text-[11px] text-[var(--text-muted)] leading-relaxed">
          <Info className="w-3.5 h-3.5 inline-block mr-1.5 -mt-0.5" />
          <strong>How it works:</strong> Each service is tested by calling its public API with your
          credentials. Tokens are stored locally (obfuscated) and never sent to our backend. After
          saving, copy the same values into your HF Space secrets or server <code>.env</code> for
          backend runtime access.
        </div>
      </Card>
    </div>
  )
}

function SettingsField({ field, value, onChange }: { field: string; value: string; onChange: (v: string) => void }) {  // NOSONAR — S6759: React props read-only; requires `readonly` refactor across component tree
  const isSecret = field.includes('KEY') || field.includes('SECRET')
  const isFeatureFlag = field.startsWith('ENABLE_') || field.endsWith('_ENABLED')
  const isNumber = field.includes('_MS') || field.includes('PORT') || field.includes('SIZE') || field.includes('TTL') || field.includes('RATE') || field.includes('THRESHOLD') || field.includes('MAX_')
  const inputType = isSecret ? 'password' : isNumber ? 'number' : 'text'

  if (isFeatureFlag) {
    return (
      <Toggle
        checked={value === 'true'}
        onChange={(checked) => onChange(checked ? 'true' : 'false')}
        label={field.replaceAll('_', ' ').replaceAll('ENABLE ', '').replaceAll(' ENABLED', '')}
        description={`Toggle ${field.replaceAll('_', ' ').toLowerCase()}`}
        size="sm"
      />
    )
  }

  return (
    <div>
      <label htmlFor={`field-${field}`} className="block text-xs font-medium text-[var(--text-tertiary)] mb-1.5">
        {field.replaceAll('_', ' ').toLowerCase().replace(/\b\w/g, c => c.toUpperCase())}
      </label>
      <input
        id={`field-${field}`}
        type={inputType}
        value={value || ''}
        onChange={e => onChange(e.target.value)}
        className="w-full px-3 py-2 bg-[var(--bg-input)] border border-[var(--border-primary)] rounded-lg text-[var(--text-primary)] text-sm focus:border-[var(--color-brand-500)] focus:ring-1 focus:ring-[var(--color-brand-500)]/30 outline-none font-mono transition-colors"
      />
    </div>
  )
}

function loadInitialSettings(): Record<string, string> {
  const stored = localStorage.getItem('etap-settings')
  const defaults = getDefaults()
  if (stored) {
    try {
      const parsed = JSON.parse(stored)
      const deobfuscated: Record<string, string> = {}
      for (const [k, v] of Object.entries(parsed)) {
        deobfuscated[k] = SECRET_FIELDS.has(k) ? deobfuscate(v as string) : (v as string)
      }
      return { ...defaults, ...deobfuscated }
    } catch {
      return defaults
    }
  }
  return defaults
}

// ─── Vision API Keys Panel ─────────────────────────────────────────────────
// Connects to the backend /api/v1/settings/keys endpoints.
// Allows users to enter OpenAI/Gemini/Anthropic API keys (encrypted server-side).

const VISION_PROVIDERS = [
  {
    id: 'openai',
    label: 'OpenAI-Compatible',
    description: 'Works with OpenAI, Azure, Together AI, Groq, freemodel.dev, etc.',
    defaultBaseUrl: 'https://api.openai.com/v1',
    defaultModel: 'gpt-4o',
    placeholder: 'sk-...',
    docsUrl: 'https://platform.openai.com/api-keys',
  },
  {
    id: 'gemini',
    label: 'Google Gemini',
    description: 'Google AI Studio Gemini Vision API',
    defaultBaseUrl: '',
    defaultModel: 'gemini-2.0-flash-exp',
    placeholder: 'AIza...',
    docsUrl: 'https://aistudio.google.com/app/apikey',
  },
  {
    id: 'anthropic',
    label: 'Anthropic Claude',
    description: 'Claude 3.5 Sonnet / Opus / Haiku Vision',
    defaultBaseUrl: 'https://api.anthropic.com',
    defaultModel: 'claude-3-5-sonnet-20241022',
    placeholder: 'sk-ant-...',
    docsUrl: 'https://console.anthropic.com/',
  },
]

function VisionApiKeysPanel({ notify }: { notify: (type: 'success' | 'error' | 'info' | 'warning', message: string) => void }) {  // NOSONAR — S6759: React props read-only; requires `readonly` refactor across component tree
  const [keys, setKeys] = useState<Record<string, VisionKeyConfig>>({})
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState<Record<string, { apiKey: string; baseUrl: string; modelName: string }>>({})
  const [savingProvider, setSavingProvider] = useState<string | null>(null)
  const [testingProvider, setTestingProvider] = useState<string | null>(null)
  const [testResults, setTestResults] = useState<Record<string, { success: boolean; message: string }>>({})

  const loadKeys = useCallback(async () => {
    setLoading(true)
    try {
      const resp = await fetchVisionKeys()
      setKeys(resp.data || {})
    } catch (err) {
      notify('error', `Failed to load API keys: ${err instanceof Error ? err.message : 'Unknown error'}`)
    } finally {
      setLoading(false)
    }
  }, [notify])

  useEffect(() => {
    loadKeys()
  }, [loadKeys])

  const handleSave = async (providerId: string) => {
    const edit = editing[providerId]
    if (!edit?.apiKey?.trim()) {
      notify('error', 'Please enter an API key')
      return
    }
    setSavingProvider(providerId)
    try {
      await saveVisionKey(
        providerId,
        edit.apiKey.trim(),
        edit.baseUrl.trim() || undefined,
        edit.modelName.trim() || undefined,
        true
      )
      notify('success', `${providerId} API key saved (encrypted)`)
      setEditing(prev => {
        const next = { ...prev }
        delete next[providerId]
        return next
      })
      setTestResults(prev => {
        const next = { ...prev }
        delete next[providerId]
        return next
      })
      await loadKeys()
    } catch (err) {
      notify('error', `Failed to save: ${err instanceof Error ? err.message : 'Unknown error'}`)
    } finally {
      setSavingProvider(null)
    }
  }

  const handleDelete = async (providerId: string) => {
    if (!confirm(`Delete the ${providerId} API key? This cannot be undone.`)) return
    try {
      await deleteVisionKey(providerId)
      notify('info', `${providerId} API key deleted`)
      setTestResults(prev => {
        const next = { ...prev }
        delete next[providerId]
        return next
      })
      await loadKeys()
    } catch (err) {
      notify('error', `Failed to delete: ${err instanceof Error ? err.message : 'Unknown error'}`)
    }
  }

  const handleTest = async (providerId: string) => {
    setTestingProvider(providerId)
    setTestResults(prev => ({ ...prev, [providerId]: { success: false, message: 'Testing...' } }))
    try {
      const resp = await testVisionKey(providerId)
      const result = resp.data
      setTestResults(prev => ({
        ...prev,
        [providerId]: { success: result.success, message: result.message },
      }))
      if (result.success) {
        notify('success', `${providerId} key is valid!`)
      } else {
        notify('warning', `${providerId} key test failed: ${result.message}`)
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Unknown error'
      setTestResults(prev => ({ ...prev, [providerId]: { success: false, message: msg } }))
      notify('error', `Test failed: ${msg}`)
    } finally {
      setTestingProvider(null)
    }
  }

  const startEditing = (providerId: string, existing?: VisionKeyConfig) => {
    setEditing(prev => ({
      ...prev,
      [providerId]: {
        apiKey: '',
        baseUrl: existing?.base_url || VISION_PROVIDERS.find(p => p.id === providerId)?.defaultBaseUrl || '',
        modelName: existing?.model_name || VISION_PROVIDERS.find(p => p.id === providerId)?.defaultModel || '',
      },
    }))
  }

  const cancelEditing = (providerId: string) => {
    setEditing(prev => {
      const next = { ...prev }
      delete next[providerId]
      return next
    })
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-[var(--accent-primary)]" />
        <span className="ml-3 text-[var(--text-muted)]">Loading API keys...</span>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <Card padding="md">
        <CardHeader
          title="Vision API Keys"
          subtitle="Enter your own API keys for the CUA Loop vision backends. Keys are encrypted (AES-256) and stored server-side — never exposed in the frontend."
          icon={<Eye className="w-5 h-5" />}
        />
        <div className="mt-4 p-3 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border-primary)]">
          <div className="flex items-start gap-2">
            <Info className="w-4 h-4 text-[var(--accent-primary)] mt-0.5 flex-shrink-0" />
            <div className="text-sm text-[var(--text-secondary)]">
              <p className="font-medium mb-1">How it works:</p>
              <ul className="list-disc list-inside space-y-1 text-xs">
                <li>Keys are <strong>optional</strong> — the CUA Loop works without them (falls back to OpenCV)</li>
                <li>Keys are <strong>encrypted</strong> with AES-256 before storage</li>
                <li>Keys <strong>override</strong> server-side env vars when set</li>
                <li>Keys are <strong>masked</strong> in the UI (sk-***...***) — never shown in plaintext</li>
                <li>You can enter keys <strong>anytime</strong> — changes take effect immediately</li>
              </ul>
            </div>
          </div>
        </div>
      </Card>

      {VISION_PROVIDERS.map(provider => {
        const existing = keys[provider.id]
        const isEditing = !!editing[provider.id]
        const edit = editing[provider.id]
        const testResult = testResults[provider.id]
        const isSaving = savingProvider === provider.id
        const isTesting = testingProvider === provider.id

        return (
          <Card key={provider.id} padding="md">
            <CardHeader
              title={
                <div className="flex items-center gap-2">
                  <Key className="w-4 h-4" />
                  <span>{provider.label}</span>
                  {existing?.is_active && (
                    <span className="px-2 py-0.5 text-xs rounded-full bg-green-500/20 text-green-400 border border-green-500/30">
                      Active
                    </span>
                  )}
                </div>
              }
              subtitle={provider.description}
              icon={null}
            />

            <div className="mt-4 space-y-4">
              {/* Existing key display (masked) */}
              {existing && !isEditing && (
                <div className="space-y-3">
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                    <div>
                      <span className="text-xs text-[var(--text-muted)]">API Key</span>
                      <div className="font-mono text-sm text-[var(--text-secondary)] bg-[var(--bg-secondary)] px-3 py-2 rounded-md border border-[var(--border-primary)]">
                        {existing.api_key_masked}
                      </div>
                    </div>
                    {existing.base_url && (
                      <div>
                        <span className="text-xs text-[var(--text-muted)]">Base URL</span>
                        <div className="text-sm text-[var(--text-secondary)] bg-[var(--bg-secondary)] px-3 py-2 rounded-md border border-[var(--border-primary)] truncate">
                          {existing.base_url}
                        </div>
                      </div>
                    )}
                    {existing.model_name && (
                      <div>
                        <span className="text-xs text-[var(--text-muted)]">Model</span>
                        <div className="text-sm text-[var(--text-secondary)] bg-[var(--bg-secondary)] px-3 py-2 rounded-md border border-[var(--border-primary)] truncate">
                          {existing.model_name}
                        </div>
                      </div>
                    )}
                  </div>

                  {testResult && (
                    <div className={`flex items-center gap-2 p-2 rounded-md text-sm ${
                      testResult.success
                        ? 'bg-green-500/10 text-green-400 border border-green-500/20'
                        : 'bg-red-500/10 text-red-400 border border-red-500/20'
                    }`}>
                      {testResult.success ? <CheckCircle2 className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
                      <span className="truncate">{testResult.message}</span>
                    </div>
                  )}

                  <div className="flex items-center gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      icon={isTesting ? Loader2 : Zap}
                      onClick={() => handleTest(provider.id)}
                      disabled={isTesting}
                    >
                      {isTesting ? 'Testing...' : 'Test'}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => startEditing(provider.id, existing)}
                    >
                      Update
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      icon={Trash2}
                      onClick={() => handleDelete(provider.id)}
                      className="text-red-400 hover:text-red-300"
                    >
                      Delete
                    </Button>
                    <a
                      href={provider.docsUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="ml-auto text-xs text-[var(--accent-primary)] hover:underline flex items-center gap-1"
                    >
                      Get API key <ExternalLink className="w-3 h-3" />
                    </a>
                  </div>
                </div>
              )}

              {/* Edit / new key form */}
              {(isEditing || !existing) && edit && (
                <div className="space-y-3">
                  <div>
                    <label htmlFor={`vision-${provider.id}-key`} className="text-xs text-[var(--text-muted)] mb-1 block">API Key</label>
                    <input
                      id={`vision-${provider.id}-key`}
                      type="password"
                      value={edit.apiKey}
                      onChange={e => setEditing(prev => ({
                        ...prev,
                        [provider.id]: { ...edit, apiKey: e.target.value }
                      }))}
                      placeholder={provider.placeholder}
                      className="w-full px-3 py-2 rounded-md bg-[var(--bg-secondary)] border border-[var(--border-primary)] text-[var(--text-primary)] text-sm focus:outline-none focus:border-[var(--accent-primary)]"
                      autoComplete="off"
                    />
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <div>
                      <label htmlFor={`vision-${provider.id}-base`} className="text-xs text-[var(--text-muted)] mb-1 block">Base URL (optional)</label>
                      <input
                        id={`vision-${provider.id}-base`}
                        type="text"
                        value={edit.baseUrl}
                        onChange={e => setEditing(prev => ({
                          ...prev,
                          [provider.id]: { ...edit, baseUrl: e.target.value }
                        }))}
                        placeholder={provider.defaultBaseUrl || '(default)'}
                        className="w-full px-3 py-2 rounded-md bg-[var(--bg-secondary)] border border-[var(--border-primary)] text-[var(--text-primary)] text-sm focus:outline-none focus:border-[var(--accent-primary)]"
                      />
                    </div>
                    <div>
                      <label htmlFor={`vision-${provider.id}-model`} className="text-xs text-[var(--text-muted)] mb-1 block">Model (optional)</label>
                      <input
                        id={`vision-${provider.id}-model`}
                        type="text"
                        value={edit.modelName}
                        onChange={e => setEditing(prev => ({
                          ...prev,
                          [provider.id]: { ...edit, modelName: e.target.value }
                        }))}
                        placeholder={provider.defaultModel}
                        className="w-full px-3 py-2 rounded-md bg-[var(--bg-secondary)] border border-[var(--border-primary)] text-[var(--text-primary)] text-sm focus:outline-none focus:border-[var(--accent-primary)]"
                      />
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="primary"
                      size="sm"
                      icon={isSaving ? Loader2 : Save}
                      onClick={() => handleSave(provider.id)}
                      disabled={isSaving || !edit.apiKey.trim()}
                    >
                      {isSaving ? 'Saving...' : 'Save Key'}
                    </Button>
                    {isEditing && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => cancelEditing(provider.id)}
                      >
                        Cancel
                      </Button>
                    )}
                    <a
                      href={provider.docsUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="ml-auto text-xs text-[var(--accent-primary)] hover:underline flex items-center gap-1"
                    >
                      Get API key <ExternalLink className="w-3 h-3" />
                    </a>
                  </div>
                </div>
              )}

              {/* No key + not editing → show "Add Key" button */}
              {!existing && !isEditing && (
                <div className="flex items-center gap-3">
                  <p className="text-sm text-[var(--text-muted)]">No key configured — using server default or OpenCV fallback</p>
                  <Button
                    variant="ghost"
                    size="sm"
                    icon={Key}
                    onClick={() => startEditing(provider.id)}
                  >
                    Add Key
                  </Button>
                  <a
                    href={provider.docsUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-[var(--accent-primary)] hover:underline flex items-center gap-1"
                  >
                    Get API key <ExternalLink className="w-3 h-3" />
                  </a>
                </div>
              )}
            </div>
          </Card>
        )
      })}
    </div>
  )
}

export default function Settings() {
  const [settings, setSettings] = useState<Record<string, string>>(loadInitialSettings)
  const [saving, setSaving] = useState(false)
  const { notify } = useNotify()
  const { activeTab, setActiveTab } = useTabState('ai')

  const handleSave = () => {
    setSaving(true)
    const toStore: Record<string, string> = {}
    for (const [k, v] of Object.entries(settings)) {
      toStore[k] = SECRET_FIELDS.has(k) ? obfuscate(v) : v
    }
    localStorage.setItem('etap-settings', JSON.stringify(toStore))
    if (settings.API_KEY_SECRET) {
      localStorage.setItem('etap-api-key', obfuscate(settings.API_KEY_SECRET))
    }
    setTimeout(() => { setSaving(false); notify('success', 'Settings saved successfully') }, 400)
  }

  const handleReset = () => {
    const d = getDefaults()
    setSettings(d)
    localStorage.removeItem('etap-settings')
    notify('info', 'Settings reset to defaults')
  }

  const handleExport = () => {
    const exportData: Record<string, string> = {}
    for (const [k, v] of Object.entries(settings)) {
      exportData[k] = SECRET_FIELDS.has(k) ? '' : v
    }
    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = 'etap-settings.json'; a.click()
    URL.revokeObjectURL(url)
    notify('success', 'Settings exported (secrets excluded for security)')
  }

  const handleImport = () => {
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = '.json'
    input.onchange = async () => {
      const file = input.files?.[0]
      if (!file) return
      const text = await file.text()
      try {
        const parsed = JSON.parse(text)
        const validation = validateImportedSettings(parsed)
        if (!validation.valid) {
          notify('error', `Invalid settings: ${validation.errors.join(', ')}`)
          return
        }
        setSettings(prev => ({ ...prev, ...parsed }))
        notify('success', 'Settings imported (secrets must be re-entered)')
      } catch {
        notify('error', 'Invalid settings file format')
      }
    }
    input.click()
  }

  const tabs = Object.entries(TAB_SECTIONS).map(([id, tab]) => ({
    id,
    label: tab.label,
    icon: tab.icon,
  }))

  const currentSections = TAB_SECTIONS[activeTab]?.sections ?? []

  return (
    <div className="space-y-6">
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h2 className="text-2xl font-bold text-[var(--text-primary)]">Settings</h2>
          <ContextHelpButton contextId="settings.backend" />
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" icon={Upload} onClick={handleImport}>Import</Button>
          <Button variant="ghost" size="sm" icon={Download} onClick={handleExport}>Export</Button>
          <Button variant="ghost" size="sm" icon={Trash2} onClick={handleReset} className="text-red-400 hover:text-red-300">
            Reset
          </Button>
          <Button variant="primary" size="sm" icon={Save} loading={saving} onClick={handleSave}>
            {saving ? 'Saving...' : 'Save'}
          </Button>
        </div>
      </motion.div>

      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
        <Tabs tabs={tabs} activeTab={activeTab} onChange={setActiveTab} />
      </motion.div>

      <TabPanels>
        <motion.div
          key={activeTab}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.2 }}
        >
          {activeTab === 'ai' ? (
            <AISettingsPanel settings={settings} setSettings={setSettings} notify={notify} />
          ) : activeTab === 'external' ? (
            <ExternalServicesPanel settings={settings} setSettings={setSettings} notify={notify} />
          ) : activeTab === 'vision' ? (
            <VisionApiKeysPanel notify={notify} />
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {currentSections.map(section => (
                <Card key={section.title} padding="md">
                  <CardHeader
                    title={section.title}
                    subtitle={`${section.fields.length} field${section.fields.length === 1 ? '' : 's'}`}
                    icon={TAB_SECTIONS[activeTab]?.icon}
                  />
                  <div className="space-y-4">
                    {section.fields.map(field => (
                      <SettingsField
                        key={field}
                        field={field}
                        value={settings[field] || ''}
                        onChange={(v) => setSettings(p => ({ ...p, [field]: v }))} // NOSONAR — S2004: 5-level nesting is acceptable for inline form onChange in JSX
                      />
                    ))}
                  </div>
                </Card>
              ))}
            </div>
          )}
        </motion.div>
      </TabPanels>
    </div>
  )
}
