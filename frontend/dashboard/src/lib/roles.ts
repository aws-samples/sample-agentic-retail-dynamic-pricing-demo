/**
 * Role-based access control utilities.
 *
 * Decodes the Cognito JWT id_token to extract user groups
 * and provides role-checking helpers for conditional UI rendering.
 *
 * Cognito groups:
 * - PricingAnalysts: Standard users (simulations, scenarios, approvals)
 * - Operations: System operators (metrics, health, architecture, TCO)
 */

import { getToken } from './auth';

export type UserRole = 'PricingAnalysts' | 'Operations' | 'unknown';

interface JwtPayload {
  'cognito:groups'?: string[];
  email?: string;
  sub?: string;
  [key: string]: unknown;
}

/**
 * Decode a JWT token payload (base64url) without verification.
 * Safe for frontend role display — actual authorization happens server-side.
 */
function decodeJwtPayload(token: string): JwtPayload | null {
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return null;

    const payload = parts[1];
    const decoded = atob(payload.replace(/-/g, '+').replace(/_/g, '/'));
    return JSON.parse(decoded);
  } catch {
    return null;
  }
}

/**
 * Get the current user's Cognito groups from their JWT token.
 */
export function getUserGroups(): string[] {
  const token = getToken();
  if (!token) return [];

  const payload = decodeJwtPayload(token);
  if (!payload) return [];

  return payload['cognito:groups'] || [];
}

/**
 * Get the current user's email from their JWT token.
 */
export function getUserEmail(): string {
  const token = getToken();
  if (!token) return '';

  const payload = decodeJwtPayload(token);
  return payload?.email || '';
}

/**
 * Check if the current user belongs to the Operations group.
 */
export function isOperationsUser(): boolean {
  return getUserGroups().includes('Operations');
}

/**
 * Check if the current user belongs to the PricingAnalysts group.
 */
export function isPricingAnalyst(): boolean {
  return getUserGroups().includes('PricingAnalysts');
}

/**
 * Get the primary role for display purposes.
 * Operations takes precedence since it's a superset.
 */
export function getPrimaryRole(): UserRole {
  const groups = getUserGroups();
  if (groups.includes('Operations')) return 'Operations';
  if (groups.includes('PricingAnalysts')) return 'PricingAnalysts';
  return 'unknown';
}
