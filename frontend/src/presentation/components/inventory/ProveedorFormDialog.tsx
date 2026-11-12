import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Button } from '@/presentation/components/ui/Button';
import { FormActions } from '@/presentation/components/ui/FormActions';
import { FormModal } from '@/presentation/components/ui/FormModal';
import { Input } from '@/presentation/components/ui/Input';
import { Select } from '@/presentation/components/ui/Select';
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
        <FormModal
            open={open}
            title={initial ? 'Editar proveedor' : 'Nuevo proveedor'}
            onClose={onClose}
        >
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
                <Input label="Nombre" {...register('nombre')} error={errors.nombre?.message} />
                <Input label="Contacto" {...register('contacto')} error={errors.contacto?.message} />
                <Select label="Tipo" {...register('tipoDistribuidor')} error={errors.tipoDistribuidor?.message}>
                    <option value="oficial">Oficial</option>
                    <option value="generico">Genérico</option>
                </Select>
                {error && <p className="text-status-red text-sm">{error}</p>}
                <FormActions>
                    <Button type="button" variant="secondary" onClick={onClose}>Cancelar</Button>
                    <Button type="submit" isLoading={isSubmitting}>{initial ? 'Guardar' : 'Crear'}</Button>
                </FormActions>
            </form>
        </FormModal>
    );
}
