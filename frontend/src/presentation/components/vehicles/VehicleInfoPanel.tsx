import { Car, User } from 'lucide-react';
import type { Vehicle } from '@/domain/entities/Vehicle';
import { vehicleMileageLabel, vehicleYearLabel } from '@/presentation/utils/vehicleDisplay';

interface VehicleInfoPanelProps {
    vehicle: Vehicle;
    /**
     * Identificación del propietario tal como la entrega la Gateway. MS2 no
     * expone nombre, correo ni teléfono del Cliente, así que la vista muestra
     * el identificador real (p. ej. "Cliente #7") en lugar de datos simulados.
     */
    ownerLabel?: string;
}

export function VehicleInfoPanel({ vehicle, ownerLabel }: VehicleInfoPanelProps) {
    return (
    <div className="card">
        <div className="flex justify-between items-center mb-6 pb-4 border-b border-border-custom">
        <h3 className="text-xl font-semibold flex items-center gap-2">
            <Car className="w-5 h-5 text-text-muted" />
            {vehicle.brand} {vehicle.model}
        </h3>
        <span className="bg-bg-secondary text-text-main font-mono font-bold px-3 py-1.5 rounded tracking-wide">
            {vehicle.patent}
        </span>
        </div>
        <div className="grid grid-cols-2 gap-4 mb-6">
        <div>
            <span className="text-text-muted text-sm block mb-1">Año</span>
            <span className="text-lg font-medium">{vehicleYearLabel(vehicle.year)}</span>
        </div>
        <div>
            <span className="text-text-muted text-sm block mb-1">Kilometraje registrado</span>
            <span className="text-lg font-medium">{vehicleMileageLabel(vehicle.mileage)}</span>
        </div>
        </div>
        {ownerLabel && (
        <div className="border-t border-border-custom pt-4">
            <span className="text-text-muted text-sm block mb-2">Propietario</span>
            <div className="flex items-center gap-2 text-sm">
            <User className="w-4 h-4 text-text-muted" /> {ownerLabel}
            </div>
        </div>
        )}
    </div>
    );
}