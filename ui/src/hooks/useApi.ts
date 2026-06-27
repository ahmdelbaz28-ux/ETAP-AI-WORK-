/* eslint-disable @typescript-eslint/no-explicit-any */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Define types for API responses
interface ApiResponse<T> {
  data: T;
  error?: string;
  success: boolean;
}

// Custom error type
interface ApiError {
  status: number;
  message: string;
}

// Generic API client with error handling and retries
const apiClient = {
  get: async <T>(endpoint: string): Promise<T> => {
    const token = localStorage.getItem('authToken');
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
    };
    
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      headers,
      signal: AbortSignal.timeout(30000),
    });

    if (!response.ok) {
      const errorText = await response.text().catch(() => 'Unknown error');
      const error: ApiError = {
        status: response.status,
        message: `API ${response.status}: ${errorText}`
      };
      throw error;
    }

    return response.json();
  },

  post: async <T, U = unknown>(endpoint: string, data?: U): Promise<T> => {
    const token = localStorage.getItem('authToken');
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
    };
    
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      method: 'POST',
      headers,
      body: data ? JSON.stringify(data) : undefined,
      signal: AbortSignal.timeout(60000), // Longer timeout for POST requests
    });

    if (!response.ok) {
      const errorText = await response.text().catch(() => 'Unknown error');
      const error: ApiError = {
        status: response.status,
        message: `API ${response.status}: ${errorText}`
      };
      throw error;
    }

    return response.json();
  },

  put: async <T, U = unknown>(endpoint: string, data?: U): Promise<T> => {
    const token = localStorage.getItem('authToken');
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
    };
    
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      method: 'PUT',
      headers,
      body: data ? JSON.stringify(data) : undefined,
      signal: AbortSignal.timeout(30000),
    });

    if (!response.ok) {
      const errorText = await response.text().catch(() => 'Unknown error');
      const error: ApiError = {
        status: response.status,
        message: `API ${response.status}: ${errorText}`
      };
      throw error;
    }

    return response.json();
  },

  delete: async <T>(endpoint: string): Promise<T> => {
    const token = localStorage.getItem('authToken');
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
    };
    
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      method: 'DELETE',
      headers,
      signal: AbortSignal.timeout(30000),
    });

    if (!response.ok) {
      const errorText = await response.text().catch(() => 'Unknown error');
      const error: ApiError = {
        status: response.status,
        message: `API ${response.status}: ${errorText}`
      };
      throw error;
    }

    return response.json();
  },
};

// Custom hook for API calls
export const useApi = () => {
  const queryClient = useQueryClient();

  // Generic GET query hook
  const useGet = <T>(
    queryKey: string[],
    endpoint: string,
    options: any = {}
  ) => {
    return useQuery<T, Error>({
      queryKey,
      queryFn: () => apiClient.get<T>(endpoint),
      retry: 2,
      staleTime: 5 * 60 * 1000, // 5 minutes
      ...options,
    });
  };

  // Generic POST mutation hook
  const usePost = <T, U = unknown>(
    mutationKey: string[],
    endpoint: string,
    options: any = {}
  ) => {
    return useMutation<ApiResponse<T>, { status: number; message: string }, U>({
      mutationKey,
      mutationFn: (data: U) => apiClient.post<T, U>(endpoint, data),
      onSuccess: () => {
        // Invalidate related queries to refresh data
        queryClient.invalidateQueries({ queryKey: mutationKey });
      },
      ...options,
    });
  };

  // Generic PUT mutation hook
  const usePut = <T, U = unknown>(
    mutationKey: string[],
    endpoint: string,
    options: any = {}
  ) => {
    return useMutation<ApiResponse<T>, { status: number; message: string }, U>({
      mutationKey,
      mutationFn: (data: U) => apiClient.put<T, U>(endpoint, data),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: mutationKey });
      },
      ...options,
    });
  };

  // Generic DELETE mutation hook
  const useDelete = <T>(
    mutationKey: string[],
    endpoint: string,
    options: any = {}
  ) => {
    return useMutation<ApiResponse<T>, { status: number; message: string }, void>({
      mutationKey,
      mutationFn: () => apiClient.delete<T>(endpoint),
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: mutationKey });
      },
      ...options,
    });
  };

  // Specific hooks for common API endpoints
  const useHealth = (options: any = {}) => {
    return useGet<any>(['health'], '/health', {
      refetchInterval: 30000, // Refetch every 30 seconds
      ...options,
    });
  };

  const useAgents = (options: any = {}) => {
    return useGet<any[]>(['agents'], '/api/v1/agents', {
      staleTime: 2 * 60 * 1000, // 2 minutes
      ...options,
    });
  };

  const useStudies = (options: any = {}) => {
    return useGet<any[]>(['studies'], '/api/v1/studies', {
      staleTime: 1 * 60 * 1000, // 1 minute
      ...options,
    });
  };

  const useRunStudy = (options: any = {}) => {
    return usePost<any, any>(['run-study'], '/api/v1/studies/run', {
      retry: 1,
      ...options,
    });
  };

  const useValidateSystem = (options: any = {}) => {
    return usePost<any, any>(['validate-system'], '/api/v1/system/validate', {
      ...options,
    });
  };

  const useChatWithAgent = (options: any = {}) => {
    return usePost<any, { agentId: string; message: string }>(['chat'], '/api/v1/agents/chat', {
      ...options,
    });
  };

  const useMetrics = (options: any = {}) => {
    return useGet<any>(['metrics'], '/metrics', {
      staleTime: 10000, // 10 seconds
      ...options,
    });
  };

  const useAuditLogs = (options: any = {}) => {
    return useGet<any[]>(['audit-logs'], '/api/v1/audit', {
      staleTime: 30000, // 30 seconds
      ...options,
    });
  };

  // Guard-specific hooks
  const useGuardReview = (options: any = {}) => {
    return usePost<any, { source: string; guard_type: string; language: string }>(['guard-review'], '/api/v1/guards/review', {
      retry: 0, // Don't retry guard reviews as they can be expensive
      ...options,
    });
  };

  const useGuardInfo = (options: any = {}) => {
    return useGet<any>(['guard-info'], '/api/v1/guards/info', {
      staleTime: 5 * 60 * 1000, // 5 minutes
      ...options,
    });
  };

  return {
    // Generic hooks
    useGet,
    usePost,
    usePut,
    useDelete,
    
    // Specific API hooks
    useHealth,
    useAgents,
    useStudies,
    useRunStudy,
    useValidateSystem,
    useChatWithAgent,
    useMetrics,
    useAuditLogs,
    useGuardReview,
    useGuardInfo,
    
    // Direct API access
    apiClient,
  };
};