import { motion } from 'framer-motion'
import { Cable, Settings2, Link2, Activity, Clock, CheckCircle, Server, FileText } from 'lucide-react'
import { useNotify } from '../context/NotificationContext'
import { Card, CardHeader, Badge, Button } from '../components/ui'

import { ContextHelpButton } from '../components/help/ContextHelpButton'
export default function EtapIntegration() {
  const { notify } = useNotify()

  const connectionItems = [
    { label: 'Worker URL', value: 'Not configured', status: 'warning' as const },
    { label: 'License', value: 'Not connected', status: 'warning' as const },
    { label: 'Worker Status', value: 'Offline', status: 'danger' as const },
    { label: 'Projects', value: '0', status: 'default' as const },
  ]

  const recentStudies = [
    { name: 'Load Flow - Industrial Plant', status: 'completed', date: '2026-06-09' },
    { name: 'Short Circuit - Substation B', status: 'completed', date: '2026-06-07' },
    { name: 'Arc Flash - MCC Panel', status: 'completed', date: '2026-06-05' },
  ]

  return (
    <div className="space-y-6">
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-brand-500/10 border border-brand-500/20">
            <Cable className="w-5 h-5 text-brand-400" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-[var(--text-primary)]">ETAP Integration</h2>
            <div className="flex items-center gap-2">
              <p className="text-sm text-[var(--text-tertiary)]">Connect to ETAP engineering platform</p>
              <ContextHelpButton contextId="etap-integration.overview" />
            </div>
          </div>
        </div>
      </motion.div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Connection Status */}
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
          <Card padding="md">
            <CardHeader
              title="Connection Status"
              subtitle="ETAP worker & license status"
              icon={<Settings2 className="w-4 h-4" />}
            />
            <div className="space-y-3">
              {connectionItems.map(item => (
                <div key={item.label} className="flex items-center justify-between p-3 bg-[var(--bg-primary)] rounded-lg border border-[var(--border-primary)]">
                  <div className="flex items-center gap-2">
                    <Server className="w-3.5 h-3.5 text-[var(--text-muted)]" />
                    <span className="text-sm text-[var(--text-tertiary)]">{item.label}</span>
                  </div>
                  <Badge variant={item.status} dot size="sm">
                    {item.value}
                  </Badge>
                </div>
              ))}
            </div>
            <div className="mt-4 pt-4 border-t border-[var(--border-primary)]">
              <Button
                variant="primary"
                size="sm"
                icon={Link2}
                onClick={() => notify('info', 'ETAP connection requires Windows with ETAP installed')}
                className="w-full"
              >
                Connect to ETAP
              </Button>
            </div>
          </Card>
        </motion.div>

        {/* Recent Studies */}
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
          <Card padding="md">
            <CardHeader
              title="Recent Studies"
              subtitle="Latest ETAP study results"
              icon={<Activity className="w-4 h-4" />}
            />
            <div className="space-y-3">
              {recentStudies.map((study, i) => (
                <div key={i} className="flex items-center justify-between p-3 bg-[var(--bg-primary)] rounded-lg border border-[var(--border-primary)]">  // NOSONAR — S6479: array index as key; items lack stable IDs (tech debt)
                  <div className="flex items-center gap-2.5">
                    <div className="p-1.5 rounded-md bg-green-500/10">
                      <FileText className="w-3.5 h-3.5 text-green-400" />
                    </div>
                    <div>
                      <p className="text-sm font-medium text-[var(--text-primary)]">{study.name}</p>
                      <div className="flex items-center gap-1.5 text-xs text-[var(--text-muted)]">
                        <Clock className="w-3 h-3" />
                        {study.date}
                      </div>
                    </div>
                  </div>
                  <Badge variant="success" size="sm">
                    {study.status}
                  </Badge>
                </div>
              ))}
            </div>
          </Card>
        </motion.div>
      </div>

      {/* Integration Info */}
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}>
        <Card padding="md">
          <CardHeader
            title="Integration Requirements"
            subtitle="Prerequisites for ETAP connectivity"
            icon={<Cable className="w-4 h-4" />}
          />
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-4 bg-[var(--bg-primary)] rounded-lg border border-[var(--border-primary)]">
              <CheckCircle className="w-5 h-5 text-amber-400 mb-2" />
              <h4 className="text-sm font-medium text-[var(--text-primary)]">ETAP Installation</h4>
              <p className="text-xs text-[var(--text-muted)] mt-1">ETAP must be installed on a Windows machine with a valid license</p>
            </div>
            <div className="p-4 bg-[var(--bg-primary)] rounded-lg border border-[var(--border-primary)]">
              <CheckCircle className="w-5 h-5 text-amber-400 mb-2" />
              <h4 className="text-sm font-medium text-[var(--text-primary)]">Worker Service</h4>
              <p className="text-xs text-[var(--text-muted)] mt-1">ETAP worker service must be running and accessible from the AI platform</p>
            </div>
            <div className="p-4 bg-[var(--bg-primary)] rounded-lg border border-[var(--border-primary)]">
              <CheckCircle className="w-5 h-5 text-amber-400 mb-2" />
              <h4 className="text-sm font-medium text-[var(--text-primary)]">License Path</h4>
              <p className="text-xs text-[var(--text-muted)] mt-1">Configure the ETAP license path in Settings under ETAP Integration</p>
            </div>
          </div>
        </Card>
      </motion.div>
    </div>
  )
}
