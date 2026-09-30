import { useEffect, useState } from 'react';

export interface UseCollectionDetailResult<T> {
    item: T | undefined;
    loading: boolean;
    notFound: boolean;
    refetch: () => void;
}

/**
 * Encapsula la carga de un item de una colección por id: intenta la API real vía
 * el loader recibido y distingue "no existe" (404 confirmado por el backend) de
 * "no se pudo confirmar" (error de red, se muestra lo que haya en caché).
 * Compartido por los hooks de detalle de órdenes y vehículos.
 */
export function useCollectionDetail<T extends { id: string }>(options: {
    id: string | undefined;
    items: T[];
    fetchById: (id: string, loader: (id: string) => Promise<T>) => Promise<{ notFound: boolean }>;
    loader: (id: string) => Promise<T>;
}): UseCollectionDetailResult<T> {
    const { id, items, fetchById, loader } = options;
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

        fetchById(id, loader).then((result) => {
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
        item: id ? items.find((cached) => cached.id === id) : undefined,
        loading,
        notFound,
        refetch: () => setReloadKey((key) => key + 1),
    };
}