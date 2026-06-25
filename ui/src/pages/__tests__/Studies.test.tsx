/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import Studies from '../Studies'

// ── Mocks ──────────────────────────────────────────────────────────────────────

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => {
      const map: Record<string, string> = {
        'studies.title': 'Engineering Studies',
        'studies.subtitle': 'Select a study type to run real engineering computations powered by the Python engine.',
        'studies.parameters': 'Parameters',
        'studies.runStudy': 'Run Study',
      }
      return map[key] || key
    },
    i18n: { language: 'en' },
  }),
}))

vi.mock('framer-motion', () => ({
  motion: {
    div: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => (
      <div {...props}>{children}</div>
    ),
  },
}))

const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

// ── Helpers ────────────────────────────────────────────────────────────────────

function renderStudies() {
  return render(
    <MemoryRouter>
      <Studies />
    </MemoryRouter>
  )
}

// ── Tests ──────────────────────────────────────────────────────────────────────

describe('Studies', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the page title and subtitle using translations', () => {
    renderStudies()
    expect(screen.getByText('Engineering Studies')).toBeTruthy()
    expect(screen.getByText(/Select a study type to run/)).toBeTruthy()
  })

  it('renders all 8 study category cards', () => {
    renderStudies()
    expect(screen.getByText('Load Flow Analysis')).toBeTruthy()
    expect(screen.getByText('Short Circuit Analysis')).toBeTruthy()
    expect(screen.getByText('Arc Flash Analysis')).toBeTruthy()
    expect(screen.getByText('Harmonic Analysis')).toBeTruthy()
    expect(screen.getByText('Protection Coordination')).toBeTruthy()
    expect(screen.getByText('Motor Starting Analysis')).toBeTruthy()
    expect(screen.getByText('Optimal Power Flow')).toBeTruthy()
    expect(screen.getByText('Transient Stability')).toBeTruthy()
  })

  it('displays standard badges for compliant studies', () => {
    renderStudies()
    // IEEE appears on both Load Flow and Motor Starting cards
    const ieeeBadges = screen.getAllByText('IEEE')
    expect(ieeeBadges.length).toBeGreaterThanOrEqual(2)
    // IEC 60909 is on Short Circuit
    expect(screen.getByText('IEC 60909')).toBeTruthy()
    // IEEE 1584-2018 is on Arc Flash
    expect(screen.getByText('IEEE 1584-2018')).toBeTruthy()
    // IEEE 519-2022 is on Harmonic Analysis
    expect(screen.getByText('IEEE 519-2022')).toBeTruthy()
  })

  it('shows parameter count for each study card', () => {
    renderStudies()
    // The text "4 Parameters" etc. is split across elements, so use a function matcher
    const paramElements = screen.getAllByText(/Parameters/)
    expect(paramElements.length).toBe(8)
  })

  it('navigates to the study run page when a card is clicked', async () => {
    const user = userEvent.setup()
    renderStudies()

    await user.click(screen.getByText('Load Flow Analysis'))
    expect(mockNavigate).toHaveBeenCalledWith('/studies/load_flow')
  })

  it('displays study descriptions', () => {
    renderStudies()
    expect(screen.getByText(/Newton-Raphson power flow solver/)).toBeTruthy()
    expect(screen.getByText(/IEC 60909 compliant fault current/)).toBeTruthy()
    expect(screen.getByText(/IEEE 1584-2018 incident energy/)).toBeTruthy()
  })

  it('renders the "Run Study" label on each card', () => {
    renderStudies()
    const runStudyLabels = screen.getAllByText('Run Study')
    expect(runStudyLabels.length).toBe(8)
  })
})
