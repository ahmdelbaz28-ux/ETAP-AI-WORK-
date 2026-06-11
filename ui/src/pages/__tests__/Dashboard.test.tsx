import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Dashboard } from '../Dashboard'
import { NotificationProvider } from '../../context/NotificationContext'

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
    expect(await screen.findByText('Dashboard')).toBeInTheDocument()
  })

  it('shows loading spinner while fetching', () => {
    renderDashboard()
    expect(document.querySelector('.animate-spin')).toBeInTheDocument()
  })

  it('renders status cards after loading', async () => {
    renderDashboard()
    expect(await screen.findByText('System Status')).toBeInTheDocument()
    expect(await screen.findByText('Online')).toBeInTheDocument()
    expect(await screen.findByText('Active Agents')).toBeInTheDocument()
  })
})
