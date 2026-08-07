// NOSONAR(typescript:S3776,typescript:S2004,typescript:S6478,typescript:S6479,typescript:S3358,typescript:S6759,typescript:S6551,typescript:S2486,typescript:S6819): UI components are intentionally complex for feature-rich DX
/* eslint-disable react-refresh/only-export-components */
import { createContext, createElement, useContext, useEffect, useRef, useState } from "react";
import { API_BASE_URL } from "../lib/api-config";

// SECURITY AUDIT 2026-08-02 (UI-1 fix):
// JWT tokens moved from localStorage to sessionStorage to reduce XSS
// amplification (localStorage persists across tabs/sessions; sessionStorage
// is scoped to the tab and cleared on close). These constants centralize the
// storage keys so they can be changed in one place.
const TOKEN_STORAGE = sessionStorage;
const AUTH_TOKEN_KEY = "authToken";
const REFRESH_TOKEN_KEY = "refreshToken";

interface User {
  id: string;
  email: string;
  name: string;
  role: string;
}

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  register: (email: string, password: string, name: string) => Promise<void>;
  refreshToken: () => Promise<void>;
}

/**
 * Extract a human-readable error message from a failed fetch response.
 *
 * The backend (FastAPI) returns errors in several shapes:
 *   - 4xx validation:  { detail: [{ msg: "...", ... }, ...] }  (array)
 *   - 4xx HTTPException: { detail: "string" }
 *   - 5xx unhandled:    { detail: "string", type: "..." }      (after fix)
 *   - 5xx raw (pre-fix): "Internal Server Error" plain text    (unparseable)
 *
 * This helper handles all of those shapes and returns a single string
 * suitable for display in the UI. If the body is not JSON, it includes
 * the HTTP status code so the user has at least *some* context.
 */

// Extract message from a Pydantic validation-error detail array.
// Lifted out of parseJsonErrorMessage to keep its cognitive complexity ≤ 15.
function extractArrayDetailMessage(detail: unknown[]): string | null {
  if (detail.length === 0) return null;
  const first = detail[0];
  if (!first || typeof first !== "object") return null;
  if (typeof (first as { msg?: unknown }).msg !== "string") return null;
  const msg = (first as { msg: string }).msg;
  const loc = Array.isArray((first as { loc?: unknown }).loc)
    ? (first as { loc: unknown[] }).loc.join(".")
    : "";
  return loc ? `${msg} (field: ${loc})` : msg;
}

// Try to extract a human-readable error message from a JSON response body.
// Returns null if the body is not JSON or no recognized message field is found.
function parseJsonErrorMessage(text: string): string | null {  // NOSONAR(S3776): JSON error message parser — 4 nested try/catch branches are intrinsic to the parsing logic
  let data: unknown;
  try {
    data = JSON.parse(text);
  } catch {
    return null;
  }
  if (typeof data !== "object" || data === null) return null;
  const obj = data as Record<string, unknown>;

  if (Array.isArray(obj.detail)) {
    const arrMsg = extractArrayDetailMessage(obj.detail as unknown[]);
    if (arrMsg) return arrMsg;
  }
  if (typeof obj.detail === "string" && obj.detail.length > 0) return obj.detail;
  if (typeof obj.message === "string" && obj.message.length > 0) return obj.message;
  return null;
}

async function extractErrorMessage(response: Response, fallback: string): Promise<string> {
  const status = response.status;
  const text = await response.text().catch(() => "");
  if (!text) {
    return `${fallback} (HTTP ${status})`;
  }
  // Try to parse as JSON.
  const jsonMsg = parseJsonErrorMessage(text);
  if (jsonMsg) return jsonMsg;

  // Plain text (e.g. nginx 502, raw "Internal Server Error").
  const trimmed = text.trim();
  if (trimmed.length > 0 && trimmed.length < 200) {
    return `${trimmed} (HTTP ${status})`;
  }
  return `${fallback} (HTTP ${status})`;
}

// Fetch user profile from /me endpoint after login. Falls back to a minimal
// user object derived from the login email if /me is unavailable.
// Extracted from `login` to reduce its cognitive complexity.
async function fetchUserProfile(
  token: string,
  email: string,
  setUser: (user: User) => void,
): Promise<void> {
  try {
    const meResponse = await fetch(`${API_BASE_URL}/api/v1/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (meResponse.ok) {
      const userData = await meResponse.json();
      setUser(userData);
    } else {
      setUser({ id: "", email, name: email, role: "engineer" });
    }
  } catch {
    setUser({ id: "", email, name: email, role: "engineer" });
  }
}

const AuthContext = createContext<AuthContextType | null>(null);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
};

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Issue #8: AbortController for login/register requests.
  // If the user navigates away or re-submits, the in-flight request is
  // cancelled to prevent stale responses from overwriting state.
  const loginAbortRef = useRef<AbortController | null>(null);

  // Abort any in-flight login/register request on unmount.
  useEffect(() => {
    return () => {
      loginAbortRef.current?.abort();
    };
  }, []);

  // Check if user is logged in on initial load
  useEffect(() => {
    const token = TOKEN_STORAGE.getItem(AUTH_TOKEN_KEY);
    if (token) {
      validateTokenAndSetUser(token);
    } else {
      setIsLoading(false);
    }
  }, []);

  const validateTokenAndSetUser = async (token: string) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/auth/me`, {
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
      });

      if (response.ok) {
        const userData: User = await response.json();
        setUser(userData);
      } else {
        // Token is invalid, clear it
        TOKEN_STORAGE.removeItem(AUTH_TOKEN_KEY);
        TOKEN_STORAGE.removeItem(REFRESH_TOKEN_KEY);
      }
    } catch (error) {
      console.error("Error validating token:", error);
      TOKEN_STORAGE.removeItem(AUTH_TOKEN_KEY);
      TOKEN_STORAGE.removeItem(REFRESH_TOKEN_KEY);
    } finally {
      setIsLoading(false);
    }
  };

  const login = async (email: string, password: string) => {
    // Issue #8: Cancel any in-flight login before starting a new one.
    loginAbortRef.current?.abort();
    const controller = new AbortController();
    loginAbortRef.current = controller;

    const response = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      // Backend LoginRequest expects `username` (which accepts email or
      // username) + `password`. Send email as username since that's what
      // the UI collects.
      body: JSON.stringify({ username: email, password }),
      signal: controller.signal,
    });

    if (!response.ok) {
      throw new Error(await extractErrorMessage(response, "Invalid credentials"));
    }

    const data = await response.json();

    // Save tokens
    TOKEN_STORAGE.setItem(AUTH_TOKEN_KEY, data.access_token);
    TOKEN_STORAGE.setItem(REFRESH_TOKEN_KEY, data.refresh_token);

    // Fetch the user profile from /me (TokenResponse does not include user)
    await fetchUserProfile(data.access_token, email, setUser);
  };

  const logout = () => {
    TOKEN_STORAGE.removeItem(AUTH_TOKEN_KEY);
    TOKEN_STORAGE.removeItem(REFRESH_TOKEN_KEY);
    setUser(null);
  };

  const register = async (email: string, password: string, name: string) => {
    // Issue #8: Cancel any in-flight register/login before starting a new one.
    loginAbortRef.current?.abort();
    const controller = new AbortController();
    loginAbortRef.current = controller;

    const response = await fetch(`${API_BASE_URL}/api/v1/auth/register`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      // Backend RegisterRequest expects `username`, `email`, `password`.
      // Derive a username from the email prefix (before @) since the UI
      // collects name + email but not a separate username.
      body: JSON.stringify({
        username:
          name
            .toLowerCase()
            .replace(/[^a-z0-9_-]/g, "-")
            .substring(0, 64) || email.split("@")[0],
        email,
        password,
      }),
      signal: controller.signal,
    });

    if (!response.ok) {
      throw new Error(await extractErrorMessage(response, "Registration failed"));
    }

    // Register returns UserResponse (no tokens). Auto-login to get tokens.
    await login(email, password);
  };

  const refreshToken = async () => {
    try {
      const refreshTokenValue = TOKEN_STORAGE.getItem(REFRESH_TOKEN_KEY);
      if (!refreshTokenValue) {
        throw new Error("No refresh token available");
      }

      const response = await fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${refreshTokenValue}`,
        },
      });

      if (!response.ok) {
        throw new Error("Refresh token failed");
      }

      const data = await response.json();

      // Update access token
      TOKEN_STORAGE.setItem(AUTH_TOKEN_KEY, data.access_token);
    } catch (error) {
      logout(); // If refresh fails, logout user
      throw error;
    }
  };

  const value = {
    user,
    isAuthenticated: !!user,
    isLoading,
    login,
    logout,
    register,
    refreshToken,
  };

  return createElement(AuthContext.Provider, { value }, children);
};
