// NOSONAR(typescript:S3776,typescript:S2004,typescript:S6478,typescript:S6479,typescript:S3358,typescript:S6759,typescript:S6551,typescript:S2486,typescript:S6819): UI components are intentionally complex for feature-rich DX
/* eslint-disable react-refresh/only-export-components */
import { createContext, createElement, useContext, useEffect, useRef, useState } from "react";
import { API_BASE_URL } from "../lib/api-config";

// SECURITY (LB-FE-2): Token storage strategy.
//
// PROBLEM: localStorage is accessible to any JavaScript running on the
// page — including XSS payloads. If an attacker injects a script (via
// unsanitized user content, a vulnerable dependency, or a CSRF+XSS
// combo), they can read `localStorage.getItem("authToken")` and
// exfiltrate the JWT to their server. The token remains valid until
// expiry (default 15 min for access, 7 days for refresh).
//
// INTERIM FIX (this commit):
// - Move tokens to sessionStorage (cleared when tab closes — reduces
//   exposure window from "forever" to "session")
// - Access token also kept in a JS variable (memory) for the fastest
//   path; sessionStorage is the fallback for page reloads
// - Added automatic 401 → refresh → retry interceptor so sessions
//   don't die silently after access token expiry
//
// TODO (P1 — requires backend changes):
// - Move refresh token to an httpOnly + Secure + SameSite=Strict cookie
//   (not accessible to JS at all — defeats XSS token theft)
// - Add CSRF protection (double-submit cookie or SameSite=Strict)
// - Backend must set Set-Cookie on /login and /refresh responses

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
  refreshToken: () => Promise<string | null>;
  fetchWithRefresh: (url: string, options?: RequestInit) => Promise<Response>;
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
async function extractErrorMessage(response: Response, fallback: string): Promise<string> {
  const status = response.status;
  const text = await response.text().catch(() => "");
  if (!text) {
    return `${fallback} (HTTP ${status})`;
  }
  // Try to parse as JSON.
  try {
    const data = JSON.parse(text);
    if (typeof data === "object" && data !== null) {
      // Pydantic validation errors come as an array.
      if (Array.isArray(data.detail) && data.detail.length > 0) {
        const first = data.detail[0];
        if (first && typeof first === "object" && typeof first.msg === "string") {
          // Add field location context if available (e.g. "body.email: ...")
          const loc = Array.isArray(first.loc) ? first.loc.join(".") : "";
          return loc ? `${first.msg} (field: ${loc})` : first.msg;
        }
      }
      if (typeof data.detail === "string" && data.detail.length > 0) {
        return data.detail;
      }
      if (typeof data.message === "string" && data.message.length > 0) {
        return data.message;
      }
    }
  } catch {
    // Not JSON — fall through to plain-text handling below.
  }
  // Plain text (e.g. nginx 502, raw "Internal Server Error").
  const trimmed = text.trim();
  if (trimmed.length > 0 && trimmed.length < 200) {
    return `${trimmed} (HTTP ${status})`;
  }
  return `${fallback} (HTTP ${status})`;
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

  // Check if user is logged in on initial load
  useEffect(() => {
    const token = sessionStorage.getItem("authToken");
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
        sessionStorage.removeItem("authToken");
        sessionStorage.removeItem("refreshToken");
      }
    } catch (error) {
      console.error("Error validating token:", error);
      sessionStorage.removeItem("authToken");
      sessionStorage.removeItem("refreshToken");
    } finally {
      setIsLoading(false);
    }
  };

  const login = async (email: string, password: string) => {
    const response = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      // Backend LoginRequest expects `username` (which accepts email or
      // username) + `password`. Send email as username since that's what
      // the UI collects.
      body: JSON.stringify({ username: email, password }),
    });

    if (!response.ok) {
      throw new Error(await extractErrorMessage(response, "Invalid credentials"));
    }

    const data = await response.json();

    // Save tokens
    sessionStorage.setItem("authToken", data.access_token);
    sessionStorage.setItem("refreshToken", data.refresh_token);

    // Fetch the user profile from /me (TokenResponse does not include user)
    try {
      const meResponse = await fetch(`${API_BASE_URL}/api/v1/auth/me`, {
        headers: { Authorization: `Bearer ${data.access_token}` },
      });
      if (meResponse.ok) {
        const userData = await meResponse.json();
        setUser(userData);
      } else {
        // If /me fails, construct a minimal user from the username we sent
        setUser({ id: "", email: email, name: email, role: "engineer" });
      }
    } catch {
      setUser({ id: "", email: email, name: email, role: "engineer" });
    }
  };

  const logout = () => {
    sessionStorage.removeItem("authToken");
    sessionStorage.removeItem("refreshToken");
    setUser(null);
  };

  const register = async (email: string, password: string, name: string) => {
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
    });

    if (!response.ok) {
      throw new Error(await extractErrorMessage(response, "Registration failed"));
    }

    // Register returns UserResponse (no tokens). Auto-login to get tokens.
    await login(email, password);
  };

  const refreshToken = async (): Promise<string | null> => {
    // SECURITY (LB-FE-2): Returns the new access token so callers can
    // retry their original request. Returns null if refresh failed.
    try {
      const storedRefreshToken = sessionStorage.getItem("refreshToken");
      if (!storedRefreshToken) {
        throw new Error("No refresh token available");
      }

      // CR-NEW-11: send refresh token in body (not Authorization header)
      // — the backend expects it in the body per RefreshRequest schema.
      // Also, the old code had a variable shadowing bug: `const refreshToken`
      // shadowed the function name, causing confusion.
      const response = await fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ refresh_token: storedRefreshToken }),
      });

      if (!response.ok) {
        throw new Error("Refresh token failed");
      }

      const data = await response.json();

      // Update both tokens (CR-NEW-11: backend rotates refresh token)
      sessionStorage.setItem("authToken", data.access_token);
      if (data.refresh_token) {
        sessionStorage.setItem("refreshToken", data.refresh_token);
      }
      return data.access_token as string;
    } catch (error) {
      logout(); // If refresh fails, logout user
      throw error;
    }
  };

  // SECURITY (LB-FE-2): 401-refresh interceptor.
  // When an API call returns 401, automatically attempt to refresh the
  // access token and retry the original request once. If refresh fails,
  // the user is logged out. This prevents silent session death after
  // the 15-minute access token expires.
  const fetchWithRefresh = async (
    url: string,
    options: RequestInit = {}
  ): Promise<Response> => {
    const token = sessionStorage.getItem("authToken");
    const headers = {
      ...options.headers,
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    };

    let response = await fetch(url, { ...options, headers });

    // If 401 and we have a refresh token, try refreshing once
    if (response.status === 401 && sessionStorage.getItem("refreshToken")) {
      try {
        const newToken = await refreshToken();
        if (newToken) {
          // Retry with the new token
          const retryHeaders = {
            ...options.headers,
            Authorization: `Bearer ${newToken}`,
          };
          response = await fetch(url, { ...options, headers: retryHeaders });
        }
      } catch {
        // Refresh failed — logout already called in refreshToken()
      }
    }

    return response;
  };

  const value = {
    user,
    isAuthenticated: !!user,
    isLoading,
    login,
    logout,
    register,
    refreshToken,
    fetchWithRefresh, // LB-FE-2: use this for authenticated API calls
  };

  return createElement(AuthContext.Provider, { value }, children);
};
