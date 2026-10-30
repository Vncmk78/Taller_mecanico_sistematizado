import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { Evidencia } from '@/domain/entities/Evidencia';
import type { Presupuesto } from '@/domain/entities/Presupuesto';
import { evidenciaService } from '@/infrastructure/api/EvidenciaService';
import { presupuestoService } from '@/infrastructure/api/PresupuestoService';
import { useEvidenceStore } from '@/infrastructure/stores/useEvidenceStore';
import { ToastProvider } from '@/presentation/components/ui/ToastProvider';
import { EvidenceUploadForm } from './EvidenceUploadForm';

vi.mock('@/infrastructure/api/EvidenciaService', () => ({
    evidenciaService: {
        getByOrder: vi.fn(),
        getById: vi.fn(),
        getDownloadUrl: vi.fn(),
        crear: vi.fn(),
    },
}));

vi.mock('@/infrastructure/api/PresupuestoService', () => ({
    presupuestoService: {
        getByOrder: vi.fn(),
        getById: vi.fn(),
        decidir: vi.fn(),
    },
}));

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

const axios500 = { isAxiosError: true, response: { status: 500, data: {} } };
const axiosNetworkError = { isAxiosError: true };

function renderForm() {
    return render(
        <ToastProvider>
            <EvidenceUploadForm orderId="31" />
        </ToastProvider>
    );
}

function seleccionarArchivo(file: File) {
    const input = screen.getByLabelText(/Archivo/) as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file] } });
}

describe('EvidenceUploadForm: carga de evidencia con progreso y estados', () => {
    beforeEach(() => {
        useEvidenceStore.getState().reset();
        vi.clearAllMocks();
    });

    it('sube el archivo y confirma el éxito', async () => {
        vi.mocked(evidenciaService.crear).mockResolvedValue(evidencia);

        renderForm();
        seleccionarArchivo(new File(['x'], 'frenos.jpg', { type: 'image/jpeg' }));
        fireEvent.click(screen.getByRole('button', { name: /Subir evidencia/ }));

        expect(await screen.findAllByText('Evidencia subida correctamente.')).not.toHaveLength(0);
        expect(evidenciaService.crear).toHaveBeenCalledWith(
            expect.objectContaining({
                ordenId: '31',
                contexto: 'diagnostico',
                visibleCliente: false,
            }),
            expect.any(Function)
        );
    });

    it('muestra el porcentaje de progreso durante la subida', async () => {
        let resolver: (valor: Evidencia) => void = () => {};
        vi.mocked(evidenciaService.crear).mockImplementation((_entrada, onProgress) => {
            onProgress?.(37);
            return new Promise<Evidencia>((resolve) => {
                resolver = resolve;
            });
        });

        renderForm();
        seleccionarArchivo(new File(['x'], 'frenos.jpg', { type: 'image/jpeg' }));
        fireEvent.click(screen.getByRole('button', { name: /Subir evidencia/ }));

        expect(await screen.findByText('37%')).toBeInTheDocument();
        expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '37');

        await act(async () => {
            resolver(evidencia);
        });
    });

    it('valida el tipo de archivo antes de enviar', async () => {
        renderForm();
        seleccionarArchivo(new File(['x'], 'notas.txt', { type: 'text/plain' }));
        fireEvent.click(screen.getByRole('button', { name: /Subir evidencia/ }));

        expect(await screen.findByText('Solo se permiten imágenes o videos.')).toBeInTheDocument();
        expect(evidenciaService.crear).not.toHaveBeenCalled();
    });

    it('rechaza archivos que superan el límite', async () => {
        renderForm();
        const grande = new File(['x'], 'enorme.jpg', { type: 'image/jpeg' });
        Object.defineProperty(grande, 'size', { value: 13 * 1024 * 1024 });
        seleccionarArchivo(grande);
        fireEvent.click(screen.getByRole('button', { name: /Subir evidencia/ }));

        expect(await screen.findByText(/supera el límite/)).toBeInTheDocument();
        expect(evidenciaService.crear).not.toHaveBeenCalled();
    });

    it('muestra el error del servidor', async () => {
        vi.mocked(evidenciaService.crear).mockRejectedValue(axios500);

        renderForm();
        seleccionarArchivo(new File(['x'], 'frenos.jpg', { type: 'image/jpeg' }));
        fireEvent.click(screen.getByRole('button', { name: /Subir evidencia/ }));

        expect(
            await screen.findByText(/El servidor tuvo un problema/)
        ).toBeInTheDocument();
    });

    it('sin conexión muestra un aviso claro', async () => {
        vi.mocked(evidenciaService.crear).mockRejectedValue(axiosNetworkError);

        renderForm();
        seleccionarArchivo(new File(['x'], 'frenos.jpg', { type: 'image/jpeg' }));
        fireEvent.click(screen.getByRole('button', { name: /Subir evidencia/ }));

        expect(await screen.findByText(/Sin conexión: no se pudo subir la evidencia/)).toBeInTheDocument();
    });

    it('en contexto presupuesto asocia el presupuesto de la orden', async () => {
        vi.mocked(presupuestoService.getByOrder).mockResolvedValue({ id: '501' } as unknown as Presupuesto);
        vi.mocked(evidenciaService.crear).mockResolvedValue(evidencia);

        renderForm();
        fireEvent.change(screen.getByLabelText('Contexto'), { target: { value: 'presupuesto' } });
        seleccionarArchivo(new File(['x'], 'presupuesto.jpg', { type: 'image/jpeg' }));

        // El presupuesto de la orden se resuelve de forma asíncrona; se espera a que
        // esté disponible antes de que la subida pueda asociarlo.
        await waitFor(() => {
            fireEvent.click(screen.getByRole('button', { name: /Subir evidencia/ }));
            expect(evidenciaService.crear).toHaveBeenCalledWith(
                expect.objectContaining({ contexto: 'presupuesto', presupuestoId: '501', visibleCliente: true }),
                expect.any(Function)
            );
        });
    });
});