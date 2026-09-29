import type { Vehicle } from '@/domain/entities/Vehicle';
import type { VehicleOwner } from '@/domain/ports/VehiclePort';

export const mockOwners: Record<string, VehicleOwner> = {
    c1: { fullName: 'Eduardo Werner', email: 'eduardo.werner@email.com', phone: '+56 9 5555 4444' },
    c2: { fullName: 'María Soto', email: 'msoto.90@email.com', phone: '+56 9 8765 4321' },
    c3: { fullName: 'Jorge Vera', email: 'jorge.vera@gmail.com', phone: '+56 9 2233 4455' },
    c4: { fullName: 'Ana Reyes', email: 'ana.reyes@hotmail.com', phone: '+56 9 9988 7766' },
    c5: { fullName: 'Camila Fuentes', email: 'cami.fuentes@gmail.com', phone: '+56 9 3344 5566' },
};

// TODO: data de ejemplo. Reemplazar por vehicleService (MS2) cuando el backend esté disponible.
export const mockVehicles: Vehicle[] = [
    { id: '1', patent: 'ABCD-12', brand: 'Ford', model: 'Fiesta', year: 2018, mileage: 85120, clientId: 'c1' },
    { id: '2', patent: 'EFGH-34', brand: 'Nissan', model: 'Kicks', year: 2021, mileage: 32500, clientId: 'c2' },
    { id: '3', patent: 'IJKL-56', brand: 'Hyundai', model: 'Tucson', year: 2022, mileage: 15200, clientId: 'c3' },
    { id: '4', patent: 'MNOP-78', brand: 'Kia', model: 'Morning', year: 2019, mileage: 60500, clientId: 'c4' },
    { id: '5', patent: 'WXYZ-90', brand: 'Toyota', model: 'Yaris', year: 2020, mileage: 45000, clientId: 'c5' },
    { id: '6', patent: 'QWER-12', brand: 'Chevrolet', model: 'Spark', year: 2017, mileage: 110000, clientId: 'c1' },
];

// Simula al cliente demo logueado (Eduardo Werner) para "Mis Vehículos".
export const CURRENT_CLIENT_ID = 'c1';

// Simula los vehículos de las órdenes asignadas al mecánico demo.
export const mockAssignedVehicleIds = ['1', '2'];