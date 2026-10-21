
export const API_BASE_URL = (import.meta.env.VITE_API_URL || '/api').replace(/\/$/, '');
const configuredTimeout = Number(import.meta.env.VITE_API_TIMEOUT_MS || 30_000);
const API_TIMEOUT_MS = Number.isInteger(configuredTimeout) && configuredTimeout >= 1_000 && configuredTimeout <= 120_000
  ? configuredTimeout : 30_000;

export async function boundedFetch(url: string, options: RequestInit = {}): Promise<Response> {
  const timeout = AbortSignal.timeout(API_TIMEOUT_MS);
  const signal = options.signal ? AbortSignal.any([options.signal, timeout]) : timeout;
  try {
    return await fetch(url, { ...options, signal, cache: 'no-store' });
  } catch (error) {
    if (timeout.aborted) throw new ApiError(408, 'The request timed out. Please try again.');
    throw error;
  }
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

/**
 * A wrapper around fetch that attaches the Clerk session token.
 * Use this inside a React component context where `getToken` from `useAuth()` is available.
 */
export async function authenticatedFetch(
  url: string,
  options: RequestInit = {},
  getToken: (options?: { skipCache?: boolean }) => Promise<string | null>
) {
  const isE2EMock = Boolean(import.meta.env.DEV && typeof window !== 'undefined' && window.__E2E_ROLE__);
  const token = isE2EMock
    ? window.__E2E_TOKEN__ || 'e2e-mock-token'
    : await getToken();
  
  const headers = new Headers(options.headers);
  if (!token) throw new ApiError(401, 'Your session has ended. Please sign in again.');
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }
  
  headers.delete('X-Argus-Role');

  // Default to JSON if not explicitly set
  if (!headers.has('Content-Type') && options.body && typeof options.body === 'string') {
    headers.set('Content-Type', 'application/json');
  }

  let response = await boundedFetch(`${API_BASE_URL}${url}`, {
    ...options,
    headers
  });

  // A cached session token may expire between UI actions.
  // Refresh once on authorization failure, then surface the server response.
  if (response.status === 401 && !isE2EMock) {
    const freshToken = await getToken({ skipCache: true });
    if (freshToken && freshToken !== token) {
      const retryHeaders = new Headers(headers);
      retryHeaders.set('Authorization', `Bearer ${freshToken}`);
      response = await boundedFetch(`${API_BASE_URL}${url}`, {
        ...options,
        headers: retryHeaders,
      });
    }
  }

  return response;
}

export async function fetchWithAuth(
  url: string,
  options: RequestInit = {},
  getToken: (options?: { skipCache?: boolean }) => Promise<string | null>
) {
  const response = await authenticatedFetch(url, options, getToken);

  if (!response.ok) {
    let errorDetail = 'An unexpected API error occurred';
    try {
      const errorData: unknown = await response.json();
      const detail = isRecord(errorData) ? errorData.detail : undefined;
      if (typeof detail === 'string') {
        errorDetail = detail;
      } else if (Array.isArray(detail)) {
        errorDetail = detail.map((item) =>
          isRecord(item) && typeof item.msg === 'string' ? item.msg : JSON.stringify(item),
        ).join('; ');
      } else if (detail) {
        errorDetail = JSON.stringify(detail);
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
