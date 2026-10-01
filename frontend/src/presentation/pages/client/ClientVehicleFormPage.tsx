import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Calendar, Car, Gauge, Hash } from 'lucide-react';
import { Button } from '@/presentation/components/ui/Button';
import { Input } from '@/presentation/components/ui/Input';
import { GlassCard } from '@/presentation/components/ui/GlassCard';
import { Alert } from '@/presentation/components/ui/Alert';
import { useAuthStore } from '@/infrastructure/stores/useAuthStore';
import { useVehicleStore } from '@/infrastructure/stores/useVehicleStore';
import { getApiErrorMessage, getApiErrorRequestId, isConflictError } from '@/infrastructure/api/errors';

// Límite que sí declara el backend para marca y modelo
// (VehiculoCrear: min_length=1, max_length=60 en MS2).
const MAX_TEXTO_VEHICULO = 60;

/**
 * Año y kilometraje son opcionales en el contrato (`anio`/`kilometraje`:
 * `int | None = None`) y no declaran cotas, así que el formulario acepta el
 * campo vacío. Los topes que se exigían antes (año >= 1980, <= año actual + 1,
 * kilometraje <= 999999) no están en el contrato y quedaban registrados como
 * discrepancia. Solo se mantiene el rechazo de lo que no es un entero
 * negativo, que sí es un dato inválido.
 */
const enteroOpcional = (mensaje: string) =>
    z
    .string()
    .trim()
    .refine((valor) => valor === '' || /^\d+$/.test(valor), mensaje);

// La patente no lleva formato: el backend solo exige `min_length=1` y su propio
// ejemplo es "AB1234".
const vehicleSchema = z.object({
    patent: z.string().trim().min(1, 'Ingrese la patente'),
    brand: z
    .string()
    .trim()
    .min(1, 'Ingrese la marca')
    .max(MAX_TEXTO_VEHICULO, `La marca no puede superar ${MAX_TEXTO_VEHICULO} caracteres`),
    model: z
    .string()
    .trim()
    .min(1, 'Ingrese el modelo')
    .max(MAX_TEXTO_VEHICULO, `El modelo no puede superar ${MAX_TEXTO_VEHICULO} caracteres`),
    year: enteroOpcional('Ingrese un año válido'),
    mileage: enteroOpcional('Ingrese un kilometraje válido'),
});

type VehicleForm = z.infer<typeof vehicleSchema>;

export function ClientVehicleFormPage() {
    const navigate = useNavigate();
    const user = useAuthStore((s) => s.user);
    const { patentExists, addVehicle } = useVehicleStore();
    const [submitError, setSubmitError] = useState<string | null>(null);
    // Referencia de la Gateway para que el usuario pueda pedir ayuda con este
    // registro concreto si el error viene de un 500/502/503/504.
    const [submitRequestId, setSubmitRequestId] = useState<string | null>(null);

    const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
    } = useForm<VehicleForm>({ resolver: zodResolver(vehicleSchema) });

    // Identidad real de la sesión (usuario_id de MS1): la Gateway asigna el
    // cliente desde el JWT y este id se usa para la ficha recién creada.
    const clientId = user?.id;

    const onSubmit = async (data: VehicleForm) => {
    if (!clientId) return;
    setSubmitError(null);
    setSubmitRequestId(null);
    const patent = data.patent.toUpperCase();

    // Los campos opcionales viajan como null, que es lo que el contrato acepta
    // (`anio`/`kilometraje`: int | None). El backend los trata como ausentes y
    // la ficha se muestra como "Sin especificar".
    const year = data.year === '' ? null : Number(data.year);
    const mileage = data.mileage === '' ? null : Number(data.mileage);

    if (patentExists(patent)) {
        setError('patent', { message: 'Ya existe un vehículo registrado con esa patente.' });
        return;
    }

    try {
        await addVehicle({ patent, brand: data.brand, model: data.model, year, mileage }, clientId);
        navigate('/client/vehiculos', { state: { justRegistered: true } });
    } catch (error) {
        // El backend es la autoridad: si la patente ya existe responde 409 con
        // su propio mensaje, y se muestra ese texto en vez de uno inventado
        // aquí, para que el motivo del rechazo sea el que dio el servidor.
        if (isConflictError(error)) {
        setError('patent', { message: getApiErrorMessage(error) });
        } else {
        setSubmitError(getApiErrorMessage(error, 'No pudimos registrar el vehículo. Intente nuevamente.'));
        setSubmitRequestId(getApiErrorRequestId(error));
        }
    }
    };

    return (
    <div className="animate-fade-in flex justify-center">
        <GlassCard className="w-full max-w-[600px] p-10">
        <h2 className="text-2xl font-bold mb-2 text-center flex items-center justify-center gap-3">
            <Car className="w-6 h-6 text-primary-orange" /> Registrar Nuevo Vehículo
        </h2>
        <p className="text-text-muted text-sm text-center mb-8">
            Complete los datos del vehículo. La patente debe ser única en el sistema.
        </p>

        <form onSubmit={handleSubmit(onSubmit)} noValidate>
            <Input
            label="Patente"
            placeholder="AB1234"
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
                label="Año (opcional)"
                type="number"
                icon={<Calendar className="w-5 h-5" />}
                error={errors.year?.message}
                {...register('year')}
            />
            <Input
                label="Kilometraje actual (opcional)"
                type="number"
                icon={<Gauge className="w-5 h-5" />}
                error={errors.mileage?.message}
                {...register('mileage')}
            />
            </div>

            {submitError && (
            <Alert tone="error" className="mb-4 justify-center">
              {submitError}
              {submitRequestId && (
                <span className="block mt-1 font-mono text-xs opacity-80">Referencia: {submitRequestId}</span>
              )}
            </Alert>
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