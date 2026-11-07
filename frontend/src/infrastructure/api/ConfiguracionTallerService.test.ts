import { beforeEach, describe, expect, it, vi } from 'vitest';
import apiClient from '@/infrastructure/config/apiClient';
import { configuracionTallerService } from '@/infrastructure/api/ConfiguracionTallerService';
import { orderService } from '@/infrastructure/api/OrderService';

vi.mock('@/infrastructure/config/apiClient', () => ({
    default: { get: vi.fn(), put: vi.fn(), post: vi.fn() },
}));

const cupoApi = {
    max_ingresos_diarios: 10, actualizado_por_id: 1, actualizado_en: '2026-11-07T09:00:00-03:00',
    jornada_local: '2026-11-07', ingresos_registrados: 4, sobre_limite: false,
};
const capacidadApi = {
    max_ordenes_activas: 1, actualizado_por_id: null, actualizado_en: '2026-11-07T09:00:00-03:00',
    mecanicos_sobre_limite: [{ mecanico_id: 50, ordenes_activas: 2 }],
};

describe('ConfiguracionTallerService y creación de orden vía la Gateway', () => {
    beforeEach(() => vi.clearAllMocks());

    it('consulta y configura el cupo diario con el contrato de MS2', async () => {
        vi.mocked(apiClient.get).mockResolvedValue({ data: cupoApi });
        vi.mocked(apiClient.put).mockResolvedValue({ data: { ...cupoApi, max_ingresos_diarios: 2 } });

        expect(await configuracionTallerService.obtenerCupoDiario()).toEqual({
            maxIngresosDiarios: 10, actualizadoPorId: '1', actualizadoEn: cupoApi.actualizado_en,
            jornadaLocal: '2026-11-07', ingresosRegistrados: 4, sobreLimite: false,
        });
        await configuracionTallerService.configurarCupoDiario(2);

        expect(apiClient.get).toHaveBeenCalledWith('/ordenes/configuracion/capacidad/ingresos-diarios');
        expect(apiClient.put).toHaveBeenCalledWith('/ordenes/configuracion/capacidad/ingresos-diarios', {
            max_ingresos_diarios: 2,
        });
    });

    it('consulta y configura la capacidad por mecánico', async () => {
        vi.mocked(apiClient.get).mockResolvedValue({ data: capacidadApi });
        vi.mocked(apiClient.put).mockResolvedValue({ data: capacidadApi });

        expect(await configuracionTallerService.obtenerCapacidadMecanicos()).toEqual({
            maxOrdenesActivas: 1, actualizadoPorId: null, actualizadoEn: capacidadApi.actualizado_en,
            mecanicosSobreLimite: [{ mecanicoId: '50', ordenesActivas: 2 }],
        });
        await configuracionTallerService.configurarCapacidadMecanicos(1);

        expect(apiClient.put).toHaveBeenCalledWith('/ordenes/configuracion/capacidad/mecanicos', {
            max_ordenes_activas: 1,
        });
    });

    it('crearOrden envía solo vehiculo_id como entero', async () => {
        vi.mocked(apiClient.post).mockResolvedValue({
            data: {
                orden_id: 55, vehiculo_id: 2, ingreso_id: 40, estado_codigo: 1, mecanico_actual_id: null,
                creado_por_id: 1, creado_en: 'x', actualizado_en: 'x',
            },
        });

        const orden = await orderService.crearOrden('2');

        expect(apiClient.post).toHaveBeenCalledWith('/ordenes', { vehiculo_id: 2 });
        expect(orden).toMatchObject({ id: '55', ingresoId: 40, estadoCodigo: 1, mecanicoActualId: null });
    });
});
