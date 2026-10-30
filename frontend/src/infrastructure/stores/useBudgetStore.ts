import { create } from 'zustand';
import type { Presupuesto } from '@/domain/entities/Presupuesto';
import {
    initialAsyncStatus,
    type AsyncStatus,
    fetchCollection,
    fetchItemById,
    mergeById,
    upsertById,
} from '@/infrastructure/stores/asyncCollection';
import {
    getApiErrorMessage,
    getApiErrorRequestId,
    isNotFoundError,
    isOfflineError,
} from '@/infrastructure/api/errors';

export interface FetchPresupuestoResult {
    presupuesto: Presupuesto | null;
    /** No hay presupuesto visible (o la orden no es del cliente): se muestra vacío. */
    notFound: boolean;
    /** El fetch falló y no hay copia local que mostrar. */
    failed: boolean;
}

interface BudgetState extends AsyncStatus {
    presupuestos: Presupuesto[];
    /** Presupuesto de una orden (versiones enviadas). `null`/notFound si aún no hay. */
    fetchByOrder: (
        ordenId: string,
        loader: (ordenId: string) => Promise<Presupuesto | null>
    ) => Promise<FetchPresupuestoResult>;
    /** Detalle de un presupuesto con sus versiones e ítems. */
    fetchById: (
        id: string,
        loader: (id: string) => Promise<Presupuesto>
    ) => Promise<FetchPresupuestoResult>;
    /** Carga en paralelo los presupuestos de varias órdenes (listado del cliente). */
    fetchForOrders: (
        ordenIds: string[],
        loader: (ordenId: string) => Promise<Presupuesto | null>
    ) => Promise<void>;
    /** Reemplaza (o inserta) un presupuesto en la caché, p. ej. tras decidir. */
    updateBudget: (presupuesto: Presupuesto) => void;
    reset: () => void;
}

// Caché en memoria compartida del portal, con la misma filosofía que
// useOrderStore: estados, merge y manejo offline centralizados en asyncCollection.
export const useBudgetStore = create<BudgetState>((set, get) => ({
    presupuestos: [],
    ...initialAsyncStatus,

    fetchByOrder: async (ordenId, loader) => {
        try {
            const presupuesto = await loader(ordenId);
            if (!presupuesto) {
                return { presupuesto: null, notFound: true, failed: false };
            }
            set((state) => ({
                presupuestos: upsertById(state.presupuestos, presupuesto),
                error: null,
                isOffline: false,
                requestId: null,
            }));
            return { presupuesto, notFound: false, failed: false };
        } catch (err) {
            if (isNotFoundError(err)) {
                return { presupuesto: null, notFound: true, failed: false };
            }
            const local = get().presupuestos.find((cached) => cached.orderId === ordenId) ?? null;
            set({
                error: getApiErrorMessage(err),
                isOffline: isOfflineError(err),
                requestId: getApiErrorRequestId(err),
            });
            return { presupuesto: local, notFound: false, failed: local === null };
        }
    },

    fetchById: async (id, loader) => {
        const result = await fetchItemById<Presupuesto, BudgetState>(
            id,
            loader,
            set,
            () => get().presupuestos,
            (state, presupuesto) => ({ presupuestos: upsertById(state.presupuestos, presupuesto) })
        );
        return { presupuesto: result.item, notFound: result.notFound, failed: result.failed };
    },

    fetchForOrders: (ordenIds, loader) =>
        fetchCollection<Presupuesto, BudgetState>(
            () =>
                Promise.all(ordenIds.map((ordenId) => loader(ordenId))).then((presupuestos) =>
                    presupuestos.filter((p): p is Presupuesto => p !== null)
                ),
            set,
            (state, fetched) => ({ presupuestos: mergeById(state.presupuestos, fetched) })
        ),

    updateBudget: (presupuesto) =>
        set((state) => ({ presupuestos: upsertById(state.presupuestos, presupuesto) })),

    reset: () => set({ presupuestos: [], ...initialAsyncStatus }),
}));
