import { create } from 'zustand';
import type { Vehicle } from '@/domain/entities/Vehicle';
import type { CreateVehicleInput } from '@/domain/ports/VehiclePort';
import { mockVehicles } from '@/infrastructure/mocks/vehicles.mock';

interface VehicleState {
    vehicles: Vehicle[];
    patentExists: (patent: string) => boolean;
    addVehicle: (input: CreateVehicleInput, clientId: string) => Promise<Vehicle>;
}

// Store en memoria para el prototipo. Reemplazar por llamadas a vehicleService
// (MS2 - Vehículos y Órdenes de Trabajo) cuando el backend esté disponible;
// la forma del estado (vehicles: Vehicle[]) ya calza con lo que devolvería
// GET /vehiculos.
export const useVehicleStore = create<VehicleState>((set, get) => ({
    vehicles: mockVehicles,

    patentExists: (patent) =>
    get().vehicles.some((v) => v.patent.toLowerCase() === patent.toLowerCase()),

    addVehicle: async (input, clientId) => {
    // TODO: reemplazar por vehicleService.createVehicle(input) cuando exista MS2.
    await new Promise((resolve) => setTimeout(resolve, 400)); // simula latencia de red

    const newVehicle: Vehicle = {
        id: crypto.randomUUID(),
        patent: input.patent.toUpperCase(),
        brand: input.brand,
        model: input.model,
        year: input.year,
        mileage: input.mileage,
        clientId,
    };

    set((state) => ({ vehicles: [...state.vehicles, newVehicle] }));
    return newVehicle;
    },
}));