import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { presupuestoService } from '@/infrastructure/api/PresupuestoService';
import { repuestoService } from '@/infrastructure/api/RepuestoService';
import { orderService } from '@/infrastructure/api/OrderService';
import { useAuthStore } from '@/infrastructure/stores/useAuthStore';
import { AplicacionPresupuestoPendienteError } from '@/domain/ports/PresupuestoPort';
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
vi.mock('@/infrastructure/api/OrderService', () => ({
    orderService: { getOrderById: vi.fn() },
}));
vi.mock('@/infrastructure/api/RepuestoService', () => ({
    repuestoService: { getRepuestos: vi.fn() },
}));

describe('MechanicBudgetPage', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        vi.mocked(orderService.getOrderById).mockResolvedValue({ id: '101', estadoCodigo: 2 } as never);
        useAuthStore.setState({ user: { id: '2', email: 'm@pruebas.cl', full_name: 'M', role: 'mecanico', roles: ['mecanico'], is_active: true } });
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


    const borrador = { id: '501', orderId: '101', versiones: [{ numero: 1, estado: 'borrador', total: 100, items: [{ id: '1', tipo: 'mano_de_obra', descripcion: 'Diagnóstico', cantidad: 1, precioUnitario: 100, subtotal: 100, repuestoId: null }] }] };
    const enviado = { ...borrador, versiones: [{ ...borrador.versiones[0], estado: 'enviada' }] };

    function renderEditor(administrador: boolean) {
        return render(<MemoryRouter initialEntries={['/ordenes/101/presupuesto']}><Routes>
            <Route path="/ordenes/:id/presupuesto" element={<BudgetEditor administrador={administrador} />} />
        </Routes></MemoryRouter>);
    }

    it('una cuenta solo Mecánico no ve el envío ni el acceso administrativo', async () => {
        vi.mocked(presupuestoService.getByOrder).mockResolvedValue(borrador as never);
        vi.mocked(presupuestoService.getById).mockResolvedValue(borrador as never);
        renderEditor(false);
        await screen.findByText(/Versión 1/);
        expect(screen.getByText(/Un Administrador revisa los precios y la envía al cliente/)).toBeInTheDocument();
        expect(screen.queryByRole('link', { name: /Revisar y enviar como Administrador/ })).not.toBeInTheDocument();
        expect(screen.queryByRole('button', { name: /Enviar al cliente/ })).not.toBeInTheDocument();
    });

    it('una cuenta Mecánico y Administrador ve el acceso a la revisión administrativa', async () => {
        useAuthStore.setState({ user: { id: '6', email: 'ma@pruebas.cl', full_name: 'MA', role: 'mecanico', roles: ['mecanico', 'administrador'], is_active: true } });
        vi.mocked(presupuestoService.getByOrder).mockResolvedValue(borrador as never);
        vi.mocked(presupuestoService.getById).mockResolvedValue(borrador as never);
        renderEditor(false);
        await screen.findByText(/Versión 1/);
        expect(screen.getByRole('link', { name: /Revisar y enviar como Administrador/ })).toHaveAttribute('href', '/admin/ordenes/101/presupuesto');
        expect(screen.queryByRole('button', { name: /Enviar al cliente/ })).not.toBeInTheDocument();
    });

    it('un 503 del envío conserva la referencia y ofrece solo el reintento de aplicación', async () => {
        vi.mocked(presupuestoService.getByOrder).mockResolvedValue(borrador as never);
        vi.mocked(presupuestoService.getById).mockResolvedValueOnce(borrador as never).mockResolvedValue(enviado as never);
        vi.mocked(presupuestoService.send).mockRejectedValue(new AplicacionPresupuestoPendienteError('envio', '501'));
        vi.mocked(presupuestoService.aplicarEnvio).mockResolvedValue(undefined);
        renderEditor(true);
        fireEvent.click(await screen.findByRole('button', { name: /Enviar al cliente/ }));
        const reintentar = await screen.findByRole('button', { name: 'Reintentar aplicación en la orden' });
        expect(screen.getByText(/Presupuesto n° 501/)).toBeInTheDocument();
        expect(screen.queryByRole('button', { name: /Enviar al cliente/ })).not.toBeInTheDocument();

        vi.mocked(orderService.getOrderById).mockResolvedValue({ id: '101', estadoCodigo: 3 } as never);
        fireEvent.click(reintentar);
        await screen.findByText(/Aplicación confirmada/);
        expect(presupuestoService.aplicarEnvio).toHaveBeenCalledWith('501');
        expect(presupuestoService.send).toHaveBeenCalledOnce();
        expect(screen.queryByRole('button', { name: 'Reintentar aplicación en la orden' })).not.toBeInTheDocument();
    });

    it('al recargar, una versión enviada con la orden sin avanzar se reconoce como pendiente', async () => {
        vi.mocked(presupuestoService.getByOrder).mockResolvedValue(enviado as never);
        vi.mocked(presupuestoService.getById).mockResolvedValue(enviado as never);
        renderEditor(true);
        expect(await screen.findByRole('button', { name: 'Reintentar aplicación en la orden' })).toBeInTheDocument();
    });

    it('sin pendiente no muestra el panel de reintento', async () => {
        vi.mocked(orderService.getOrderById).mockResolvedValue({ id: '101', estadoCodigo: 3 } as never);
        vi.mocked(presupuestoService.getByOrder).mockResolvedValue(enviado as never);
        vi.mocked(presupuestoService.getById).mockResolvedValue(enviado as never);
        renderEditor(true);
        await screen.findByText(/Versión 1/);
        await vi.waitFor(() => expect(orderService.getOrderById).toHaveBeenCalled());
        expect(screen.queryByRole('button', { name: 'Reintentar aplicación en la orden' })).not.toBeInTheDocument();
    });
});
