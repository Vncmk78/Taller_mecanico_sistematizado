import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { Proveedor } from '@/domain/entities/Proveedor';
import type { Repuesto } from '@/domain/entities/Repuesto';
import { RepuestoFormDialog } from './RepuestoFormDialog';

const PROVEEDORES: Proveedor[] = [
    {
        proveedorId: 1,
        nombre: 'Distribuidora Uno',
        contacto: 'ventas@uno.cl',
        tipoDistribuidor: 'oficial',
        cantidadRepuestos: 0,
    },
    {
        proveedorId: 2,
        nombre: 'Repuestos Dos',
        contacto: 'ventas@dos.cl',
        tipoDistribuidor: 'generico',
        cantidadRepuestos: 0,
    },
];

const REPUESTO: Repuesto = {
    repuestoId: 9,
    nombre: 'Filtro de aceite',
    proveedorId: 2,
    proveedorNombre: 'Repuestos Dos',
    proveedorTipoDistribuidor: 'generico',
    stock: 30,
    umbralParticular: 4,
    umbralEfectivo: 4,
    bajoUmbral: false,
};

interface SetupOverrides {
    open?: boolean;
    initial?: Repuesto | null;
    proveedores?: Proveedor[];
    isSubmitting?: boolean;
    error?: string | null;
}

function setup(overrides: SetupOverrides = {}) {
    const onSubmit = vi.fn();
    const onClose = vi.fn();
    render(
        <RepuestoFormDialog
            open
            proveedores={PROVEEDORES}
            onSubmit={onSubmit}
            onClose={onClose}
            {...overrides}
        />
    );
    return { onSubmit, onClose };
}

const escribir = (label: string | RegExp, value: string) =>
    fireEvent.change(screen.getByLabelText(label), { target: { value } });

const enviar = () => fireEvent.click(screen.getByRole('button', { name: /Crear|Guardar/ }));

describe('RepuestoFormDialog: visibilidad y campos del formulario', () => {
    it('no renderiza nada cuando está cerrado', () => {
        setup({ open: false });

        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('expone el diálogo y todos los campos de un repuesto nuevo', () => {
        setup();

        expect(screen.getByRole('dialog', { name: 'Nuevo repuesto' })).toBeInTheDocument();
        expect(screen.getByLabelText('Nombre')).toBeInTheDocument();
        expect(screen.getByLabelText('Proveedor')).toBeInTheDocument();
        expect(screen.getByLabelText('Stock inicial')).toBeInTheDocument();
        expect(screen.getByLabelText('Umbral particular (vacío = general)')).toBeInTheDocument();
    });

    it('sugiere el primer proveedor disponible', () => {
        setup();

        expect(screen.getByLabelText('Proveedor')).toHaveValue('1');
    });
});

describe('RepuestoFormDialog: validaciones de campos obligatorios', () => {
    it('rechaza el nombre vacío sin llamar a onSubmit', async () => {
        const { onSubmit } = setup();

        enviar();

        expect(await screen.findByText('Ingrese el nombre')).toBeInTheDocument();
        expect(onSubmit).not.toHaveBeenCalled();
    });

    it('rechaza un nombre que solo contiene espacios', async () => {
        const { onSubmit } = setup();

        escribir('Nombre', '   ');
        enviar();

        expect(await screen.findByText('Ingrese el nombre')).toBeInTheDocument();
        expect(onSubmit).not.toHaveBeenCalled();
    });

    it('marca el nombre inválido para lectores de pantalla', async () => {
        setup();

        enviar();

        await screen.findByText('Ingrese el nombre');
        const nombre = screen.getByLabelText('Nombre');
        expect(nombre).toHaveAttribute('aria-invalid', 'true');

        const errorId = nombre.getAttribute('aria-describedby');
        expect(errorId).toBeTruthy();
        expect(document.getElementById(errorId as string)).toHaveTextContent('Ingrese el nombre');
    });

    it('rechaza el nombre de más de 120 caracteres', async () => {
        const { onSubmit } = setup();

        escribir('Nombre', 'R'.repeat(121));
        enviar();

        expect(await screen.findByText('Máximo 120 caracteres')).toBeInTheDocument();
        expect(onSubmit).not.toHaveBeenCalled();
    });

    it('acepta un nombre de exactamente 120 caracteres', async () => {
        const { onSubmit } = setup();
        const nombre = 'R'.repeat(120);

        escribir('Nombre', nombre);
        enviar();

        await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
        expect(onSubmit).toHaveBeenCalledWith(
            expect.objectContaining({ nombre })
        );
    });

    it('recorta los espacios exteriores del nombre antes de enviarlo', async () => {
        const { onSubmit } = setup();

        escribir('Nombre', '  Filtro de aire  ');
        enviar();

        await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
        expect(onSubmit).toHaveBeenCalledWith(
            expect.objectContaining({ nombre: 'Filtro de aire' })
        );
    });

    it('exige un proveedor cuando la lista está vacía', async () => {
        const { onSubmit } = setup({ proveedores: [] });

        escribir('Nombre', 'Bujía');
        enviar();

        expect(await screen.findByText('Seleccione un proveedor')).toBeInTheDocument();
        expect(onSubmit).not.toHaveBeenCalled();
    });
});

describe('RepuestoFormDialog: casos límite de stock y umbral', () => {
    it('rechaza un stock inicial negativo', async () => {
        const { onSubmit } = setup();

        escribir('Nombre', 'Bujía');
        escribir('Stock inicial', '-1');
        enviar();

        expect(await screen.findByText('Stock no puede ser negativo')).toBeInTheDocument();
        expect(onSubmit).not.toHaveBeenCalled();
    });

    it('rechaza un stock inicial con decimales', async () => {
        const { onSubmit } = setup();

        escribir('Nombre', 'Bujía');
        escribir('Stock inicial', '1.5');
        enviar();

        // El input numérico usa paso 1, así que la validación nativa frena el
        // envío antes de llegar a la API.
        expect(onSubmit).not.toHaveBeenCalled();
    });

    it('acepta stock inicial cero', async () => {
        const { onSubmit } = setup();

        escribir('Nombre', 'Bujía');
        escribir('Stock inicial', '0');
        enviar();

        await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
        expect(onSubmit).toHaveBeenCalledWith(
            expect.objectContaining({ stockInicial: 0 })
        );
    });

    it('rechaza un umbral particular negativo', async () => {
        const { onSubmit } = setup();

        escribir('Nombre', 'Bujía');
        escribir('Umbral particular (vacío = general)', '-3');
        enviar();

        expect(await screen.findByText('Umbral inválido')).toBeInTheDocument();
        expect(onSubmit).not.toHaveBeenCalled();
    });

    it('no envía un umbral particular con decimales', async () => {
        const { onSubmit } = setup();

        escribir('Nombre', 'Bujía');
        escribir('Umbral particular (vacío = general)', '1.5');
        enviar();

        // Igual que el stock, el paso 1 del input impide el envío.
        expect(onSubmit).not.toHaveBeenCalled();
    });

    it('envía el umbral vacío como null', async () => {
        const { onSubmit } = setup();

        escribir('Nombre', 'Bujía');
        enviar();

        await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
        expect(onSubmit).toHaveBeenCalledWith(
            expect.objectContaining({ umbralParticular: null })
        );
    });

    it('convierte el umbral escrito a número', async () => {
        const { onSubmit } = setup();

        escribir('Nombre', 'Bujía');
        escribir('Umbral particular (vacío = general)', '7');
        enviar();

        await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
        expect(onSubmit).toHaveBeenCalledWith(
            expect.objectContaining({ umbralParticular: 7 })
        );
    });
});

describe('RepuestoFormDialog: edición, estado de envío y error del servidor', () => {
    it('precarga los datos y oculta el stock inicial al editar', async () => {
        const { onSubmit } = setup({ initial: REPUESTO });

        expect(screen.getByRole('dialog', { name: 'Editar repuesto' })).toBeInTheDocument();
        expect(screen.getByLabelText('Nombre')).toHaveValue('Filtro de aceite');
        expect(screen.getByLabelText('Proveedor')).toHaveValue('2');
        expect(screen.getByLabelText('Umbral particular (vacío = general)')).toHaveValue(4);
        expect(screen.queryByLabelText('Stock inicial')).not.toBeInTheDocument();

        enviar();

        await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
        expect(onSubmit).toHaveBeenCalledWith({
            proveedorId: 2,
            nombre: 'Filtro de aceite',
            stockInicial: undefined,
            umbralParticular: 4,
        });
    });

    it('deshabilita el envío mientras se está guardando', () => {
        setup({ isSubmitting: true });

        expect(screen.getByRole('button', { name: 'Cargando...' })).toBeDisabled();
    });

    it('muestra el error del servidor sin cerrar el formulario', () => {
        setup({ error: 'No se pudo crear el repuesto.' });

        expect(screen.getByText('No se pudo crear el repuesto.')).toBeInTheDocument();
        expect(screen.getByRole('dialog', { name: 'Nuevo repuesto' })).toBeInTheDocument();
    });

    it('cierra el formulario al pulsar Cancelar', () => {
        const { onClose } = setup();

        fireEvent.click(screen.getByRole('button', { name: 'Cancelar' }));

        expect(onClose).toHaveBeenCalledTimes(1);
    });
});
