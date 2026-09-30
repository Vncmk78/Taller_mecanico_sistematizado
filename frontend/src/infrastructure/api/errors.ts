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
    // Validación de FastAPI: detail llega como lista de { msg, loc }.
    if (Array.isArray(detail)) {
        const first = detail.find((d): d is { msg: string } => typeof (d as { msg?: unknown })?.msg === 'string');
        if (first) return first.msg;
    }
    if (error.response.status === 404) return 'El recurso solicitado no fue encontrado.';
    if (error.response.status === 409) return 'Ya existe un registro con esos datos.';
    if (error.response.status >= 500) return 'El servidor tuvo un problema. Intente más tarde.';
    }
    return fallback;
}

export function isNotFoundError(error: unknown): boolean {
    return axios.isAxiosError(error) && error.response?.status === 404;
}

/**
 * true solo cuando el fallo es de transporte: no hubo respuesta de la Gateway o
 * el servicio/ms no estaba disponible (502/503/504). Cualquier otro status HTTP
 * (401/403/404/409/422/500) es un error del servidor y se muestra como tal, no
 * como "sin conexión".
 */
export function isOfflineError(error: unknown): boolean {
    if (!axios.isAxiosError(error)) return true;
    if (!error.response) return true;
    return [502, 503, 504].includes(error.response.status);
}

export function isConflictError(error: unknown): boolean {
    return axios.isAxiosError(error) && error.response?.status === 409;
}