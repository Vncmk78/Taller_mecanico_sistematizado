import { Car, Mail, Phone, User } from 'lucide-react';
import type { Vehicle } from '@/domain/entities/Vehicle';
import type { VehicleOwner } from '@/domain/ports/VehiclePort';

interface VehicleInfoPanelProps {
    vehicle: Vehicle;
    owner?: VehicleOwner;
}

export function VehicleInfoPanel({ vehicle, owner }: VehicleInfoPanelProps) {
    return (
    <div className="glass-card">
        <div className="flex justify-between items-center mb-6 pb-4 border-b border-border-custom">
        <h3 className="text-xl font-semibold flex items-center gap-2">
            <Car className="w-5 h-5 text-text-muted" />
            {vehicle.brand} {vehicle.model}
        </h3>
        <span className="bg-white/90 text-black font-mono font-bold px-3 py-1.5 rounded tracking-wide">
            {vehicle.patent}
        </span>
        </div>
        <div className="grid grid-cols-2 gap-4 mb-6">
        <div>
            <span className="text-text-muted text-sm block mb-1">Año</span>
            <span className="text-lg font-medium">{vehicle.year}</span>
        </div>
        <div>
            <span className="text-text-muted text-sm block mb-1">Kilometraje registrado</span>
            <span className="text-lg font-medium">{vehicle.mileage.toLocaleString('es-CL')} km</span>
        </div>
        </div>
        {owner && (
        <div className="border-t border-border-custom pt-4">
            <span className="text-text-muted text-sm block mb-2">Propietario</span>
            <div className="flex items-center gap-2 text-sm mb-1">
            <User className="w-4 h-4 text-text-muted" /> {owner.fullName}
            </div>
            <div className="flex items-center gap-2 text-sm text-text-muted mb-1">
            <Mail className="w-4 h-4" /> {owner.email}
            </div>
            {owner.phone && (
            <div className="flex items-center gap-2 text-sm text-text-muted">
                <Phone className="w-4 h-4" /> {owner.phone}
            </div>
            )}
        </div>
        )}
    </div>
    );
}