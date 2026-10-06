import { create } from 'zustand';
import type { Vehicle } from '@/domain/entities/Vehicle';
import type { CreateVehicleInput } from '@/domain/ports/VehiclePort';
import { vehicleService } from '@/infrastructure/api/VehicleService';
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
    failed: boolean;
}

interface VehicleState extends AsyncStatus {
    vehicles: Vehicle[];
    fetchVehicles: (loader: () => Promise<Vehicle[]>) => Promise<void>;
    fetchVehicleById: (id: string, loader: (id: string) => Promise<Vehicle>) => Promise<FetchVehicleResult>;
    patentExists: (patent: string) => boolean;
    addVehicle: (input: CreateVehicleInput, clientId: string) => Promise<Vehicle>;
    /**
     * Vacía la caché y vuelve al estado inicial. Se invoca al cerrar sesión: la
     * caché es compartida entre portales y sin esto el siguiente usuario que
     * iniciara sesión en el mismo navegador vería los vehículos del anterior.
     */
    reset: () => void;
}

// Caché en memoria compartida entre portales, inicialmente vacía: solo contiene
// respuestas reales de la Gateway. La lógica de estados, merge y offline vive en
// asyncCollection (fetchCollection / fetchItemById).
export const useVehicleStore = create<VehicleState>((set, get) => ({
    vehicles: [],
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
        return { vehicle: result.item, notFound: result.notFound, failed: result.failed };
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

    reset: () => set({ vehicles: [], ...initialAsyncStatus }),
}));