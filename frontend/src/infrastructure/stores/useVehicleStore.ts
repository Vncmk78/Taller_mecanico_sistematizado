import { create } from 'zustand';
import type { Vehicle } from '@/domain/entities/Vehicle';
import type { CreateVehicleInput } from '@/domain/ports/VehiclePort';
import { vehicleService } from '@/infrastructure/api/VehicleService';
import { mockVehicles } from '@/infrastructure/mocks/vehicles.mock';
import {
    initialAsyncStatus,
    type AsyncStatus,
    fetchCollection,
    fetchItemById,
    mergeById,
    upsertById,
} from '@/infrastructure/stores/asyncCollection';

interface FetchVehicleResult {
    vehicle: Vehicle | null;
    notFound: boolean;
}

interface VehicleState extends AsyncStatus {
    vehicles: Vehicle[];
    fetchVehicles: (loader: () => Promise<Vehicle[]>) => Promise<void>;
    fetchVehicleById: (id: string, loader: (id: string) => Promise<Vehicle>) => Promise<FetchVehicleResult>;
    patentExists: (patent: string) => boolean;
    addVehicle: (input: CreateVehicleInput, clientId: string) => Promise<Vehicle>;
}

// Caché en memoria compartida entre portales. Se inicializa con datos de
// demostración para que la UI nunca quede vacía ante fallos de red o mientras
// algún endpoint de MS2 aún no está disponible. La lógica de estados, merge y
// offline vive en asyncCollection (fetchCollection / fetchItemById).
export const useVehicleStore = create<VehicleState>((set, get) => ({
    vehicles: mockVehicles,
    ...initialAsyncStatus,

    fetchVehicles: (loader) =>
        fetchCollection<Vehicle, VehicleState>(
            loader,
            set,
            (state, fetched) => ({ vehicles: mergeById(state.vehicles, fetched) })
        ),

    fetchVehicleById: async (id, loader) => {
        const result = await fetchItemById<Vehicle, VehicleState>(
            id,
            loader,
            set,
            () => get().vehicles,
            (state, vehicle) => ({ vehicles: upsertById(state.vehicles, vehicle) })
        );
        return { vehicle: result.item, notFound: result.notFound };
    },

    patentExists: (patent) =>
        get().vehicles.some((v) => v.patent.toLowerCase() === patent.toLowerCase()),

    addVehicle: async (input, clientId) => {
        // Registro real contra MS2 vía la API Gateway. El backend valida la
        // unicidad de patente de forma autoritativa (409) y asigna el cliente
        // desde el JWT; patentExists del cliente es solo una verificación
        // optimista antes de llamar a la API.
        const creado = await vehicleService.createVehicle(input);
        const vehiculo: Vehicle = { ...creado, clientId };
        set((state) => ({
            vehicles: [
                vehiculo,
                ...state.vehicles.filter((v) => v.id !== vehiculo.id),
            ],
        }));
        return vehiculo;
    },
}));