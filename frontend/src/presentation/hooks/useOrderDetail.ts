import { useEffect, useState } from 'react';
import type { Order } from '@/domain/entities/Order';
import { useOrderStore } from '@/infrastructure/stores/useOrderStore';

interface UseOrderDetailResult {
    order: Order | undefined;
    loading: boolean;
    notFound: boolean;
    refetch: () => void;
}

/**
 * Encapsula la carga de una orden por id: intenta la API real vía el loader
 * recibido y distingue "no existe" (404 confirmado por el backend) de "no se
 * pudo confirmar" (error de red, se muestra lo que haya en caché). Reutilizado
 * por las páginas de detalle de los 3 portales.
 */
export function useOrderDetail(
    id: string | undefined,
    loader: (id: string) => Promise<Order>
): UseOrderDetailResult {
    const orders = useOrderStore((s) => s.orders);
    const fetchOrderById = useOrderStore((s) => s.fetchOrderById);
    const [loading, setLoading] = useState(true);
    const [notFound, setNotFound] = useState(false);
    const [reloadKey, setReloadKey] = useState(0);

    useEffect(() => {
        if (!id) {
            setLoading(false);
            setNotFound(true);
            return;
        }
        let active = true;
        setLoading(true);
        setNotFound(false);

        fetchOrderById(id, loader).then((result) => {
            if (!active) return;
            setNotFound(result.notFound);
            setLoading(false);
        });

        return () => {
            active = false;
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [id, reloadKey]);

    return {
        order: id ? orders.find((o) => o.id === id) : undefined,
        loading,
        notFound,
        refetch: () => setReloadKey((k) => k + 1),
    };
}