import { useEffect, useMemo, useState } from 'react';
import type { BitacoraEntry } from '@/domain/entities/Bitacora';
import type { OrderPort } from '@/domain/ports/OrderPort';
import { useOrderBitacoraStore } from '@/infrastructure/stores/useOrderBitacoraStore';

interface UseOrderBitacoraResult {
    entries: BitacoraEntry[];
    loading: boolean;
    refetch: () => void;
}

/**
 * Encapsula la carga de la bitácora de una orden. La fuente de verdad es la
 * caché de useOrderBitacoraStore filtrada por orden; el fetch a la API se
 * dispara al montar (y en cada refetch) intentando actualizar esa caché.
 */
export function useOrderBitacora(
    ordenId: string | undefined,
    loader: OrderPort['getOrderBitacora']
): UseOrderBitacoraResult {
    const allEntries = useOrderBitacoraStore((s) => s.entries);
    const fetchOrderBitacora = useOrderBitacoraStore((s) => s.fetchOrderBitacora);
    const [loading, setLoading] = useState(true);
    const [reloadKey, setReloadKey] = useState(0);

    useEffect(() => {
        if (!ordenId) {
            setLoading(false);
            return;
        }
        let active = true;
        setLoading(true);

        fetchOrderBitacora(ordenId, loader).finally(() => {
            if (active) setLoading(false);
        });

        return () => {
            active = false;
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [ordenId, reloadKey]);

    const entries = useMemo(() => {
        const list = ordenId ? allEntries.filter((e) => e.ordenId === ordenId) : [];
        // Más reciente primero (última entrada arriba).
        return [...list].sort((a, b) => (a.creadoEn < b.creadoEn ? 1 : -1));
    }, [allEntries, ordenId]);

    return {
        entries,
        loading,
        refetch: () => setReloadKey((k) => k + 1),
    };
}
