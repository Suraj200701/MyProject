/**
 * The single HTTP entry point to the backend.
 *
 * Every API module goes through `apiFetch`, which owns:
 *   * base-URL resolution
 *   * `Authorization: Bearer` injection
 *   * refresh-on-401, single-flighted so a page issuing eight parallel queries
 *     performs one refresh rather than eight
 *   * turning the backend's `{success, message, errors}` envelope into a typed
 *     `ApiError` that UI code can render directly
 *
 * Nothing else in the app should call `fetch` against the backend.
 */

import type { ApiErrorBody, TokenResponse, ValidationErrorDetail } from "@/lib/api/types";
import {
  clearTokens,
  getAccessToken,
  getActiveOrganizationId,
  getRefreshToken,
  setTokens,
  whenSessionBootstrapped,
} from "@/lib/api/tokens";

/**
 * Inlined into the client bundle at BUILD time, so its value is fixed when the
 * image is built and cannot be changed by the running container.
 *
 * Read into a named constant because unset and set-to-empty mean different
 * things here — see `API_ORIGIN`.
 */
const CONFIGURED_ORIGIN = process.env.NEXT_PUBLIC_API_BASE_URL;

/**
 * Backend ORIGIN, with any accidental `/api/v1` suffix and trailing slash
 * stripped. The versioned prefix is added by `API_PREFIX` below — a base that
 * already contained it would produce `/api/v1/api/v1/...` and 404 on every
 * request. (That exact mistake shipped in the generated Postman collection, so
 * it is defended against here rather than left to configuration discipline.)
 *
 * An *explicitly empty* value means same-origin: requests go to `/api/v1/...`
 * relative to whatever host served the page. That is what production uses — the
 * reverse proxy serves the app and the API on one origin, so the build needs no
 * CORS and no rebuild per domain, and one image deploys to any hostname.
 *
 * Hence the explicit `undefined` check rather than `||`: unset (local dev with
 * no `.env.local`) and set-to-empty (production, same origin) are different
 * intentions, and `||` collapsed the second into the first — which would have
 * pointed every deployed browser at port 8000 on its own machine.
 */
export const API_ORIGIN = (
  CONFIGURED_ORIGIN === undefined ? "http://localhost:8000" : CONFIGURED_ORIGIN
)
  .replace(/\/+$/, "")
  .replace(/\/api\/v1$/, "");

export const API_PREFIX = "/api/v1";

/** Full URL for a versioned API path, e.g. `/leads` -> `http://host/api/v1/leads`. */
export function apiUrl(path: string): string {
  const suffix = path.startsWith("/") ? path : `/${path}`;
  return `${API_ORIGIN}${API_PREFIX}${suffix}`;
}

/**
 * Absolute URL for a path the API itself handed us (e.g. `ExportOut.download_url`),
 * which is already root-relative and already carries `/api/v1`.
 */
export function absoluteUrl(rootRelativePath: string): string {
  const suffix = rootRelativePath.startsWith("/") ? rootRelativePath : `/${rootRelativePath}`;
  return `${API_ORIGIN}${suffix}`;
}

// --- Errors ---------------------------------------------------------------

export class ApiError extends Error {
  readonly status: number;
  readonly errors: ValidationErrorDetail[] | null;

  constructor(status: number, message: string, errors: ValidationErrorDetail[] | null = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.errors = errors;
  }

  /** Session is gone or invalid — the caller should send the user to /login. */
  get isUnauthorized(): boolean {
    return this.status === 401;
  }

  /** Authenticated but not allowed (e.g. a Viewer trying to export). */
  get isForbidden(): boolean {
    return this.status === 403;
  }

  get isNotFound(): boolean {
    return this.status === 404;
  }

  /** Out of credits. The backend uses 402 specifically for this. */
  get isPaymentRequired(): boolean {
    return this.status === 402;
  }

  get isRateLimited(): boolean {
    return this.status === 429;
  }

  /** Network failure / backend unreachable, rather than an HTTP error response. */
  get isNetworkError(): boolean {
    return this.status === 0;
  }

  /**
   * First validation message, formatted for display next to a field.
   * Falls back to the envelope message when there is no field detail.
   */
  get fieldMessage(): string {
    const first = this.errors?.[0];
    if (!first) return this.message;
    // loc is like ["body", "email"]; the last segment is the field name.
    const field = first.loc.filter((p) => p !== "body").join(".");
    return field ? `${field}: ${first.msg}` : first.msg;
  }
}

// --- Refresh (single-flight) ---------------------------------------------

/**
 * In-flight refresh, shared by every request that 401s while it runs.
 * Without this, a dashboard mounting eight queries at once would fire eight
 * refreshes, and all but one would fail against a rotated refresh token.
 */
let refreshInFlight: Promise<boolean> | null = null;

async function refreshAccessToken(): Promise<boolean> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return false;

  try {
    const response = await fetch(apiUrl("/auth/refresh"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    if (!response.ok) {
      clearTokens();
      return false;
    }

    const pair = (await response.json()) as TokenResponse;
    if (!pair?.access_token) {
      clearTokens();
      return false;
    }
    // The backend rotates the refresh token, so store whatever came back.
    setTokens(pair.access_token, pair.refresh_token);
    return true;
  } catch {
    // Network failure: do NOT clear tokens. The session may still be valid and
    // the backend merely unreachable; wiping it would log the user out over a
    // dropped Wi-Fi packet.
    return false;
  }
}

function refreshOnce(): Promise<boolean> {
  if (!refreshInFlight) {
    refreshInFlight = refreshAccessToken().finally(() => {
      refreshInFlight = null;
    });
  }
  return refreshInFlight;
}

/** Called when a refresh fails, so the AuthProvider can redirect to /login. */
type SessionExpiredHandler = () => void;
let onSessionExpired: SessionExpiredHandler | null = null;

export function setSessionExpiredHandler(handler: SessionExpiredHandler | null): void {
  onSessionExpired = handler;
}

// --- Core request --------------------------------------------------------

/**
 * Values a query string can carry.
 *
 * Note that query-param bags must be declared as **type aliases**, not
 * interfaces: TypeScript only gives implicit index signatures to type aliases,
 * so an `interface LeadsQuery {...}` is not assignable to `QueryParams` while
 * `type LeadsQuery = {...}` is.
 */
export type QueryValue = string | number | boolean | null | undefined;
export type QueryParams = Record<string, QueryValue>;

export interface ApiFetchOptions extends Omit<RequestInit, "body"> {
  /** JSON-serialized automatically. Use `formData` for multipart instead. */
  body?: unknown;
  /** Sent as-is; the browser sets the multipart boundary. */
  formData?: FormData;
  /** Appended as a query string, skipping null/undefined/"" values. */
  query?: QueryParams;
  /** Skip auth entirely (login, signup, password reset). */
  anonymous?: boolean;
  /** Internal: prevents a refresh loop by only ever retrying once. */
  _isRetry?: boolean;
}

function buildQueryString(query: QueryParams | undefined): string {
  if (!query) return "";
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    // Empty strings are dropped: the leads endpoint treats "" and absent
    // differently for some filters, and absent is what "no filter" means.
    if (value === null || value === undefined || value === "") continue;
    params.append(key, String(value));
  }
  const encoded = params.toString();
  return encoded ? `?${encoded}` : "";
}

export async function apiFetch<T>(path: string, options: ApiFetchOptions = {}): Promise<T> {
  const { body, formData, query, anonymous, _isRetry, headers, ...rest } = options;

  const requestHeaders = new Headers(headers);
  if (!formData && body !== undefined) {
    requestHeaders.set("Content-Type", "application/json");
  }

  if (!anonymous) {
    // Wait for the session to be established before reading the token. Without
    // this, a component that fetches on its first render can beat the OAuth
    // token out of the URL into storage, send an unauthenticated request, and
    // have the resulting 401 clear the session. Settles on the first tick.
    await whenSessionBootstrapped();

    const token = getAccessToken();
    if (token) requestHeaders.set("Authorization", `Bearer ${token}`);
    const organizationId = getActiveOrganizationId();
    if (organizationId) requestHeaders.set("X-Organization-Id", organizationId);
  }

  let response: Response;
  try {
    response = await fetch(`${apiUrl(path)}${buildQueryString(query)}`, {
      ...rest,
      headers: requestHeaders,
      body: formData ?? (body !== undefined ? JSON.stringify(body) : undefined),
    });
  } catch {
    throw new ApiError(
      0,
      "Cannot reach the server. Check that the backend is running and NEXT_PUBLIC_API_BASE_URL is correct.",
    );
  }

  // 401 -> try exactly one refresh, then replay the original request.
  if (response.status === 401 && !anonymous && !_isRetry) {
    const refreshed = await refreshOnce();
    if (refreshed) {
      return apiFetch<T>(path, { ...options, _isRetry: true });
    }
    clearTokens();
    onSessionExpired?.();
    throw new ApiError(401, "Your session has expired. Please sign in again.");
  }

  if (!response.ok) {
    throw await toApiError(response);
  }

  // 204 and empty bodies are legitimate (e.g. some DELETEs).
  if (response.status === 204) return undefined as T;
  const text = await response.text();
  if (!text) return undefined as T;

  try {
    return JSON.parse(text) as T;
  } catch {
    throw new ApiError(response.status, "The server returned a malformed response.");
  }
}

async function toApiError(response: Response): Promise<ApiError> {
  let message = `Request failed (${response.status})`;
  let errors: ValidationErrorDetail[] | null = null;

  try {
    const parsed = (await response.json()) as Partial<ApiErrorBody>;
    if (parsed?.message) message = parsed.message;
    if (parsed?.errors) errors = parsed.errors;
  } catch {
    // Non-JSON error body (a proxy's HTML 502 page, say) — keep the generic message.
  }

  return new ApiError(response.status, message, errors);
}

// --- Binary responses ---------------------------------------------------

/**
 * Fetches a URL as a Blob with auth attached — used for authenticated file
 * downloads where the response is not JSON.
 */
export async function apiFetchBlob(path: string, options: ApiFetchOptions = {}): Promise<Blob> {
  // `body`/`formData`/`_isRetry` are destructured out even though unused here, so
  // they don't land in `rest` and collide with RequestInit's own `body` type.
  const { query, anonymous, headers, body: _body, formData: _formData, _isRetry, ...rest } = options;
  void _body;
  void _formData;
  void _isRetry;
  const requestHeaders = new Headers(headers);

  if (!anonymous) {
    await whenSessionBootstrapped();
    const token = getAccessToken();
    if (token) requestHeaders.set("Authorization", `Bearer ${token}`);
    const organizationId = getActiveOrganizationId();
    if (organizationId) requestHeaders.set("X-Organization-Id", organizationId);
  }

  let response: Response;
  try {
    response = await fetch(`${apiUrl(path)}${buildQueryString(query)}`, {
      ...rest,
      headers: requestHeaders,
    });
  } catch {
    throw new ApiError(0, "Cannot reach the server.");
  }

  if (response.status === 401 && !anonymous) {
    const refreshed = await refreshOnce();
    if (refreshed) return apiFetchBlob(path, { ...options, anonymous });
    clearTokens();
    onSessionExpired?.();
    throw new ApiError(401, "Your session has expired. Please sign in again.");
  }

  if (!response.ok) throw await toApiError(response);
  return response.blob();
}

/** Triggers a browser save dialog for an already-fetched Blob. */
export function saveBlob(blob: Blob, fileName: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = fileName;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  // Revoked on the next tick so Safari has time to start the download.
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

/** Human-readable message for any thrown value. Safe to call in a catch block. */
export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.fieldMessage;
  if (error instanceof Error) return error.message;
  return "Something went wrong.";
}
