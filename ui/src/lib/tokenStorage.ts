/**
 * Secure Token Storage Utility
 * ============================
 * SECURITY FIX: Migrated from localStorage to sessionStorage.
 *
 * localStorage persists across browser sessions and tabs, making tokens
 * accessible to XSS attacks indefinitely. sessionStorage is scoped to
 * the current tab and cleared when the tab closes — significantly
 * reducing the attack window for token theft via XSS.
 *
 * For production, consider migrating to httpOnly cookies set by the
 * server, which are completely inaccessible to JavaScript.
 */

const TOKEN_KEY = "authToken";
const REFRESH_TOKEN_KEY = "refreshToken";

/**
 * Get the current auth token from sessionStorage.
 * Falls back to localStorage for migration (reads and clears the old value).
 */
export function getAuthToken(): string | null {
  // Priority: sessionStorage
  const sessionToken = sessionStorage.getItem(TOKEN_KEY);
  if (sessionToken) return sessionToken;

  // Migration: check localStorage for existing tokens
  const localToken = localStorage.getItem(TOKEN_KEY);
  if (localToken) {
    // Migrate to sessionStorage and clear localStorage
    sessionStorage.setItem(TOKEN_KEY, localToken);
    localStorage.removeItem(TOKEN_KEY);
    return localToken;
  }

  return null;
}

/**
 * Store the auth token in sessionStorage.
 */
export function setAuthToken(token: string): void {
  sessionStorage.setItem(TOKEN_KEY, token);
  // Ensure no stale token in localStorage
  localStorage.removeItem(TOKEN_KEY);
}

/**
 * Remove the auth token from all storage.
 */
export function removeAuthToken(): void {
  sessionStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(TOKEN_KEY);
}

/**
 * Get the refresh token from sessionStorage.
 */
export function getRefreshToken(): string | null {
  const sessionToken = sessionStorage.getItem(REFRESH_TOKEN_KEY);
  if (sessionToken) return sessionToken;

  // Migration
  const localToken = localStorage.getItem(REFRESH_TOKEN_KEY);
  if (localToken) {
    sessionStorage.setItem(REFRESH_TOKEN_KEY, localToken);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
    return localToken;
  }

  return null;
}

/**
 * Store the refresh token in sessionStorage.
 */
export function setRefreshToken(token: string): void {
  sessionStorage.setItem(REFRESH_TOKEN_KEY, token);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
}

/**
 * Remove the refresh token from all storage.
 */
export function removeRefreshToken(): void {
  sessionStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
}

/**
 * Clear all auth tokens (logout).
 */
export function clearAuthTokens(): void {
  removeAuthToken();
  removeRefreshToken();
}
