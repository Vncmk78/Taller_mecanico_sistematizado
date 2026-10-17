import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { Evidencia, EvidenciaEntradaCrear } from '@/domain/entities/Evidencia';
import { useEvidenceStore } from '@/infrastructure/stores/useEvidenceStore';

const evidencia: Evidencia = {
    id: 'ev-1',
    orderId: '31',
    presupuestoId: null,
    contexto: 'diagnostico',
    tipoArchivo: 'foto',
    visibleCliente: false,
    estado: 'confirmada',
    nombreOriginal: 'frenos.jpg',
    contentType: 'image/jpeg',
    tamanoBytes: 1024,
    creadaEn: '2026-10-07T10:15:00-03:00',
};

const entrada = {
    ordenId: '31',
    archivo: new File(['x'], 'frenos.jpg', { type: 'image/jpeg' }),
    contexto: 'diagnostico' as const,
};

describe('useEvidenceStore: subida de evidencia', () => {
    beforeEach(() => {
        useEvidenceStore.getState().reset();
    });

    it('subir guarda el progreso y agrega la evidencia al confirmar', async () => {
        const loader = vi.fn(
            async (_entrada: EvidenciaEntradaCrear, onProgress: (p: number) => void) => {
                onProgress(40);
                onProgress(100);
                return evidencia;
            }
        );

        const resultado = await useEvidenceStore.getState().subir(entrada, loader);

        expect(resultado).toEqual(evidencia);
        const estado = useEvidenceStore.getState();
        expect(estado.uploadStatus).toBe('success');
        expect(estado.uploadProgress).toBe(100);
        expect(estado.evidencias).toContainEqual(evidencia);
        expect(estado.uploadError).toBeNull();
        expect(estado.uploadIsOffline).toBe(false);
    });

    it('subir expone el error del servidor sin marcar offline', async () => {
        const loader = vi.fn().mockRejectedValue({ isAxiosError: true, response: { status: 500, data: {} } });

        const resultado = await useEvidenceStore.getState().subir(entrada, loader);

        expect(resultado).toBeNull();
        const estado = useEvidenceStore.getState();
        expect(estado.uploadStatus).toBe('error');
        expect(estado.uploadIsOffline).toBe(false);
        expect(estado.uploadError).toBeTruthy();
        expect(estado.evidencias).toHaveLength(0);
    });

    it('subir marca offline cuando no hubo respuesta del servidor', async () => {
        const loader = vi.fn().mockRejectedValue({ isAxiosError: true });

        await useEvidenceStore.getState().subir(entrada, loader);

        const estado = useEvidenceStore.getState();
        expect(estado.uploadStatus).toBe('error');
        expect(estado.uploadIsOffline).toBe(true);
    });

    it('subir evita envíos simultáneos', async () => {
        let resolver: (valor: Evidencia) => void = () => {};
        const loader = vi.fn(
            () => new Promise<Evidencia>((resolve) => {
                resolver = resolve;
            })
        );

        const primera = useEvidenceStore.getState().subir(entrada, loader);
        expect(useEvidenceStore.getState().uploadStatus).toBe('uploading');

        const segunda = await useEvidenceStore.getState().subir(entrada, loader);
        expect(segunda).toBeNull();
        expect(loader).toHaveBeenCalledTimes(1);

        resolver(evidencia);
        await primera;
        expect(useEvidenceStore.getState().uploadStatus).toBe('success');
    });

    it('reset limpia la lista y el estado de subida', () => {
        useEvidenceStore.setState({
            evidencias: [evidencia],
            uploadStatus: 'error',
            uploadProgress: 50,
            uploadError: 'boom',
        });

        useEvidenceStore.getState().reset();

        const estado = useEvidenceStore.getState();
        expect(estado.evidencias).toHaveLength(0);
        expect(estado.uploadStatus).toBe('idle');
        expect(estado.uploadProgress).toBe(0);
        expect(estado.uploadError).toBeNull();
    });
});