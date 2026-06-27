import type { ContextMapping } from './types'

// ============================================================================
// Context Registry
// ============================================================================
// Maps `data-help-context` attribute values to their corresponding help topic
// IDs. The Magic Help Inspector reads this attribute when you click an element,
// then opens the Smart Help drawer with the matching topic.
//
// To wire up a new element:
//   1. Add `data-help-context="my.context.id"` to the JSX element
//   2. Add an entry here mapping "my.context.id" to a topic ID
//   3. Add the topic to helpTopics.ts if it doesn't exist yet
// ============================================================================

export const contextRegistry: ContextMapping[] = [
  // ─── Dashboard ────────────────────────────────────────────────────
  { contextId: 'dashboard', topicId: 'dashboard.overview', priority: 1 },
  { contextId: 'dashboard.overview', topicId: 'dashboard.overview', priority: 1 },
  { contextId: 'dashboard.status-cards', topicId: 'dashboard.overview', priority: 2 },
  { contextId: 'dashboard.quick-actions', topicId: 'studies.overview', priority: 2 },
  { contextId: 'dashboard.recent-studies', topicId: 'studies.overview', priority: 2 },

  // ─── Projects ─────────────────────────────────────────────────────
  { contextId: 'projects', topicId: 'projects.create', priority: 1 },
  { contextId: 'projects.create', topicId: 'projects.create', priority: 1 },
  { contextId: 'projects.manage', topicId: 'projects.manage', priority: 1 },
  { contextId: 'projects.new-button', topicId: 'projects.create', priority: 2 },
  { contextId: 'projects.search', topicId: 'projects.manage', priority: 2 },
  { contextId: 'projects.filter', topicId: 'projects.manage', priority: 2 },
  { contextId: 'projects.card', topicId: 'projects.manage', priority: 2 },

  // ─── Studies ──────────────────────────────────────────────────────
  { contextId: 'studies', topicId: 'studies.overview', priority: 1 },
  { contextId: 'studies.overview', topicId: 'studies.overview', priority: 1 },
  { contextId: 'studies.load-flow', topicId: 'studies.load-flow', priority: 1 },
  { contextId: 'studies.short-circuit', topicId: 'studies.short-circuit', priority: 1 },
  { contextId: 'studies.arc-flash', topicId: 'studies.arc-flash', priority: 1 },
  { contextId: 'studies.harmonic', topicId: 'studies.harmonic', priority: 1 },
  { contextId: 'studies.motor-starting', topicId: 'studies.motor-starting', priority: 1 },
  { contextId: 'studies.protection', topicId: 'studies.protection', priority: 1 },
  { contextId: 'studies.cable-sizing', topicId: 'studies.cable-sizing', priority: 1 },
  { contextId: 'studies.earth-grid', topicId: 'studies.earth-grid', priority: 1 },
  { contextId: 'studies.stability', topicId: 'studies.stability', priority: 1 },
  { contextId: 'studies.opf', topicId: 'studies.opf', priority: 1 },
  { contextId: 'studies.run-button', topicId: 'studies.overview', priority: 2 },
  { contextId: 'studies.parameters', topicId: 'studies.overview', priority: 2 },

  // ─── AI Assistant ─────────────────────────────────────────────────
  { contextId: 'ai-assistant', topicId: 'ai-assistant.overview', priority: 1 },
  { contextId: 'ai-assistant.overview', topicId: 'ai-assistant.overview', priority: 1 },
  { contextId: 'ai-assistant.chat-input', topicId: 'ai-assistant.overview', priority: 2 },
  { contextId: 'ai-assistant.agent-selector', topicId: 'ai-assistant.overview', priority: 2 },
  { contextId: 'ai-assistant.send-button', topicId: 'ai-assistant.overview', priority: 2 },

  // ─── Asset Management ─────────────────────────────────────────────
  { contextId: 'asset-management', topicId: 'asset-management.overview', priority: 1 },
  { contextId: 'asset-management.overview', topicId: 'asset-management.overview', priority: 1 },
  { contextId: 'asset-management.add-asset', topicId: 'asset-management.overview', priority: 2 },

  // ─── ETAP Integration ─────────────────────────────────────────────
  { contextId: 'etap', topicId: 'etap-integration.overview', priority: 1 },
  { contextId: 'etap-integration', topicId: 'etap-integration.overview', priority: 1 },
  { contextId: 'etap-integration.overview', topicId: 'etap-integration.overview', priority: 1 },
  { contextId: 'etap.worker-url', topicId: 'etap-integration.overview', priority: 2 },
  { contextId: 'etap.license-path', topicId: 'etap-integration.overview', priority: 2 },
  { contextId: 'etap.use-toggle', topicId: 'etap-integration.overview', priority: 2 },

  // ─── GIS Integration ──────────────────────────────────────────────
  { contextId: 'gis', topicId: 'gis-integration.overview', priority: 1 },
  { contextId: 'gis-integration', topicId: 'gis-integration.overview', priority: 1 },
  { contextId: 'gis-integration.overview', topicId: 'gis-integration.overview', priority: 1 },
  { contextId: 'gis.provider-select', topicId: 'gis-integration.overview', priority: 2 },
  { contextId: 'gis.import-button', topicId: 'gis-integration.overview', priority: 2 },

  // ─── Reports ──────────────────────────────────────────────────────
  { contextId: 'reports', topicId: 'reports.generate', priority: 1 },
  { contextId: 'reports.generate', topicId: 'reports.generate', priority: 1 },
  { contextId: 'reports.new-button', topicId: 'reports.generate', priority: 2 },
  { contextId: 'reports.format-select', topicId: 'reports.generate', priority: 2 },

  // ─── Digital Twin ─────────────────────────────────────────────────
  { contextId: 'digital-twin', topicId: 'digital-twin.overview', priority: 1 },
  { contextId: 'digital-twin.overview', topicId: 'digital-twin.overview', priority: 1 },
  { contextId: 'digital-twin.sync-toggle', topicId: 'digital-twin.overview', priority: 2 },

  // ─── Settings ─────────────────────────────────────────────────────
  { contextId: 'settings', topicId: 'settings.backend', priority: 1 },
  { contextId: 'settings.backend', topicId: 'settings.backend', priority: 1 },
  { contextId: 'settings.external-services', topicId: 'settings.external-services', priority: 1 },
  { contextId: 'settings.ai-providers', topicId: 'settings.ai-providers', priority: 1 },
  { contextId: 'settings.scada', topicId: 'integration.scada', priority: 1 },
  { contextId: 'settings.test-connection', topicId: 'settings.external-services', priority: 2 },
  { contextId: 'settings.save', topicId: 'settings.backend', priority: 2 },
  { contextId: 'settings.export', topicId: 'settings.backend', priority: 2 },
  { contextId: 'settings.reset', topicId: 'settings.backend', priority: 2 },

  // ─── Code Guard ───────────────────────────────────────────────────
  { contextId: 'code-guard', topicId: 'code-guard.overview', priority: 1 },
  { contextId: 'code-guard.overview', topicId: 'code-guard.overview', priority: 1 },
  { contextId: 'code-guard.editor', topicId: 'code-guard.overview', priority: 2 },
  { contextId: 'code-guard.review-button', topicId: 'code-guard.overview', priority: 2 },

  // ─── Data Import / Export ─────────────────────────────────────────
  { contextId: 'data-import', topicId: 'data-import.overview', priority: 1 },
  { contextId: 'data-import.overview', topicId: 'data-import.overview', priority: 1 },
  { contextId: 'data-export', topicId: 'data-export.overview', priority: 1 },
  { contextId: 'data-export.overview', topicId: 'data-export.overview', priority: 1 },

  // ─── Administration ───────────────────────────────────────────────
  { contextId: 'admin', topicId: 'administration.overview', priority: 1 },
  { contextId: 'administration', topicId: 'administration.overview', priority: 1 },
  { contextId: 'administration.overview', topicId: 'administration.overview', priority: 1 },
  { contextId: 'administration.user-list', topicId: 'administration.overview', priority: 2 },

  // ─── Diagnostics ──────────────────────────────────────────────────
  { contextId: 'diagnostics', topicId: 'diagnostics.overview', priority: 1 },
  { contextId: 'diagnostics.overview', topicId: 'diagnostics.overview', priority: 1 },
  { contextId: 'diagnostics.health-checks', topicId: 'diagnostics.overview', priority: 2 },

  // ─── Logs ─────────────────────────────────────────────────────────
  { contextId: 'logs', topicId: 'logs.overview', priority: 1 },
  { contextId: 'logs.overview', topicId: 'logs.overview', priority: 1 },
  { contextId: 'logs.filter', topicId: 'logs.overview', priority: 2 },

  // ─── Magic Help Inspector ─────────────────────────────────────────
  { contextId: 'magic-help', topicId: 'magic-help.inspector', priority: 1 },
  { contextId: 'magic-help.inspector', topicId: 'magic-help.inspector', priority: 1 },

  // ─── Troubleshooting ──────────────────────────────────────────────
  { contextId: 'troubleshooting.backend', topicId: 'troubleshooting.backend', priority: 1 },
  { contextId: 'troubleshooting.api', topicId: 'troubleshooting.api', priority: 1 },
  { contextId: 'troubleshooting.auth', topicId: 'troubleshooting.auth', priority: 1 },

  // ─── Action shortcuts (for buttons that don't have a direct page) ─
  { contextId: 'action.create-project', topicId: 'projects.create', priority: 1 },
  { contextId: 'action.add-device', topicId: 'asset-management.overview', priority: 1 },
  { contextId: 'action.generate-report', topicId: 'reports.generate', priority: 1 },
  { contextId: 'action.run-study', topicId: 'studies.overview', priority: 1 },
  { contextId: 'action.sync-project', topicId: 'digital-twin.overview', priority: 1 },
  { contextId: 'action.configure-backend', topicId: 'settings.backend', priority: 1 },
  { contextId: 'action.configure-scada', topicId: 'integration.scada', priority: 1 },
  { contextId: 'action.test-connection', topicId: 'settings.external-services', priority: 1 },
  { contextId: 'action.open-help', topicId: 'magic-help.inspector', priority: 1 },
]

export function resolveContext(contextId: string): string | null {
  const match = contextRegistry
    .filter(c => c.contextId === contextId)
    .sort((a, b) => (b.priority ?? 0) - (a.priority ?? 0))[0]
  return match?.topicId ?? null
}
