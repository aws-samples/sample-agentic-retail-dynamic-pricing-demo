import { setToken, removeToken } from './auth';

/**
 * Cognito configuration from environment variables.
 */
const COGNITO_DOMAIN = import.meta.env.VITE_COGNITO_DOMAIN;
const COGNITO_CLIENT_ID = import.meta.env.VITE_COGNITO_CLIENT_ID;
const REDIRECT_URI = `${window.location.origin}/callback`;
const LOGOUT_REDIRECT_URI = window.location.origin;

/**
 * Build the Cognito Hosted UI login URL.
 * Uses the implicit grant flow (response_type=token) for SPA.
 */
export function buildLoginUrl(): string {
  const params = new URLSearchParams({
    client_id: COGNITO_CLIENT_ID,
    response_type: 'token',
    scope: 'openid email profile',
    redirect_uri: REDIRECT_URI,
  });
  return `https://${COGNITO_DOMAIN}/login?${params.toString()}`;
}

/**
 * Build the Cognito Hosted UI logout URL.
 * Clears the Cognito session and redirects back to the app.
 */
export function buildLogoutUrl(): string {
  const params = new URLSearchParams({
    client_id: COGNITO_CLIENT_ID,
    logout_uri: LOGOUT_REDIRECT_URI,
  });
  return `https://${COGNITO_DOMAIN}/logout?${params.toString()}`;
}

/**
 * Parse the access token from the URL hash fragment after Cognito redirect.
 * The hash contains: #access_token=...&id_token=...&token_type=Bearer&expires_in=3600
 * Returns the id_token (JWT) if present, otherwise null.
 */
export function handleAuthCallback(): string | null {
  const hash = window.location.hash.substring(1);
  if (!hash) {
    return null;
  }

  const params = new URLSearchParams(hash);
  const idToken = params.get('id_token');

  if (idToken) {
    setToken(idToken);
    return idToken;
  }

  // Fallback to access_token if id_token is not present
  const accessToken = params.get('access_token');
  if (accessToken) {
    setToken(accessToken);
    return accessToken;
  }

  return null;
}

/**
 * Redirect the user to the Cognito Hosted UI login page.
 */
export function login(): void {
  window.location.href = buildLoginUrl();
}

/**
 * Clear the local token and redirect to the Cognito logout endpoint.
 */
export function logout(): void {
  removeToken();
  window.location.href = buildLogoutUrl();
}
