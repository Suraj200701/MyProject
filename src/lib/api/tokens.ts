/**
 * JWT storage for the browser.
 *
 * Where tokens live
 * -----------------
 * `localStorage`. The backend issues its access/refresh pair in a JSON response
 * body (`POST /auth/login`) and authenticates via an `Authorization` header — it
 * never sets a cookie — so there is no httpOnly-cookie option available without
 * changing the backend, which is out of scope here.
 *
 * The tradeoff, stated plainly: anything that can run JavaScript on this origin
 * can read these tokens, so a stored token is only as safe as the app is from
 * XSS. That is mitigated by React escaping all rendered content by default, no
 * use of `dangerouslySetInnerHTML`, and a short access-token lifetime with the
 * refresh path below. If this ever needs to be hardened further, the fix is on
 * the backend: set the refresh token as an httpOnly, Secure, SameSite=Strict
 * cookie and keep only the access token in memory.
 *
 * Access is funnelled through this module (rather than components touching
 * `localStorage` directly) so that swap only has to happen in one place.
 */

const ACCESS_TOKEN_KEY = "leadmaster.access_token";
const REFRESH_TOKEN_KEY = "leadmaster.refresh_token";
const ORGANIZATION_KEY = "leadmaster.organization_id";

/** True in the browser. Guards every access — these modules are imported during SSR too. */
const canUseStorage = () => typeof window !== "undefined" && !!window.localStorage;

/**
 * In-memory mirror of the access token.
 *
 * Read first on every request so the common path costs nothing, and so a token
 * refreshed mid-flight is visible immediately without a storage round-trip.
 */
let accessTokenCache: string | null = null;

function safeGet(key: string): string | null {
  if (!canUseStorage()) return null;
  try {
    return window.localStorage.getItem(key);
  } catch {
    // Private browsing modes and storage-disabled environments throw on access.
    // Losing persistence is survivable; crashing the app is not.
    return null;
  }
}

function safeSet(key: string, value: string | null): void {
  if (!canUseStorage()) return;
  try {
    if (value === null) window.localStorage.removeItem(key);
    else window.localStorage.setItem(key, value);
  } catch {
    /* ignore — see safeGet */
  }
}

export function getAccessToken(): string | null {
  if (accessTokenCache !== null) return accessTokenCache;
  accessTokenCache = safeGet(ACCESS_TOKEN_KEY);
  return accessTokenCache;
}

export function getRefreshToken(): string | null {
  return safeGet(REFRESH_TOKEN_KEY);
}

export function setTokens(accessToken: string, refreshToken?: string | null): void {
  accessTokenCache = accessToken;
  safeSet(ACCESS_TOKEN_KEY, accessToken);
  if (refreshToken) safeSet(REFRESH_TOKEN_KEY, refreshToken);
}

export function clearTokens(): void {
  accessTokenCache = null;
  safeSet(ACCESS_TOKEN_KEY, null);
  safeSet(REFRESH_TOKEN_KEY, null);
  safeSet(ORGANIZATION_KEY, null);
}

export function hasSession(): boolean {
  return !!getAccessToken();
}

/**
 * Active organization, sent as `X-Organization-Id`.
 *
 * Optional: with no header the backend falls back to the user's oldest
 * membership, which is the right behaviour for the single-workspace case. This
 * exists so a future workspace switcher has somewhere to write to.
 */
export function getActiveOrganizationId(): string | null {
  return safeGet(ORGANIZATION_KEY);
}

export function setActiveOrganizationId(id: string | null): void {
  safeSet(ORGANIZATION_KEY, id);
}

// --- Bootstrap barrier ---------------------------------------------------

/**
 * Gate that authenticated requests wait behind until the session has been
 * established.
 *
 * Why this exists: on a Google OAuth return the token arrives in the URL and is
 * only persisted once `AuthProvider`'s mount effect runs. Any component that
 * fetches during that same first tick would send a request with no
 * `Authorization` header, take a 401, and — because the OAuth callback issues no
 * refresh token — trip the refresh path into clearing the session that had just
 * been saved. That is exactly the bug this guards against.
 *
 * Ordering the component tree correctly is the primary fix (see
 * `app/dashboard/layout.tsx`); this is the backstop, so a component mounted
 * outside a guard in future cannot resurrect the same failure.
 *
 * Costs nothing in practice: bootstrap does no I/O, so the promise settles on the
 * first tick after mount.
 */
let resolveBootstrap: (() => void) | null = null;

/**
 * Safety net so the barrier can never deadlock the app.
 *
 * If `markSessionBootstrapped()` somehow never runs — a render error before
 * `AuthProvider`'s effect, or the provider being omitted from a tree — every
 * authenticated request would otherwise hang forever with no error to diagnose.
 * Releasing after a short delay degrades to the old behaviour (a request that may
 * lack a token) instead of an app that silently never loads.
 */
const BOOTSTRAP_TIMEOUT_MS = 3_000;

const bootstrapComplete: Promise<void> =
  typeof window === "undefined"
    ? // On the server there is no localStorage and no session to wait for.
      Promise.resolve()
    : new Promise<void>((resolve) => {
        resolveBootstrap = resolve;
        setTimeout(() => {
          if (resolveBootstrap) {
            console.warn(
              "[auth] Session bootstrap did not complete within " +
                `${BOOTSTRAP_TIMEOUT_MS}ms; releasing the request barrier. ` +
                "Is <AuthProvider> mounted?",
            );
            resolveBootstrap();
            resolveBootstrap = null;
          }
        }, BOOTSTRAP_TIMEOUT_MS);
      });

/** Called once by `AuthProvider` after it has read the URL and storage. */
export function markSessionBootstrapped(): void {
  resolveBootstrap?.();
  resolveBootstrap = null;
}

/** Awaited by `apiFetch` before sending anything that carries credentials. */
export function whenSessionBootstrapped(): Promise<void> {
  return bootstrapComplete;
}
