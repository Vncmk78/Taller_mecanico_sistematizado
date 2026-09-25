// Cambio de estado de una orden, espejo de HistorialEstado (MS2). El registro
// inicial de una orden llega con estadoAnteriorCodigo = null y origen
// 'sistema'; los demás cambios los registra un usuario (origen 'usuario'),
// cuya identidad es una referencia lógica a MS1.
export interface OrderHistoryEntry {
    id: string;
    ordenId: string;
    estadoAnteriorCodigo: number | null;
    estadoNuevoCodigo: number;
    actorUsuarioId: number | null;
    origen: 'usuario' | 'sistema';
    fecha: string;
    observacion?: string;
    // Solo presentación/demo: no viene en el contrato del historial.
    usuarioNombre?: string;
}