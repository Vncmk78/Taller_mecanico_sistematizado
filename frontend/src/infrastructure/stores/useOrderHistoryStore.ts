import { create } from 'zustand';
import type { OrderHistoryEntry } from '@/domain/entities/OrderHistory';
import { getApiErrorMessage } from '@/infrastructure/api/errors';
import { mockOrderHistory } from '@/infrastructure/mocks/orders.history.mock';
import type { FetchStatus } from '@/infrastructure/stores/useVehicleStore';
import type { OrderPort } from '@/domain/ports/OrderPort';

interface OrderHistoryState {
    entries: OrderHistoryEntry[];
    status: FetchStatus;
    error: string | null;
    /** true cuando lo mostrado son datos locales porque la API no respondió (endpoint de historial aún no existe en MS2). */
    isOffline: boolean;
    fetchOrderHistory: (ordenId: string, loader: OrderPort['getOrderHistory']) => Promise<void>;
}

// Caché plana compartida entre portales, con la misma filosofía que
// useOrderStore: inicializada con los historiales de demostración y siempre
// intentando la API real primero. Al llegar una respuesta del servidor para
// una orden, se reemplaza por completo su historial (es la fuente autoritativa
// de esa orden), para no mezclar datos reales con los demos de la misma orden.
export const useOrderHistoryStore = create<OrderHistoryState>((set) => ({
    entries: mockOrderHistory,
    status: 'idle',
    error: null,
    isOffline: false,

    fetchOrderHistory: async (ordenId, loader) => {
        set({ status: 'loading', error: null });
        try {
            const fetched = await loader(ordenId);
            set((state) => {
                const withoutOrder = state.entries.filter((e) => e.ordenId !== ordenId);
                return {
                    entries: [...withoutOrder, ...fetched],
                    status: 'success',
                    isOffline: false,
                    error: null,
                };
            });
        } catch (err) {
            set({ status: 'error', error: getApiErrorMessage(err), isOffline: true });
        }
    },
}));