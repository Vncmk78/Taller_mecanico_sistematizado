import type { Order } from '@/domain/entities/Order';

// Mecánico demo usado para filtrar "Mis Órdenes" cuando no hay API.
export const CURRENT_MECHANIC_ID = 'm1';

export const mockMechanics: Record<string, string> = {
    m1: 'Martín Herrera',
    m2: 'Gustavo Jara',
};

// TODO: data de ejemplo. Reemplazar por orderService (MS2) cuando el backend
// esté disponible. Coincide con mockVehicles: el cliente demo c1 es dueño de
// los vehículos 1 y 6; el mecánico demo m1 tiene asignadas las de los
// vehículos 1, 2 y 4.
export const mockOrders: Order[] = [
    {
        id: '101',
        vehicleId: '1',
        ingresoId: 1,
        estadoCodigo: 5,
        mecanicoActualId: 'm1',
        creadoPorId: 'u1',
        creadoEn: '2026-09-01T10:15:00',
        actualizadoEn: '2026-09-05T16:30:00',
        patente: 'ABCD-12',
        vehiculo: 'Ford Fiesta',
        mecanicoNombre: 'Martín Herrera',
    },
    {
        id: '102',
        vehicleId: '2',
        ingresoId: 2,
        estadoCodigo: 3,
        mecanicoActualId: 'm1',
        creadoPorId: 'u1',
        creadoEn: '2026-09-03T09:00:00',
        actualizadoEn: '2026-09-04T12:20:00',
        patente: 'EFGH-34',
        vehiculo: 'Nissan Kicks',
        mecanicoNombre: 'Martín Herrera',
    },
    {
        id: '103',
        vehicleId: '4',
        ingresoId: 3,
        estadoCodigo: 2,
        mecanicoActualId: 'm1',
        creadoPorId: 'u2',
        creadoEn: '2026-09-08T15:40:00',
        actualizadoEn: '2026-09-09T09:10:00',
        patente: 'MNOP-78',
        vehiculo: 'Kia Morning',
        mecanicoNombre: 'Martín Herrera',
    },
    {
        id: '104',
        vehicleId: '3',
        ingresoId: 4,
        estadoCodigo: 4,
        mecanicoActualId: 'm2',
        creadoPorId: 'u1',
        creadoEn: '2026-09-10T11:00:00',
        actualizadoEn: '2026-09-12T17:45:00',
        patente: 'IJKL-56',
        vehiculo: 'Hyundai Tucson',
        mecanicoNombre: 'Gustavo Jara',
    },
    {
        id: '105',
        vehicleId: '6',
        ingresoId: 5,
        estadoCodigo: 1,
        mecanicoActualId: null,
        creadoPorId: 'u2',
        creadoEn: '2026-09-15T08:30:00',
        actualizadoEn: '2026-09-15T08:30:00',
        patente: 'QWER-12',
        vehiculo: 'Chevrolet Spark',
    },
    {
        id: '106',
        vehicleId: '6',
        ingresoId: 6,
        estadoCodigo: 6,
        mecanicoActualId: null,
        creadoPorId: 'u1',
        creadoEn: '2026-08-20T14:00:00',
        actualizadoEn: '2026-08-25T10:00:00',
        patente: 'QWER-12',
        vehiculo: 'Chevrolet Spark',
        mecanicoNombre: 'Martín Herrera',
    },
];