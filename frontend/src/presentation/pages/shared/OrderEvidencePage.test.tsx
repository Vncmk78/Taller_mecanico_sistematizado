import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { evidenciaService } from '@/infrastructure/api/EvidenciaService';
import { useEvidenceStore } from '@/infrastructure/stores/useEvidenceStore';
import { mockEvidenciasOrden101 } from '@/infrastructure/mocks/evidence.mock';
import { ToastProvider } from '@/presentation/components/ui/ToastProvider';
import { OrderEvidencePage } from './OrderEvidencePage';

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

const axios404 = { isAxiosError: true, response: { status: 404, data: {} } };

function renderPage() {
    return render(
        <ToastProvider>
            <MemoryRouter initialEntries={['/mechanic/ordenes/101/evidencias']}>
                <Routes>
                    <Route
                        path="/mechanic/ordenes/:id/evidencias"
                        element={
                            <OrderEvidencePage
                                backTo="/mechanic/ordenes"
                                backLabel="Volver a mis órdenes"
                                canUpload
                            />
                        }
                    />
                </Routes>
            </MemoryRouter>
        </ToastProvider>
    );
}

describe('OrderEvidencePage: evidencia del personal', () => {
    beforeEach(() => {
        useEvidenceStore.getState().reset();
        vi.clearAllMocks();
        vi.mocked(evidenciaService.getDownloadUrl).mockResolvedValue({
            url: 'https://almacenamiento.taller.example/evidencias/x.jpg?firma',
            expiraEn: 300,
        });
    });

    it('muestra el encabezado, el formulario de carga y la galería', async () => {
        vi.mocked(evidenciaService.getByOrder).mockResolvedValue(mockEvidenciasOrden101);

        renderPage();

        expect(await screen.findByText('Evidencia multimedia')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /Subir evidencia/ })).toBeInTheDocument();
        expect(await screen.findByText('desgaste-pastillas.jpg')).toBeInTheDocument();
        expect(
            screen.getByRole('link', { name: 'Volver a mis órdenes' })
        ).toHaveAttribute('href', '/mechanic/ordenes');
    });

    it('sin evidencia muestra el estado vacío con el formulario', async () => {
        vi.mocked(evidenciaService.getByOrder).mockResolvedValue([]);

        renderPage();

        expect(await screen.findByText('Aún no hay evidencia multimedia')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /Subir evidencia/ })).toBeInTheDocument();
    });

    it('una orden ajena o inexistente (404) muestra la orden no encontrada', async () => {
        vi.mocked(evidenciaService.getByOrder).mockRejectedValue(axios404);

        renderPage();

        expect(await screen.findByText('Orden no encontrada.')).toBeInTheDocument();
    });
});