/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import Settings from '../Settings'
import { NotificationProvider } from '../../context/NotificationContext'

// ── Mocks ──────────────────────────────────────────────────────────────────────

vi.mock('framer-motion', () => ({
  motion: {
    div: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => (
      <div {...props}>{children}</div>
    ),
  },
  AnimatePresence: ({ children }: React.PropsWithChildren) => <>{children}</>,
}))

vi.mock('../../lib/api', () => ({
  fetchHealth: vi.fn().mockResolvedValue({ ok: true }),
}))

// ── Helpers ────────────────────────────────────────────────────────────────────

function renderSettings() {
  return render(
    <NotificationProvider>
      <Settings />
    </NotificationProvider>
  )
}

// ── Tests ──────────────────────────────────────────────────────────────────────

describe('Settings', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
  })

  it('renders the Settings page title', () => {
    renderSettings()
    expect(screen.getByText('Settings')).toBeTruthy()
  })

  it('renders tab navigation for settings sections', () => {
    renderSettings()
    expect(screen.getByText('AI Providers')).toBeTruthy()
    expect(screen.getByText('Engineering Service')).toBeTruthy()
    expect(screen.getByText('Database & Cache')).toBeTruthy()
    expect(screen.getByText('Security')).toBeTruthy()
    expect(screen.getByText('Integration')).toBeTruthy()
    expect(screen.getByText('Performance')).toBeTruthy()
  })

  it('switches tabs and displays the correct section content', async () => {
    const user = userEvent.setup()
    renderSettings()

    // Default tab is AI Providers - should show OpenAI Provider section header (h3)
    expect(screen.getByText('OpenAI Provider')).toBeTruthy()

    // Switch to Security tab
    await user.click(screen.getByText('Security'))
    // Should now show the Authentication section header
    expect(screen.getByText('Authentication')).toBeTruthy()
  })

  it('saves settings to localStorage on Save click', async () => {
    const user = userEvent.setup()
    renderSettings()

    const saveBtn = screen.getByText('Save')
    await user.click(saveBtn)

    await waitFor(() => {
      const stored = localStorage.getItem('etap-settings')
      expect(stored).not.toBeNull()
      const parsed = JSON.parse(stored!)
      expect(parsed.OPENAI_MODEL).toBeTruthy()
    })
  })

  it('resets settings to defaults on Reset click', async () => {
    const user = userEvent.setup()
    localStorage.setItem('etap-settings', JSON.stringify({ OPENAI_MODEL: 'custom-model' }))

    renderSettings()

    const resetBtn = screen.getByText('Reset')
    await user.click(resetBtn)

    expect(localStorage.getItem('etap-settings')).toBeNull()
  })

  it('renders secret fields as password inputs', () => {
    renderSettings()
    const passwordInputs = document.querySelectorAll('input[type="password"]')
    expect(passwordInputs.length).toBeGreaterThan(0)
  })

  it('renders feature flag toggles when on Performance tab', async () => {
    const user = userEvent.setup()
    renderSettings()

    // Switch to Performance tab which has ENABLE_* feature flags
    await user.click(screen.getByText('Performance'))

    // Toggle components render with role="switch"
    const switches = document.querySelectorAll('[role="switch"]')
    expect(switches.length).toBeGreaterThan(0)
  })

  it('displays Export and Import buttons', () => {
    renderSettings()
    expect(screen.getByText('Export')).toBeTruthy()
    expect(screen.getByText('Import')).toBeTruthy()
  })
})
