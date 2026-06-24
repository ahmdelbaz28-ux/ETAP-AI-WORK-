import { motion } from 'framer-motion'
import { Map, Layers, CheckCircle, XCircle, AlertTriangle, Shield, RefreshCw, Globe, Database } from 'lucide-react'
import { useNotify } from '../context/NotificationContext'
import { Card, CardHeader, Badge, Button } from '../components/ui'
import { cn } from '../utils/helpers'

export default function GisIntegration() {
  const { notify } = useNotify()

  const providers = [
    { name: 'ArcGIS Provider', status: 'configured', icon: <Globe className="w-4 h-4" /> },
    { name: 'QGIS Provider', status: 'not_configured', icon: <Database className="w-4 h-4" /> },
  ]

  const validators = [
    { label: 'CRS Validator', status: 'pass', description: 'Coordinate reference system check' },
    { label: 'Topology Validator', status: 'pass', description: 'Network topology integrity' },
    { label: 'Grid Consistency Engine', status: 'warn', description: 'Grid model consistency' },
    { label: 'Impedance Validator', status: 'pass', description: 'Impedance data validation' },
  ]

  const validatorStatusConfig = {
    pass: { variant: 'success' as const, icon: <CheckCircle className="w-4 h-4 text-green-400" /> },
    warn: { variant: 'warning' as const, icon: <AlertTriangle className="w-4 h-4 text-amber-400" /> },
    fail: { variant: 'danger' as const, icon: <XCircle className="w-4 h-4 text-red-400" /> },
  }

  return (
    <div className="space-y-6">
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-green-500/10 border border-green-500/20">
            <Map className="w-5 h-5 text-green-400" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-[var(--text-primary)]">GIS Integration</h2>
            <p className="text-sm text-[var(--text-tertiary)]">Geographic information system connectivity</p>
          </div>
        </div>
      </motion.div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* GIS Providers */}
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
          <Card padding="md">
            <CardHeader
              title="GIS Providers"
              subtitle="Connected data sources"
              icon={<Layers className="w-4 h-4" />}
            />
            <div className="space-y-3">
              {providers.map(p => (
                <div key={p.name} className="flex items-center justify-between p-3 bg-[var(--bg-primary)] rounded-lg border border-[var(--border-primary)]">
                  <div className="flex items-center gap-2.5">
                    <div className={cn(
                      'p-1.5 rounded-md',
                      p.status === 'configured' ? 'bg-green-500/10' : 'bg-[var(--bg-elevated)]'
                    )}>
                      {p.icon}
                    </div>
                    <span className="text-sm font-medium text-[var(--text-primary)]">{p.name}</span>
                  </div>
                  <Badge
                    variant={p.status === 'configured' ? 'success' : 'default'}
                    dot
                    size="sm"
                  >
                    {p.status === 'configured' ? 'Ready' : 'Not configured'}
                  </Badge>
                </div>
              ))}
            </div>
            <div className="mt-4 pt-4 border-t border-[var(--border-primary)]">
              <div className="flex items-center gap-2 text-xs text-[var(--text-muted)]">
                <Layers className="w-3.5 h-3.5" />
                <span>Configure GIS providers in Settings</span>
              </div>
            </div>
          </Card>
        </motion.div>

        {/* GIS Validation */}
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
          <Card padding="md">
            <CardHeader
              title="GIS Validation"
              subtitle="Data quality checks"
              icon={<Shield className="w-4 h-4" />}
            />
            <div className="space-y-3">
              {validators.map(v => {
                const config = validatorStatusConfig[v.status as keyof typeof validatorStatusConfig]
                return (
                  <div key={v.label} className="flex items-center justify-between p-3 bg-[var(--bg-primary)] rounded-lg border border-[var(--border-primary)]">
                    <div className="flex items-center gap-2.5">
                      {config.icon}
                      <div>
                        <p className="text-sm font-medium text-[var(--text-primary)]">{v.label}</p>
                        <p className="text-xs text-[var(--text-muted)]">{v.description}</p>
                      </div>
                    </div>
                    <Badge variant={config.variant} size="sm" className="uppercase">
                      {v.status}
                    </Badge>
                  </div>
                )
              })}
            </div>
            <div className="mt-4 pt-4 border-t border-[var(--border-primary)]">
              <Button
                variant="primary"
                size="sm"
                icon={RefreshCw}
                onClick={() => notify('info', 'GIS validation requires connected data sources')}
                className="w-full"
              >
                Run Validation
              </Button>
            </div>
          </Card>
        </motion.div>
      </div>
    </div>
  )
}
