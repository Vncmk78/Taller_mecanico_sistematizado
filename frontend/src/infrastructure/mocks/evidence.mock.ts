import type { Evidencia } from '@/domain/entities/Evidencia';

// Fixtures SOLO para tests (ver notas de budgets.mock.ts). Reflejan lo que MS4
// devuelve al cliente: evidencias confirmadas, visibles y con metadatos, sin URL
// de archivo (esa se pide aparte como URL prefirmada).
export const mockEvidenciaFrenos: Evidencia = {
    id: 'ev-frenos',
    orderId: '101',
    presupuestoId: null,
    contexto: 'diagnostico',
    tipoArchivo: 'foto',
    visibleCliente: true,
    estado: 'confirmada',
    nombreOriginal: 'desgaste-pastillas.jpg',
    contentType: 'image/jpeg',
    tamanoBytes: 482133,
    creadaEn: '2026-09-02T09:10:00',
};

export const mockEvidenciaFiltro: Evidencia = {
    id: 'ev-filtro',
    orderId: '101',
    presupuestoId: null,
    contexto: 'resultado_final',
    tipoArchivo: 'foto',
    visibleCliente: true,
    estado: 'confirmada',
    nombreOriginal: 'filtro-motor.jpg',
    contentType: 'image/jpeg',
    tamanoBytes: 655360,
    creadaEn: '2026-09-04T17:45:00',
};

export const mockEvidenciaVideo: Evidencia = {
    id: 'ev-video',
    orderId: '101',
    presupuestoId: null,
    contexto: 'resultado_final',
    tipoArchivo: 'video',
    visibleCliente: true,
    estado: 'confirmada',
    nombreOriginal: 'prueba-motor.mp4',
    contentType: 'video/mp4',
    tamanoBytes: 6291456,
    creadaEn: '2026-09-04T17:50:00',
};

export const mockEvidenciasOrden101: Evidencia[] = [
    mockEvidenciaFrenos,
    mockEvidenciaFiltro,
    mockEvidenciaVideo,
];

// Evidencia de contexto `presupuesto` (siempre visible para el cliente y con
// `presupuestoId` de la orden 101, igual que budgets.mock → id '501').
export const mockEvidenciaPresupuesto: Evidencia = {
    id: 'ev-presupuesto',
    orderId: '101',
    presupuestoId: '501',
    contexto: 'presupuesto',
    tipoArchivo: 'foto',
    visibleCliente: true,
    estado: 'confirmada',
    nombreOriginal: 'cotizacion-repuestos.jpg',
    contentType: 'image/jpeg',
    tamanoBytes: 314572,
    creadaEn: '2026-09-01T11:00:00',
};
