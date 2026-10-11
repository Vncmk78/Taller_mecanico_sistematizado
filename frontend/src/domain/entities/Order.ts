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

// Transiciones accionables por el mecánico en "Actualizar Estados". Son espejo
// de MS2 (transiciones_orden.py), pero recortadas al avance que la vista puede
// realizar: la aprobación del presupuesto y la entrega física las gestionan el
// cliente y el administrador, y cancelar corresponde al cliente. El backend
// conserva la autoridad final sobre permisos, operaciones y precondiciones.
// La primera asignación (1 -> 2) usa la operación administrativa específica.
// El envío inicial (2 -> 3) corresponde al administrador, y la disponibilidad
// posterior (4 -> 5) depende de un evento MS3 cuyo actor sigue sin definirse.
// Ninguno de esos flujos se ofrece como acción del mecánico.
export const AVANCES_MECANICO: Record<number, number[]> = {
    5: [6], // En reparación -> Listo
};

// Orden de trabajo. Coincide con el contrato de la API Gateway
// (OrdenRespuesta). MS2 no expone el nombre del mecánico (solo
// mecanico_actual_id) ni la patente del vehículo, así que patente/vehiculo se
// resuelven desde la caché de vehículos del portal y las vistas identifican al
// mecánico por su id real en lugar de mostrar nombres simulados.
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
