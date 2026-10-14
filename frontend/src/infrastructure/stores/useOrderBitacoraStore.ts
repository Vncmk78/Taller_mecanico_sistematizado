import { create } from 'zustand';
import type { BitacoraEntry } from '@/domain/entities/Bitacora';
import type { OrderPort } from '@/domain/ports/OrderPort';
import {
    initialAsyncStatus,
    type AsyncStatus,
    fetchCollection,
    replaceWhere,
    upsertById,
} from '@/infrastructure/stores/asyncCollection';

interface OrderBitacoraState extends AsyncStatus {
    entries: BitacoraEntry[];
    fetchOrderBitacora: (ordenId: string, loader: OrderPort['getOrderBitacora']) => Promise<void>;
    /** Inserta o actualiza una entrada ya confirmada por el servidor. */
    addEntry: (entry: BitacoraEntry) => void;
    reset: () => void;
}

// Caché plana compartida entre portales con la misma filosofía que
// useOrderHistoryStore: al llegar la respuesta del servidor para una orden se
// reemplaza por completo su bitácora (fuente autoritativa de esa orden).
export const useOrderBitacoraStore = create<OrderBitacoraState>((set) => ({
    entries: [],
    ...initialAsyncStatus,

    fetchOrderBitacora: (ordenId, loader) =>
        fetchCollection<BitacoraEntry, OrderBitacoraState>(
            () => loader(ordenId),
            set,
            (state, fetched) => ({ entries: replaceWhere(state.entries, 'ordenId', ordenId, fetched) })
        ),

    addEntry: (entry) => set((state) => ({ entries: upsertById(state.entries, entry) })),

    reset: () => set({ entries: [], ...initialAsyncStatus }),
}));
