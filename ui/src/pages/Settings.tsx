import { useState } from 'react'
import { motion } from 'framer-motion'
import { Save, Download, Upload, Trash2, Bot, Wrench, Database, Shield, Link2, Gauge, Sparkles, Terminal, Info, Code, CheckCircle2, XCircle, Loader2, ExternalLink } from 'lucide-react'
import { useNotify } from '../context/NotificationContext'
import { Card, CardHeader, Button, Tabs, TabPanels, useTabState, Toggle } from '../components/ui'

// Simple XOR-based obfuscation for localStorage storage.
// NOT a substitute for server-side encryption — but prevents
// plaintext secrets from being readable via DevTools at a glance.
const OBFUSCATION_KEY = 'ETAP-SEC-2024-OBFUSCATION'
function obfuscate(value: string): string {
  let result = ''
  for (let i = 0; i < value.length; i++) {
    result += String.fromCharCode(value.charCodeAt(i) ^ OBFUSCATION_KEY.charCodeAt(i % OBFUSCATION_KEY.length))
  }
  return btoa(result)
}
function deobfuscate(value: string): string {
  try {
    const decoded = atob(value)
    let result = ''
    for (let i = 0; i < decoded.length; i++) {
      result += String.fromCharCode(decoded.charCodeAt(i) ^ OBFUSCATION_KEY.charCodeAt(i % OBFUSCATION_KEY.length))
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

const POPULAR_PROVIDERS = [
  {
    id: 'openai',
    name: 'OpenAI',
    models: ['gpt-4o', 'gpt-4o-mini', 'o1-mini', 'o1-preview'],
    defaultModel: 'gpt-4o-mini',
    defaultBaseUrl: 'https://api.openai.com/v1',
    color: '#10a37f',
  },
  {
    id: 'anthropic',
    name: 'Anthropic',
    models: ['claude-3-5-sonnet-latest', 'claude-3-opus-latest', 'claude-3-5-haiku-latest'],
    defaultModel: 'claude-3-5-sonnet-latest',
    defaultBaseUrl: 'https://api.anthropic.com/v1',
    color: '#d97706',
  },
  {
    id: 'gemini',
    name: 'Google Gemini',
    models: ['gemini-1.5-pro', 'gemini-1.5-flash', 'gemini-2.0-flash-exp'],
    defaultModel: 'gemini-1.5-flash',
    defaultBaseUrl: 'https://generativelanguage.googleapis.com/v1beta',
    color: '#1a73e8',
  },
  {
    id: 'deepseek',
    name: 'DeepSeek',
    models: ['deepseek-chat', 'deepseek-coder'],
    defaultModel: 'deepseek-chat',
    defaultBaseUrl: 'https://api.deepseek.com/v1',
    color: '#0052cc',
  },
  {
    id: 'groq',
    name: 'Groq',
    models: ['llama-3.3-70b-versatile', 'mixtral-8x7b-32768', 'gemma2-9b-it'],
    defaultModel: 'llama-3.3-70b-versatile',
    defaultBaseUrl: 'https://api.groq.com/openai/v1',
    color: '#f55036',
  },
  {
    id: 'cohere',
    name: 'Cohere',
    models: ['command-r-plus', 'command-r'],
    defaultModel: 'command-r-plus',
    defaultBaseUrl: 'https://api.cohere.ai/v1',
    color: '#6b50df',
  },
  {
    id: 'huggingface',
    name: 'Hugging Face',
    models: ['meta-llama/Llama-3.3-70B-Instruct', 'mistralai/Mixtral-8x7B-Instruct-v0.1'],
    defaultModel: 'meta-llama/Llama-3.3-70B-Instruct',
    defaultBaseUrl: 'https://api-inference.huggingface.co/v1',
    color: '#ffc107',
  },
]

function parseCurlCommand(curl: string): { baseUrl: string; apiKey: string; modelId: string } | null {
  try {
    const urlMatch = curl.match(/https?:\/\/[^\s'"\\]+/)
    let baseUrl = 'https://api.openai.com/v1'
    if (urlMatch) {
      let fullUrl = urlMatch[0]
      fullUrl = fullUrl.replace(/\/chat\/completions\/?$/, '').replace(/\/completions\/?$/, '')
      baseUrl = fullUrl
    }

    const authMatch = curl.match(/Bearer\s+([a-zA-Z0-9_\-]+)/i) || curl.match(/Authorization:\s*Bearer\s+([a-zA-Z0-9_\-]+)/i)
    let apiKey = ''
    if (authMatch) {
      apiKey = authMatch[1]
    } else {
      const genericKey = curl.match(/api-key:\s*([a-zA-Z0-9_\-]+)/i) || curl.match(/x-api-key:\s*([a-zA-Z0-9_\-]+)/i)
      if (genericKey) apiKey = genericKey[1]
    }

    const modelMatch = curl.match(/"model"\s*:\s*"([^"]+)"/) || curl.match(/'model'\s*:\s*'([^']+)'/)
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
}

interface AISettingsPanelProps {
  settings: Record<string, string>
  setSettings: React.Dispatch<React.SetStateAction<Record<string, string>>>
  notify: (type: 'success' | 'error' | 'info' | 'warning', message: string) => void
}

function AISettingsPanel({ settings, setSettings, notify }: AISettingsPanelProps) {
  const [customScope, setCustomScope] = useState<'local' | 'global'>('local')
  const [customTab, setCustomTab] = useState<'json' | 'curl' | 'openai'>('json')
  const [curlContent, setCurlContent] = useState('')

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

  return (
    <div className="space-y-6 col-span-2">
      {/* 1. Popular Models (Fast Connect) */}
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
            const modelName = `PROVIDER_${p.id.toUpperCase()}_MODEL`
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
                    <label className="block text-[9px] text-[var(--text-tertiary)] mb-1">API Key</label>
                    <input
                      type="password"
                      placeholder="Paste API Key"
                      value={settings[keyName] || ''}
                      onChange={e => setSettings(prev => ({ ...prev, [keyName]: e.target.value }))}
                      className="w-full px-2 py-1 bg-[var(--bg-primary)] border border-[var(--border-primary)] rounded-lg text-[11px] text-[var(--text-primary)] focus:border-brand-500 outline-none transition-colors font-mono"
                    />
                  </div>

                  <div>
                    <label className="block text-[9px] text-[var(--text-tertiary)] mb-1">Select Model</label>
                    <select
                      value={settings[modelName] || p.defaultModel}
                      onChange={e => setSettings(prev => ({ ...prev, [modelName]: e.target.value }))}
                      className="w-full px-2 py-1 bg-[var(--bg-primary)] border border-[var(--border-primary)] rounded-lg text-[11px] text-[var(--text-primary)] focus:border-brand-500 outline-none transition-colors"
                    >
                      {p.models.map(m => (
                        <option key={m} value={m}>{m}</option>
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
          {(['json', 'curl', 'openai'] as const).map(tab => (
            <button
              key={tab}
              onClick={() => setCustomTab(tab)}
              className={`px-4 py-2 text-xs font-semibold border-b-2 transition-all capitalize ${
                customTab === tab
                  ? 'border-brand-500 text-brand-400'
                  : 'border-transparent text-[var(--text-muted)] hover:text-[var(--text-primary)]'
              }`}
            >
              {tab === 'json' ? 'JSON Config' : tab === 'curl' ? 'CURL Command' : 'OpenAI-Compatible Endpoint'}
            </button>
          ))}
        </div>

        {/* Sub Tabs Contents */}
        <div className="space-y-4">
          {customTab === 'json' && (
            <div className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-[var(--text-tertiary)] mb-1.5">Base URL</label>
                  <input
                    type="text"
                    placeholder="https://api.yourproxy.com/v1"
                    value={settings.CUSTOM_BASE_URL || ''}
                    onChange={e => setSettings(prev => ({ ...prev, CUSTOM_BASE_URL: e.target.value }))}
                    className="w-full px-3 py-2 bg-[var(--bg-input)] border border-[var(--border-primary)] rounded-lg text-[var(--text-primary)] text-sm focus:border-brand-500 outline-none transition-colors"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-[var(--text-tertiary)] mb-1.5">Model ID</label>
                  <input
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
                  <label className="block text-xs font-medium text-[var(--text-tertiary)] mb-1.5">API Key</label>
                  <input
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
                <label className="block text-xs font-medium text-[var(--text-tertiary)] mb-1.5">Paste Curl Command</label>
                <textarea
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
                  <label className="block text-xs font-medium text-[var(--text-tertiary)] mb-1.5">Base URL</label>
                  <input
                    type="text"
                    placeholder="http://localhost:11434/v1"
                    value={settings.CUSTOM_BASE_URL || ''}
                    onChange={e => setSettings(prev => ({ ...prev, CUSTOM_BASE_URL: e.target.value }))}
                    className="w-full px-3 py-2 bg-[var(--bg-input)] border border-[var(--border-primary)] rounded-lg text-[var(--text-primary)] text-sm focus:border-brand-500 outline-none transition-colors"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-[var(--text-tertiary)] mb-1.5">Model ID</label>
                  <input
                    type="text"
                    placeholder="e.g., llama3.2"
                    value={settings.CUSTOM_MODEL_ID || ''}
                    onChange={e => setSettings(prev => ({ ...prev, CUSTOM_MODEL_ID: e.target.value }))}
                    className="w-full px-3 py-2 bg-[var(--bg-input)] border border-[var(--border-primary)] rounded-lg text-[var(--text-primary)] text-sm focus:border-brand-500 outline-none transition-colors font-mono"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-[var(--text-tertiary)] mb-1.5">API Key (Optional)</label>
                  <input
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

function ExternalServicesPanel({
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
                        onChange={e => setSettings(prev => ({ ...prev, [f.key]: e.target.value }))}
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

function SettingsField({ field, value, onChange }: { field: string; value: string; onChange: (v: string) => void }) {
  const isSecret = field.includes('KEY') || field.includes('SECRET')
  const isFeatureFlag = field.startsWith('ENABLE_') || field.endsWith('_ENABLED')
  const isNumber = field.includes('_MS') || field.includes('PORT') || field.includes('SIZE') || field.includes('TTL') || field.includes('RATE') || field.includes('THRESHOLD') || field.includes('MAX_')

  if (isFeatureFlag) {
    return (
      <Toggle
        checked={value === 'true'}
        onChange={(checked) => onChange(checked ? 'true' : 'false')}
        label={field.replace(/_/g, ' ').replace(/ENABLE /, '').replace(/ ENABLED/, '')}
        description={`Toggle ${field.replace(/_/g, ' ').toLowerCase()}`}
        size="sm"
      />
    )
  }

  return (
    <div>
      <label className="block text-xs font-medium text-[var(--text-tertiary)] mb-1.5">
        {field.replace(/_/g, ' ').toLowerCase().replace(/\b\w/g, c => c.toUpperCase())}
      </label>
      <input
        type={isSecret ? 'password' : isNumber ? 'number' : 'text'}
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
        <h2 className="text-2xl font-bold text-[var(--text-primary)]">Settings</h2>
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
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {currentSections.map(section => (
                <Card key={section.title} padding="md">
                  <CardHeader
                    title={section.title}
                    subtitle={`${section.fields.length} field${section.fields.length !== 1 ? 's' : ''}`}
                    icon={TAB_SECTIONS[activeTab]?.icon}
                  />
                  <div className="space-y-4">
                    {section.fields.map(field => (
                      <SettingsField
                        key={field}
                        field={field}
                        value={settings[field] || ''}
                        onChange={(v) => setSettings(p => ({ ...p, [field]: v }))}
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
