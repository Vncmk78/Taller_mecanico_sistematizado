import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { evidenciaService } from '@/infrastructure/api/EvidenciaService';
import { useEvidenceStore } from '@/infrastructure/stores/useEvidenceStore';
import { useOrderStore } from '@/infrastructure/stores/useOrderStore';
import { mockEvidenciasOrden101, mockEvidenciaFrenos } from '@/infrastructure/mocks/evidence.mock';
import { ClientOrderEvidencePage } from './ClientOrderEvidencePage';

vi.mock('@/infrastructure/api/EvidenciaService', () => ({
    evidenciaService: {
        getByOrder: vi.fn(),
        getById: vi.fn(),
        getDownloadUrl: vi.fn(),
    },
}));

const axios404 = { isAxiosError: true, response: { status: 404, data: {} } };
const axiosNetworkError = { isAxiosError: true };
const axios500 = { isAxiosError: true, response: { status: 500, data: {} } };

function renderPage() {
    return render(
        <MemoryRouter initialEntries={['/client/ordenes/101/evidencias']}>
            <Routes>
                <Route path="/client/ordenes/:id/evidencias" element={<ClientOrderEvidencePage />} />
            </Routes>
        </MemoryRouter>
    );
}

function mockDownloadOk(url = 'https://almacenamiento.taller.example/evidencias/x.jpg?firma') {
    vi.mocked(evidenciaService.getDownloadUrl).mockResolvedValue({ url, expiraEn: 300 });
}

describe('ClientOrderEvidencePage: evidencia multimedia del cliente', () => {
    beforeEach(() => {
        useEvidenceStore.setState({
            evidencias: [],
            status: 'idle',
            error: null,
            isOffline: false,
            requestId: null,
        });
        useOrderStore.setState({ orders: [], status: 'idle', error: null, isOffline: false, requestId: null });
        vi.clearAllMocks();
        vi.restoreAllMocks();
    });

    it('lista las evidencias visibles con su contexto, tamaño y miniatura', async () => {
        vi.mocked(evidenciaService.getByOrder).mockResolvedValue(mockEvidenciasOrden101);
        mockDownloadOk();

        renderPage();

        expect(await screen.findByText('Evidencia multimedia')).toBeInTheDocument();
        expect(screen.getByText('desgaste-pastillas.jpg')).toBeInTheDocument();
        expect(screen.getByText('filtro-motor.jpg')).toBeInTheDocument();
        expect(screen.getByText('prueba-motor.mp4')).toBeInTheDocument();
        // Contextos en español.
        expect(screen.getAllByText('Resultado final').length).toBeGreaterThan(0);
        expect(screen.getByText('Diagnóstico')).toBeInTheDocument();
        // La miniatura de la foto se resuelve con la URL prefirmada.
        expect(await screen.findByAltText('desgaste-pastillas.jpg')).toHaveAttribute(
            'src',
            'https://almacenamiento.taller.example/evidencias/x.jpg?firma'
        );
    });

    it('un servicio sin evidencia visible muestra el estado vacío', async () => {
        vi.mocked(evidenciaService.getByOrder).mockResolvedValue([]);

        renderPage();

        expect(await screen.findByText('Aún no hay evidencia multimedia')).toBeInTheDocument();
    });

    it('un servicio ajeno o inexistente (404) no se confunde con una lista vacía', async () => {
        vi.mocked(evidenciaService.getByOrder).mockRejectedValue(axios404);

        renderPage();

        expect(await screen.findByText('Servicio no encontrado.')).toBeInTheDocument();
        expect(screen.queryByText('Aún no hay evidencia multimedia')).not.toBeInTheDocument();
    });

    it('un error del servidor ofrece reintentar', async () => {
        vi.mocked(evidenciaService.getByOrder).mockRejectedValue(axios500);

        renderPage();

        expect(await screen.findByText('No se pudo cargar la evidencia')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Reintentar' })).toBeInTheDocument();
    });

    it('sin conexión conserva las evidencias desde la caché', async () => {
        useEvidenceStore.setState({ evidencias: mockEvidenciasOrden101 });
        vi.mocked(evidenciaService.getByOrder).mockRejectedValue(axiosNetworkError);
        mockDownloadOk();

        renderPage();

        expect(await screen.findByText('desgaste-pastillas.jpg')).toBeInTheDocument();
        expect(await screen.findByText(/No se pudo conectar con el servidor/)).toBeInTheDocument();
    });

    it('abre la vista previa y permite descargar el archivo original', async () => {
        vi.mocked(evidenciaService.getByOrder).mockResolvedValue([mockEvidenciaFrenos]);
        mockDownloadOk();
        const openSpy = vi.spyOn(window, 'open').mockImplementation(() => null);

        renderPage();

        // Espera a que la URL prefirmada resuelva la miniatura antes de abrir.
        await screen.findByAltText('desgaste-pastillas.jpg');
        fireEvent.click(screen.getByRole('button', { name: 'Ver desgaste-pastillas.jpg' }));

        const dialog = screen.getByRole('dialog', { name: 'Vista previa de desgaste-pastillas.jpg' });
        expect(dialog).toBeInTheDocument();

        fireEvent.click(screen.getByRole('button', { name: /Descargar/ }));
        expect(openSpy).toHaveBeenCalledWith(
            'https://almacenamiento.taller.example/evidencias/x.jpg?firma',
            '_blank',
            'noopener,noreferrer'
        );
    });

    it('filtra la galería por contexto y permite volver al listado completo', async () => {
        vi.mocked(evidenciaService.getByOrder).mockResolvedValue(mockEvidenciasOrden101);
        mockDownloadOk();

        renderPage();

        expect(await screen.findByText('desgaste-pastillas.jpg')).toBeInTheDocument();

        fireEvent.click(screen.getByRole('button', { name: 'Resultado final (2)' }));

        expect(await screen.findByText('filtro-motor.jpg')).toBeInTheDocument();
        expect(screen.getByText('prueba-motor.mp4')).toBeInTheDocument();
        expect(screen.queryByText('desgaste-pastillas.jpg')).not.toBeInTheDocument();
        expect(screen.getByText(/Mostrando 2 de 3 archivos\./)).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Resultado final (2)' })).toHaveAttribute(
            'aria-pressed',
            'true'
        );

        fireEvent.click(screen.getByRole('button', { name: 'Todos (3)' }));

        expect(await screen.findByText('desgaste-pastillas.jpg')).toBeInTheDocument();
        expect(screen.queryByText(/Mostrando/)).not.toBeInTheDocument();
    });

    it('si la URL prefirmada falla, la tarjeta ofrece reintentar en vez de mostrar la imagen rota', async () => {
        vi.mocked(evidenciaService.getByOrder).mockResolvedValue([mockEvidenciaFrenos]);
        vi.mocked(evidenciaService.getDownloadUrl).mockRejectedValue(axios500);

        renderPage();

        expect(await screen.findByText('No se pudo cargar el archivo.')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /Reintentar/ })).toBeInTheDocument();
        expect(screen.queryByAltText('desgaste-pastillas.jpg')).not.toBeInTheDocument();
    });
});
