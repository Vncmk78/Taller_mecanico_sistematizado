import type { Vehicle } from '../entities/Vehicle';

export interface VehicleOwner {
    fullName: string;
    email: string;
    phone?: string;
}

export interface CreateVehicleInput {
    patent: string;
    brand: string;
    model: string;
    year: number;
    mileage: number;
}

export interface VehiclePort {
  /** Vehículos del cliente autenticado (portal Cliente). */
    getMyVehicles(): Promise<Vehicle[]>;
  /** Catálogo completo de vehículos (portal Administrador). */
    getAllVehicles(): Promise<Vehicle[]>;
  /** Vehículos de las órdenes actualmente asignadas al mecánico autenticado. */
    getAssignedVehicles(): Promise<Vehicle[]>;
    getVehicleById(id: string): Promise<Vehicle>;
    createVehicle(data: CreateVehicleInput): Promise<Vehicle>;
}