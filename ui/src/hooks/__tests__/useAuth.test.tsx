/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'
import { createElement } from 'react'
import { AuthProvider, useAuth } from '../../hooks/useAuth'

// ── Mocks ──────────────────────────────────────────────────────────────────────

const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

// ── Helpers ────────────────────────────────────────────────────────────────────

function createWrapper() {
  return ({ children }: { children: React.ReactNode }) =>
    createElement(AuthProvider, null, children)
}

// ── Tests ──────────────────────────────────────────────────────────────────────

describe('useAuth', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    // Default: no token, so no validate call needed
    mockFetch.mockResolvedValue({
      ok: false,
      json: () => Promise.resolve({ detail: 'Not authenticated' }),
    })
  })

  it('throws error when useAuth is used outside AuthProvider', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {})
    expect(() => {
      renderHook(() => useAuth())
    }).toThrow('useAuth must be used within an AuthProvider')
    spy.mockRestore()
  })

  it('starts with no user and not authenticated after loading', async () => {
    const { result } = renderHook(() => useAuth(), { wrapper: createWrapper() })

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    expect(result.current.user).toBeNull()
    expect(result.current.isAuthenticated).toBe(false)
  })

  it('performs login and sets user with tokens', async () => {
    const mockUser = { id: '1', email: 'engineer@etap.com', name: 'Engineer', role: 'admin' }
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({
        access_token: 'test-access-token',
        refresh_token: 'test-refresh-token',
        user: mockUser,
      }),
    })

    const { result } = renderHook(() => useAuth(), { wrapper: createWrapper() })

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    await act(async () => {
      await result.current.login('engineer@etap.com', 'password123')
    })

    expect(mockFetch).toHaveBeenCalledWith('https://ahmdelbaz28-ahmedetap-platform.hf.space/api/v1/auth/login', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ email: 'engineer@etap.com', password: 'password123' }),
    }))

    expect(localStorage.getItem('authToken')).toBe('test-access-token')
    expect(localStorage.getItem('refreshToken')).toBe('test-refresh-token')
    expect(result.current.user).toEqual(mockUser)
    expect(result.current.isAuthenticated).toBe(true)
  })

  it('throws error on failed login', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      json: () => Promise.resolve({ detail: 'Invalid credentials' }),
    })

    const { result } = renderHook(() => useAuth(), { wrapper: createWrapper() })

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    await expect(
      act(async () => {
        await result.current.login('bad@example.com', 'wrong')
      })
    ).rejects.toThrow('Invalid credentials')

    expect(result.current.user).toBeNull()
    expect(result.current.isAuthenticated).toBe(false)
  })

  it('clears user and tokens on logout', async () => {
    const mockUser = { id: '1', email: 'engineer@etap.com', name: 'Engineer', role: 'admin' }
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({
        access_token: 'test-access-token',
        refresh_token: 'test-refresh-token',
        user: mockUser,
      }),
    })

    const { result } = renderHook(() => useAuth(), { wrapper: createWrapper() })

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    await act(async () => {
      await result.current.login('engineer@etap.com', 'password123')
    })

    expect(result.current.isAuthenticated).toBe(true)

    act(() => {
      result.current.logout()
    })

    expect(result.current.user).toBeNull()
    expect(result.current.isAuthenticated).toBe(false)
    expect(localStorage.getItem('authToken')).toBeNull()
    expect(localStorage.getItem('refreshToken')).toBeNull()
  })

  it('validates existing token on mount and sets user', async () => {
    localStorage.setItem('authToken', 'existing-token')
    const mockUser = { id: '2', email: 'existing@etap.com', name: 'Existing User', role: 'user' }
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockUser),
    })

    const { result } = renderHook(() => useAuth(), { wrapper: createWrapper() })

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    expect(mockFetch).toHaveBeenCalledWith('https://ahmdelbaz28-ahmedetap-platform.hf.space/api/v1/auth/me', expect.objectContaining({
      headers: expect.objectContaining({
        Authorization: 'Bearer existing-token',
      }),
    }))

    expect(result.current.user).toEqual(mockUser)
    expect(result.current.isAuthenticated).toBe(true)
  })

  it('removes invalid token on mount', async () => {
    localStorage.setItem('authToken', 'invalid-token')
    mockFetch.mockResolvedValueOnce({
      ok: false,
      json: () => Promise.resolve({ detail: 'Token expired' }),
    })

    const { result } = renderHook(() => useAuth(), { wrapper: createWrapper() })

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    expect(localStorage.getItem('authToken')).toBeNull()
    expect(result.current.user).toBeNull()
    expect(result.current.isAuthenticated).toBe(false)
  })

  it('refreshes token successfully', async () => {
    localStorage.setItem('refreshToken', 'old-refresh-token')
    const { result } = renderHook(() => useAuth(), { wrapper: createWrapper() })

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ access_token: 'new-access-token' }),
    })

    await act(async () => {
      await result.current.refreshToken()
    })

    expect(mockFetch).toHaveBeenCalledWith('https://ahmdelbaz28-ahmedetap-platform.hf.space/api/v1/auth/refresh', expect.objectContaining({
      method: 'POST',
      headers: expect.objectContaining({
        Authorization: 'Bearer old-refresh-token',
      }),
    }))

    expect(localStorage.getItem('authToken')).toBe('new-access-token')
  })

  it('logs out when refresh token fails', async () => {
    localStorage.setItem('authToken', 'old-token')
    localStorage.setItem('refreshToken', 'expired-refresh-token')

    // Mount validation succeeds
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ id: '1', email: 'user@etap.com', name: 'User', role: 'user' }),
    })

    const { result } = renderHook(() => useAuth(), { wrapper: createWrapper() })

    await waitFor(() => {
      expect(result.current.isAuthenticated).toBe(true)
    })

    // Refresh fails - mock non-ok response
    mockFetch.mockResolvedValueOnce({
      ok: false,
      json: () => Promise.resolve({}),
    })

    // Call refreshToken and catch the error
    // QUALITY v2.1.1: typed refreshError as Error | undefined and used non-null
    // assertion in expect() to satisfy strict mode's control-flow narrowing.
    let refreshError: Error | undefined
    await act(async () => {
      try {
        await result.current.refreshToken()
        refreshError = undefined
      } catch (e: unknown) {
        refreshError = e instanceof Error ? e : new Error(String(e))
      }
    })

    expect(refreshError!.message).toBe('Refresh token failed')

    // After refresh failure, logout is called which clears user
    expect(result.current.user).toBeNull()
    expect(result.current.isAuthenticated).toBe(false)
  })
})
