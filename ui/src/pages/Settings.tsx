import { useState } from 'react'
import { motion } from 'framer-motion'
import { Save, Download, Upload, Trash2, Bot, Wrench, Database, Shield, Link2, Gauge } from 'lucide-react'
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

interface SettingsSection {
  title: string
  fields: string[]
}

const TAB_SECTIONS: Record<string, { label: string; icon: React.ReactNode; sections: SettingsSection[] }> = {
  ai: {
    label: 'AI Providers',
    icon: <Bot className="w-4 h-4" />,
    sections: [
      { title: 'OpenAI Provider', fields: ['OPENAI_API_KEY', 'OPENAI_MODEL', 'OPENAI_BASE_URL'] },
      { title: 'NVIDIA Provider', fields: ['NVIDIA_API_KEY', 'NVIDIA_MODEL', 'NVIDIA_BASE_URL'] },
      { title: 'QWEN Provider', fields: ['QWEN_API_KEY', 'QWEN_BASE_URL'] },
      { title: 'GLM Provider', fields: ['GLM_API_KEY', 'GLM_BASE_URL'] },
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
      { title: 'Email Alerts', fields: ['SMTP_SERVER', 'SMTP_PORT', 'SMTP_USERNAME', 'ALERT_EMAIL_TO'] },
    ],
  },
  performance: {
    label: 'Performance',
    icon: <Gauge className="w-4 h-4" />,
    sections: [
      { title: 'Observability', fields: ['LANGWATCH_API_KEY', 'HEALTH_CHECK_API_URL', 'PROMETHEUS_ENABLED', 'PROMETHEUS_PORT'] },
      { title: 'Rate Limiting & Circuit Breaker', fields: ['RATE_LIMIT_REQUESTS_PER_MINUTE', 'CIRCUIT_BREAKER_FAILURE_THRESHOLD', 'MAX_BODY_SIZE'] },
      { title: 'Feature Flags', fields: ['ENABLE_ASYNC_EXECUTION', 'ENABLE_CACHING', 'ENABLE_OBSERVABILITY'] },
    ],
  },
}

function SettingsField({ field, value, onChange }: { field: string; value: string; onChange: (v: string) => void }) {
  const isSecret = field.includes('KEY') || field.includes('SECRET')
  const isFeatureFlag = field.startsWith('ENABLE_')
  const isNumber = field.includes('_MS') || field.includes('PORT') || field.includes('SIZE') || field.includes('TTL') || field.includes('RATE') || field.includes('THRESHOLD') || field.includes('MAX_')

  if (isFeatureFlag) {
    return (
      <Toggle
        checked={value === 'true'}
        onChange={(checked) => onChange(checked ? 'true' : 'false')}
        label={field.replace(/_/g, ' ').replace(/ENABLE /, '')}
        description={`Toggle ${field.replace(/_/g, ' ').toLowerCase()}`}
        size="sm"
      />
    )
  }

  return (
    <div>
      <label className="block text-xs font-medium text-[var(--text-tertiary)] mb-1.5">{field}</label>
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
          className="grid grid-cols-1 lg:grid-cols-2 gap-6"
        >
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
        </motion.div>
      </TabPanels>
    </div>
  )
}
