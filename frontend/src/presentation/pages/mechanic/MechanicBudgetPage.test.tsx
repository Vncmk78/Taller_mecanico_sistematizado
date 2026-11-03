import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { presupuestoService } from '@/infrastructure/api/PresupuestoService';
import { repuestoService } from '@/infrastructure/api/RepuestoService';
import { MechanicBudgetPage } from './MechanicBudgetPage';

vi.mock('@/infrastructure/api/PresupuestoService', () => ({
    presupuestoService: {
        getByOrder: vi.fn(),
        create: vi.fn(),
        createVersion: vi.fn(),
        replaceItems: vi.fn(),
        send: vi.fn(),
    },
}));
vi.mock('@/infrastructure/api/RepuestoService', () => ({
    repuestoService: { getRepuestos: vi.fn() },
}));

describe('MechanicBudgetPage', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        vi.mocked(presupuestoService.getByOrder).mockResolvedValue(null);
        vi.mocked(repuestoService.getRepuestos).mockResolvedValue({ total: 0, desde: 0, limite: 200, umbralGeneral: null, repuestos: [] });
    });

    it('muestra el título de la página', async () => {
        render(
            <MemoryRouter initialEntries={['/mechanic/ordenes/101/presupuesto']}>
                <Routes>
                    <Route path="/mechanic/ordenes/:id/presupuesto" element={<MechanicBudgetPage />} />
                </Routes>
            </MemoryRouter>
        );
        expect(await screen.findByText(/Presupuesto de la orden/)).toBeInTheDocument();
    });

    it('permite agregar un ítem', async () => {
        render(
            <MemoryRouter initialEntries={['/mechanic/ordenes/101/presupuesto']}>
                <Routes>
                    <Route path="/mechanic/ordenes/:id/presupuesto" element={<MechanicBudgetPage />} />
                </Routes>
            </MemoryRouter>
        );
        await screen.findByText(/Presupuesto de la orden/);
        // El botón "Agregar ítem" está presente.
        expect(screen.getByRole('button', { name: /Agregar ítem/i })).toBeInTheDocument();
    });
});
