import { beforeEach, describe, expect, it, vi } from 'vitest';
import apiClient from '@/infrastructure/config/apiClient';
import { nuevaAtencionService, RespuestaIncompletaError } from './NuevaAtencionService';

// Fija el contrato acordado (contrato-web-bloques-3-4.md, Entrega B). El
// backend B se implementa en paralelo: estas respuestas son simulaciones.
vi.mock('@/infrastructure/config/apiClient', () => ({
    default: { get: vi.fn(), post: vi.fn() },
}));

const solicitudApi = {
    solicitud_id: 4,
    orden_cancelada_id: 25,
    vehiculo_id: 9,
    cliente_usuario_id: 10,
    descripcion: 'Ruido al frenar',
    solicitada_en: '2026-11-08T14:00:00-03:00',
    situacion: 'pendiente' as const,
    respuesta: null,
    revisor_id: null,
    revisada_en: null,
    orden_generada_id: null,
};

beforeEach(() => vi.clearAllMocks());

describe('NuevaAtencionService', () => {
    it('solicitar publica solo la descripción recortada y distingue 201 de 200', async () => {
        vi.mocked(apiClient.post)
            .mockResolvedValueOnce({ status: 201, data: solicitudApi })
            .mockResolvedValueOnce({ status: 200, data: solicitudApi });

        const nueva = await nuevaAtencionService.solicitar('25', '  Ruido al frenar \n');
        const existente = await nuevaAtencionService.solicitar('25', 'Ruido al frenar');

        expect(apiClient.post).toHaveBeenNthCalledWith(1, '/ordenes/25/nueva-atencion', {
            descripcion: 'Ruido al frenar',
        });
        expect(nueva.creada).toBe(true);
        expect(existente.creada).toBe(false);
        expect(nueva.solicitud).toEqual({
            id: '4',
            ordenCanceladaId: '25',
            vehiculoId: '9',
            clienteUsuarioId: '10',
            descripcion: 'Ruido al frenar',
            solicitadaEn: '2026-11-08T14:00:00-03:00',
            situacion: 'pendiente',
            respuesta: null,
            revisorId: null,
            revisadaEn: null,
            ordenGeneradaId: null,
        });
    });

    it('listar envía paginación y solo los filtros indicados', async () => {
        vi.mocked(apiClient.get).mockResolvedValue({
            data: { items: [{ ...solicitudApi, situacion: 'aceptada', orden_generada_id: 30, revisor_id: 3 }], total: 1, limit: 20, offset: 0 },
        });

        const pagina = await nuevaAtencionService.listar({ ordenCanceladaId: '25' }, { limit: 20, offset: 0 });
        await nuevaAtencionService.listar({ situacion: 'rechazada', ordenGeneradaId: '30' }, { limit: 20, offset: 40 });

        expect(apiClient.get).toHaveBeenNthCalledWith(1, '/ordenes/nuevas-atenciones', {
            params: { limit: 20, offset: 0, orden_cancelada_id: 25 },
        });
        expect(apiClient.get).toHaveBeenNthCalledWith(2, '/ordenes/nuevas-atenciones', {
            params: { limit: 20, offset: 40, situacion: 'rechazada', orden_generada_id: 30 },
        });
        expect(pagina.total).toBe(1);
        expect(pagina.items[0]).toMatchObject({ situacion: 'aceptada', ordenGeneradaId: '30', revisorId: '3' });
    });

    it('obtener consulta el detalle por id', async () => {
        vi.mocked(apiClient.get).mockResolvedValue({ data: solicitudApi });

        const s = await nuevaAtencionService.obtener('4');

        expect(apiClient.get).toHaveBeenCalledWith('/ordenes/nuevas-atenciones/4');
        expect(s.id).toBe('4');
    });
});

describe('NuevaAtencionService: revisión y generación (Entrega C)', () => {
    const revisadaApi = {
        ...solicitudApi,
        situacion: 'aceptada' as const,
        respuesta: 'Lo esperamos el lunes',
        revisor_id: 3,
        revisada_en: '2026-11-08T15:00:00-03:00',
    };
    const ordenApi = {
        orden_id: 30,
        vehiculo_id: 9,
        ingreso_id: 12,
        estado_codigo: 1,
        mecanico_actual_id: null,
        creado_por_id: 3,
        creado_en: '2026-11-08T15:10:00-03:00',
        actualizado_en: '2026-11-08T15:10:00-03:00',
        devuelto_en: null,
        devuelto_por_id: null,
    };

    it('revisar envía solo decisión y respuesta recortada y devuelve la auditoría del servidor', async () => {
        vi.mocked(apiClient.post).mockResolvedValue({ status: 200, data: revisadaApi });

        const s = await nuevaAtencionService.revisar('4', 'aceptada', '  Lo esperamos el lunes \n');

        expect(apiClient.post).toHaveBeenCalledWith('/ordenes/nuevas-atenciones/4/revision', {
            decision: 'aceptada',
            respuesta: 'Lo esperamos el lunes',
        });
        expect(s).toMatchObject({ situacion: 'aceptada', revisorId: '3', revisadaEn: '2026-11-08T15:00:00-03:00' });
    });

    it('una revisión sin auditoría o aún pendiente no se da por buena', async () => {
        vi.mocked(apiClient.post)
            .mockResolvedValueOnce({ status: 200, data: { ...revisadaApi, revisor_id: null } })
            .mockResolvedValueOnce({ status: 200, data: solicitudApi });

        await expect(nuevaAtencionService.revisar('4', 'aceptada', 'Ok')).rejects.toBeInstanceOf(RespuestaIncompletaError);
        await expect(nuevaAtencionService.revisar('4', 'aceptada', 'Ok')).rejects.toBeInstanceOf(RespuestaIncompletaError);
    });

    it('generarOrden usa su endpoint con body {} y distingue 201 de 200 sin forzar el estado', async () => {
        vi.mocked(apiClient.post)
            .mockResolvedValueOnce({ status: 201, data: { solicitud: { ...revisadaApi, orden_generada_id: 30 }, orden: ordenApi } })
            .mockResolvedValueOnce({ status: 200, data: { solicitud: { ...revisadaApi, orden_generada_id: 30 }, orden: { ...ordenApi, estado_codigo: 5, mecanico_actual_id: 40 } } });

        const nueva = await nuevaAtencionService.generarOrden('4');
        const existente = await nuevaAtencionService.generarOrden('4');

        expect(apiClient.post).toHaveBeenNthCalledWith(1, '/ordenes/nuevas-atenciones/4/orden', {});
        expect(apiClient.post).not.toHaveBeenCalledWith('/ordenes', expect.anything());
        expect(nueva).toMatchObject({ creada: true, orden: { id: '30', estadoCodigo: 1, mecanicoActualId: null } });
        expect(nueva.solicitud.ordenGeneradaId).toBe('30');
        expect(existente).toMatchObject({ creada: false, orden: { id: '30', estadoCodigo: 5 } });
    });

    it('una generación sin la orden vinculada no se da por buena', async () => {
        vi.mocked(apiClient.post)
            .mockResolvedValueOnce({ status: 201, data: { solicitud: revisadaApi, orden: ordenApi } })
            .mockResolvedValueOnce({ status: 201, data: { solicitud: { ...revisadaApi, orden_generada_id: 30 } } });

        await expect(nuevaAtencionService.generarOrden('4')).rejects.toBeInstanceOf(RespuestaIncompletaError);
        await expect(nuevaAtencionService.generarOrden('4')).rejects.toBeInstanceOf(RespuestaIncompletaError);
    });
});

