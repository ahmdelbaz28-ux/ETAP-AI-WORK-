/**
 * @vitest-environment jsdom
 *
 * Tests for the Login page component.
 *
 * Auth behavior (post-PR #86):
 *   - Login.tsx calls useAuth().login(email, password) first.
 *   - If login resolves → navigates to /dashboard.
 *   - If login rejects with a network error → falls back to Demo Mode
 *     (writes fake token to localStorage, navigates to /dashboard).
 *   - If login rejects with a real auth error (e.g. "Invalid credentials")
 *     → shows the error message in a red banner and does NOT navigate.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import Login from '../Login'
import { AuthProvider } from '../../hooks/useAuth'

// ── Mocks ──────────────────────────────────────────────────────────────────────

const mockLogin = vi.fn()

vi.mock('../../hooks/useAuth', async () => {
  const actual = await vi.importActual<typeof import('../../hooks/useAuth')>('../../hooks/useAuth')
  return {
    ...actual,
    useAuth: () => ({
      user: null,
      isAuthenticated: false,
      isLoading: false,
      login: mockLogin,
      logout: vi.fn(),
      register: vi.fn(),
      refreshToken: vi.fn(),
    }),
  }
})

// Capture navigation
const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

// Mock fetch for AuthProvider (returns 401 so it doesn't crash on mount)
const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

// ── Helpers ────────────────────────────────────────────────────────────────────

function renderLogin() {
  return render(
    <MemoryRouter>
      <AuthProvider>
        <Login />
      </AuthProvider>
    </MemoryRouter>
  )
}

// ── Tests ──────────────────────────────────────────────────────────────────────

describe('Login', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useRealTimers()
    mockFetch.mockResolvedValue({
      ok: false,
      json: () => Promise.resolve({ detail: 'Not authenticated' }),
    })
  })

  it('renders the login form with email and password fields', () => {
    renderLogin()
    expect(screen.getByLabelText(/Email/i)).toBeTruthy()
    expect(screen.getByPlaceholderText(/^•+$/)).toBeTruthy()
    expect(screen.getByRole('button', { name: /Sign in/i })).toBeTruthy()
  })

  it('renders the "Sign in to your engineering account" heading', () => {
    renderLogin()
    expect(screen.getByText(/Sign in to your engineering account/i)).toBeTruthy()
  })

  it('shows validation error when submitting empty required fields', async () => {
    // jsdom does not enforce HTML5 `required` validation, so the form submits
    // even with empty fields. We verify instead that Login.tsx's own guard
    // (`if (!email || !password) { notify('error', ...); return }`) fires
    // and blocks the call to useAuth().login.
    const user = userEvent.setup()
    renderLogin()

    const emailInput = screen.getByLabelText(/Email/i) as HTMLInputElement
    const passwordInput = screen.getByPlaceholderText(/^•+$/) as HTMLInputElement
    await user.clear(emailInput)
    await user.clear(passwordInput)
    // Both fields now empty — the handleSubmit guard should short-circuit.

    const submitBtn = screen.getByRole('button', { name: /Sign in/i })
    await user.click(submitBtn)

    // The component's own guard should have prevented the login call.
    expect(mockLogin).not.toHaveBeenCalled()
  })

  it('calls useAuth().login and navigates on successful backend auth', async () => {
    // Real backend auth path: login resolves, navigate to /dashboard.
    mockLogin.mockResolvedValue(undefined)
    const user = userEvent.setup()
    renderLogin()

    const emailInput = screen.getByLabelText(/Email/i) as HTMLInputElement
    const passwordInput = screen.getByPlaceholderText(/^•+$/) as HTMLInputElement
    await user.clear(emailInput)
    await user.clear(passwordInput)
    await user.type(emailInput, 'engineer@etap.com')
    await user.type(passwordInput, 'securePassword123')

    const submitBtn = screen.getByRole('button', { name: /Sign in/i })
    await user.click(submitBtn)

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith('engineer@etap.com', 'securePassword123')
    })
    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/dashboard')
    })
  })

  it('shows error message in red banner when backend rejects with auth error', async () => {
    // Real auth failure (401): backend returns "Invalid credentials".
    // Login should show the error message and NOT navigate.
    mockLogin.mockRejectedValue(new Error('Invalid credentials'))
    const user = userEvent.setup()
    renderLogin()

    const emailInput = screen.getByLabelText(/Email/i) as HTMLInputElement
    const passwordInput = screen.getByPlaceholderText(/^•+$/) as HTMLInputElement
    await user.clear(emailInput)
    await user.clear(passwordInput)
    await user.type(emailInput, 'bad@example.com')
    await user.type(passwordInput, 'wrongpassword')

    const submitBtn = screen.getByRole('button', { name: /Sign in/i })
    await user.click(submitBtn)

    // The error message should be visible in the alert banner
    await waitFor(() => {
      expect(screen.getByText('Invalid credentials')).toBeTruthy()
    })

    // Should NOT have navigated (real auth failure blocks the demo fallback)
    expect(mockNavigate).not.toHaveBeenCalled()
  })

  it('falls back to Demo Mode when backend is unreachable (network error)', async () => {
    // Network error path: login rejects with "Failed to fetch" → demo fallback.
    mockLogin.mockRejectedValue(new Error('Failed to fetch'))
    const user = userEvent.setup()
    renderLogin()

    const emailInput = screen.getByLabelText(/Email/i) as HTMLInputElement
    const passwordInput = screen.getByPlaceholderText(/^•+$/) as HTMLInputElement
    await user.clear(emailInput)
    await user.clear(passwordInput)
    await user.type(emailInput, 'test@example.com')
    await user.type(passwordInput, 'password123')

    const submitBtn = screen.getByRole('button', { name: /Sign in/i })
    await user.click(submitBtn)

    // Demo-mode fallback warning should be visible
    await waitFor(() => {
      expect(screen.getByText(/Backend unreachable/i)).toBeTruthy()
    })

    // A demo token should have been written to localStorage
    await waitFor(() => {
      expect(localStorage.getItem('authToken')).toMatch(/^demo-token-\d+$/)
    })

    // Should navigate to /dashboard (after the 1.2s demo-mode delay)
    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/dashboard')
    }, { timeout: 3000 })
  })

  it('shows loading state during login submission', async () => {
    // Make login hang so we can observe the loading state
    mockLogin.mockReturnValue(new Promise(() => {}))
    const user = userEvent.setup()
    renderLogin()

    const emailInput = screen.getByLabelText(/Email/i) as HTMLInputElement
    const passwordInput = screen.getByPlaceholderText(/^•+$/) as HTMLInputElement
    await user.clear(emailInput)
    await user.clear(passwordInput)
    await user.type(emailInput, 'test@etap.com')
    await user.type(passwordInput, 'password123')

    const submitBtn = screen.getByRole('button', { name: /Sign in/i })
    await user.click(submitBtn)

    await waitFor(() => {
      expect(screen.getByText('Signing in...')).toBeTruthy()
    })
  })

  it('has a link to the registration page', () => {
    renderLogin()
    const signUpLink = screen.getByText('Sign up')
    expect(signUpLink).toBeTruthy()
    expect(signUpLink.closest('a')?.getAttribute('href')).toBe('/register')
  })

  it('has proper input types for email and password', () => {
    renderLogin()
    const emailInput = screen.getByLabelText(/Email/i) as HTMLInputElement
    const passwordInput = screen.getByPlaceholderText(/^•+$/) as HTMLInputElement
    expect(emailInput.type).toBe('email')
    expect(passwordInput.type).toBe('password')
  })
})
