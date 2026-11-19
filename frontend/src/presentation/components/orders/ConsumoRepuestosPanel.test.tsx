import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { ResultadoDisponibilidad } from '@/domain/entities/Inventario';
import { inventarioService } from '@/infrastructure/api/InventarioService';
import { errorAxios } from '@/infrastructure/mocks/payloads.reales';
import { ConsumoRepuestosPanel } from './ConsumoRepuestosPanel';
import { puedeConsumirRepuestos } from './consumoRepuestos';

vi.mock('@/infrastructure/api/InventarioService', () => ({
    inventarioService: {
        getDisponibilidadOrden: vi.fn(),
        consumir: vi.fn(),
    },
}));

const disponibilidad: ResultadoDisponibilidad = {
    ordenId: 101,
    disponible: true,
    presupuestoId: 501,
    version: 2,
    repuestos: [
        {
            repuestoId: 12,
            nombre: 'Pastillas de freno',
            proveedorNombre: 'Repuestos Sur',
            requerido: 3,
            stock: 10,
            reservadoParaOrden: 0,
            comprometidoOtrasOrdenes: 0,
            disponible: 5,
            alcanza: true,
            faltan: 0,
        },
        {
            repuestoId: 13,
            nombre: 'Aceite 5W-30',
            proveedorNombre: 'Lubricantes Norte',
            requerido: 0,
            stock: 8,
            reservadoParaOrden: 0,
            comprometidoOtrasOrdenes: 0,
            disponible: 8,
            alcanza: true,
            faltan: 0,
        },
    ],
};

function renderPanel(onConsumed = vi.fn()) {
    const result = render(
        <ConsumoRepuestosPanel orderId="101" onConsumed={onConsumed} />
    );
    return { ...result, onConsumed };
}

describe('puedeConsumirRepuestos: ventana de trabajo en taller', () => {
    it.each([4, 5, 6])('permite consumir en el estado %i', (estado) => {
        expect(puedeConsumirRepuestos(estado)).toBe(true);
    });

    it.each([1, 2, 3, 7, 8])('no permite consumir en el estado %i', (estado) => {
        expect(puedeConsumirRepuestos(estado)).toBe(false);
    });
});

describe('ConsumoRepuestosPanel: descuento de repuestos de la orden', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        vi.mocked(inventarioService.getDisponibilidadOrden).mockResolvedValue(disponibilidad);
    });

    it('lista solo lo pendiente del presupuesto aprobado', async () => {
        renderPanel();

        expect(await screen.findByText('Pastillas de freno')).toBeInTheDocument();
        expect(screen.getByText(/Pendiente del presupuesto: 3/)).toBeInTheDocument();
        expect(screen.getByText(/Disponible para la orden: 5/)).toBeInTheDocument();
        // Lo ya consumido (requerido 0) no se ofrece de nuevo.
        expect(screen.queryByText('Aceite 5W-30')).not.toBeInTheDocument();
        expect(inventarioService.getDisponibilidadOrden).toHaveBeenCalledWith(101);
    });

    it('exige indicar al menos una cantidad', async () => {
        renderPanel();

        fireEvent.click(await screen.findByRole('button', { name: 'Registrar consumo' }));

        expect(
            screen.getByText('Indique la cantidad de al menos un repuesto para registrar el consumo.')
        ).toBeInTheDocument();
        expect(inventarioService.consumir).not.toHaveBeenCalled();
    });

    it('valida que la cantidad no supere lo requerido ni el stock disponible', async () => {
        renderPanel();

        fireEvent.change(await screen.findByLabelText('Cantidad de Pastillas de freno'), {
            target: { value: '4' },
        });
        fireEvent.click(screen.getByRole('button', { name: 'Registrar consumo' }));

        // máximo = mínimo(requerido 3, disponible 5)
        expect(screen.getByText('Puede consumir como máximo 3.')).toBeInTheDocument();
        expect(inventarioService.consumir).not.toHaveBeenCalled();
    });

    it('registra el consumo con clave idempotente y refresca disponibilidad y orden', async () => {
        vi.mocked(inventarioService.consumir).mockResolvedValue({
            ordenId: 101,
            movimientos: [],
            repetido: false,
        });

        const { onConsumed } = renderPanel();

        fireEvent.change(await screen.findByLabelText('Cantidad de Pastillas de freno'), {
            target: { value: '2' },
        });
        fireEvent.click(screen.getByRole('button', { name: 'Registrar consumo' }));

        await waitFor(() =>
            expect(inventarioService.consumir).toHaveBeenCalledWith(
                101,
                [{ repuestoId: 12, cantidad: 2 }],
                expect.stringMatching(/^[A-Za-z0-9._:-]{8,60}$/)
            )
        );
        expect(await screen.findByText('Consumo registrado para 1 repuesto.')).toBeInTheDocument();
        // Una carga inicial y el refresco posterior al consumo.
        expect(inventarioService.getDisponibilidadOrden).toHaveBeenCalledTimes(2);
        expect(onConsumed).toHaveBeenCalledTimes(1);
    });

    it('traduce el 409 con faltantes, no descuenta nada y refresca', async () => {
        vi.mocked(inventarioService.consumir).mockRejectedValue(
            errorAxios(409, {
                detail: 'Stock insuficiente para descontar los repuestos de la orden 101; no se descontó ninguno',
                faltantes: [
                    {
                        repuesto_id: 12,
                        nombre: 'Pastillas de freno',
                        solicitado: 3,
                        disponible: 1,
                        faltan: 2,
                    },
                ],
            })
        );

        const { onConsumed } = renderPanel();

        fireEvent.change(await screen.findByLabelText('Cantidad de Pastillas de freno'), {
            target: { value: '3' },
        });
        fireEvent.click(screen.getByRole('button', { name: 'Registrar consumo' }));

        expect(
            await screen.findByText(
                'Stock insuficiente: Pastillas de freno (solicitado 3, disponible 1, faltan 2). No se descontó ningún repuesto.'
            )
        ).toBeInTheDocument();
        expect(inventarioService.getDisponibilidadOrden).toHaveBeenCalledTimes(2);
        expect(onConsumed).not.toHaveBeenCalled();
    });

    it('conserva la misma clave al reintentar tras una respuesta incierta', async () => {
        vi.mocked(inventarioService.consumir)
            .mockRejectedValueOnce({ isAxiosError: true })
            .mockResolvedValueOnce({ ordenId: 101, movimientos: [], repetido: true });

        renderPanel();

        fireEvent.change(await screen.findByLabelText('Cantidad de Pastillas de freno'), {
            target: { value: '1' },
        });
        fireEvent.click(screen.getByRole('button', { name: 'Registrar consumo' }));

        expect(await screen.findByText(/reintentar con los mismos datos es seguro/)).toBeInTheDocument();

        fireEvent.click(screen.getByRole('button', { name: 'Registrar consumo' }));

        expect(await screen.findByText('El consumo ya estaba registrado; no se descontó dos veces.')).toBeInTheDocument();
        const primeraClave = vi.mocked(inventarioService.consumir).mock.calls[0][2];
        const segundaClave = vi.mocked(inventarioService.consumir).mock.calls[1][2];
        expect(segundaClave).toBe(primeraClave);
    });

    it('avisa cuando la orden no tiene presupuesto aprobado', async () => {
        vi.mocked(inventarioService.getDisponibilidadOrden).mockRejectedValue(
            errorAxios(409, { detail: 'La orden 101 no tiene un presupuesto aprobado' })
        );

        renderPanel();

        expect(
            await screen.findByText(
                /La orden no tiene un presupuesto aprobado del que obtener los repuestos a consumir/
            )
        ).toBeInTheDocument();
    });

    it('permite reintentar cuando falla la carga de disponibilidad', async () => {
        vi.mocked(inventarioService.getDisponibilidadOrden)
            .mockRejectedValueOnce(errorAxios(500, { detail: 'Servicio no disponible' }))
            .mockResolvedValueOnce(disponibilidad);

        renderPanel();

        expect(
            await screen.findByText('No se pudo cargar la disponibilidad de repuestos')
        ).toBeInTheDocument();
        fireEvent.click(screen.getByRole('button', { name: 'Reintentar' }));

        expect(await screen.findByText('Pastillas de freno')).toBeInTheDocument();
    });

    it('avisa cuando ya no quedan repuestos por consumir', async () => {
        vi.mocked(inventarioService.getDisponibilidadOrden).mockResolvedValue({
            ...disponibilidad,
            repuestos: [{ ...disponibilidad.repuestos[0], requerido: 0 }],
        });

        renderPanel();

        expect(
            await screen.findByText(
                'No quedan repuestos pendientes de consumir del presupuesto aprobado.'
            )
        ).toBeInTheDocument();
    });
});
