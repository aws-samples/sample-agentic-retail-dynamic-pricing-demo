import { Navigate, useLocation } from 'react-router-dom';
import { isAuthenticated } from '../lib/auth';

interface AuthGuardProps {
  children: React.ReactNode;
}

/**
 * AuthGuard wraps protected routes and redirects unauthenticated users to login.
 * Passes the attempted URL as state so the user can be redirected back after login.
 */
export default function AuthGuard({ children }: AuthGuardProps) {
  const location = useLocation();

  if (!isAuthenticated()) {
    return (
      <Navigate
        to="/login"
        replace
        state={{ from: location.pathname, error: 'Please sign in to access the dashboard.' }}
      />
    );
  }

  return <>{children}</>;
}
