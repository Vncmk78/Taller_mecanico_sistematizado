import type { Order } from '@/domain/entities/Order';
import { useOrderStore } from '@/infrastructure/stores/useOrderStore';
import { useCollectionDetail } from '@/presentation/hooks/useCollectionDetail';

export interface UseOrderDetailResult {
    order: Order | undefined;
    loading: boolean;
    notFound: boolean;
    failed: boolean;
    refetch: () => void;
}

/**
 * Encapsula la carga de una orden por id vía useCollectionDetail. Reutilizado
 * por las páginas de detalle de los 3 portales.
 */
export function useOrderDetail(
    id: string | undefined,
    loader: (id: string) => Promise<Order>
): UseOrderDetailResult {
    const orders = useOrderStore((s) => s.orders);
    const fetchOrderById = useOrderStore((s) => s.fetchOrderById);
    const { item, loading, notFound, failed, refetch } = useCollectionDetail<Order>({
        id,
        items: orders,
        fetchById: fetchOrderById,
        loader,
    });
    return { order: item, loading, notFound, failed, refetch };
}