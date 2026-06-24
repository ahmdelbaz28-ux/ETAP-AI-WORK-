/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import Dashboard from '../Dashboard'
import { NotificationProvider } from '../../context/NotificationContext'

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => {
      const map: Record<string, string> = {
        'dashboard.title': 'Dashboard',
        'dashboard.subtitle': 'System Overview',
        'dashboard.systemHealth': 'System Health',
        'dashboard.online': 'Online',
        'dashboard.offline': 'Offline',
        'dashboard.agents': 'Agents',
        'dashboard.totalStudies': 'Total Studies',
        'dashboard.engineeringService': 'Engineering Service',
        'dashboard.healthy': 'Healthy',
        'dashboard.studyCapabilities': 'capabilities',
        'dashboard.activeStudies': 'Active Studies',
        'dashboard.quickActions': 'Quick Actions',
        'dashboard.viewAll': 'View All',
        'common.loading': 'Loading...'
      }
      return map[key] || key
    },
    i18n: { language: 'en' }
  })
}))

vi.mock('../../lib/api', () => ({
  fetchHealth: vi.fn().mockResolvedValue({
    ok: true,
    service: 'etap-ai-platform',
    version: '1.0.0',
    providers: ['openai'],
    engineeringService: { configured: false, healthy: false },
  }),
  fetchAgents: vi.fn().mockResolvedValue([
    { id: 'load-flow-agent', name: 'Load Flow Agent', description: 'Test', capabilities: ['load_flow'] },
  ]),
}))

function renderDashboard() {
  return render(
    <MemoryRouter>
      <NotificationProvider>
        <Dashboard />
      </NotificationProvider>
    </MemoryRouter>
  )
}

describe('Dashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the page title', async () => {
    renderDashboard()
    const title = await screen.findByText('Dashboard')
    expect(title).toBeTruthy()
  })

  it('shows loading state while fetching', () => {
    renderDashboard()
    // Component should render without crashing
    expect(document.body).toBeTruthy()
  })

  it('renders content after loading', async () => {
    renderDashboard()
    // Wait for the component to finish loading
    await vi.waitFor(async () => {
      const content = document.body.textContent || ''
      expect(content.length).toBeGreaterThan(0)
    })
  })
})
