import type { Vehicle } from '@/domain/entities/Vehicle';

// Fixtures SOLO para tests. La producción consume exclusivamente respuestas
// reales de la Gateway (vehicles.mock no se usa en src/presentation ni en los
// stores). Cualquier dato de aquí no se muestra en la app.

export const mockVehicles: Vehicle[] = [
    { id: '1', patent: 'ABCD-12', brand: 'Ford', model: 'Fiesta', year: 2018, mileage: 85120, clientId: 'c1' },
    { id: '2', patent: 'EFGH-34', brand: 'Nissan', model: 'Kicks', year: 2021, mileage: 32500, clientId: 'c2' },
    { id: '3', patent: 'IJKL-56', brand: 'Hyundai', model: 'Tucson', year: 2022, mileage: 15200, clientId: 'c3' },
    { id: '4', patent: 'MNOP-78', brand: 'Kia', model: 'Morning', year: 2019, mileage: 60500, clientId: 'c4' },
    { id: '5', patent: 'WXYZ-90', brand: 'Toyota', model: 'Yaris', year: 2020, mileage: 45000, clientId: 'c5' },
    { id: '6', patent: 'QWER-12', brand: 'Chevrolet', model: 'Spark', year: 2017, mileage: 110000, clientId: 'c1' },
];

// Vehículos de las órdenes asignadas al mecánico de prueba.
export const mockAssignedVehicleIds = ['1', '2'];
