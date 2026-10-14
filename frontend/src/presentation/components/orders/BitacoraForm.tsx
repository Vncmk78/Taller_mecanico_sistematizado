import { useEffect, useState } from 'react';
import { useFieldArray, useForm, useWatch } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Plus, Trash2 } from 'lucide-react';
import { z } from 'zod';
import type { BitacoraEntradaCrear, BitacoraEntry } from '@/domain/entities/Bitacora';
import { getApiErrorMessage, isOfflineError } from '@/infrastructure/api/errors';
import { orderService } from '@/infrastructure/api/OrderService';
import { useOrderBitacoraStore } from '@/infrastructure/stores/useOrderBitacoraStore';
import { useOrderStore } from '@/infrastructure/stores/useOrderStore';
import { Alert } from '@/presentation/components/ui/Alert';
import { Button } from '@/presentation/components/ui/Button';
import { useToast } from '@/presentation/components/ui/toastContext';

const INPUT_CLASS =
    'w-full py-2.5 px-3 bg-surface border border-border-custom rounded-lg text-text-main text-sm outline-none focus:border-primary-blue';

const repuestoSchema = z.object({
    nombre: z
        .string()
        .trim()
        .min(1, 'Indica el nombre del repuesto')
        .max(120, 'Máximo 120 caracteres'),
    cantidad: z
        .string()
        .trim()
        .min(1, 'Indica la cantidad')
        .regex(/^\d+$/, 'Cantidad inválida')
        .refine((valor) => Number(valor) > 0, 'La cantidad debe ser mayor que 0'),
});

const bitacoraSchema = z.object({
    tipo: z.enum(['observacion', 'accion']),
    descripcion: z.string().trim().min(1, 'Describe la observación o la acción realizada'),
    repuestos: z.array(repuestoSchema).max(50, 'Máximo 50 repuestos por entrada'),
});

type BitacoraFormValues = z.infer<typeof bitacoraSchema>;

interface BitacoraFormProps {
    ordenId: string;
    onSuccess?: (entry: BitacoraEntry) => void;
    className?: string;
}

/**
 * Formulario del mecánico para registrar una entrada de bitácora: una
 * observación (nota libre) o una acción (trabajo realizado) que puede declarar
 * los repuestos utilizados. Valida con Zod antes de enviar y publica la entrada
 * confirmada en la caché compartida. El selector oculta y limpia los repuestos
 * al elegir "observación": una observación nunca registra repuestos.
 */
export function BitacoraForm({ ordenId, onSuccess, className }: BitacoraFormProps) {
    const addEntry = useOrderBitacoraStore((s) => s.addEntry);
    const isOffline = useOrderStore((s) => s.isOffline);
    const { showToast } = useToast();
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState('');

    const {
        register,
        control,
        handleSubmit,
        reset,
        formState: { errors },
    } = useForm<BitacoraFormValues>({
        resolver: zodResolver(bitacoraSchema),
        defaultValues: { tipo: 'accion', descripcion: '', repuestos: [] },
        mode: 'onSubmit',
    });

    const { fields, append, remove, replace } = useFieldArray({ control, name: 'repuestos' });
    const tipoSeleccionado = useWatch({ control, name: 'tipo' });

    useEffect(() => {
        if (tipoSeleccionado === 'observacion') {
            replace([]);
        }
    }, [tipoSeleccionado, replace]);

    const submit = handleSubmit(async (values) => {
        setSubmitting(true);
        setError('');
        try {
            const entrada: BitacoraEntradaCrear = {
                tipo: values.tipo,
                descripcion: values.descripcion.trim(),
                repuestos:
                    values.tipo === 'accion'
                        ? values.repuestos.map((repuesto) => ({
                              nombre: repuesto.nombre.trim(),
                              cantidad: Number(repuesto.cantidad),
                          }))
                        : [],
            };
            const entry = await orderService.registrarBitacora(ordenId, entrada);
            addEntry(entry);
            showToast('Entrada registrada en la bitácora.', 'success');
            reset({ tipo: 'accion', descripcion: '', repuestos: [] });
            onSuccess?.(entry);
        } catch (err) {
            setError(
                isOfflineError(err)
                    ? 'Sin conexión. La bitácora necesita conexión para registrarse.'
                    : getApiErrorMessage(err)
            );
        } finally {
            setSubmitting(false);
        }
    });

    return (
        <form onSubmit={submit} className={className} noValidate>
            <h4 className="mb-4 font-semibold">Registrar entrada</h4>

            {isOffline && (
                <Alert tone="warning" className="mb-4">
                    Sin conexión. No se puede registrar una entrada hasta recuperar la conexión.
                </Alert>
            )}
            {error && (
                <Alert tone="error" className="mb-4">
                    {error}
                </Alert>
            )}

            <label className="mb-4 block text-sm">
                <span className="mb-1 block text-text-muted">Tipo</span>
                <select aria-label="Tipo de entrada" className={INPUT_CLASS} {...register('tipo')}>
                    <option value="accion">Acción</option>
                    <option value="observacion">Observación</option>
                </select>
            </label>

            <label className="mb-4 block text-sm">
                <span className="mb-1 block text-text-muted">Descripción</span>
                <textarea
                    rows={3}
                    aria-label="Descripción de la entrada"
                    aria-invalid={errors.descripcion ? true : undefined}
                    placeholder="Describe la observación o la acción realizada..."
                    className={`${INPUT_CLASS} ${errors.descripcion ? 'border-status-red' : ''}`}
                    {...register('descripcion')}
                />
                {errors.descripcion && (
                    <p role="alert" className="mt-1 text-sm text-status-red">
                        {errors.descripcion.message}
                    </p>
                )}
            </label>

            {tipoSeleccionado === 'accion' && (
                <fieldset className="mb-4">
                    <legend className="mb-2 text-sm text-text-muted">
                        Repuestos utilizados (opcional)
                    </legend>
                    <div className="space-y-3">
                        {fields.map((field, index) => (
                            <div key={field.id} className="flex items-start gap-2">
                                <div className="flex-1">
                                    <input
                                        aria-label={`Nombre del repuesto ${index + 1}`}
                                        aria-invalid={errors.repuestos?.[index]?.nombre ? true : undefined}
                                        placeholder="Nombre del repuesto"
                                        className={INPUT_CLASS}
                                        {...register(`repuestos.${index}.nombre`)}
                                    />
                                    {errors.repuestos?.[index]?.nombre && (
                                        <p role="alert" className="mt-1 text-sm text-status-red">
                                            {errors.repuestos[index]?.nombre?.message}
                                        </p>
                                    )}
                                </div>
                                <div className="w-24">
                                    <input
                                        type="number"
                                        min={1}
                                        inputMode="numeric"
                                        aria-label={`Cantidad del repuesto ${index + 1}`}
                                        aria-invalid={errors.repuestos?.[index]?.cantidad ? true : undefined}
                                        className={INPUT_CLASS}
                                        {...register(`repuestos.${index}.cantidad`)}
                                    />
                                    {errors.repuestos?.[index]?.cantidad && (
                                        <p role="alert" className="mt-1 text-xs text-status-red">
                                            {errors.repuestos[index]?.cantidad?.message}
                                        </p>
                                    )}
                                </div>
                                <Button
                                    variant="danger"
                                    className="!px-3 !py-2.5"
                                    aria-label={`Quitar repuesto ${index + 1}`}
                                    onClick={() => remove(index)}
                                >
                                    <Trash2 className="h-4 w-4" aria-hidden />
                                </Button>
                            </div>
                        ))}
                    </div>
                    {fields.length < 50 && (
                        <Button
                            variant="secondary"
                            className="!px-4 !py-2 mt-3"
                            onClick={() => append({ nombre: '', cantidad: '1' })}
                        >
                            <span className="inline-flex items-center gap-2">
                                <Plus className="h-4 w-4" aria-hidden />
                                Agregar repuesto
                            </span>
                        </Button>
                    )}
                </fieldset>
            )}

            <Button type="submit" variant="primary" className="mt-2" isLoading={submitting} disabled={isOffline}>
                Registrar entrada
            </Button>
        </form>
    );
}
