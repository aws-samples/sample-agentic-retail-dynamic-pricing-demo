import { BrowserRouter, Routes, Route, Navigate, useLocation, useSearchParams, Link } from 'react-router-dom';
import AuthGuard from './components/AuthGuard';
import AuthCallback from './components/AuthCallback';
import PricingRequestForm from './pages/PricingRequestForm';
import { login, logout } from './lib/cognito';

function DashboardHome() {
  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
          <h1 className="text-2xl font-semibold text-gray-900">
            Retail Dynamic Pricing Dashboard
          </h1>
          <button
            onClick={logout}
            className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            Sign Out
          </button>
        </div>
      </header>
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <p className="text-gray-600 mb-4">Welcome to the Dynamic Pricing Dashboard.</p>
        <Link
          to="/pricing-request"
          className="inline-flex items-center px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          New Pricing Request
        </Link>
      </main>
    </div>
  );
}

function LoginPage() {
  const location = useLocation();
  const [searchParams] = useSearchParams();

  // Get error from URL params (e.g., from AuthCallback or API 401 redirect) or from route state
  const urlError = searchParams.get('error');
  const stateError = (location.state as { error?: string })?.error;

  let errorMessage: string | null = null;
  if (urlError === 'auth_failed') {
    errorMessage = 'Authentication failed. Please try again.';
  } else if (urlError === 'session_expired') {
    errorMessage = 'Your session has expired. Please sign in again.';
  } else if (stateError) {
    errorMessage = stateError;
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="max-w-md w-full space-y-8 p-8 bg-white rounded-lg shadow">
        <h2 className="text-center text-3xl font-bold text-gray-900">
          Sign In
        </h2>
        <p className="text-center text-gray-600">
          Please sign in with your credentials to access the dashboard.
        </p>
        {errorMessage && (
          <div className="bg-red-50 border border-red-200 rounded-md p-3">
            <p className="text-sm text-red-700 text-center">{errorMessage}</p>
          </div>
        )}
        <button
          onClick={login}
          className="w-full flex justify-center py-3 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
        >
          Sign in with Cognito
        </button>
      </div>
    </div>
  );
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/callback" element={<AuthCallback />} />
        <Route
          path="/"
          element={
            <AuthGuard>
              <DashboardHome />
            </AuthGuard>
          }
        />
        <Route
          path="/pricing-request"
          element={
            <AuthGuard>
              <div className="min-h-screen bg-gray-50">
                <header className="bg-white shadow-sm border-b border-gray-200">
                  <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <Link to="/" className="text-sm text-blue-600 hover:text-blue-800">&larr; Back</Link>
                      <h1 className="text-2xl font-semibold text-gray-900">
                        Retail Dynamic Pricing Dashboard
                      </h1>
                    </div>
                    <button
                      onClick={logout}
                      className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                      Sign Out
                    </button>
                  </div>
                </header>
                <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                  <PricingRequestForm />
                </main>
              </div>
            </AuthGuard>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
