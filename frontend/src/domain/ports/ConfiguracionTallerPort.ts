import type { CapacidadMecanicos, CupoDiarioIngresos } from '../entities/ConfiguracionTaller';

/** Configuración operativa del taller (solo Administrador; MS2 vía la Gateway). */
export interface ConfiguracionTallerPort {
    obtenerCupoDiario(): Promise<CupoDiarioIngresos>;
    configurarCupoDiario(maxIngresosDiarios: number): Promise<CupoDiarioIngresos>;
    obtenerCapacidadMecanicos(): Promise<CapacidadMecanicos>;
    configurarCapacidadMecanicos(maxOrdenesActivas: number): Promise<CapacidadMecanicos>;
}
