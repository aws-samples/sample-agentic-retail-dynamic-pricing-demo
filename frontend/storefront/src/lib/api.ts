import axios from 'axios';

/**
 * Axios instance configured for the public storefront API.
 * No authentication is required — this is a public-facing app.
 */
const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:4000',
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 15000,
});

export default api;
