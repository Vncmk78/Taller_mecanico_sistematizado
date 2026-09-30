import type { Vehicle } from '../entities/Vehicle';

export interface CreateVehicleInput {
    patent: string;
    brand: string;
    model: string;
    year: number;
    mileage: number;
}

export interface VehiclePort {
  /** Vehículos del cliente autenticado (portal Cliente). */
    getMyVehicles(clientId: string): Promise<Vehicle[]>;
  /** Catálogo completo de vehículos (portal Administrador). */
    getAllVehicles(): Promise<Vehicle[]>;
  /** Vehículos de las órdenes actualmente asignadas al mecánico autenticado. */
    getAssignedVehicles(): Promise<Vehicle[]>;
  /**
   * Ficha técnica por id. En el portal Cliente se pasa el clientId de la sesión
   * para conservar la pertenencia del vehículo en la caché compartida; sin ese
   * parámetro el propietario queda con el cliente_id real que devuelve la API.
   */
    getVehicleById(id: string, clientId?: string): Promise<Vehicle>;
    createVehicle(data: CreateVehicleInput): Promise<Vehicle>;
}