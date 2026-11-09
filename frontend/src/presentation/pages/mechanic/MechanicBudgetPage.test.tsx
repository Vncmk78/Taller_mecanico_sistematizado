import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { presupuestoService } from '@/infrastructure/api/PresupuestoService';
import { repuestoService } from '@/infrastructure/api/RepuestoService';
import { BudgetEditor } from '@/presentation/components/budgets/BudgetEditor';
import { MechanicBudgetPage } from './MechanicBudgetPage';

vi.mock('@/infrastructure/api/PresupuestoService', () => ({
    presupuestoService: {
        getByOrder: vi.fn(),
        getById: vi.fn(),
        aplicarEnvio: vi.fn(),
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
    it.each([false, true])('el envío es exclusivo de la vista administrativa (%s)', async (administrador) => {
        const presupuesto = { id: '501', orderId: '101', versiones: [{ numero: 1, estado: 'borrador', total: 100, items: [{ id: '1', tipo: 'mano_de_obra', descripcion: 'Diagnóstico', cantidad: 1, precioUnitario: 100, subtotal: 100, repuestoId: null }] }] };
        vi.mocked(presupuestoService.getByOrder).mockResolvedValue(presupuesto as never);
        vi.mocked(presupuestoService.getById).mockResolvedValue(presupuesto as never);
        render(<MemoryRouter initialEntries={['/ordenes/101/presupuesto']}><Routes>
            <Route path="/ordenes/:id/presupuesto" element={<BudgetEditor administrador={administrador} />} />
        </Routes></MemoryRouter>);
        await screen.findByText(/Versión 1/);
        expect(presupuestoService.getById).toHaveBeenCalledWith('501');
        const enviar = screen.queryByRole('button', { name: /Enviar al cliente/ });
        if (!administrador) expect(enviar).not.toBeInTheDocument();
        else {
            fireEvent.change(screen.getByDisplayValue('100'), { target: { value: '250' } });
            fireEvent.click(enviar!);
            await waitFor(() => expect(presupuestoService.send).toHaveBeenCalledWith('501', 1));
            expect(presupuestoService.replaceItems).toHaveBeenCalledWith('501', 1, [expect.objectContaining({ precioUnitario: 250 })]);
            expect(vi.mocked(presupuestoService.replaceItems).mock.invocationCallOrder[0]).toBeLessThan(vi.mocked(presupuestoService.send).mock.invocationCallOrder[0]);
        }
    });

});
