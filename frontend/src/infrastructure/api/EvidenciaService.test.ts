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

    it('crear sube el archivo como multipart con sus metadatos', async () => {
        vi.mocked(apiClient.post).mockResolvedValue({ data: evidenciaApi });
        const archivo = new File(['contenido'], 'frenos delanteros.jpg', { type: 'image/jpeg' });

        const evidencia = await evidenciaService.crear({
            ordenId: '31',
            archivo,
            contexto: 'diagnostico',
            visibleCliente: true,
        });

        expect(apiClient.post).toHaveBeenCalledWith(
            '/evidencias',
            expect.any(FormData),
            expect.objectContaining({ onUploadProgress: expect.any(Function) })
        );
        const form = vi.mocked(apiClient.post).mock.calls[0][1] as FormData;
        expect(form.get('archivo')).toBe(archivo);
        expect(form.get('orden_id')).toBe('31');
        expect(form.get('contexto')).toBe('diagnostico');
        expect(form.get('visible_cliente')).toBe('true');
        // Sin presupuesto el campo no se envía (el backend aplica su defecto).
        expect(form.get('presupuesto_id')).toBeNull();
        expect(evidencia.id).toBe(evidenciaApi.evidencia_id);
    });

    it('crear asocia el presupuesto cuando el contexto es presupuesto', async () => {
        vi.mocked(apiClient.post).mockResolvedValue({ data: evidenciaApi });
        const archivo = new File(['contenido'], 'detalle.png', { type: 'image/png' });

        await evidenciaService.crear({
            ordenId: '31',
            archivo,
            contexto: 'presupuesto',
            presupuestoId: '501',
        });

        const form = vi.mocked(apiClient.post).mock.calls[0][1] as FormData;
        expect(form.get('presupuesto_id')).toBe('501');
        // No se envía visible_cliente: en presupuesto el backend lo fuerza a true.
        expect(form.get('visible_cliente')).toBeNull();
    });

    it('crear reporta el progreso de la subida como porcentaje', async () => {
        vi.mocked(apiClient.post).mockResolvedValue({ data: evidenciaApi });
        const archivo = new File(['contenido'], 'video.mp4', { type: 'video/mp4' });
        const progresos: number[] = [];

        await evidenciaService.crear(
            { ordenId: '31', archivo, contexto: 'reparacion' },
            (porcentaje) => progresos.push(porcentaje)
        );

        const config = vi.mocked(apiClient.post).mock.calls[0][2] as {
            onUploadProgress: (evento: { loaded: number; total?: number }) => void;
        };
        config.onUploadProgress({ loaded: 50, total: 200 });
        config.onUploadProgress({ loaded: 200, total: 200 });

        expect(progresos).toEqual([25, 100]);
    });
});
