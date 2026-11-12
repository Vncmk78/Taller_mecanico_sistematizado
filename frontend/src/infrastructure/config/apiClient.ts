import axios, { type AxiosError } from 'axios';
import { getToken } from '@/infrastructure/config/tokenStorage';

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
  baseURL: import.meta.env.VITE_API_URL || '/api',
  headers: {
    'Content-Type': 'application/json',
  },
  // Techo para peticiones colgadas: sin él, una Gateway que no responde deja
  // el estado de carga para siempre (el usuario solo ve spinners). Al vencer,
  // axios rechaza sin respuesta y el manejo global de errores lo presenta
  // como fallo de conexión con reintento. Generoso para consultas de
  // inventario pesadas; las subidas de evidencias (FormData) llevan uno
  // propio mayor en EvidenciaService.
  timeout: 30000,
});

apiClient.interceptors.request.use((config) => {
  const token = getToken();
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