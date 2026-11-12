import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { UmbralGeneral } from '@/domain/entities/Inventario';
import { inventarioService } from '@/infrastructure/api/InventarioService';
import { AdminThresholdPage } from './AdminThresholdPage';

vi.mock('@/infrastructure/api/InventarioService', () => ({
    inventarioService: {
        getUmbralGeneral: vi.fn(),
        getHistorialUmbral: vi.fn(),
        cambiarUmbralGeneral: vi.fn(),
    },
}));

const umbral = (over: Partial<UmbralGeneral> = {}): UmbralGeneral => ({
    umbralGeneral: 5,
    vigenteDesde: '2026-11-01T09:00:00-03:00',
    actualizadoPorId: 1,
    ...over,
});

function renderPage() {
    return render(<AdminThresholdPage />);
}

async function esperarFormulario() {
    return screen.findByLabelText('Nuevo umbral');
}

const escribirUmbral = async (valor: string) =>
    fireEvent.change(await esperarFormulario(), { target: { value: valor } });

const guardar = () => fireEvent.click(screen.getByRole('button', { name: 'Guardar' }));

function errorServidor(detail: string) {
    return {
        isAxiosError: true,
        response: { status: 422, data: { detail } },
    };
}

describe('AdminThresholdPage', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        vi.mocked(inventarioService.getUmbralGeneral).mockResolvedValue(umbral());
        vi.mocked(inventarioService.getHistorialUmbral).mockResolvedValue([]);
    });

    it('muestra umbral general', async () => {
        renderPage();

        expect(await screen.findByText('5')).toBeInTheDocument();
    });

    it('precarga el umbral vigente en el campo de edición', async () => {
        renderPage();

        expect(await esperarFormulario()).toHaveValue(5);
    });
});

describe('AdminThresholdPage: validaciones del formulario de umbral', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        vi.mocked(inventarioService.getUmbralGeneral).mockResolvedValue(umbral());
        vi.mocked(inventarioService.getHistorialUmbral).mockResolvedValue([]);
    });

    it.each(['-1', '2.5'])('rechaza "%s" sin llamar a la API', async (valor) => {
        renderPage();

        await escribirUmbral(valor);
        guardar();

        expect(
            await screen.findByText('Ingrese un entero mayor o igual a 0.')
        ).toBeInTheDocument();
        expect(inventarioService.cambiarUmbralGeneral).not.toHaveBeenCalled();
    });

    it('rechaza un campo vacío en vez de interpretarlo como umbral 0', async () => {
        renderPage();

        await escribirUmbral('');
        guardar();

        expect(
            await screen.findByText('Ingrese un entero mayor o igual a 0.')
        ).toBeInTheDocument();
        expect(inventarioService.cambiarUmbralGeneral).not.toHaveBeenCalled();
    });

    it('acepta el valor límite 0', async () => {
        vi.mocked(inventarioService.cambiarUmbralGeneral).mockResolvedValue(umbral({ umbralGeneral: 0 }));
        renderPage();

        await escribirUmbral('0');
        guardar();

        await waitFor(() =>
            expect(inventarioService.cambiarUmbralGeneral).toHaveBeenCalledWith({
                umbralGeneral: 0,
                observacion: null,
            })
        );
    });

    it('envía la observación cuando se escribe', async () => {
        vi.mocked(inventarioService.cambiarUmbralGeneral).mockResolvedValue(umbral({ umbralGeneral: 8 }));
        renderPage();

        await escribirUmbral('8');
        fireEvent.change(screen.getByLabelText('Observación'), {
            target: { value: 'Ajuste por inventario físico' },
        });
        guardar();

        await waitFor(() =>
            expect(inventarioService.cambiarUmbralGeneral).toHaveBeenCalledWith({
                umbralGeneral: 8,
                observacion: 'Ajuste por inventario físico',
            })
        );
    });

    it('muestra el mensaje del servidor y conserva el umbral vigente', async () => {
        vi.mocked(inventarioService.cambiarUmbralGeneral).mockRejectedValue(
            errorServidor('El umbral debe ser un entero mayor o igual a 0.')
        );
        renderPage();

        await escribirUmbral('3');
        guardar();

        expect(
            await screen.findByText('El umbral debe ser un entero mayor o igual a 0.')
        ).toBeInTheDocument();
        expect(screen.getByText('5')).toBeInTheDocument();
    });

    it('no envía el formulario dos veces mientras guarda', async () => {
        let resolver: (valor: UmbralGeneral) => void = () => {};
        vi.mocked(inventarioService.cambiarUmbralGeneral).mockImplementation(
            () => new Promise<UmbralGeneral>((r) => (resolver = r))
        );
        renderPage();

        await escribirUmbral('6');
        const formulario = (await esperarFormulario()).closest('form') as HTMLFormElement;
        fireEvent.submit(formulario);
        fireEvent.submit(formulario);

        expect(screen.getByRole('button', { name: 'Guardando...' })).toBeDisabled();
        expect(inventarioService.cambiarUmbralGeneral).toHaveBeenCalledTimes(1);
        resolver(umbral({ umbralGeneral: 6 }));
        await waitFor(() =>
            expect(screen.getByRole('button', { name: 'Guardar' })).toBeEnabled()
        );
    });
});
