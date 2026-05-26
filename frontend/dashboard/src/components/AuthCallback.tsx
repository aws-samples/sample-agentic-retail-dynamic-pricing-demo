import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { handleAuthCallback } from '../lib/cognito';

/**
 * AuthCallback handles the OAuth redirect from Cognito Hosted UI.
 * It parses the token from the URL hash, stores it, and redirects to the dashboard.
 * If token parsing fails, it redirects to login with an error message.
 */
export default function AuthCallback() {
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = handleAuthCallback();

    if (token) {
      // Clear the hash from the URL for security
      window.history.replaceState(null, '', window.location.pathname);
      navigate('/', { replace: true });
    } else {
      setError('Authentication failed. No valid token received.');
      // Redirect to login after a brief delay so the user sees the error
      const timeout = setTimeout(() => {
        navigate('/login?error=auth_failed', { replace: true });
      }, 2000);
      return () => clearTimeout(timeout);
    }
  }, [navigate]);

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="max-w-md w-full p-8 bg-white rounded-lg shadow">
          <div className="text-center">
            <div className="text-red-500 text-4xl mb-4">⚠️</div>
            <h2 className="text-xl font-semibold text-gray-900 mb-2">
              Authentication Failed
            </h2>
            <p className="text-gray-600">{error}</p>
            <p className="text-sm text-gray-400 mt-2">
              Redirecting to login...
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="max-w-md w-full p-8 bg-white rounded-lg shadow">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Completing sign in...</p>
        </div>
      </div>
    </div>
  );
}
