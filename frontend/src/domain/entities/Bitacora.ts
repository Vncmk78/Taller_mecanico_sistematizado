// Bitácora de trabajo del mecánico, espejo de BitacoraRespuesta (MS2). A
// diferencia del historial de estados, cada entrada NO exige un cambio de
// estado: documenta lo que el mecánico observa o ejecuta (RF-11). Una acción
// puede declarar los repuestos utilizados, que son texto libre y cantidad: la
// bitácora no referencia el catálogo de repuestos de MS3.
export type TipoBitacora = 'observacion' | 'accion';

export const TIPO_BITACORA_LABEL: Record<TipoBitacora, string> = {
    observacion: 'Observación',
    accion: 'Acción',
};

export interface RepuestoBitacora {
    nombre: string;
    cantidad: number;
}

export interface BitacoraEntry {
    /** id de la entrada (bitacora_id). */
    id: string;
    ordenId: string;
    autorUsuarioId: string;
    tipo: TipoBitacora;
    descripcion: string;
    creadoEn: string;
    repuestos: RepuestoBitacora[];
}

// Datos que el mecánico aporta al registrar una entrada. `repuestos` solo se
// envía cuando el tipo es 'accion' (el backend rechaza con 422 una observación
// con repuestos).
export interface BitacoraEntradaCrear {
    tipo: TipoBitacora;
    descripcion: string;
    repuestos?: RepuestoBitacora[];
}
