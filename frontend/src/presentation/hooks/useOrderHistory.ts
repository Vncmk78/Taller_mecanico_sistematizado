import { useEffect, useMemo, useState } from 'react';
import type { OrderHistoryEntry } from '@/domain/entities/OrderHistory';
import type { OrderPort } from '@/domain/ports/OrderPort';
import { useOrderHistoryStore } from '@/infrastructure/stores/useOrderHistoryStore';

interface UseOrderHistoryResult {
    entries: OrderHistoryEntry[];
    loading: boolean;
    refetch: () => void;
}

/**
 * Encapsula la carga del historial de estados de una orden. La fuente de verdad
 * es la caché de useOrderHistoryStore filtrada por orden; el fetch a la API se
 * dispara al montar (y en cada refetch) intentando actualizar esa caché.
 */
export function useOrderHistory(
    ordenId: string | undefined,
    loader: OrderPort['getOrderHistory']
): UseOrderHistoryResult {
    const allEntries = useOrderHistoryStore((s) => s.entries);
    const fetchOrderHistory = useOrderHistoryStore((s) => s.fetchOrderHistory);
    const [loading, setLoading] = useState(true);
    const [reloadKey, setReloadKey] = useState(0);

    useEffect(() => {
        if (!ordenId) {
            setLoading(false);
            return;
        }
        let active = true;
        setLoading(true);

        fetchOrderHistory(ordenId, loader).finally(() => {
            if (active) setLoading(false);
        });

        return () => {
            active = false;
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [ordenId, reloadKey]);

    const entries = useMemo(() => {
        const list = ordenId ? allEntries.filter((e) => e.ordenId === ordenId) : [];
        // Más reciente primero (estado actual arriba).
        return [...list].sort((a, b) => (a.fecha < b.fecha ? 1 : -1));
    }, [allEntries, ordenId]);

    return {
        entries,
        loading,
        refetch: () => setReloadKey((k) => k + 1),
    };
}