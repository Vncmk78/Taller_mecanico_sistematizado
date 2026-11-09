/**
 * Límites operativos del taller configurados por el Administrador (MS2).
 * Son independientes: el cupo cuenta ingresos físicos por jornada local y la
 * capacidad cuenta órdenes activas por mecánico. `null` = aún no configurado.
 */
export interface CupoDiarioIngresos {
    maxIngresosDiarios: number | null;
    actualizadoPorId: string | null;
    actualizadoEn: string;
    /** Jornada local del taller (AAAA-MM-DD) sobre la que se cuenta el uso. */
    jornadaLocal: string;
    ingresosRegistrados: number;
    /** El uso de hoy ya supera el máximo (p. ej. tras reducirlo). */
    sobreLimite: boolean;
}

export interface MecanicoSobreLimite {
    mecanicoId: string;
    ordenesActivas: number;
}

export interface CapacidadMecanicos {
    maxOrdenesActivas: number | null;
    actualizadoPorId: string | null;
    actualizadoEn: string;
    mecanicosSobreLimite: MecanicoSobreLimite[];
}
