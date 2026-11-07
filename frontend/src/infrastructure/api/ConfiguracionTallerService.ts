import type { CapacidadMecanicos, CupoDiarioIngresos } from '@/domain/entities/ConfiguracionTaller';
import type { ConfiguracionTallerPort } from '@/domain/ports/ConfiguracionTallerPort';
import apiClient from '../config/apiClient';

// Contratos de MS2 vía la Gateway (/api/ordenes/configuracion/capacidad/*).
// Cada PUT queda auditado en MS2 (administrador, valor anterior y nuevo, fecha).
interface CupoDiarioApi {
    max_ingresos_diarios: number | null;
    actualizado_por_id: number | null;
    actualizado_en: string;
    jornada_local: string;
    ingresos_registrados: number;
    sobre_limite: boolean;
}

interface CapacidadMecanicosApi {
    max_ordenes_activas: number | null;
    actualizado_por_id: number | null;
    actualizado_en: string;
    mecanicos_sobre_limite: { mecanico_id: number; ordenes_activas: number }[];
}

const RUTA_CUPO = '/ordenes/configuracion/capacidad/ingresos-diarios';
const RUTA_CAPACIDAD = '/ordenes/configuracion/capacidad/mecanicos';

const idOpcional = (id: number | null) => (id === null ? null : String(id));

function mapCupo(c: CupoDiarioApi): CupoDiarioIngresos {
    return {
        maxIngresosDiarios: c.max_ingresos_diarios,
        actualizadoPorId: idOpcional(c.actualizado_por_id),
        actualizadoEn: c.actualizado_en,
        jornadaLocal: c.jornada_local,
        ingresosRegistrados: c.ingresos_registrados,
        sobreLimite: c.sobre_limite,
    };
}

function mapCapacidad(c: CapacidadMecanicosApi): CapacidadMecanicos {
    return {
        maxOrdenesActivas: c.max_ordenes_activas,
        actualizadoPorId: idOpcional(c.actualizado_por_id),
        actualizadoEn: c.actualizado_en,
        mecanicosSobreLimite: c.mecanicos_sobre_limite.map((m) => ({
            mecanicoId: String(m.mecanico_id),
            ordenesActivas: m.ordenes_activas,
        })),
    };
}

class ConfiguracionTallerService implements ConfiguracionTallerPort {
    async obtenerCupoDiario(): Promise<CupoDiarioIngresos> {
        const { data } = await apiClient.get<CupoDiarioApi>(RUTA_CUPO);
        return mapCupo(data);
    }

    async configurarCupoDiario(maxIngresosDiarios: number): Promise<CupoDiarioIngresos> {
        const { data } = await apiClient.put<CupoDiarioApi>(RUTA_CUPO, {
            max_ingresos_diarios: maxIngresosDiarios,
        });
        return mapCupo(data);
    }

    async obtenerCapacidadMecanicos(): Promise<CapacidadMecanicos> {
        const { data } = await apiClient.get<CapacidadMecanicosApi>(RUTA_CAPACIDAD);
        return mapCapacidad(data);
    }

    async configurarCapacidadMecanicos(maxOrdenesActivas: number): Promise<CapacidadMecanicos> {
        const { data } = await apiClient.put<CapacidadMecanicosApi>(RUTA_CAPACIDAD, {
            max_ordenes_activas: maxOrdenesActivas,
        });
        return mapCapacidad(data);
    }
}

export const configuracionTallerService = new ConfiguracionTallerService();
