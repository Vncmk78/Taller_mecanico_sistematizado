import type { Order } from '@/domain/entities/Order';
import type { Vehicle } from '@/domain/entities/Vehicle';

export function orderVehicleLabel(order: Order, vehicles: Vehicle[]): string {
    const vehicle = vehicles.find((v) => v.id === order.vehicleId);
    if (order.vehiculo) return order.vehiculo;
    if (vehicle) return `${vehicle.brand} ${vehicle.model}`;
    return `Vehículo N°${order.vehicleId}`;
}

export function orderPatente(order: Order, vehicles: Vehicle[]): string | undefined {
    const vehicle = vehicles.find((v) => v.id === order.vehicleId);
    return order.patente ?? vehicle?.patent;
}

export function formatDateTime(iso: string): string {
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return iso;
    return date.toLocaleString('es-CL', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
    });
}

export function formatDate(iso: string): string {
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return iso;
    return date.toLocaleDateString('es-CL', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
    });
}