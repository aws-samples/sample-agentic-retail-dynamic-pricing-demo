import axios from 'axios';
import { getToken, removeToken } from './auth';

/**
 * Axios instance configured with the API Gateway base URL.
 * Automatically attaches the Cognito JWT token as a Bearer token
 * in the Authorization header for all outgoing requests.
 */
const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor: attach JWT token to every request
api.interceptors.request.use(
  (config) => {
    const token = getToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  },
);

// Response interceptor: handle 401 unauthorized responses
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Token expired or invalid — clear token and redirect to login with error
      removeToken();
      window.location.href = '/login?error=session_expired';
    }
    return Promise.reject(error);
  },
);

export default api;
