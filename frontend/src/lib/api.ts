import type {
  AssistantResponse,
  HealthResponse,
  Report,
} from './types';

/**
 * AccessPilot backend client.
 *
 * Default base URL is http://localhost:8000 (the backend dev server).
 * Override at build time with VITE_API_BASE_URL, e.g.:
 *   VITE_API_BASE_URL=http://localhost:8000 npm run build
 *
 * In dev, the Vite server also proxies /api -> http://localhost:8000
 * (see vite.config.ts), so you can alternatively call relative "/api/..."
 * URLs from the browser. This client uses the absolute base URL so it
 * works in dev, preview and production builds alike.
 */
const BASE_URL: string =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ??
  'http://localhost:8000';

export { BASE_URL };

/** Error with a decoded backend `detail` when available. */
export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

/**
 * Throw ApiError with a friendly message. Tries to decode a JSON error
 * body (FastAPI: {"detail": "..."}); falls back to the status text.
 */
async function toApiError(response: Response): Promise<ApiError> {
  let detail = '';
  try {
    const body: unknown = await response.json();
    if (body && typeof body === 'object') {
      const d = (body as { detail?: unknown }).detail;
      if (typeof d === 'string') detail = d;
      else if (d != null) detail = JSON.stringify(d);
    }
  } catch {
    // body was not JSON (e.g. HTML error page) — fall through.
  }
  const message = detail
    ? detail
    : `Request failed (HTTP ${response.status})`;
  return new ApiError(message, response.status);
}

async function getJson<T>(path: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`);
  } catch {
    throw new ApiError(
      `Could not reach the backend at ${BASE_URL}`,
      0,
    );
  }
  if (!response.ok) throw await toApiError(response);
  return (await response.json()) as T;
}

export const api = {
  /** GET /api/health */
  health(): Promise<HealthResponse> {
    return getJson<HealthResponse>('/api/health');
  },

  /** POST /api/analyze — multipart form, field name "file". */
  analyze(file: File): Promise<Report> {
    const form = new FormData();
    form.append('file', file);
    return new Promise<Report>((resolve, reject) => {
      fetch(`${BASE_URL}/api/analyze`, {
        method: 'POST',
        body: form,
      })
        .then(async (response) => {
          if (!response.ok) {
            reject(await toApiError(response));
            return;
          }
          resolve((await response.json()) as Report);
        })
        .catch((err) => {
          reject(
            new ApiError(
              `Could not reach the backend at ${BASE_URL}`,
              0,
            ),
          );
          void err;
        });
    });
  },

  /** GET /api/reports/{report_id} */
  getReport(reportId: string): Promise<Report> {
    return getJson<Report>(`/api/reports/${encodeURIComponent(reportId)}`);
  },

  /** POST /api/assistant — JSON {question, context}. */
  askAssistant(
    question: string,
    context: Record<string, unknown>,
  ): Promise<AssistantResponse> {
    return new Promise<AssistantResponse>((resolve, reject) => {
      fetch(`${BASE_URL}/api/assistant`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question, context }),
      })
        .then(async (response) => {
          if (!response.ok) {
            reject(await toApiError(response));
            return;
          }
          resolve((await response.json()) as AssistantResponse);
        })
        .catch(() => {
          reject(
            new ApiError(`Could not reach the backend at ${BASE_URL}`, 0),
          );
        });
    });
  },
};

/**
 * Trigger a browser download of a report artifact.
 * Uses fetch + object URL so the same code works when the backend is
 * same-origin (proxy) or cross-origin (direct URL).
 */
export async function downloadReport(
  reportId: string,
  format: 'json' | 'html',
): Promise<void> {
  const path = `/api/reports/${encodeURIComponent(reportId)}/download.${format}`;
  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`);
  } catch {
    throw new ApiError(
      `Could not reach the backend at ${BASE_URL}`,
      0,
    );
  }
  if (!response.ok) throw await toApiError(response);
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = `accesspilot-${reportId}.${format === 'json' ? 'json' : 'html'}`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
