import { create } from 'zustand';
import type { Vehicle } from '@/domain/entities/Vehicle';
import type { CreateVehicleInput } from '@/domain/ports/VehiclePort';
import { getApiErrorMessage, isNotFoundError } from '@/infrastructure/api/errors';
import { mockVehicles } from '@/infrastructure/mocks/vehicles.mock';

export type FetchStatus = 'idle' | 'loading' | 'success' | 'error';

interface FetchVehicleResult {
    vehicle: Vehicle | null;
    notFound: boolean;
}

interface VehicleState {
    vehicles: Vehicle[];
    status: FetchStatus;
    error: string | null;
  /** true cuando lo mostrado son datos locales porque la API no respondió (MS2/Gateway aún no disponibles). */
    isOffline: boolean;
    fetchVehicles: (loader: () => Promise<Vehicle[]>) => Promise<void>;
    fetchVehicleById: (
    id: string,
    loader: (id: string) => Promise<Vehicle>
    ) => Promise<FetchVehicleResult>;
    patentExists: (patent: string) => boolean;
    addVehicle: (input: CreateVehicleInput, clientId: string) => Promise<Vehicle>;
}

// Caché en memoria compartida entre portales. Se inicializa con datos de
// demostración para que la UI nunca quede vacía mientras MS2 + API Gateway
// no estén desplegados (misión "Conectar registro con la API Gateway", en
// pausa). Cada fetch* intenta la API real primero; si falla, se conserva la
// caché local y se marca isOffline para avisar al usuario.
export const useVehicleStore = create<VehicleState>((set, get) => ({
    vehicles: mockVehicles,
    status: 'idle',
    error: null,
    isOffline: false,

    fetchVehicles: async (loader) => {
    set({ status: 'loading', error: null });
    try {
        const fetched = await loader();
        set((state) => {
        // Merge por id: cada portal trae un subconjunto distinto (todos /
        // míos / asignados); no queremos que uno pise la caché del otro.
        const byId = new Map(state.vehicles.map((v) => [v.id, v]));
        fetched.forEach((v) => byId.set(v.id, v));
        return {
            vehicles: Array.from(byId.values()),
            status: 'success',
            isOffline: false,
            error: null,
        };
        });
    } catch (err) {
        set({ status: 'error', error: getApiErrorMessage(err), isOffline: true });
    }
    },

    fetchVehicleById: async (id, loader) => {
    try {
        const vehicle = await loader(id);
        set((state) => {
        const exists = state.vehicles.some((v) => v.id === vehicle.id);
        return {
            vehicles: exists
            ? state.vehicles.map((v) => (v.id === vehicle.id ? vehicle : v))
            : [...state.vehicles, vehicle],
            isOffline: false,
            error: null,
        };
        });
        return { vehicle, notFound: false };
    } catch (err) {
        if (isNotFoundError(err)) {
        // El backend respondió: el vehículo realmente no existe.
        return { vehicle: null, notFound: true };
        }
      // Error de red/servidor: no sabemos si existe; mostramos lo que haya
      // en caché local y avisamos que no se pudo confirmar contra el servidor.
        const local = get().vehicles.find((v) => v.id === id) ?? null;
        set({ error: getApiErrorMessage(err), isOffline: true });
        return { vehicle: local, notFound: local === null };
    }
    },

    patentExists: (patent) =>
    get().vehicles.some((v) => v.patent.toLowerCase() === patent.toLowerCase()),

    addVehicle: async (input, clientId) => {
    // TODO: reemplazar por vehicleService.createVehicle(input) cuando MS2 +
    // API Gateway estén disponibles (misión en pausa). El backend deberá
    // validar la unicidad de patente de forma autoritativa (UNIQUE en el MER);
    // patentExists aquí es solo una verificación optimista en el cliente.
    await new Promise((resolve) => setTimeout(resolve, 400));

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