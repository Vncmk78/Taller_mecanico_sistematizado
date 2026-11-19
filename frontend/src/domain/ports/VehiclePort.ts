import type { Vehicle } from '../entities/Vehicle';

export interface CreateVehicleInput {
    patent: string;
    brand: string;
    model: string;
    /** Opcional en el contrato (`anio`: int | None). `null` = sin dato. */
    year: number | null;
    /** Opcional en el contrato (`kilometraje`: int | None). `null` = sin dato. */
    mileage: number | null;
}

/**
 * Campos editables de un vehículo (PATCH /vehiculos/{id}). El contrato
 * `VehiculoActualizar` no incluye la patente: no se puede cambiar. Todos los
 * campos son opcionales, pero se exige al menos uno; `year`/`mileage` admiten
 * `null` para dejar el dato sin informar.
 */
export interface UpdateVehicleInput {
    brand?: string;
    model?: string;
    year?: number | null;
    mileage?: number | null;
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
    /**
     * Actualiza marca, modelo, año y kilometraje. El portal Cliente pasa su
     * `clientId` para conservar la pertenencia del vehículo en la caché
     * compartida entre portales.
     */
    updateVehicle(id: string, data: UpdateVehicleInput, clientId?: string): Promise<Vehicle>;
}