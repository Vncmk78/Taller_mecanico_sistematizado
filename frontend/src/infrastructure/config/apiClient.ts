import axios, { type AxiosError } from 'axios';

type NetworkHandler = (error: AxiosError) => void;

let unauthorizedHandler: NetworkHandler | null = null;
let forbiddenHandler: NetworkHandler | null = null;

export function setUnauthorizedHandler(handler: NetworkHandler | null): void {
  unauthorizedHandler = handler;
}

export function setForbiddenHandler(handler: NetworkHandler | null): void {
  forbiddenHandler = handler;
}

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;
    const url = error.config?.url ?? '';
    const isLoginRequest = url.includes('/auth/login');
    if (status === 401 && unauthorizedHandler && !isLoginRequest) {
      unauthorizedHandler(error);
    } else if (status === 403 && forbiddenHandler) {
      forbiddenHandler(error);
    }
    return Promise.reject(error);
  }
);

export default apiClient;