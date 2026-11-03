import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { X } from 'lucide-react';
import { Button } from '@/presentation/components/ui/Button';
import { Input } from '@/presentation/components/ui/Input';
import type { Repuesto } from '@/domain/entities/Repuesto';
import type { Proveedor } from '@/domain/entities/Proveedor';

const schema = z.object({
    nombre: z.string().trim().min(1, 'Ingrese el nombre').max(120, 'Máximo 120 caracteres'),
    proveedorId: z.coerce.number().int().positive('Seleccione un proveedor'),
    stockInicial: z.coerce.number().int().min(0, 'Stock no puede ser negativo').optional(),
    umbralParticular: z
        .string()
        .trim()
        .refine((v) => v === '' || /^\d+$/.test(v), 'Umbral inválido')
        .optional(),
});

type FormValues = z.infer<typeof schema>;

interface Props {
    open: boolean;
    initial?: Repuesto | null;
    proveedores: Proveedor[];
    isSubmitting?: boolean;
    error?: string | null;
    onSubmit: (values: { proveedorId: number; nombre: string; stockInicial?: number; umbralParticular: number | null }) => void;
    onClose: () => void;
}

export function RepuestoFormDialog({ open, initial, proveedores, isSubmitting, error, onSubmit, onClose }: Props) {
    const {
        register,
        handleSubmit,
        reset,
        formState: { errors },
    } = useForm<FormValues>({
        resolver: zodResolver(schema),
        defaultValues: {
            nombre: initial?.nombre ?? '',
            proveedorId: initial?.proveedorId ?? (proveedores[0]?.proveedorId ?? 0),
            stockInicial: 0,
            umbralParticular: initial?.umbralParticular != null ? String(initial.umbralParticular) : '',
        },
    });

    useEffect(() => {
        if (!open) return;
        reset({
            nombre: initial?.nombre ?? '',
            proveedorId: initial?.proveedorId ?? (proveedores[0]?.proveedorId ?? 0),
            stockInicial: 0,
            umbralParticular: initial?.umbralParticular != null ? String(initial.umbralParticular) : '',
        });
    }, [open, initial, proveedores, reset]);

    if (!open) return null;

    const submit = (values: FormValues) => {
        onSubmit({
            proveedorId: values.proveedorId,
            nombre: values.nombre,
            stockInicial: initial ? undefined : (values.stockInicial ?? 0),
            umbralParticular: values.umbralParticular ? Number(values.umbralParticular) : null,
        });
    };

    return (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
            <div className="card w-full max-w-[520px] p-6 relative">
                <button type="button" aria-label="Cerrar" onClick={onClose} className="absolute right-4 top-4 text-text-muted">
                    <X className="w-5 h-5" />
                </button>
                <h3 className="text-xl font-bold mb-4">{initial ? 'Editar repuesto' : 'Nuevo repuesto'}</h3>
                <form onSubmit={handleSubmit(submit)} className="space-y-4">
                    <Input label="Nombre" {...register('nombre')} error={errors.nombre?.message} />
                    <label className="block">
                        <span className="block mb-2 text-sm text-text-muted">Proveedor</span>
                        <select
                            {...register('proveedorId')}
                            className="w-full bg-surface border border-border-custom rounded-lg px-3 py-2 text-text-main text-sm"
                        >
                            {proveedores.map((p) => (
                                <option key={p.proveedorId} value={p.proveedorId}>{p.nombre}</option>
                            ))}
                        </select>
                        {errors.proveedorId && <p className="text-status-red text-xs mt-1">{errors.proveedorId.message}</p>}
                    </label>
                    {!initial && (
                        <Input label="Stock inicial" type="number" {...register('stockInicial')} error={errors.stockInicial?.message} />
                    )}
                    <Input label="Umbral particular (vacío = general)" type="number" {...register('umbralParticular')} error={errors.umbralParticular?.message} />
                    {error && <p className="text-status-red text-sm">{error}</p>}
                    <div className="flex justify-end gap-3">
                        <Button type="button" variant="secondary" onClick={onClose}>Cancelar</Button>
                        <Button type="submit" isLoading={isSubmitting}>{initial ? 'Guardar' : 'Crear'}</Button>
                    </div>
                </form>
            </div>
        </div>
    );
}