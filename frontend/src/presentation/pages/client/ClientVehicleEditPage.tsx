import { Link, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, Car, SearchX } from 'lucide-react';
import { EmptyState } from '@/presentation/components/ui/EmptyState';
import { ErrorState } from '@/presentation/components/ui/ErrorState';
import { GlassCard } from '@/presentation/components/ui/GlassCard';
import { LoadingState } from '@/presentation/components/ui/LoadingState';
import { VehicleForm } from '@/presentation/components/vehicles/VehicleForm';
import { useVehicleDetail } from '@/presentation/hooks/useVehicleDetail';
import { vehicleService } from '@/infrastructure/api/VehicleService';
import { useAuthStore } from '@/infrastructure/stores/useAuthStore';
import { useVehicleStore } from '@/infrastructure/stores/useVehicleStore';

export function ClientVehicleEditPage() {
    const { id } = useParams<{ id: string }>();
    const navigate = useNavigate();
    const user = useAuthStore((s) => s.user);
    const clientId = user?.id;
    const { updateVehicle, error, requestId } = useVehicleStore();
    const { vehicle, loading, notFound, failed, refetch } = useVehicleDetail(id, (vid) =>
    vehicleService.getVehicleById(vid, clientId)
    );

    if (loading) {
    return <LoadingState message="Cargando datos del vehículo..." className="p-4 sm:p-6 lg:p-10" />;
    }

    if (failed) {
    return (
        <ErrorState
        className="p-4 sm:p-6 lg:p-10"
        title="No se pudo cargar el vehículo para editarlo"
        message={error}
        requestId={requestId}
        onRetry={refetch}
        action={
            <Link to="/client/vehiculos" className="text-primary-blue text-sm font-medium no-underline hover:underline">
            Volver a mis vehículos
            </Link>
        }
        />
    );
    }

    // La caché es compartida entre portales: se exige pertenencia antes de
    // permitir editar el vehículo.
    if (!vehicle || notFound || vehicle.clientId !== clientId) {
    return (
        <EmptyState
        className="p-4 sm:p-6 lg:p-10"
        icon={SearchX}
        title="Vehículo no encontrado o no pertenece a su cuenta."
        description="Verifique la patente o que el vehículo siga registrado a su nombre."
        action={
            <Link to="/client/vehiculos" className="text-primary-blue text-sm font-medium no-underline hover:underline">
            Volver a mis vehículos
            </Link>
        }
        />
    );
    }

    return (
    <div className="p-4 sm:p-6 lg:p-10 animate-fade-in flex justify-center">
        <GlassCard className="w-full max-w-[600px] p-6 sm:p-10">
        <Link
            to={`/client/vehiculos/${vehicle.id}`}
            className="inline-flex items-center gap-2 text-text-muted hover:text-primary-blue mb-6 no-underline"
        >
            <ArrowLeft className="w-4 h-4" aria-hidden /> Volver a la ficha del vehículo
        </Link>

        <h1 className="text-2xl font-bold mb-2 text-center flex items-center justify-center gap-3">
            <Car className="w-6 h-6 text-primary-orange" aria-hidden /> Editar Vehículo
        </h1>
        <p className="text-text-muted text-sm text-center mb-8">
            Actualice los datos del vehículo. La patente no se puede modificar.
        </p>

        <VehicleForm
            mode="edit"
            initialValues={{
            patent: vehicle.patent,
            brand: vehicle.brand,
            model: vehicle.model,
            year: vehicle.year,
            mileage: vehicle.mileage,
            }}
            submitLabel="Guardar Cambios"
            onCancel={() => navigate(`/client/vehiculos/${vehicle.id}`)}
            onSubmit={async (values) => {
            await updateVehicle(
                vehicle.id,
                {
                brand: values.brand,
                model: values.model,
                year: values.year,
                mileage: values.mileage,
                },
                clientId
            );
            navigate(`/client/vehiculos/${vehicle.id}`, { state: { justUpdated: true } });
            }}
        />
        </GlassCard>
    </div>
    );
}
