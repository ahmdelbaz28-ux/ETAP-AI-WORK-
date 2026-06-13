import { useState, useEffect } from 'react'
import { MdSave, MdFileDownload, MdFileUpload, MdDelete } from 'react-icons/md'
import { useNotify } from '../context/NotificationContext'

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
  'LANGWATCH_API_KEY', 'REDIS_URL', 'DATABASE_URL', 'VAULT_TOKEN',
  'SMTP_USERNAME', 'ETAP_LICENSE_PATH',
])

const SETTINGS_SCHEMA = {
  requiredKeys: ['OPENAI_MODEL', 'OPENAI_BASE_URL', 'ENGINEERING_SERVICE_URL'],
  maxFields: 60,
  maxKeyLength: 50,
  maxValueLength: 500,
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

export function Settings() {
  const [settings, setSettings] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)
  const { notify } = useNotify()

  useEffect(() => {
    const stored = localStorage.getItem('etap-settings')
    const defaults = getDefaults()
    if (stored) {
      try {
        const parsed = JSON.parse(stored)
        // Deobfuscate secret fields
        const deobfuscated: Record<string, string> = {}
        for (const [k, v] of Object.entries(parsed)) {
          deobfuscated[k] = SECRET_FIELDS.has(k) ? deobfuscate(v as string) : (v as string)
        }
        setSettings({ ...defaults, ...deobfuscated })
      } catch {
        setSettings(defaults)
      }
    } else {
      setSettings(defaults)
    }
  }, [])

  const handleSave = () => {
    setSaving(true)
    // Obfuscate secret fields before storing
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
    // Export without secret values — user must re-enter secrets after import
    const exportData: Record<string, string> = {}
    for (const [k, v] of Object.entries(settings)) {
      if (SECRET_FIELDS.has(k)) {
        exportData[k] = '' // Clear secrets on export
      } else {
        exportData[k] = v
      }
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

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-white">Settings</h2>
        <div className="flex items-center gap-2">
          <button onClick={handleImport} className="flex items-center gap-1 px-3 py-1.5 text-sm text-surface-300 hover:text-white transition-colors"><MdFileUpload /> Import</button>
          <button onClick={handleExport} className="flex items-center gap-1 px-3 py-1.5 text-sm text-surface-300 hover:text-white transition-colors"><MdFileDownload /> Export</button>
          <button onClick={handleReset} className="flex items-center gap-1 px-3 py-1.5 text-sm text-red-400 hover:text-red-300 transition-colors"><MdDelete /> Reset</button>
          <button onClick={handleSave} disabled={saving}
            className="flex items-center gap-2 px-4 py-2 bg-brand-600 hover:bg-brand-500 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors">
            <MdSave /> {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {([
          { title: 'Authentication', fields: ['API_KEY_SECRET', 'JWT_SECRET_KEY'] },
          { title: 'OpenAI Provider', fields: ['OPENAI_API_KEY', 'OPENAI_MODEL', 'OPENAI_BASE_URL'] },
          { title: 'NVIDIA Provider', fields: ['NVIDIA_API_KEY', 'NVIDIA_MODEL', 'NVIDIA_BASE_URL'] },
          { title: 'Fallback Providers', fields: ['QWEN_API_KEY', 'QWEN_BASE_URL', 'GLM_API_KEY', 'GLM_BASE_URL'] },
          { title: 'Engineering Service', fields: ['ENGINEERING_SERVICE_URL', 'ENGINEERING_SERVICE_API_KEY', 'ENGINEERING_SERVICE_TIMEOUT_MS'] },
          { title: 'Database', fields: ['MASTRA_DB_URL', 'DATABASE_URL', 'REDIS_URL'] },
          { title: 'Observability', fields: ['LANGWATCH_API_KEY', 'HEALTH_CHECK_API_URL', 'PROMETHEUS_ENABLED', 'PROMETHEUS_PORT'] },
          { title: 'Rate Limiting & Circuit Breaker', fields: ['RATE_LIMIT_REQUESTS_PER_MINUTE', 'CIRCUIT_BREAKER_FAILURE_THRESHOLD', 'MAX_BODY_SIZE'] },
          { title: 'ETAP Integration', fields: ['ETAP_LICENSE_PATH', 'ETAP_WORKER_URL'] },
          { title: 'Vault & Secrets', fields: ['VAULT_ADDR', 'VAULT_TOKEN'] },
          { title: 'Email Alerts', fields: ['SMTP_SERVER', 'SMTP_PORT', 'SMTP_USERNAME', 'ALERT_EMAIL_TO'] },
          { title: 'Feature Flags', fields: ['ENABLE_ASYNC_EXECUTION', 'ENABLE_CACHING', 'ENABLE_OBSERVABILITY'] },
          { title: 'Performance', fields: ['MAX_WORKERS', 'CACHE_SIZE_MB', 'CACHE_DEFAULT_TTL'] },
        ] as { title: string; fields: string[] }[]).map(section => (
          <div key={section.title} className="bg-surface-800 rounded-xl p-5 border border-surface-700">
            <h3 className="text-lg font-semibold text-white mb-4">{section.title}</h3>
            <div className="space-y-3">
              {section.fields.map(field => (
                <div key={field}>
                  <label className="block text-xs font-medium text-surface-400 mb-1">{field}</label>
                  <input
                    type={field.includes('KEY') || field.includes('SECRET') ? 'password' : 'text'}
                    value={settings[field] || ''}
                    onChange={e => setSettings(p => ({ ...p, [field]: e.target.value }))}
                    className="w-full px-3 py-2 bg-surface-900 border border-surface-600 rounded-lg text-white text-sm focus:border-brand-500 outline-none font-mono"
                  />
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
