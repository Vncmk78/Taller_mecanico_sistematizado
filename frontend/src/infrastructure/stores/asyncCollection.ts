import { getApiErrorMessage, isNotFoundError } from '@/infrastructure/api/errors';

export type FetchStatus = 'idle' | 'loading' | 'success' | 'error';

export interface AsyncStatus {
    status: FetchStatus;
    error: string | null;
    /** true cuando lo mostrado son datos locales porque la API no respondió (MS2/Gateway aún no disponibles). */
    isOffline: boolean;
}

export const initialAsyncStatus: AsyncStatus = {
    status: 'idle',
    error: null,
    isOffline: false,
};

export interface FetchItemResult<T> {
    item: T | null;
    notFound: boolean;
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
 * conserva la caché local marcando isOffline para avisar al usuario.
 */
export async function fetchCollection<T, S extends AsyncStatus>(
    loader: () => Promise<T[]>,
    set: SetStateUpdater<S>,
    merge: (state: S, fetched: T[]) => Partial<S>
): Promise<void> {
    set({ status: 'loading', error: null } as Partial<S>);
    try {
        const fetched = await loader();
        set((state): Partial<S> => ({
            ...merge(state, fetched),
            status: 'success',
            error: null,
            isOffline: false,
        }));
    } catch (err) {
        set({ status: 'error', error: getApiErrorMessage(err), isOffline: true } as Partial<S>);
    }
}

/**
 * Fetch de un item por id. Distingue "no existe" (404 confirmado por el
 * backend, no toca la caché) de "no se pudo confirmar" (error de red/servidor:
 * se conserva la caché local y se avisa con isOffline).
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
        return { item, notFound: false };
    } catch (err) {
        if (isNotFoundError(err)) {
            return { item: null, notFound: true };
        }
        const local = getItems().find((cached) => cached.id === id) ?? null;
        set({ error: getApiErrorMessage(err), isOffline: true } as Partial<S>);
        return { item: local, notFound: local === null };
    }
}