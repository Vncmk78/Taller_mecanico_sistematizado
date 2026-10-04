import { create } from 'zustand';
import type { Order } from '@/domain/entities/Order';
import {
    initialAsyncStatus,
    type AsyncStatus,
    fetchCollection,
    fetchItemById,
    mergeById,
    upsertById,
} from '@/infrastructure/stores/asyncCollection';

interface FetchOrderResult {
    order: Order | null;
    notFound: boolean;
    failed: boolean;
}

interface OrderState extends AsyncStatus {
    orders: Order[];
    fetchOrders: (loader: () => Promise<Order[]>) => Promise<void>;
    fetchOrderById: (id: string, loader: (id: string) => Promise<Order>) => Promise<FetchOrderResult>;
    /** Reemplaza (o inserta) una orden en la caché, p. ej. tras cambiar de estado. */
    updateOrder: (order: Order) => void;
    /**
     * Vacía la caché y vuelve al estado inicial. Se invoca al cerrar sesión: la
     * caché es compartida entre portales y sin esto el siguiente usuario que
     * iniciara sesión en el mismo navegador vería las órdenes del anterior.
     */
    reset: () => void;
}

// Caché en memoria compartida entre portales, con la misma filosofía que
// asyncCollection: los estados, el merge y el manejo offline centralizados.
export const useOrderStore = create<OrderState>((set, get) => ({
    orders: [],
    ...initialAsyncStatus,

    fetchOrders: (loader) =>
        fetchCollection<Order, OrderState>(
            loader,
            set,
            (state, fetched) => ({ orders: mergeById(state.orders, fetched) })
        ),

    fetchOrderById: async (id, loader) => {
        const result = await fetchItemById<Order, OrderState>(
            id,
            loader,
            set,
            () => get().orders,
            (state, order) => ({ orders: upsertById(state.orders, order) })
        );
        return { order: result.item, notFound: result.notFound, failed: result.failed };
    },

    updateOrder: (order) =>
        set((state) => ({ orders: upsertById(state.orders, order) })),

    reset: () => set({ orders: [], ...initialAsyncStatus }),
}));