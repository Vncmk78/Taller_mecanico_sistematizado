import { beforeEach, describe, expect, it, vi } from 'vitest';
import { evidenciaService } from '@/infrastructure/api/EvidenciaService';
import apiClient from '@/infrastructure/config/apiClient';

// Fija el contrato HTTP de MS4 consumido por el frontend (ver
// docs/contratos-openapi.md). La respuesta no trae la URL del archivo: se pide
// aparte como URL prefirmada.
vi.mock('@/infrastructure/config/apiClient', () => ({
    default: {
        get: vi.fn(),
        post: vi.fn(),
    },
}));

const evidenciaApi = {
    evidencia_id: '3f2b8c1e-5d4a-4e6b-9c7d-1a2b3c4d5e6f',
    orden_id: 31,
    presupuesto_id: null,
    contexto: 'diagnostico' as const,
    tipo_archivo: 'foto' as const,
    visible_cliente: false,
    estado: 'confirmada' as const,
    nombre_original: 'frenos delanteros.jpg',
    content_type: 'image/jpeg',
    tamano_bytes: 482133,
    creada_en: '2026-10-07T10:15:00-03:00',
};

describe('EvidenciaService: contrato HTTP de MS4 (evidencia multimedia)', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('getByOrder consulta GET /evidencias?orden_id y traduce los metadatos', async () => {
        vi.mocked(apiClient.get).mockResolvedValue({ data: [evidenciaApi] });

        const evidencias = await evidenciaService.getByOrder('31');

        expect(apiClient.get).toHaveBeenCalledWith('/evidencias', { params: { orden_id: '31' } });
        expect(evidencias).toEqual([
            {
                id: '3f2b8c1e-5d4a-4e6b-9c7d-1a2b3c4d5e6f',
                orderId: '31',
                presupuestoId: null,
                contexto: 'diagnostico',
                tipoArchivo: 'foto',
                visibleCliente: false,
                estado: 'confirmada',
                nombreOriginal: 'frenos delanteros.jpg',
                contentType: 'image/jpeg',
                tamanoBytes: 482133,
                creadaEn: '2026-10-07T10:15:00-03:00',
            },
        ]);
    });

    it('getByOrder devuelve una lista vacía cuando la orden no tiene evidencias visibles', async () => {
        vi.mocked(apiClient.get).mockResolvedValue({ data: [] });

        expect(await evidenciaService.getByOrder('31')).toEqual([]);
    });

    it('getById consulta el detalle y normaliza el presupuesto_id a string', async () => {
        vi.mocked(apiClient.get).mockResolvedValue({
            data: { ...evidenciaApi, contexto: 'presupuesto', presupuesto_id: 501, visible_cliente: true },
        });

        const evidencia = await evidenciaService.getById('3f2b8c1e-5d4a-4e6b-9c7d-1a2b3c4d5e6f');

        expect(apiClient.get).toHaveBeenCalledWith('/evidencias/3f2b8c1e-5d4a-4e6b-9c7d-1a2b3c4d5e6f');
        expect(evidencia.presupuestoId).toBe('501');
        expect(evidencia.contexto).toBe('presupuesto');
    });

    it('getDownloadUrl pide la URL prefirmada y expone su vigencia', async () => {
        vi.mocked(apiClient.get).mockResolvedValue({
            data: { url: 'https://almacenamiento.taller.example/evidencias/x.jpg?firma', expira_en: 300 },
        });

        const descarga = await evidenciaService.getDownloadUrl('3f2b8c1e-5d4a-4e6b-9c7d-1a2b3c4d5e6f');

        expect(apiClient.get).toHaveBeenCalledWith(
            '/evidencias/3f2b8c1e-5d4a-4e6b-9c7d-1a2b3c4d5e6f/descarga'
        );
        expect(descarga).toEqual({
            url: 'https://almacenamiento.taller.example/evidencias/x.jpg?firma',
            expiraEn: 300,
        });
    });
});
