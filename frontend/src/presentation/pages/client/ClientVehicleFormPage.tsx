import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { AlertCircle, Calendar, Car, Gauge, Hash } from 'lucide-react';
import { Button } from '@/presentation/components/ui/Button';
import { Input } from '@/presentation/components/ui/Input';
import { GlassCard } from '@/presentation/components/ui/GlassCard';
import { useAuthStore } from '@/infrastructure/stores/useAuthStore';
import { useVehicleStore } from '@/infrastructure/stores/useVehicleStore';
import { isConflictError } from '@/infrastructure/api/errors';
import { CURRENT_CLIENT_ID } from '@/infrastructure/mocks/vehicles.mock';

const PATENT_REGEX = /^[A-Za-z]{4}-\d{2}$/;
const currentYear = new Date().getFullYear();

const vehicleSchema = z.object({
    patent: z
    .string()
    .trim()
    .regex(PATENT_REGEX, 'Formato inválido. Use 4 letras y 2 números, ej: ABCD-12'),
    brand: z.string().trim().min(2, 'Ingrese la marca'),
    model: z.string().trim().min(1, 'Ingrese el modelo'),
    year: z.coerce
    .number({ invalid_type_error: 'Ingrese un año válido' })
    .int()
    .min(1980, 'Ingrese un año válido')
    .max(currentYear + 1, `El año no puede ser mayor a ${currentYear + 1}`),
    mileage: z.coerce
    .number({ invalid_type_error: 'Ingrese un kilometraje válido' })
    .int()
    .min(0, 'El kilometraje no puede ser negativo')
    .max(999999, 'Verifique el kilometraje ingresado'),
});

type VehicleForm = z.infer<typeof vehicleSchema>;

export function ClientVehicleFormPage() {
    const navigate = useNavigate();
    const user = useAuthStore((s) => s.user);
    const { patentExists, addVehicle } = useVehicleStore();
    const [submitError, setSubmitError] = useState<string | null>(null);

    const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
    } = useForm<VehicleForm>({ resolver: zodResolver(vehicleSchema) });

    const clientId = user?.id ?? CURRENT_CLIENT_ID;

    const onSubmit = async (data: VehicleForm) => {
    setSubmitError(null);
    const patent = data.patent.toUpperCase();

    if (patentExists(patent)) {
        setError('patent', { message: 'Ya existe un vehículo registrado con esa patente.' });
        return;
    }

    try {
        await addVehicle({ ...data, patent }, clientId);
        navigate('/client/vehiculos', { state: { justRegistered: true } });
    } catch (error) {
        if (isConflictError(error)) {
        setError('patent', { message: 'Ya existe un vehículo registrado con esa patente.' });
        } else {
        setSubmitError('No pudimos registrar el vehículo. Intente nuevamente.');
        }
    }
    };

    return (
    <div className="animate-fade-in flex justify-center">
        <GlassCard className="w-full max-w-[600px] p-10">
        <h2 className="text-2xl font-bold mb-2 text-center flex items-center justify-center gap-3">
            <Car className="w-6 h-6 text-primary-red" /> Registrar Nuevo Vehículo
        </h2>
        <p className="text-text-muted text-sm text-center mb-8">
            Complete los datos del vehículo. La patente debe ser única en el sistema.
        </p>

        <form onSubmit={handleSubmit(onSubmit)} noValidate>
            <Input
            label="Patente"
            placeholder="ABCD-12"
            icon={<Hash className="w-5 h-5" />}
            error={errors.patent?.message}
            {...register('patent')}
            />
            <Input
            label="Marca"
            placeholder="Ford"
            icon={<Car className="w-5 h-5" />}
            error={errors.brand?.message}
            {...register('brand')}
            />
            <Input
            label="Modelo"
            placeholder="Fiesta"
            error={errors.model?.message}
            {...register('model')}
            />
            <div className="grid grid-cols-2 gap-4">
            <Input
                label="Año"
                type="number"
                icon={<Calendar className="w-5 h-5" />}
                error={errors.year?.message}
                {...register('year')}
            />
            <Input
                label="Kilometraje actual"
                type="number"
                icon={<Gauge className="w-5 h-5" />}
                error={errors.mileage?.message}
                {...register('mileage')}
            />
            </div>

            {submitError && (
            <div className="flex items-center gap-2 mb-4 text-status-red text-sm bg-status-red/10 border border-status-red/40 rounded-lg px-4 py-3">
                <AlertCircle className="w-4 h-4 shrink-0" />
                {submitError}
            </div>
            )}

            <div className="flex gap-3 mt-2">
            <Button
                type="button"
                variant="secondary"
                className="flex-1"
                onClick={() => navigate('/client/vehiculos')}
            >
                Cancelar
            </Button>
            <Button type="submit" isLoading={isSubmitting} className="flex-[2]">
                Registrar Vehículo
            </Button>
            </div>
        </form>
        </GlassCard>
    </div>
    );
}