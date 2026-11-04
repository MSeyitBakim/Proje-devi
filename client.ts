export interface FieldError {
  field: string;
  message: string;
}

export class ApiError extends Error {
  status: number;
  code: string;
  details: FieldError[];

  constructor(status: number, code: string, message: string, details: FieldError[] = []) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

type Query = Record<string, string | number | undefined | null>;
type Init = { method?: string; body?: unknown; query?: Query; signal?: AbortSignal };

export function buildUrl(baseUrl: string, path: string, query?: Query): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== undefined && value !== null && value !== '') params.set(key, String(value));
  }
  const qs = params.toString();
  return `${baseUrl.replace(/\/$/, '')}/api/v1${path}${qs ? `?${qs}` : ''}`;
}

export function createClient(fetchFn: typeof fetch, baseUrl = '') {
  return async function request<T>(path: string, init: Init = {}): Promise<T> {
    let response: Response;
    try {
      response = await fetchFn(buildUrl(baseUrl, path, init.query), {
        method: init.method ?? 'GET',
        headers: init.body === undefined ? undefined : { 'Content-Type': 'application/json' },
        body: init.body === undefined ? undefined : JSON.stringify(init.body),
        signal: init.signal
      });
    } catch (cause) {
      if (cause instanceof DOMException && cause.name === 'AbortError') throw cause;
      throw new ApiError(0, 'network_error', 'Could not reach the server. Check your connection.');
    }
    if (response.status === 204) return undefined as T;
    let payload: any = null;
    try {
      payload = await response.json();
    } catch {
      /* non-JSON body */
    }
    if (!response.ok) {
      const error = payload?.error;
      throw new ApiError(
        response.status,
        error?.code ?? 'http_error',
        error?.message ?? `Request failed (${response.status})`,
        error?.details ?? []
      );
    }
    return payload as T;
  };
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    const first = error.details[0];
    return first ? `${error.message}: ${first.field} – ${first.message}` : error.message;
  }
  return error instanceof Error ? error.message : 'Something went wrong';
}
