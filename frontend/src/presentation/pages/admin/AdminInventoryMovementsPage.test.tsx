import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import type { Movimiento, ResultadoMovimiento } from '@/domain/entities/Inventario';
import { inventarioService } from '@/infrastructure/api/InventarioService';
import { AdminInventoryMovementsPage } from './AdminInventoryMovementsPage';

vi.mock('@/infrastructure/api/InventarioService', () => ({
    inventarioService: { listMovimientos: vi.fn(), registrarMovimiento: vi.fn() },
}));

const MOVIMIENTO: Movimiento = {
    movimientoId: 1,
    claveOperacion: 'k',
    repuestoId: 2,
    tipo: 'ingreso',
    cantidad: 5,
    ordenId: null,
    proveedorId: null,
    fechaHora: '2026-01-01T00:00:00Z',
    registradoPorId: 1,
};

const RESULTADO: ResultadoMovimiento = {
    movimiento: MOVIMIENTO,
    stock: {
        repuestoId: 2,
        nombre: 'Filtro',
        proveedorNombre: 'Proveedor',
        stock: 5,
        comprometido: 0,
        disponible: 5,
        umbralEfectivo: null,
        bajoUmbral: false,
        compromisos: [],
    },
    alerta: { activa: false, nueva: false },
    repetido: false,
};

const pagina = (movimientos: Movimiento[]) => ({
    total: movimientos.length,
    desde: 0,
    limite: 50,
    movimientos,
});

async function abrirFormulario() {
    fireEvent.click(screen.getByRole('button', { name: 'Registrar movimiento' }));
    return screen.findByRole('dialog', { name: 'Registrar movimiento' });
}

function escribirEn(dialog: HTMLElement, label: string | RegExp, value: string) {
    fireEvent.change(within(dialog).getByLabelText(label), { target: { value } });
}

function submit(dialog: HTMLElement) {
    fireEvent.click(within(dialog).getByRole('button', { name: 'Registrar' }));
}

describe('AdminInventoryMovementsPage', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        vi.mocked(inventarioService.listMovimientos).mockResolvedValue(pagina([MOVIMIENTO]));
        vi.mocked(inventarioService.registrarMovimiento).mockResolvedValue(RESULTADO);
        vi.stubGlobal('crypto', { randomUUID: () => 'uuid-fijo' });
    });

    afterEach(() => {
        vi.unstubAllGlobals();
    });

    it('lista movimientos', async () => {
        render(<AdminInventoryMovementsPage />);

        expect(await screen.findByText('ingreso')).toBeInTheDocument();
    });

    it('muestra vacío cuando no hay movimientos', async () => {
        vi.mocked(inventarioService.listMovimientos).mockResolvedValue(pagina([]));
        render(<AdminInventoryMovementsPage />);

        expect(await screen.findByText('No hay movimientos')).toBeInTheDocument();
    });
});

describe('AdminInventoryMovementsPage: formulario de registro', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        vi.mocked(inventarioService.listMovimientos).mockResolvedValue(pagina([]));
        vi.mocked(inventarioService.registrarMovimiento).mockResolvedValue(RESULTADO);
        vi.stubGlobal('crypto', { randomUUID: () => 'uuid-fijo' });
    });

    afterEach(() => {
        vi.unstubAllGlobals();
    });

    it('abre el diálogo con sus campos y el tipo ingreso por defecto', async () => {
        render(<AdminInventoryMovementsPage />);
        await screen.findByText('No hay movimientos');

        const dialog = await abrirFormulario();

        expect(within(dialog).getByLabelText('Repuesto ID')).toBeInTheDocument();
        expect(within(dialog).getByLabelText('Cantidad')).toBeInTheDocument();
        expect(within(dialog).getByLabelText('Tipo')).toHaveValue('ingreso');
        expect(within(dialog).getByLabelText('Orden ID (opcional)')).toBeInTheDocument();
        expect(within(dialog).getByLabelText('Proveedor ID (opcional)')).toBeInTheDocument();
    });

    it.each(['', '0', '-2'])(
        'rechaza el repuesto "%s" sin llamar a la API',
        async (repuesto) => {
            render(<AdminInventoryMovementsPage />);
            await screen.findByText('No hay movimientos');
            const dialog = await abrirFormulario();

            escribirEn(dialog, 'Repuesto ID', repuesto);
            escribirEn(dialog, 'Cantidad', '5');
            submit(dialog);

            expect(await within(dialog).findByText('Repuesto inválido.')).toBeInTheDocument();
            expect(inventarioService.registrarMovimiento).not.toHaveBeenCalled();
        }
    );

    it('rechaza una cantidad cero sin llamar a la API', async () => {
        render(<AdminInventoryMovementsPage />);
        await screen.findByText('No hay movimientos');
        const dialog = await abrirFormulario();

        escribirEn(dialog, 'Repuesto ID', '2');
        escribirEn(dialog, 'Cantidad', '0');
        submit(dialog);

        expect(await within(dialog).findByText('Cantidad inválida.')).toBeInTheDocument();
        expect(inventarioService.registrarMovimiento).not.toHaveBeenCalled();
    });

    it('registra el movimiento con una clave de operación y sin referencias opcionales', async () => {
        render(<AdminInventoryMovementsPage />);
        await screen.findByText('No hay movimientos');
        const dialog = await abrirFormulario();

        escribirEn(dialog, 'Repuesto ID', '2');
        escribirEn(dialog, 'Cantidad', '5');
        submit(dialog);

        await waitFor(() =>
            expect(inventarioService.registrarMovimiento).toHaveBeenCalledWith({
                claveOperacion: 'uuid-fijo',
                repuestoId: 2,
                tipo: 'ingreso',
                cantidad: 5,
                ordenId: null,
                proveedorId: null,
            })
        );
        await waitFor(() =>
            expect(screen.queryByRole('dialog', { name: 'Registrar movimiento' })).not.toBeInTheDocument()
        );
        // Se recarga el historial después de registrar.
        expect(inventarioService.listMovimientos).toHaveBeenCalledTimes(2);
    });

    it('envía orden y proveedor como números cuando se informan', async () => {
        render(<AdminInventoryMovementsPage />);
        await screen.findByText('No hay movimientos');
        const dialog = await abrirFormulario();

        escribirEn(dialog, 'Repuesto ID', '7');
        fireEvent.change(within(dialog).getByLabelText('Tipo'), { target: { value: 'ajuste' } });
        escribirEn(dialog, 'Cantidad', '-3');
        escribirEn(dialog, 'Orden ID (opcional)', '55');
        escribirEn(dialog, 'Proveedor ID (opcional)', '4');
        submit(dialog);

        await waitFor(() =>
            expect(inventarioService.registrarMovimiento).toHaveBeenCalledWith(
                expect.objectContaining({
                    repuestoId: 7,
                    tipo: 'ajuste',
                    cantidad: -3,
                    ordenId: 55,
                    proveedorId: 4,
                })
            )
        );
    });

    it('muestra el error del servidor y deja el diálogo abierto', async () => {
        vi.mocked(inventarioService.registrarMovimiento).mockRejectedValue({
            isAxiosError: true,
            response: { status: 409, data: { detail: 'Stock insuficiente para el repuesto.' } },
        });
        render(<AdminInventoryMovementsPage />);
        await screen.findByText('No hay movimientos');
        const dialog = await abrirFormulario();

        escribirEn(dialog, 'Repuesto ID', '2');
        escribirEn(dialog, 'Cantidad', '5');
        submit(dialog);

        expect(
            await within(dialog).findByText('Stock insuficiente para el repuesto.')
        ).toBeInTheDocument();
        expect(screen.getByRole('dialog', { name: 'Registrar movimiento' })).toBeInTheDocument();
    });
});

describe('AdminInventoryMovementsPage: modo mecánico', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        vi.mocked(inventarioService.listMovimientos).mockResolvedValue(pagina([]));
        vi.mocked(inventarioService.registrarMovimiento).mockResolvedValue(RESULTADO);
        vi.stubGlobal('crypto', { randomUUID: () => 'uuid-fijo' });
    });

    afterEach(() => {
        vi.unstubAllGlobals();
    });

    it('solo ofrece compromiso, consumo y liberación, y exige la orden asignada', async () => {
        render(<AdminInventoryMovementsPage mode="mechanic" />);
        await screen.findByText('No hay movimientos');

        const dialog = await abrirFormulario();

        expect(within(dialog).getByLabelText('Tipo')).toHaveValue('compromiso');
        const opciones = within(dialog)
            .getAllByRole('option')
            .map((opcion) => (opcion as HTMLOptionElement).value);
        expect(opciones).toEqual(['compromiso', 'consumo', 'liberacion']);
        expect(within(dialog).getByLabelText('Orden asignada (obligatoria)')).toBeInTheDocument();
        expect(within(dialog).queryByLabelText('Proveedor ID (opcional)')).not.toBeInTheDocument();
    });

    it('no registra el movimiento si falta la orden asignada', async () => {
        render(<AdminInventoryMovementsPage mode="mechanic" />);
        await screen.findByText('No hay movimientos');
        const dialog = await abrirFormulario();

        escribirEn(dialog, 'Repuesto ID', '2');
        escribirEn(dialog, 'Cantidad', '5');
        submit(dialog);

        expect(
            await within(dialog).findByText(
                'Indica la orden asignada a la que pertenece el movimiento.'
            )
        ).toBeInTheDocument();
        expect(inventarioService.registrarMovimiento).not.toHaveBeenCalled();
    });

    it('registra el movimiento de la orden sin proveedor', async () => {
        render(<AdminInventoryMovementsPage mode="mechanic" />);
        await screen.findByText('No hay movimientos');
        const dialog = await abrirFormulario();

        escribirEn(dialog, 'Repuesto ID', '2');
        escribirEn(dialog, 'Cantidad', '5');
        escribirEn(dialog, 'Orden asignada (obligatoria)', '12');
        submit(dialog);

        await waitFor(() =>
            expect(inventarioService.registrarMovimiento).toHaveBeenCalledWith({
                claveOperacion: 'uuid-fijo',
                repuestoId: 2,
                tipo: 'compromiso',
                cantidad: 5,
                ordenId: 12,
                proveedorId: null,
            })
        );
    });
});
