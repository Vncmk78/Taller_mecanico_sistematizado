import { useNavigate } from 'react-router-dom';
import { Car } from 'lucide-react';
import { GlassCard } from '@/presentation/components/ui/GlassCard';
import { VehicleForm } from '@/presentation/components/vehicles/VehicleForm';
import { useAuthStore } from '@/infrastructure/stores/useAuthStore';
import { useVehicleStore } from '@/infrastructure/stores/useVehicleStore';
import { getApiErrorMessage, isConflictError } from '@/infrastructure/api/errors';

export function ClientVehicleFormPage() {
    const navigate = useNavigate();
    const user = useAuthStore((s) => s.user);
    const { patentExists, addVehicle } = useVehicleStore();

    // Identidad real de la sesión (usuario_id de MS1): la Gateway asigna el
    // cliente desde el JWT y este id se usa para la ficha recién creada.
    const clientId = user?.id;

    return (
    <div className="p-4 sm:p-6 lg:p-10 animate-fade-in flex justify-center">
        <GlassCard className="w-full max-w-[600px] p-6 sm:p-10">
        <h1 className="text-2xl font-bold mb-2 text-center flex items-center justify-center gap-3">
            <Car className="w-6 h-6 text-primary-orange" aria-hidden /> Registrar Nuevo Vehículo
        </h1>
        <p className="text-text-muted text-sm text-center mb-8">
            Complete los datos del vehículo. La patente debe ser única en el sistema.
        </p>

        <VehicleForm
            mode="create"
            submitLabel="Registrar Vehículo"
            onCancel={() => navigate('/client/vehiculos')}
            onSubmit={async (values, { setFieldError }) => {
            if (!clientId) return;

            if (patentExists(values.patent)) {
                setFieldError('patent', 'Ya existe un vehículo registrado con esa patente.');
                return;
            }

            try {
                await addVehicle(
                {
                    patent: values.patent,
                    brand: values.brand,
                    model: values.model,
                    year: values.year,
                    mileage: values.mileage,
                },
                clientId
                );
                navigate('/client/vehiculos', { state: { justRegistered: true } });
            } catch (error) {
                // El backend es la autoridad: si la patente ya existe responde
                // 409 con su propio mensaje y se muestra ese texto en el campo.
                if (isConflictError(error)) {
                setFieldError('patent', getApiErrorMessage(error));
                return;
                }
                throw error;
            }
            }}
        />
        </GlassCard>
    </div>
    );
}
