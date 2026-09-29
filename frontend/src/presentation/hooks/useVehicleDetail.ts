import { useEffect, useState } from 'react';
import type { Vehicle } from '@/domain/entities/Vehicle';
import { useVehicleStore } from '@/infrastructure/stores/useVehicleStore';

interface UseVehicleDetailResult {
    vehicle: Vehicle | undefined;
    loading: boolean;
    notFound: boolean;
    refetch: () => void;
}

/**
 * Encapsula la carga de un vehículo por id: intenta la API real vía el loader
 * recibido y distingue "no existe" (404 confirmado por el backend) de "no se
 * pudo confirmar" (error de red, se muestra lo que haya en caché). Reutilizado
 * por las páginas de ficha técnica de los 3 portales.
 */
export function useVehicleDetail(
    id: string | undefined,
    loader: (id: string) => Promise<Vehicle>
): UseVehicleDetailResult {
    const vehicles = useVehicleStore((s) => s.vehicles);
    const fetchVehicleById = useVehicleStore((s) => s.fetchVehicleById);
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

    fetchVehicleById(id, loader).then((result) => {
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
    vehicle: id ? vehicles.find((v) => v.id === id) : undefined,
    loading,
    notFound,
    refetch: () => setReloadKey((k) => k + 1),
    };
}