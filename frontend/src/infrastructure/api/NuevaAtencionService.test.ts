import { beforeEach, describe, expect, it, vi } from 'vitest';
import apiClient from '@/infrastructure/config/apiClient';
import { nuevaAtencionService } from './NuevaAtencionService';

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
