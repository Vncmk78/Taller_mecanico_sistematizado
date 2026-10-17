import type { Vehicle } from '@/domain/entities/Vehicle';
import { useVehicleStore } from '@/infrastructure/stores/useVehicleStore';
import { useCollectionDetail } from '@/presentation/hooks/useCollectionDetail';

export interface UseVehicleDetailResult {
    vehicle: Vehicle | undefined;
    loading: boolean;
    notFound: boolean;
    failed: boolean;
    refetch: () => void;
}

/**
 * Encapsula la carga de un vehículo por id vía useCollectionDetail. Reutilizado
 * por las páginas de ficha técnica de los 3 portales.
 */
export function useVehicleDetail(
    id: string | undefined,
    loader: (id: string) => Promise<Vehicle>
): UseVehicleDetailResult {
    const vehicles = useVehicleStore((s) => s.vehicles);
    const fetchVehicleById = useVehicleStore((s) => s.fetchVehicleById);
    const { item, loading, notFound, failed, refetch } = useCollectionDetail<Vehicle>({
        id,
        items: vehicles,
        fetchById: fetchVehicleById,
        loader,
    });
    return { vehicle: item, loading, notFound, failed, refetch };
}