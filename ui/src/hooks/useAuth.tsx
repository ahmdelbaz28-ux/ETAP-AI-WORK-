/* eslint-disable react-refresh/only-export-components */
import { useState, useEffect, createContext, useContext, createElement } from 'react';
import { API_BASE_URL } from '../lib/api-config';

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

const AuthContext = createContext<AuthContextType | null>(null);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Check if user is logged in on initial load
  useEffect(() => {
    const token = localStorage.getItem('authToken');
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
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        const userData: User = await response.json();
        setUser(userData);
      } else {
        // Token is invalid, clear it
        localStorage.removeItem('authToken');
        localStorage.removeItem('refreshToken');
      }
    } catch (error) {
      console.error('Error validating token:', error);
      localStorage.removeItem('authToken');
      localStorage.removeItem('refreshToken');
    } finally {
      setIsLoading(false);
    }
  };

  const login = async (email: string, password: string) => {
    const response = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      // Backend LoginRequest expects `username` (which accepts email or
      // username) + `password`. Send email as username since that's what
      // the UI collects.
      body: JSON.stringify({ username: email, password }),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: 'Invalid credentials' }));
      throw new Error(errorData.detail || 'Invalid credentials');
    }

    const data = await response.json();

    // Save tokens
    localStorage.setItem('authToken', data.access_token);
    localStorage.setItem('refreshToken', data.refresh_token);

    // Set user
    setUser(data.user);
  };

  const logout = () => {
    localStorage.removeItem('authToken');
    localStorage.removeItem('refreshToken');
    setUser(null);
  };

  const register = async (email: string, password: string, name: string) => {
    const response = await fetch(`${API_BASE_URL}/api/v1/auth/register`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      // Backend RegisterRequest expects `username`, `email`, `password`.
      // Derive a username from the email prefix (before @) since the UI
      // collects name + email but not a separate username.
      body: JSON.stringify({
        username: name.toLowerCase().replace(/[^a-z0-9_-]/g, '-').substring(0, 64) || email.split('@')[0],
        email,
        password,
      }),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: 'Registration failed' }));
      throw new Error(errorData.detail || 'Registration failed');
    }

    const data = await response.json();

    // Save tokens
    localStorage.setItem('authToken', data.access_token);
    localStorage.setItem('refreshToken', data.refresh_token);

    // Set user
    setUser(data.user);
  };

  const refreshToken = async () => {
    try {
      const refreshToken = localStorage.getItem('refreshToken');
      if (!refreshToken) {
        throw new Error('No refresh token available');
      }

      const response = await fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${refreshToken}`,
        },
      });

      if (!response.ok) {
        throw new Error('Refresh token failed');
      }

      const data = await response.json();

      // Update access token
      localStorage.setItem('authToken', data.access_token);
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
