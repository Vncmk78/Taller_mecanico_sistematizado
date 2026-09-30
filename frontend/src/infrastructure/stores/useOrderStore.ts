import { create } from 'zustand';
import type { Order } from '@/domain/entities/Order';
import { mockOrders } from '@/infrastructure/mocks/orders.mock';
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
}

interface OrderState extends AsyncStatus {
    orders: Order[];
    fetchOrders: (loader: () => Promise<Order[]>) => Promise<void>;
    fetchOrderById: (id: string, loader: (id: string) => Promise<Order>) => Promise<FetchOrderResult>;
}

// Caché en memoria compartida entre portales, con la misma filosofía que
// asyncCollection: los estados, el merge y el manejo offline centralizados.
export const useOrderStore = create<OrderState>((set, get) => ({
    orders: mockOrders,
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
        return { order: result.item, notFound: result.notFound };
    },
}));