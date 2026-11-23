import apiClient from '../config/apiClient';

/**
 * Tamaño de página usado al recorrer un listado paginado del backend.
 *
 * La API expone `limite`/`desde` y el total en `X-Total-Count`. Los servicios
 * de la app siguen entregando la colección completa al dominio, así que aquí
 * se piden páginas grandes para reducir viajes sin truncar datos.
 */
export const LIMITE_PAGINA = 100;

/** Techo defensivo: evita un bucle infinito si el backend no avanza. */
const MAX_PAGINAS = 100;

interface OpcionesRecorridoPaginas {
    /** Registros por página (1–100 según el contrato). */
    limite?: number;
    /** Máximo de páginas a recorrer. */
    maxPaginas?: number;
}

function leerTotalPaginas(headers: unknown): number | null {
    if (!headers || typeof headers !== 'object') return null;
    const raw = (headers as Record<string, unknown>)['x-total-count'];
    if (raw === undefined || raw === null) return null;
    const total = Number(raw);
    return Number.isFinite(total) && total >= 0 ? total : null;
}

/**
 * Recorre todas las páginas de un listado y devuelve la colección completa.
 *
 * Usa `limite`/`desde` y `X-Total-Count`. Si la respuesta no trae la cabecera
 * (mocks o versiones antiguas), una página incompleta marca el final.
 */
export async function obtenerTodasLasPaginas<T>(
    url: string,
    params: Readonly<Record<string, unknown>> = {},
    opciones: OpcionesRecorridoPaginas = {}
): Promise<T[]> {
    const limite = opciones.limite ?? LIMITE_PAGINA;
    const maxPaginas = opciones.maxPaginas ?? MAX_PAGINAS;
    const acumulado: T[] = [];

    for (let indice = 0; indice < maxPaginas; indice += 1) {
        const { data, headers } = await apiClient.get<T[]>(url, {
            params: { ...params, limite, desde: indice * limite },
        });
        acumulado.push(...data);

        if (data.length === 0) return acumulado;

        const total = leerTotalPaginas(headers);
        if (total === null) {
            // Sin cabecera no hay forma de conocer el total: una página corta
            // es la única señal fiable de que ya no quedan registros.
            if (data.length < limite) return acumulado;
            continue;
        }
        if (acumulado.length >= total) return acumulado;
    }

    return acumulado;
}
