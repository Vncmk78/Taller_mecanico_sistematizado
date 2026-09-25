/**
 * Utilidades para normalizar errores de Axios en mensajes legibles.
 * Centralizado para reutilizar en cualquier store/hook que consuma la API Gateway.
 */
import axios from 'axios';

export function getApiErrorMessage(
    error: unknown,
    fallback = 'Ocurrió un error inesperado. Intente nuevamente.'
): string {
    if (axios.isAxiosError(error)) {
    if (!error.response) {
        return 'No se pudo conectar con el servidor. Verifique su conexión e intente nuevamente.';
    }
    const detail = (error.response.data as { detail?: unknown } | undefined)?.detail;
    if (typeof detail === 'string') return detail;
    if (error.response.status === 404) return 'El recurso solicitado no fue encontrado.';
    if (error.response.status === 409) return 'Ya existe un registro con esos datos.';
    if (error.response.status >= 500) return 'El servidor tuvo un problema. Intente más tarde.';
    }
    return fallback;
}

export function isNotFoundError(error: unknown): boolean {
    return axios.isAxiosError(error) && error.response?.status === 404;
}

export function isConflictError(error: unknown): boolean {
    return axios.isAxiosError(error) && error.response?.status === 409;
}