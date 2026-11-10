import { beforeEach, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, within } from '@testing-library/react';
import type { Movimiento } from '@/domain/entities/Inventario';
import { inventarioService } from '@/infrastructure/api/InventarioService';
import { repuestoService } from '@/infrastructure/api/RepuestoService';
import { AdminInventoryMovementsPage } from './AdminInventoryMovementsPage';

vi.mock('@/infrastructure/api/InventarioService', () => ({
    inventarioService: { listMovimientos: vi.fn(), registrarMovimiento: vi.fn() },
}));
vi.mock('@/infrastructure/api/RepuestoService', () => ({
    repuestoService: { getRepuestos: vi.fn() },
}));

const CONSUMO: Movimiento = {
    movimientoId: 9, claveOperacion: 'k-9', repuestoId: 2, tipo: 'consumo', cantidad: 3,
    ordenId: 41, proveedorId: null, fechaHora: '2026-11-09T17:00:00Z', registradoPorId: 2,
};

beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(inventarioService.listMovimientos).mockResolvedValue({ total: 1, desde: 0, limite: 50, movimientos: [CONSUMO] });
    vi.mocked(repuestoService.getRepuestos).mockResolvedValue({
        total: 1, desde: 0, limite: 200, umbralGeneral: 5,
        repuestos: [{ repuestoId: 2, nombre: 'Disco de freno delantero' }],
    } as never);
});

it('muestra repuesto, cantidad, orden, responsable y fecha del movimiento', async () => {
    render(<AdminInventoryMovementsPage />);
    const fila = (await screen.findByText('Disco de freno delantero (#2)')).closest('tr')!;
    expect(within(fila).getByText('consumo')).toBeInTheDocument();
    expect(within(fila).getByText('3')).toBeInTheDocument();
    expect(within(fila).getByText('41')).toBeInTheDocument();
    expect(within(fila).getByText('Usuario #2')).toBeInTheDocument();
    expect(within(fila).getByText(new Date(CONSUMO.fechaHora).toLocaleString('es-CL'))).toBeInTheDocument();
});

it('con stock insuficiente explica cuánto falta y que no se registró nada', async () => {
    vi.mocked(inventarioService.registrarMovimiento).mockRejectedValue({
        isAxiosError: true,
        response: { status: 409, data: {
            detail: "El ajuste dejaría el stock de 'Disco de freno delantero' en -3",
            faltantes: [{ repuesto_id: 2, nombre: 'Disco de freno delantero', solicitado: 5, disponible: 2, faltan: 3 }],
        } },
    });
    render(<AdminInventoryMovementsPage />);
    fireEvent.click(await screen.findByRole('button', { name: 'Registrar movimiento' }));
    const dialogo = await screen.findByRole('dialog', { name: 'Registrar movimiento' });
    fireEvent.change(within(dialogo).getByLabelText(/Repuesto/), { target: { value: '2' } });
    fireEvent.change(within(dialogo).getByLabelText('Tipo'), { target: { value: 'ajuste' } });
    fireEvent.change(within(dialogo).getByLabelText(/Cantidad/), { target: { value: '-5' } });
    fireEvent.click(within(dialogo).getByRole('button', { name: 'Registrar' }));
    expect(await within(dialogo).findByText(/faltan 3 \(disponible 2, solicitado 5\)/)).toBeInTheDocument();
    expect(within(dialogo).getByText(/No se registró ningún cambio/)).toBeInTheDocument();
    expect(inventarioService.listMovimientos).toHaveBeenCalledTimes(1);
});
