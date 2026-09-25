import { create } from 'zustand';
import type { Order } from '@/domain/entities/Order';
import { getApiErrorMessage, isNotFoundError } from '@/infrastructure/api/errors';
import { mockOrders } from '@/infrastructure/mocks/orders.mock';
import type { FetchStatus } from '@/infrastructure/stores/useVehicleStore';

interface FetchOrderResult {
    order: Order | null;
    notFound: boolean;
}

interface OrderState {
    orders: Order[];
    status: FetchStatus;
    error: string | null;
    /** true cuando lo mostrado son datos locales porque la API no respondió (MS2/Gateway aún no disponibles). */
    isOffline: boolean;
    fetchOrders: (loader: () => Promise<Order[]>) => Promise<void>;
    fetchOrderById: (id: string, loader: (id: string) => Promise<Order>) => Promise<FetchOrderResult>;
}

// Caché en memoria compartida entre portales. Se inicializa con datos de
// demostración para que la UI nunca quede vacía ante fallos de red o mientras
// algún endpoint de MS2 aún no está disponible. Cada fetch* intenta la API
// real primero; si falla, se conserva la caché local y se marca isOffline
// para avisar al usuario.
export const useOrderStore = create<OrderState>((set, get) => ({
    orders: mockOrders,
    status: 'idle',
    error: null,
    isOffline: false,

    fetchOrders: async (loader) => {
        set({ status: 'loading', error: null });
        try {
            const fetched = await loader();
            set((state) => {
                // Merge por id: cada portal trae un subconjunto distinto
                // (todas / las mías / las de mis vehículos); no queremos que
                // uno pise la caché del otro.
                const byId = new Map(state.orders.map((o) => [o.id, o]));
                fetched.forEach((o) => byId.set(o.id, o));
                return {
                    orders: Array.from(byId.values()),
                    status: 'success',
                    isOffline: false,
                    error: null,
                };
            });
        } catch (err) {
            set({ status: 'error', error: getApiErrorMessage(err), isOffline: true });
        }
    },

    fetchOrderById: async (id, loader) => {
        try {
            const order = await loader(id);
            set((state) => {
                const exists = state.orders.some((o) => o.id === order.id);
                return {
                    orders: exists
                        ? state.orders.map((o) => (o.id === order.id ? order : o))
                        : [...state.orders, order],
                    isOffline: false,
                    error: null,
                };
            });
            return { order, notFound: false };
        } catch (err) {
            if (isNotFoundError(err)) {
                // El backend respondió: la orden realmente no existe o no es
                // alcanzable para el rol autenticado.
                return { order: null, notFound: true };
            }
            // Error de red/servidor: no sabemos si existe; mostramos lo que
            // haya en caché local y avisamos que no se pudo confirmar.
            const local = get().orders.find((o) => o.id === id) ?? null;
            set({ error: getApiErrorMessage(err), isOffline: true });
            return { order: local, notFound: local === null };
        }
    },
}));