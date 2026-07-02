/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, useLocation } from 'react-router-dom'
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

// Mock fetch for AuthProvider
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
    mockFetch.mockResolvedValue({
      ok: false,
      json: () => Promise.resolve({ detail: 'Not authenticated' }),
    })
  })

  it('renders the login form with email and password fields', () => {
    renderLogin()
    expect(screen.getByLabelText(/Email/i)).toBeTruthy()
    expect(screen.getByLabelText(/Password/i)).toBeTruthy()
    expect(screen.getByRole('button', { name: /Sign in/i })).toBeTruthy()
  })

  it('renders the "Sign in to your account" heading', () => {
    renderLogin()
    expect(screen.getByText('Sign in to your account')).toBeTruthy()
  })

  it('shows validation error when submitting empty required fields', async () => {
    const user = userEvent.setup()
    renderLogin()

    // HTML5 required validation: clicking submit on empty form
    const submitBtn = screen.getByRole('button', { name: /Sign in/i })
    await user.click(submitBtn)

    // The form should not call login since fields are required
    expect(mockLogin).not.toHaveBeenCalled()
  })

  it('calls login and navigates on successful login', async () => {
    const user = userEvent.setup()
    mockLogin.mockResolvedValue(undefined)
    renderLogin()

    const emailInput = screen.getByLabelText(/Email/i)
    const passwordInput = screen.getByLabelText(/Password/i)

    await user.type(emailInput, 'engineer@etap.com')
    await user.type(passwordInput, 'securePassword123')

    const submitBtn = screen.getByRole('button', { name: /Sign in/i })
    await user.click(submitBtn)

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith('engineer@etap.com', 'securePassword123')
    })

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/', { replace: true })
    })
  })

  it('displays error message when login fails', async () => {
    const user = userEvent.setup()
    mockLogin.mockRejectedValue(new Error('Invalid credentials'))
    renderLogin()

    const emailInput = screen.getByLabelText(/Email/i)
    const passwordInput = screen.getByLabelText(/Password/i)

    await user.type(emailInput, 'bad@example.com')
    await user.type(passwordInput, 'wrongpassword')

    const submitBtn = screen.getByRole('button', { name: /Sign in/i })
    await user.click(submitBtn)

    await waitFor(() => {
      expect(screen.getByText('Invalid credentials')).toBeTruthy()
    })
  })

  it('shows loading state during login submission', async () => {
    const user = userEvent.setup()
    // Make login hang so we can observe the loading state
    mockLogin.mockReturnValue(new Promise(() => {}))
    renderLogin()

    const emailInput = screen.getByLabelText(/Email/i)
    const passwordInput = screen.getByLabelText(/Password/i)

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
    const passwordInput = screen.getByLabelText(/Password/i) as HTMLInputElement
    expect(emailInput.type).toBe('email')
    expect(passwordInput.type).toBe('password')
  })
})
