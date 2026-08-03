/**
 * Consumes the tokens the Google OAuth callback delivers in the URL.
 *
 * The backend finishes the OAuth dance with a redirect:
 *
 *     GET /api/v1/auth/google/callback
 *       -> 307 {FRONTEND_URL}/dashboard?access_token=<JWT>
 *
 * so the token arrives as a query parameter on a top-level navigation rather
 * than in a JSON response body. This module extracts it, and `AuthProvider`
 * persists it through exactly the same `setTokens` path that email/password
 * login uses — there is no second storage mechanism.
 *
 * Two things about that contract worth knowing:
 *
 * 1. **Only `access_token` is sent — there is no refresh token.** The callback
 *    builds one access token and nothing else. So a Google session lives for
 *    `ACCESS_TOKEN_EXPIRE_MINUTES` (30 by default) and then cannot be renewed:
 *    the next 401 finds no refresh token, and the user is sent to /login. That
 *    is the backend's current design, which this change is not permitted to
 *    alter, so `refresh_token` is read opportunistically below — if the callback
 *    ever starts sending one, it will be stored with no further changes here.
 *
 * 2. **A JWT in a query string is exposed** — it lands in browser history, and
 *    can leak through `Referer` headers and any logging proxy in between. That
 *    is why the URL is rewritten immediately after the token is read, and why
 *    `history.replaceState`-style navigation (`router.replace`) is used rather
 *    than a push: it leaves no history entry that still contains the token.
 */

/** Query parameters the callback may attach. */
const ACCESS_TOKEN_PARAM = "access_token";
const REFRESH_TOKEN_PARAM = "refresh_token";
const ERROR_PARAM = "error";

export interface OAuthCallbackResult {
  accessToken: string;
  /** Absent today — see the note above. */
  refreshToken: string | null;
  /**
   * The current path with the auth parameters stripped, ready for
   * `router.replace()`. Any unrelated query parameters are preserved.
   */
  cleanedUrl: string;
}

/**
 * Reads OAuth tokens from the current URL, if present.
 *
 * Reads `window.location` directly rather than `useSearchParams()` on purpose:
 * this runs from `AuthProvider`, which sits at the root of the app, and
 * `useSearchParams` there would force the whole tree behind a Suspense boundary
 * and opt every route out of static rendering.
 *
 * Returns `null` when there is nothing to consume, which is the common case.
 */
export function readOAuthCallback(): OAuthCallbackResult | null {
  if (typeof window === "undefined") return null;

  const url = new URL(window.location.href);
  const accessToken = url.searchParams.get(ACCESS_TOKEN_PARAM);
  if (!accessToken) return null;

  const refreshToken = url.searchParams.get(REFRESH_TOKEN_PARAM);

  url.searchParams.delete(ACCESS_TOKEN_PARAM);
  url.searchParams.delete(REFRESH_TOKEN_PARAM);
  url.searchParams.delete(ERROR_PARAM);

  // Path + any surviving query, relative so `router.replace` treats it as an
  // internal navigation. The hash is preserved in case a deep link used one.
  const query = url.searchParams.toString();
  const cleanedUrl = `${url.pathname}${query ? `?${query}` : ""}${url.hash}`;

  return { accessToken, refreshToken, cleanedUrl };
}

/** True when the current URL carries an OAuth error instead of a token. */
export function readOAuthError(): string | null {
  if (typeof window === "undefined") return null;
  return new URL(window.location.href).searchParams.get(ERROR_PARAM);
}
