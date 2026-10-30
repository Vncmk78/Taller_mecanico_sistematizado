import type { Presupuesto } from '@/domain/entities/Presupuesto';

// Fixtures SOLO para tests (ver notas de vehicles.mock.ts). Reflejan lo que MS3
// devuelve al cliente: solo versiones enviadas/aprobadas/rechazadas, con el
// dinero ya normalizado a number.
export const mockPresupuestoPendiente: Presupuesto = {
    id: '501',
    orderId: '101',
    creadoEn: '2026-09-02T09:20:00',
    cantidadVersiones: 1,
    ultimaVersion: 1,
    estadoUltimaVersion: 'enviada',
    totalUltimaVersion: 108000,
    versionVigente: null,
    versiones: [
        {
            numero: 1,
            estado: 'enviada',
            esModificacion: false,
            creadoEn: '2026-09-02T09:20:00',
            enviadoEn: '2026-09-02T09:20:00',
            total: 108000,
            items: [
                {
                    id: 'i1',
                    tipo: 'repuesto',
                    descripcion: 'Kit Pastillas Freno Delanteras',
                    cantidad: 1,
                    precioUnitario: 35000,
                    subtotal: 35000,
                    repuestoId: '9',
                    repuestoNombre: 'Kit Pastillas Freno Delanteras',
                    proveedorNombre: 'Distribuidor Oficial Derco',
                },
                {
                    id: 'i2',
                    tipo: 'repuesto',
                    descripcion: 'Aceite Sintético 5W-30 (4L)',
                    cantidad: 1,
                    precioUnitario: 28000,
                    subtotal: 28000,
                    repuestoId: '10',
                    repuestoNombre: 'Aceite Sintético 5W-30 (4L)',
                    proveedorNombre: 'Distribuidor Genérico Autoplanet',
                },
                {
                    id: 'i3',
                    tipo: 'mano_de_obra',
                    descripcion: 'Mano de obra (Mantención general)',
                    cantidad: 1,
                    precioUnitario: 45000,
                    subtotal: 45000,
                    repuestoId: null,
                },
            ],
        },
    ],
};

export const mockPresupuestoAprobado: Presupuesto = {
    id: '502',
    orderId: '102',
    creadoEn: '2026-09-04T12:20:00',
    cantidadVersiones: 1,
    ultimaVersion: 1,
    estadoUltimaVersion: 'aprobada',
    totalUltimaVersion: 73000,
    versionVigente: 1,
    versiones: [
        {
            numero: 1,
            estado: 'aprobada',
            esModificacion: false,
            creadoEn: '2026-09-04T12:20:00',
            enviadoEn: '2026-09-04T12:20:00',
            bloqueadaEn: '2026-09-05T10:00:00',
            total: 73000,
            items: [
                {
                    id: 'i4',
                    tipo: 'mano_de_obra',
                    descripcion: 'Cambio de aceite y filtros',
                    cantidad: 1,
                    precioUnitario: 73000,
                    subtotal: 73000,
                    repuestoId: null,
                },
            ],
            decision: {
                id: 'd1',
                decision: 'aprobado',
                fecha: '2026-09-05T10:00:00',
            },
        },
    ],
};

export const mockPresupuestoRechazado: Presupuesto = {
    id: '503',
    orderId: '103',
    creadoEn: '2026-09-06T09:00:00',
    cantidadVersiones: 1,
    ultimaVersion: 1,
    estadoUltimaVersion: 'rechazada',
    totalUltimaVersion: 38000,
    versionVigente: null,
    versiones: [
        {
            numero: 1,
            estado: 'rechazada',
            esModificacion: false,
            creadoEn: '2026-09-06T09:00:00',
            enviadoEn: '2026-09-06T09:00:00',
            bloqueadaEn: '2026-09-06T18:00:00',
            total: 38000,
            items: [
                {
                    id: 'i5',
                    tipo: 'mano_de_obra',
                    descripcion: 'Diagnóstico general',
                    cantidad: 1,
                    precioUnitario: 38000,
                    subtotal: 38000,
                    repuestoId: null,
                },
            ],
            decision: {
                id: 'd2',
                decision: 'rechazado',
                fecha: '2026-09-06T18:00:00',
                motivo: 'Costo elevado',
            },
        },
    ],
};
