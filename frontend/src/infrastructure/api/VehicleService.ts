import type { Vehicle } from '@/domain/entities/Vehicle';
import type { CreateVehicleInput, VehiclePort } from '@/domain/ports/VehiclePort';
import apiClient from '../config/apiClient';

// Endpoints propuestos para cuando exista MS2 (Vehículos y Órdenes de Trabajo).
// Ajustar prefijo/paths cuando se acuerden los contratos definitivos de la API Gateway.
class VehicleService implements VehiclePort {
    async getMyVehicles(): Promise<Vehicle[]> {
    const { data } = await apiClient.get<Vehicle[]>('/vehiculos/mios');
    return data;
    }

    async getAllVehicles(): Promise<Vehicle[]> {
    const { data } = await apiClient.get<Vehicle[]>('/vehiculos');
    return data;
    }

    async getAssignedVehicles(): Promise<Vehicle[]> {
    const { data } = await apiClient.get<Vehicle[]>('/vehiculos/asignados');
    return data;
    }

    async getVehicleById(id: string): Promise<Vehicle> {
    const { data } = await apiClient.get<Vehicle>(`/vehiculos/${id}`);
    return data;
    }

    async createVehicle(input: CreateVehicleInput): Promise<Vehicle> {
    const { data } = await apiClient.post<Vehicle>('/vehiculos', input);
    return data;
    }
}

export const vehicleService = new VehicleService();