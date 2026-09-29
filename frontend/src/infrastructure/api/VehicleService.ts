import type { Vehicle } from '@/domain/entities/Vehicle';
import type { CreateVehicleInput, VehiclePort } from '@/domain/ports/VehiclePort';
import apiClient from '../config/apiClient';

// Contrato HTTP de MS2 a través de la API Gateway (/api/vehiculos). MS2 usa
// nombres en español (patente, marca, modelo, anio, kilometraje) y devuelve
// vehículo_id; el dominio del frontend usa nombres en inglés. Este servicio
// traduce ambos sentidos manteniendo intacto el resto de la app.
interface VehiculoApi {
    vehiculo_id: number;
    patente: string;
    marca: string;
    modelo: string;
    anio: number | null;
    kilometraje: number | null;
}

function mapVehiculoApi(v: VehiculoApi, clientId = ''): Vehicle {
    return {
        id: String(v.vehiculo_id),
        patent: v.patente,
        brand: v.marca,
        model: v.modelo,
        year: v.anio ?? 0,
        mileage: v.kilometraje ?? 0,
        clientId,
    };
}

class VehicleService implements VehiclePort {
    async getMyVehicles(clientId: string): Promise<Vehicle[]> {
    const { data } = await apiClient.get<VehiculoApi[]>('/vehiculos');
    return data.map((v) => mapVehiculoApi(v, clientId));
    }

    async getAllVehicles(): Promise<Vehicle[]> {
    const { data } = await apiClient.get<VehiculoApi[]>('/vehiculos');
    return data.map((v) => mapVehiculoApi(v));
    }

    async getAssignedVehicles(): Promise<Vehicle[]> {
    const { data } = await apiClient.get<VehiculoApi[]>('/vehiculos/asignados');
    return data.map((v) => mapVehiculoApi(v));
    }

    async getVehicleById(id: string): Promise<Vehicle> {
    const { data } = await apiClient.get<VehiculoApi>(`/vehiculos/${id}`);
    return mapVehiculoApi(data);
    }

    async createVehicle(input: CreateVehicleInput): Promise<Vehicle> {
    const { data } = await apiClient.post<VehiculoApi>('/vehiculos', {
        patente: input.patent,
        marca: input.brand,
        modelo: input.model,
        anio: input.year,
        kilometraje: input.mileage,
    });
    return mapVehiculoApi(data);
    }
}

export const vehicleService = new VehicleService();