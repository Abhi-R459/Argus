export const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

/**
 * A wrapper around fetch that attaches the Clerk JWT token.
 * Use this inside a React component context where `getToken` from `useAuth()` is available.
 */
export async function fetchWithAuth(
  url: string,
  options: RequestInit = {},
  getToken: () => Promise<string | null>
) {
  let token = null;
  if (import.meta.env.DEV && typeof window !== 'undefined' && (window as any).__E2E_ROLE__) {
    token = (window as any).__E2E_TOKEN__ || 'e2e-mock-token';
  } else {
    token = await getToken();
  }
  
  const headers = new Headers(options.headers);
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }
  
  // Default to JSON if not explicitly set
  if (!headers.has('Content-Type') && options.body && typeof options.body === 'string') {
    headers.set('Content-Type', 'application/json');
  }

  const response = await fetch(`${API_BASE_URL}${url}`, {
    ...options,
    headers
  });

  if (!response.ok) {
    let errorDetail = 'An unexpected API error occurred';
    try {
      const errorData = await response.json();
      if (typeof errorData.detail === 'string') {
        errorDetail = errorData.detail;
      } else if (Array.isArray(errorData.detail)) {
        errorDetail = errorData.detail.map((d: any) => d.msg || JSON.stringify(d)).join('; ');
      } else if (errorData.detail) {
        errorDetail = JSON.stringify(errorData.detail);
      }
    } catch {
      // Ignore JSON parse errors for non-JSON error responses
    }
    throw new ApiError(response.status, errorDetail);
  }

  if (response.status === 204) {
    return null;
  }
  
  return response.json();
}
