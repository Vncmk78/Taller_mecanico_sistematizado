// Catálogo de estados espejo del backend (ms2_taller, estado_orden.py). El
// código numérico viene en OrdenRespuesta.estado_codigo; la etiqueta es
// responsabilidad del frontend.
export const ESTADOS_ORDEN: Record<number, string> = {
    1: 'Recibido',
    2: 'Esperando diagnóstico',
    3: 'Esperando aprobación de presupuesto',
    4: 'Esperando repuestos',
    5: 'En reparación',
    6: 'Listo',
    7: 'Entregado',
    8: 'Cancelado',
};

export function ordenStatusLabel(codigo: number): string {
    return ESTADOS_ORDEN[codigo] ?? `Estado ${codigo}`;
}

// Orden de trabajo. Coincide con el contrato de la API Gateway
// (OrdenRespuesta); los campos patente/vehiculo/mecanicoNombre son solo de
// presentación/demo y no vienen del backend.
export interface Order {
    id: string;
    vehicleId: string;
    ingresoId: number;
    estadoCodigo: number;
    mecanicoActualId: string | null;
    creadoPorId: string;
    creadoEn: string;
    actualizadoEn: string;
    patente?: string;
    vehiculo?: string;
    mecanicoNombre?: string;
}