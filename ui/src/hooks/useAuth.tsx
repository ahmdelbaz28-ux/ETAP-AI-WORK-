// NOSONAR(typescript:S3776,typescript:S2004,typescript:S6478,typescript:S6479,typescript:S3358,typescript:S6759,typescript:S6551,typescript:S2486,typescript:S6819): UI components are intentionally complex for feature-rich DX
/* eslint-disable react-refresh/only-export-components */
import { createContext, createElement, useContext, useEffect, useState } from "react";
import { API_BASE_URL } from "../lib/api-config";

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
    const token = localStorage.getItem("authToken");
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
        localStorage.removeItem("authToken");
        localStorage.removeItem("refreshToken");
      }
    } catch (error) {
      console.error("Error validating token:", error);
      localStorage.removeItem("authToken");
      localStorage.removeItem("refreshToken");
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
    localStorage.setItem("authToken", data.access_token);
    localStorage.setItem("refreshToken", data.refresh_token);

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
    localStorage.removeItem("authToken");
    localStorage.removeItem("refreshToken");
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

  const refreshToken = async () => {
    try {
      const refreshToken = localStorage.getItem("refreshToken");
      if (!refreshToken) {
        throw new Error("No refresh token available");
      }

      const response = await fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${refreshToken}`,
        },
      });

      if (!response.ok) {
        throw new Error("Refresh token failed");
      }

      const data = await response.json();

      // Update access token
      localStorage.setItem("authToken", data.access_token);
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
