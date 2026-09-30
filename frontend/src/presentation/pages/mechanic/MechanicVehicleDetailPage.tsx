import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, ClipboardList, SearchX } from 'lucide-react';
import { VehicleInfoPanel } from '@/presentation/components/vehicles/VehicleInfoPanel';
import { OfflineBanner } from '@/presentation/components/vehicles/OfflineBanner';
import { Alert } from '@/presentation/components/ui/Alert';
import { EmptyState } from '@/presentation/components/ui/EmptyState';
import { ErrorState } from '@/presentation/components/ui/ErrorState';
import { LoadingState } from '@/presentation/components/ui/LoadingState';
import { RetryButton } from '@/presentation/components/ui/RetryButton';
import { useVehicleDetail } from '@/presentation/hooks/useVehicleDetail';
import { useVehicleStore } from '@/infrastructure/stores/useVehicleStore';
import { vehicleService } from '@/infrastructure/api/VehicleService';

export function MechanicVehicleDetailPage() {
    const { id } = useParams<{ id: string }>();
    const { vehicle, loading, notFound, failed, refetch } = useVehicleDetail(id, (vid) =>
    vehicleService.getVehicleById(vid)
    );
    const { isOffline, error } = useVehicleStore();
    // El alcance no se comprueba en el cliente: la Gateway responde 404 al rol
    // Mecánico cuando el vehículo no está entre sus órdenes asignadas, y offline
    // solo se muestra lo que quedó en la caché de esa misma respuesta.

    if (loading) {
    return <LoadingState message="Cargando ficha del vehículo..." className="p-10" />;
    }

    // El fetch falló y no hay copia local: se muestra un error reintentable en
    // lugar de un "no encontrado" que no es cierto.
    if (failed) {
    return (
        <ErrorState
            className="p-10"
            title="No se pudo cargar la ficha del vehículo"
            message={error}
            onRetry={refetch}
            action={
            <Link to="/mechanic/vehiculos" className="text-primary-blue text-sm font-medium no-underline hover:underline">
                Volver
            </Link>
            }
        />
    );
    }

    if (!vehicle || notFound) {
    return (
        <EmptyState
            className="p-10"
            icon={SearchX}
            title="Vehículo no encontrado o no está entre sus órdenes asignadas."
            description="Verifique la patente o que el vehículo siga asignado a su cuenta."
            action={
            <Link to="/mechanic/vehiculos" className="text-primary-blue text-sm font-medium no-underline hover:underline">
                Volver
            </Link>
            }
        />
    );
    }

    return (
    <div className="animate-fade-in p-10">
        <Link
        to="/mechanic/vehiculos"
        className="inline-flex items-center gap-2 text-text-muted hover:text-primary-blue mb-6 no-underline"
        >
        <ArrowLeft className="w-4 h-4" /> Volver a vehículos asignados
        </Link>

        {isOffline && <OfflineBanner message={error} onRetry={refetch} className="mb-6" />}

        {/* Error del servidor con copia local en caché: se conserva la ficha y se avisa. */}
        {!isOffline && error && (
        <Alert tone="error" className="mb-6" action={<RetryButton tone="error" onClick={refetch} />}>
            {error} Se muestran los últimos datos disponibles.
        </Alert>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-[1fr_1.4fr] gap-6">
        <VehicleInfoPanel
            vehicle={vehicle}
            ownerLabel={vehicle.clientId ? `Cliente #${vehicle.clientId}` : undefined}
          />
        <div className="card">
            <h3 className="text-xl font-semibold flex items-center gap-2 mb-4 pb-4 border-b border-border-custom">
            <ClipboardList className="w-5 h-5 text-text-muted" />
            Historial de Órdenes
            </h3>
            <p className="text-text-muted text-sm">
            El historial completo se integrará junto con la Gestión de Órdenes (próxima misión).
            </p>
        </div>
        </div>
    </div>
    );
}