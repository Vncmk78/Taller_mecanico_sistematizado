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
  // El cliente fija `application/json` por defecto y axios 1.20 fuerza
  // `x-www-form-urlencoded` en POST si no hay Content-Type. Con FormData eso
  // serializa el archivo como `{}` (422 en /evidencias). El adaptador fetch
  // permite que el navegador genere el boundary del multipart.
  if (typeof FormData !== 'undefined' && config.data instanceof FormData) {
    config.headers.setContentType('multipart/form-data', true);
    // Respetar adaptadores inyectados en pruebas; en el navegador se usa fetch.
    if (typeof config.adapter !== 'function') {
      config.adapter = 'fetch';
    }
  }
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