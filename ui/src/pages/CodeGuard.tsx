import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { motion } from 'framer-motion'
import {
  Shield, AlertTriangle, AlertCircle, Info,
  Code, FileText, TestTube, Bug, Send
} from 'lucide-react'
import { useNotify } from '../context/NotificationContext'
import { guardReview, type GuardReviewResult, type GuardViolation } from '../lib/api'
import { Card, CardHeader, Badge } from '../components/ui'

const fadeIn = {
  initial: { opacity: 0, y: 20 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.4 }
}

const severityConfig = {
  must_fix: { icon: AlertTriangle, color: 'text-red-500', bg: 'bg-red-500/10', border: 'border-red-500/30', label: 'MUST FIX' },
  should_fix: { icon: AlertCircle, color: 'text-amber-500', bg: 'bg-amber-500/10', border: 'border-amber-500/30', label: 'SHOULD FIX' },
  worth_noting: { icon: Info, color: 'text-blue-500', bg: 'bg-blue-500/10', border: 'border-blue-500/30', label: 'INFO' },
}

export default function CodeGuard() {
  const { t } = useTranslation()
  const { notify } = useNotify()
  const [source, setSource] = useState('')
  const [guardType, setGuardType] = useState('all')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<GuardReviewResult | null>(null)

  const handleReview = async () => {
    if (!source.trim()) {
      notify('error', 'Please enter source code to review')
      return
    }
    setLoading(true)
    try {
      const res = await guardReview(source, guardType)
      setResult(res)
      if (res.all_passed) {
        notify('success', 'Code passed all guard checks!')
      } else {
        notify('warning', `Found ${res.must_fix_total} must-fix and ${res.should_fix_total} should-fix violations`)
      }
    } catch (err) {
      notify('error', `Guard review failed: ${err}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <motion.div {...fadeIn}>
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-purple-500/10 rounded-xl">
            <Shield className="w-6 h-6 text-purple-500" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
              {t('codeGuard.title', 'Code Guard')}
            </h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              {t('codeGuard.subtitle', 'AI-powered code quality review — 14 failure modes + 23 clean-code rules + 9 test rules + 10 docs rules')}
            </p>
          </div>
        </div>
      </motion.div>

      {/* Input Panel */}
      <motion.div {...fadeIn} transition={{ delay: 0.1 }}>
        <Card>
          <CardHeader title="Source Code" icon={<Code className="w-4 h-4 text-purple-500" />}
            action={
              <div className="flex gap-2">
                {[
                  { value: 'all', label: 'All Guards', icon: Shield },
                  { value: 'code', label: 'Code', icon: Code },
                  { value: 'test', label: 'Tests', icon: TestTube },
                  { value: 'docs', label: 'Docs', icon: FileText },
                  { value: 'ai_failure_modes', label: 'AI Modes', icon: Bug },
                ].map(({ value, label, icon: Icon }) => (
                  <button
                    key={value}
                    onClick={() => setGuardType(value)}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm transition-colors ${
                      guardType === value
                        ? 'bg-purple-500 text-white'
                        : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700'
                    }`}
                  >
                    <Icon className="w-3.5 h-3.5" />
                    {label}
                  </button>
                ))}
              </div>
            }
          />
          <textarea
            value={source}
            onChange={(e) => setSource(e.target.value)}
            placeholder={`# Paste your Python code here...\n# Example:\ndef calculate_impedance(voltage, current):\n    return voltage / current`}
            className="w-full h-64 p-4 font-mono text-sm bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg resize-y focus:outline-none focus:ring-2 focus:ring-purple-500"
          />
          <div className="flex justify-end mt-4">
            <button
              onClick={handleReview}
              disabled={loading || !source.trim()}
              className="flex items-center gap-2 px-6 py-2.5 bg-purple-500 hover:bg-purple-600 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg font-medium transition-colors"
            >
              <Send className="w-4 h-4" />
              {loading ? 'Scanning...' : 'Run Guard Review'}
            </button>
          </div>
        </Card>
      </motion.div>

      {/* Results Panel */}
      {result && (
        <motion.div {...fadeIn} transition={{ delay: 0.2 }}>
          {/* Summary Cards */}
          <div className="grid grid-cols-4 gap-4 mb-6">
            <Card>
              <div className="p-4 text-center">
                <div className={`text-3xl font-bold ${result.all_passed ? 'text-green-500' : 'text-red-500'}`}>
                  {result.all_passed ? 'PASS' : 'FAIL'}
                </div>
                <div className="text-sm text-gray-500 mt-1">Overall</div>
              </div>
            </Card>
            <Card>
              <div className="p-4 text-center">
                <div className="text-3xl font-bold text-red-500">{result.must_fix_total}</div>
                <div className="text-sm text-gray-500 mt-1">Must Fix</div>
              </div>
            </Card>
            <Card>
              <div className="p-4 text-center">
                <div className="text-3xl font-bold text-amber-500">{result.should_fix_total}</div>
                <div className="text-sm text-gray-500 mt-1">Should Fix</div>
              </div>
            </Card>
            <Card>
              <div className="p-4 text-center">
                <div className="text-3xl font-bold text-blue-500">{result.worth_noting_total}</div>
                <div className="text-sm text-gray-500 mt-1">Worth Noting</div>
              </div>
            </Card>
          </div>

          {/* Violations List */}
          {Object.entries(result.guard_results).map(([guardName, guardData]) => (
            <div key={guardName} className="mb-6">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-3 flex items-center gap-2">
                <Shield className="w-5 h-5 text-purple-500" />
                {guardData.guard_name}
                <Badge variant={guardData.passed ? 'success' : 'danger'}>
                  {guardData.passed ? 'PASSED' : 'FAILED'}
                </Badge>
              </h3>
              <div className="space-y-3">
                {guardData.violations.length === 0 ? (
                  <div className="p-4 bg-green-500/5 border border-green-500/20 rounded-lg text-green-600 dark:text-green-400">
                    No violations found
                  </div>
                ) : (
                  guardData.violations.map((v: GuardViolation, i: number) => {
                    const config = severityConfig[v.severity as keyof typeof severityConfig] || severityConfig.worth_noting
                    const Icon = config.icon
                    return (
                      <div key={i} className={`p-4 rounded-lg border ${config.bg} ${config.border}`}>
                        <div className="flex items-start gap-3">
                          <Icon className={`w-5 h-5 mt-0.5 ${config.color}`} />
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1">
                              <Badge variant={v.severity === 'must_fix' ? 'danger' : v.severity === 'should_fix' ? 'warning' : 'default'}>
                                {v.rule_id}
                              </Badge>
                              <span className="font-medium text-gray-900 dark:text-white">{v.rule_name}</span>
                              <span className={`text-xs px-2 py-0.5 rounded ${config.bg} ${config.color}`}>
                                {config.label}
                              </span>
                            </div>
                            <p className="text-sm text-gray-600 dark:text-gray-400">{v.description}</p>
                            {v.location && (
                              <p className="text-xs text-gray-500 mt-1 font-mono">{v.location}</p>
                            )}
                            {v.suggestion && (
                              <p className="text-sm text-purple-600 dark:text-purple-400 mt-2">
                                Fix: {v.suggestion}
                              </p>
                            )}
                          </div>
                        </div>
                      </div>
                    )
                  })
                )}
              </div>
            </div>
          ))}
        </motion.div>
      )}
    </div>
  )
}
