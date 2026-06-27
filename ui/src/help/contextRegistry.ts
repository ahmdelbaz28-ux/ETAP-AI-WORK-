import type { ContextMapping } from './types'

export const contextRegistry: ContextMapping[] = [
  // Dashboard
  { contextId: 'dashboard.overview', topicId: 'dashboard.overview', priority: 1 },

  // Projects
  { contextId: 'projects.create', topicId: 'projects.create', priority: 1 },
  { contextId: 'projects.manage', topicId: 'projects.manage', priority: 1 },

  // Fire Alarm
  { contextId: 'fire-alarm.detector-placement', topicId: 'fire-alarm.detector-placement', priority: 1 },
  { contextId: 'fire-alarm.symbol-library', topicId: 'fire-alarm.symbol-library', priority: 1 },
  { contextId: 'fire-alarm.zone-navigation', topicId: 'fire-alarm.zone-navigation', priority: 1 },

  // Reports
  { contextId: 'reports.generate', topicId: 'reports.generate', priority: 1 },

  // Digital Twin
  { contextId: 'digital-twin.overview', topicId: 'digital-twin.overview', priority: 1 },

  // Settings
  { contextId: 'settings.backend', topicId: 'settings.backend', priority: 1 },
  { contextId: 'settings.scada', topicId: 'integration.scada', priority: 1 },

  // Troubleshooting
  { contextId: 'troubleshooting.backend', topicId: 'troubleshooting.backend', priority: 1 },
  { contextId: 'troubleshooting.api', topicId: 'troubleshooting.api', priority: 1 },
  { contextId: 'troubleshooting.auth', topicId: 'troubleshooting.auth', priority: 1 },

  // Actions → help
  { contextId: 'action.create-project', topicId: 'projects.create', priority: 1 },
  { contextId: 'action.add-device', topicId: 'fire-alarm.detector-placement', priority: 1 },
  { contextId: 'action.create-connection', topicId: 'fire-alarm.zone-navigation', priority: 1 },
  { contextId: 'action.generate-report', topicId: 'reports.generate', priority: 1 },
  { contextId: 'action.run-compliance', topicId: 'fire-alarm.detector-placement', priority: 1 },
  { contextId: 'action.sync-project', topicId: 'digital-twin.overview', priority: 1 },
  { contextId: 'action.configure-backend', topicId: 'settings.backend', priority: 1 },
  { contextId: 'action.configure-scada', topicId: 'integration.scada', priority: 1 },
]

export function resolveContext(contextId: string): string | null {
  const match = contextRegistry
    .filter(c => c.contextId === contextId)
    .sort((a, b) => (b.priority ?? 0) - (a.priority ?? 0))[0]
  return match?.topicId ?? null
}
