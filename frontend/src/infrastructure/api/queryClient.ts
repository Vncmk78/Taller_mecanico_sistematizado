import axios from 'axios';
import { QueryCache, QueryClient } from '@tanstack/react-query';
import { getApiErrorMessage, getApiErrorRequestId } from './errors';

/** Tope de reintentos automáticos para una consulta fallida. */
export const MAX_REINTENTOS_QUERY = 2;

/**
 * Reintentar una consulta solo tiene sentido cuando el fallo puede ser
 * transitorio: no hubo respuesta (red caída / timeout) o el servidor falló con
 * un 5xx. Un 4xx (400/401/403/404/409/422) es determinista: repetirlo solo
 * duplica la carga y el ruido, así que la consulta falla de inmediato y la
 * vista muestra su ErrorState con reintento manual.
 */
export function shouldRetryQuery(failureCount: number, error: unknown): boolean {
    if (failureCount >= MAX_REINTENTOS_QUERY) return false;
    if (!axios.isAxiosError(error)) return false;
    if (!error.response) return true;
    return error.response.status >= 500;
}

/**
 * Cliente de React Query único de la app (antes se instanciaba suelto en
 * App.tsx). Centraliza:
 * - el reintento inteligente (shouldRetryQuery) en vez del `retry: 1` que
 *   reintentaba también los 4xx;
 * - el logging de todo fallo de consulta en QueryCache.onError, con el
 *   mensaje normalizado y el X-Request-ID para rastrearlo en los logs del
 *   backend.
 *
 * Nunca se vuelca el objeto `error` completo: un AxiosError lleva
 * `config.headers.Authorization` (el token de acceso) y la consola del navegador
 * es lo que se ve al compartir pantalla.
 */
export function createQueryClient(): QueryClient {
    return new QueryClient({
        defaultOptions: {
            queries: {
                retry: shouldRetryQuery,
                refetchOnWindowFocus: false,
            },
        },
        queryCache: new QueryCache({
            onError: (error, query) => {
                const requestId = getApiErrorRequestId(error);
                console.error(
                    '[React Query] Fallo de consulta',
                    `queryKey=${JSON.stringify(query.queryKey)}`,
                    `mensaje=${getApiErrorMessage(error)}`,
                    requestId ? `request-id=${requestId}` : 'request-id=null'
                );
            },
        }),
    });
}
