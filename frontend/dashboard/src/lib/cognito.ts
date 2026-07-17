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
 * Uses authorization code flow (response_type=code) — the secure flow for SPAs.
 * Implicit grant is disabled on the server side for security.
 */
export function buildLoginUrl(): string {
  const params = new URLSearchParams({
    client_id: COGNITO_CLIENT_ID,
    response_type: 'code',
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
 * Exchange the authorization code for tokens via the Cognito token endpoint.
 * This is the secure way to obtain tokens — codes are single-use and short-lived.
 */
export async function exchangeCodeForToken(code: string): Promise<string | null> {
  const tokenEndpoint = `https://${COGNITO_DOMAIN}/oauth2/token`;

  const body = new URLSearchParams({
    grant_type: 'authorization_code',
    client_id: COGNITO_CLIENT_ID,
    code,
    redirect_uri: REDIRECT_URI,
  });

  try {
    const response = await fetch(tokenEndpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: body.toString(),
    });

    if (!response.ok) {
      console.error('Token exchange failed:', response.status, await response.text());
      return null;
    }

    const data = await response.json();
    const idToken = data.id_token;

    if (idToken) {
      setToken(idToken);
      return idToken;
    }

    return null;
  } catch (error) {
    console.error('Token exchange error:', error);
    return null;
  }
}

/**
 * Handle the OAuth callback — parse the authorization code from query params.
 * Legacy support: also checks hash fragment for backward compatibility.
 */
export async function handleAuthCallback(): Promise<string | null> {
  // Authorization code flow: code comes as a query parameter
  const urlParams = new URLSearchParams(window.location.search);
  const code = urlParams.get('code');

  if (code) {
    return await exchangeCodeForToken(code);
  }

  // Fallback: check hash fragment (legacy implicit flow — should not happen
  // with current CDK config, but handles edge cases during migration)
  const hash = window.location.hash.substring(1);
  if (hash) {
    const hashParams = new URLSearchParams(hash);
    const idToken = hashParams.get('id_token') || hashParams.get('access_token');
    if (idToken) {
      setToken(idToken);
      return idToken;
    }
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
