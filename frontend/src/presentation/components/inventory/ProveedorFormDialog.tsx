import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { X } from 'lucide-react';
import { Button } from '@/presentation/components/ui/Button';
import { Input } from '@/presentation/components/ui/Input';
import type { Proveedor, TipoDistribuidor } from '@/domain/entities/Proveedor';

const schema = z.object({
    nombre: z.string().trim().min(1, 'Ingrese el nombre').max(120, 'Máximo 120 caracteres'),
    contacto: z.string().trim().min(1, 'Ingrese el contacto').max(200, 'Máximo 200 caracteres'),
    tipoDistribuidor: z.enum(['oficial', 'generico']),
});

type FormValues = z.infer<typeof schema>;

interface Props {
    open: boolean;
    initial?: Proveedor | null;
    isSubmitting?: boolean;
    error?: string | null;
    onSubmit: (values: { nombre: string; contacto: string; tipoDistribuidor: TipoDistribuidor }) => void;
    onClose: () => void;
}

export function ProveedorFormDialog({ open, initial, isSubmitting, error, onSubmit, onClose }: Props) {
    const {
        register,
        handleSubmit,
        reset,
        formState: { errors },
    } = useForm<FormValues>({
        resolver: zodResolver(schema),
        defaultValues: {
            nombre: initial?.nombre ?? '',
            contacto: initial?.contacto ?? '',
            tipoDistribuidor: initial?.tipoDistribuidor ?? 'generico',
        },
    });

    useEffect(() => {
        if (!open) return;
        reset({
            nombre: initial?.nombre ?? '',
            contacto: initial?.contacto ?? '',
            tipoDistribuidor: initial?.tipoDistribuidor ?? 'generico',
        });
    }, [open, initial, reset]);

    if (!open) return null;

    return (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
            <div className="card w-full max-w-[520px] p-6 relative">
                <button type="button" aria-label="Cerrar" onClick={onClose} className="absolute right-4 top-4 text-text-muted">
                    <X className="w-5 h-5" />
                </button>
                <h3 className="text-xl font-bold mb-4">{initial ? 'Editar proveedor' : 'Nuevo proveedor'}</h3>
                <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
                    <Input label="Nombre" {...register('nombre')} error={errors.nombre?.message} />
                    <Input label="Contacto" {...register('contacto')} error={errors.contacto?.message} />
                    <label className="block">
                        <span className="block mb-2 text-sm text-text-muted">Tipo</span>
                        <select
                            {...register('tipoDistribuidor')}
                            className="w-full bg-surface border border-border-custom rounded-lg px-3 py-2 text-text-main text-sm"
                        >
                            <option value="oficial">Oficial</option>
                            <option value="generico">Genérico</option>
                        </select>
                        {errors.tipoDistribuidor && <p className="text-status-red text-xs mt-1">{errors.tipoDistribuidor.message}</p>}
                    </label>
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