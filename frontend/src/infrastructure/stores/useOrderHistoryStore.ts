import { create } from 'zustand';
import type { OrderHistoryEntry } from '@/domain/entities/OrderHistory';
import { mockOrderHistory } from '@/infrastructure/mocks/orders.history.mock';
import type { OrderPort } from '@/domain/ports/OrderPort';
import {
    initialAsyncStatus,
    type AsyncStatus,
    fetchCollection,
    replaceWhere,
} from '@/infrastructure/stores/asyncCollection';

interface OrderHistoryState extends AsyncStatus {
    entries: OrderHistoryEntry[];
    fetchOrderHistory: (ordenId: string, loader: OrderPort['getOrderHistory']) => Promise<void>;
}

// Caché plana compartida entre portales, con la misma filosofía que
// asyncCollection: al llegar una respuesta del servidor para una orden, se
// reemplaza por completo su historial (fuente autoritativa de esa orden) para
// no mezclar datos reales con los demos de la misma orden.
export const useOrderHistoryStore = create<OrderHistoryState>((set) => ({
    entries: mockOrderHistory,
    ...initialAsyncStatus,

    fetchOrderHistory: (ordenId, loader) =>
        fetchCollection<OrderHistoryEntry, OrderHistoryState>(
            () => loader(ordenId),
            set,
            (state, fetched) => ({ entries: replaceWhere(state.entries, 'ordenId', ordenId, fetched) })
        ),
}));