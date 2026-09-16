import { useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Calendar, Car, Gauge, Hash } from 'lucide-react';
import { Button } from '@/presentation/components/ui/Button';
import { Input } from '@/presentation/components/ui/Input';
import { GlassCard } from '@/presentation/components/ui/GlassCard';

const vehicleSchema = z.object({
    patent: z.string().min(5, 'Ingrese una patente válida').max(10),
    brand: z.string().min(2, 'Ingrese la marca'),
    model: z.string().min(1, 'Ingrese el modelo'),
    year: z.coerce.number().min(1980).max(new Date().getFullYear() + 1),
    mileage: z.coerce.number().min(0, 'El kilometraje no puede ser negativo'),
});

type VehicleForm = z.infer<typeof vehicleSchema>;

export function ClientVehicleFormPage() {
    const navigate = useNavigate();
    const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    } = useForm<VehicleForm>({ resolver: zodResolver(vehicleSchema) });

    const onSubmit = async (data: VehicleForm) => {
    // TODO: reemplazar por vehicleService.createVehicle(data) cuando MS2 esté disponible.
    console.log('Registrar vehículo (mock):', data);
    navigate('/client/vehiculos');
    };

    return (
    <div className="animate-fade-in flex justify-center">
        <GlassCard className="w-full max-w-[600px] p-10">
        <h2 className="text-2xl font-bold mb-8 text-center flex items-center justify-center gap-3">
            <Car className="w-6 h-6 text-primary-red" /> Registrar Nuevo Vehículo
        </h2>
        <form onSubmit={handleSubmit(onSubmit)}>
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
            <Input label="Modelo" placeholder="Fiesta" error={errors.model?.message} {...register('model')} />
            <div className="grid grid-cols-2 gap-4">
            <Input
                label="Año"
                type="number"
                icon={<Calendar className="w-5 h-5" />}
                error={errors.year?.message}
                {...register('year')}
            />
            <Input
                label="Kilometraje"
                type="number"
                icon={<Gauge className="w-5 h-5" />}
                error={errors.mileage?.message}
                {...register('mileage')}
            />
            </div>
            <Button type="submit" isLoading={isSubmitting} className="w-full mt-2">
            Registrar Vehículo
            </Button>
        </form>
        </GlassCard>
    </div>
    );
}