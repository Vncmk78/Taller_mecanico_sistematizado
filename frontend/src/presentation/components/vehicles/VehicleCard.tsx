import { Link } from 'react-router-dom';
import { Car, User, FileText } from 'lucide-react';
import type { Vehicle } from '@/domain/entities/Vehicle';

interface VehicleCardProps {
    vehicle: Vehicle;
    detailPath: string;
    ownerName?: string;
}

export function VehicleCard({ vehicle, detailPath, ownerName }: VehicleCardProps) {
    return (
    <div className="glass-card p-0 overflow-hidden flex flex-col">
        <div className="h-[140px] bg-white/5 flex items-center justify-center text-text-muted">
        <Car className="w-12 h-12" />
        </div>
        <div className="p-5 flex-grow flex flex-col">
        <div className="flex justify-between items-center mb-3">
            <h3 className="text-lg font-semibold">
            {vehicle.brand} {vehicle.model}
            </h3>
            <span className="bg-white/90 text-black font-mono font-bold text-sm px-2.5 py-1 rounded tracking-wide">
            {vehicle.patent}
            </span>
        </div>
        <div className="text-sm text-text-main mb-1">Año: {vehicle.year}</div>
        <div className="text-sm text-text-muted mb-4">
            Km registrado: {vehicle.mileage.toLocaleString('es-CL')} km
        </div>
        {ownerName && (
            <div className="flex items-center gap-2 text-sm bg-white/5 rounded-lg px-3 py-2 mb-4">
            <User className="w-4 h-4 text-text-muted" />
            <span>Dueño: {ownerName}</span>
        </div>
        )}
        <Link
            to={detailPath}
            className="mt-auto flex items-center justify-center gap-2 bg-white/5 border border-border-custom text-white py-2.5 rounded-lg text-sm hover:bg-white/15 transition-colors no-underline"
        >
            <FileText className="w-4 h-4" />
            Ver ficha técnica
        </Link>
        </div>
    </div>
    );
}