import { useEffect, useState } from 'react';

export interface UseCollectionDetailResult<T> {
    item: T | undefined;
    loading: boolean;
    notFound: boolean;
    /** El fetch falló y no hay copia local: la vista debe mostrar un estado de error reintentable. */
    failed: boolean;
    refetch: () => void;
}

/**
 * Encapsula la carga de un item de una colección por id: intenta la API real vía
 * el loader recibido y distingue "no existe" (404 confirmado por el backend),
 * "no se pudo confirmar" con copia local (se muestra lo que haya en caché) de
 * "no se pudo confirmar" sin copia local (failed).
 * Compartido por los hooks de detalle de órdenes y vehículos.
 */
export function useCollectionDetail<T extends { id: string }>(options: {
    id: string | undefined;
    items: T[];
    fetchById: (id: string, loader: (id: string) => Promise<T>) => Promise<{ notFound: boolean; failed: boolean }>;
    loader: (id: string) => Promise<T>;
}): UseCollectionDetailResult<T> {
    const { id, items, fetchById, loader } = options;
    const [loading, setLoading] = useState(true);
    const [notFound, setNotFound] = useState(false);
    const [failed, setFailed] = useState(false);
    const [reloadKey, setReloadKey] = useState(0);

    useEffect(() => {
        if (!id) {
            setLoading(false);
            setNotFound(true);
            setFailed(false);
            return;
        }
        let active = true;
        setLoading(true);
        setNotFound(false);
        setFailed(false);

        fetchById(id, loader).then((result) => {
            if (!active) return;
            setNotFound(result.notFound);
            setFailed(result.failed);
            setLoading(false);
        });

        return () => {
            active = false;
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [id, reloadKey]);

    return {
        item: id ? items.find((cached) => cached.id === id) : undefined,
        loading,
        notFound,
        failed,
        refetch: () => setReloadKey((key) => key + 1),
    };
}