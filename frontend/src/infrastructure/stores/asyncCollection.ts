import { getApiErrorMessage, isNotFoundError, isOfflineError } from '@/infrastructure/api/errors';

export type FetchStatus = 'idle' | 'loading' | 'success' | 'error';

export interface AsyncStatus {
    status: FetchStatus;
    error: string | null;
    /** true solo cuando la API no respondió o el servicio no estaba disponible (red caída / 502-504). */
    isOffline: boolean;
}

export const initialAsyncStatus: AsyncStatus = {
    status: 'idle',
    error: null,
    isOffline: false,
};

export interface FetchItemResult<T> {
    item: T | null;
    /** El backend confirmó con 404 que el recurso no existe. */
    notFound: boolean;
    /** El fetch falló y no hay copia local que mostrar: la vista debe renderizar un estado de error. */
    failed: boolean;
}

type SetStateUpdater<S> = (partial: Partial<S> | ((state: S) => Partial<S>)) => void;

export function mergeById<T extends { id: string }>(current: T[], incoming: T[]): T[] {
    const byId = new Map(current.map((item) => [item.id, item]));
    incoming.forEach((item) => byId.set(item.id, item));
    return Array.from(byId.values());
}

export function upsertById<T extends { id: string }>(current: T[], item: T): T[] {
    return current.some((existing) => existing.id === item.id)
        ? current.map((existing) => (existing.id === item.id ? item : existing))
        : [...current, item];
}

/** Reemplaza los elementos que calzan con `key = value` por los entrantes (p. ej. el historial de una orden). */
export function replaceWhere<T, K extends keyof T>(current: T[], key: K, value: T[K], incoming: T[]): T[] {
    return [...current.filter((item) => item[key] !== value), ...incoming];
}

/**
 * Fetch de colección compartido por todos los stores. Establece el estado de
 * carga, integra la respuesta con la caché (cada portal trae un subconjunto
 * distinto y no queremos que uno pise el del otro) y ante cualquier fallo
 * conserva la caché local: isOffline distingue los fallos de transporte de los
 * errores del servidor para que la vista elija el mensaje correcto.
 */
export async function fetchCollection<T, S extends AsyncStatus>(
    loader: () => Promise<T[]>,
    set: SetStateUpdater<S>,
    merge: (state: S, fetched: T[]) => Partial<S>
): Promise<void> {
    set({ status: 'loading', error: null, isOffline: false } as Partial<S>);
    try {
        const fetched = await loader();
        set((state): Partial<S> => ({
            ...merge(state, fetched),
            status: 'success',
            error: null,
            isOffline: false,
        }));
    } catch (err) {
        set({
            status: 'error',
            error: getApiErrorMessage(err),
            isOffline: isOfflineError(err),
        } as Partial<S>);
    }
}

/**
 * Fetch de un item por id. Distingue tres salidas: "no existe" (404 confirmado
 * por el backend, no toca la caché), "no se pudo confirmar" con copia local
 * (se conserva la caché y se avisa con isOffline/error) y "no se pudo confirmar"
 * sin copia local (failed: la vista muestra un estado de error reintentable en
 * lugar de un falso "no encontrado").
 */
export async function fetchItemById<T extends { id: string }, S extends AsyncStatus>(
    id: string,
    loader: (id: string) => Promise<T>,
    set: SetStateUpdater<S>,
    getItems: () => T[],
    upsert: (state: S, item: T) => Partial<S>
): Promise<FetchItemResult<T>> {
    try {
        const item = await loader(id);
        set((state): Partial<S> => ({
            ...upsert(state, item),
            error: null,
            isOffline: false,
        }));
        return { item, notFound: false, failed: false };
    } catch (err) {
        if (isNotFoundError(err)) {
            return { item: null, notFound: true, failed: false };
        }
        const local = getItems().find((cached) => cached.id === id) ?? null;
        set({ error: getApiErrorMessage(err), isOffline: isOfflineError(err) } as Partial<S>);
        return { item: local, notFound: false, failed: local === null };
    }
}