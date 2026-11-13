import { useMemo, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Calendar, Car, Gauge, Hash } from 'lucide-react';
import { Alert } from '@/presentation/components/ui/Alert';
import { Button } from '@/presentation/components/ui/Button';
import { Input } from '@/presentation/components/ui/Input';
import { getApiErrorMessage, getApiErrorRequestId } from '@/infrastructure/api/errors';

// Límite que sí declara el backend para marca y modelo
// (VehiculoCrear: min_length=1, max_length=60 en MS2).
const MAX_TEXTO_VEHICULO = 60;

/**
 * Año y kilometraje son opcionales en el contrato (`anio`/`kilometraje`:
 * `int | None = None`) y no declaran cotas, así que el formulario acepta el
 * campo vacío. Solo se rechaza lo que no es un entero no negativo.
 */
const enteroOpcional = (mensaje: string) =>
    z
    .string()
    .trim()
    .refine((valor) => valor === '' || /^\d+$/.test(valor), mensaje);

/**
 * La patente solo es obligatoria al crear: `VehiculoActualizar` no la incluye
 * y el formulario de edición la muestra de solo lectura.
 */
function crearEsquema(mode: 'create' | 'edit') {
    return z.object({
    patent:
        mode === 'create'
        ? z.string().trim().min(1, 'Ingrese la patente')
        : z.string(),
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
}

type VehicleFormFields = z.infer<ReturnType<typeof crearEsquema>>;

export interface VehicleFormValues {
    patent: string;
    brand: string;
    model: string;
    year: number | null;
    mileage: number | null;
}

export type VehicleFormField = 'patent' | 'brand' | 'model' | 'year' | 'mileage';

interface VehicleFormProps {
    mode: 'create' | 'edit';
    initialValues?: Partial<VehicleFormValues>;
    submitLabel: string;
    onSubmit: (
    values: VehicleFormValues,
    controls: { setFieldError: (field: VehicleFormField, message: string) => void }
    ) => Promise<void>;
    onCancel: () => void;
}

/**
 * Formulario compartido por el alta y la edición de vehículos del portal
 * Cliente. Mantiene las mismas validaciones y mensajes que el contrato de MS2
 * en ambos flujos.
 */
export function VehicleForm({
    mode,
    initialValues,
    submitLabel,
    onSubmit,
    onCancel,
}: VehicleFormProps) {
    const schema = useMemo(() => crearEsquema(mode), [mode]);
    const [submitError, setSubmitError] = useState<string | null>(null);
    // Referencia de la Gateway para que el usuario pueda pedir ayuda con esta
    // operación concreta si el error viene de un 500/502/503/504.
    const [submitRequestId, setSubmitRequestId] = useState<string | null>(null);

    const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
    } = useForm<VehicleFormFields>({
    resolver: zodResolver(schema),
    defaultValues: {
        patent: initialValues?.patent ?? '',
        brand: initialValues?.brand ?? '',
        model: initialValues?.model ?? '',
        // 0 significa "sin dato" en el dominio (VehicleService normaliza null a 0).
        year: initialValues?.year ? String(initialValues.year) : '',
        mileage: initialValues?.mileage ? String(initialValues.mileage) : '',
    },
    });

    const submit = async (data: VehicleFormFields) => {
    setSubmitError(null);
    setSubmitRequestId(null);

    const values: VehicleFormValues = {
        patent: data.patent.trim().toUpperCase(),
        brand: data.brand.trim(),
        model: data.model.trim(),
        year: data.year === '' ? null : Number(data.year),
        mileage: data.mileage === '' ? null : Number(data.mileage),
    };

    try {
        await onSubmit(values, {
        setFieldError: (field, message) => setError(field, { message }),
        });
    } catch (error) {
        setSubmitError(
        getApiErrorMessage(
            error,
            mode === 'create'
            ? 'No pudimos registrar el vehículo. Intente nuevamente.'
            : 'No pudimos actualizar el vehículo. Intente nuevamente.'
        )
        );
        setSubmitRequestId(getApiErrorRequestId(error));
    }
    };

    return (
    <form onSubmit={handleSubmit(submit)} noValidate>
        <Input
        label={mode === 'edit' ? 'Patente (no editable)' : 'Patente'}
        placeholder="AB1234"
        icon={<Hash className="w-5 h-5" />}
        error={errors.patent?.message}
        hint={mode === 'edit' ? 'La patente no se puede modificar.' : undefined}
        required={mode === 'create'}
        readOnly={mode === 'edit'}
        {...register('patent')}
        />
        <Input
        label="Marca"
        placeholder="Ford"
        icon={<Car className="w-5 h-5" />}
        error={errors.brand?.message}
        required
        {...register('brand')}
        />
        <Input
        label="Modelo"
        placeholder="Fiesta"
        error={errors.model?.message}
        required
        {...register('model')}
        />
        <div className="grid grid-cols-2 gap-4">
        <Input
            label="Año (opcional)"
            type="number"
            inputMode="numeric"
            icon={<Calendar className="w-5 h-5" />}
            error={errors.year?.message}
            {...register('year')}
        />
        <Input
            label="Kilometraje actual (opcional)"
            type="number"
            inputMode="numeric"
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
        <Button type="button" variant="secondary" className="flex-1" onClick={onCancel}>
            Cancelar
        </Button>
        <Button type="submit" isLoading={isSubmitting} className="flex-[2]">
            {submitLabel}
        </Button>
        </div>
    </form>
    );
}
