import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { Proveedor } from '@/domain/entities/Proveedor';
import { ProveedorFormDialog } from './ProveedorFormDialog';

const PROVEEDOR: Proveedor = {
    proveedorId: 3,
    nombre: 'Distribuidora Norte',
    contacto: 'contacto@norte.cl',
    tipoDistribuidor: 'oficial',
    cantidadRepuestos: 12,
};

interface SetupOverrides {
    open?: boolean;
    initial?: Proveedor | null;
    isSubmitting?: boolean;
    error?: string | null;
}

function setup(overrides: SetupOverrides = {}) {
    const onSubmit = vi.fn();
    const onClose = vi.fn();
    render(
        <ProveedorFormDialog
            open
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

describe('ProveedorFormDialog: visibilidad y campos del formulario', () => {
    it('no renderiza nada cuando está cerrado', () => {
        setup({ open: false });

        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('expone el diálogo y los campos de un proveedor nuevo', () => {
        setup();

        expect(screen.getByRole('dialog', { name: 'Nuevo proveedor' })).toBeInTheDocument();
        expect(screen.getByLabelText('Nombre')).toBeInTheDocument();
        expect(screen.getByLabelText('Contacto')).toBeInTheDocument();
        expect(screen.getByLabelText('Tipo')).toBeInTheDocument();
    });

    it('parte con el tipo genérico seleccionado', () => {
        setup();

        expect(screen.getByLabelText('Tipo')).toHaveValue('generico');
    });
});

describe('ProveedorFormDialog: validaciones de campos obligatorios', () => {
    it('rechaza nombre y contacto vacíos sin llamar a onSubmit', async () => {
        const { onSubmit } = setup();

        enviar();

        expect(await screen.findByText('Ingrese el nombre')).toBeInTheDocument();
        expect(screen.getByText('Ingrese el contacto')).toBeInTheDocument();
        expect(onSubmit).not.toHaveBeenCalled();
    });

    it('rechaza nombre y contacto compuestos solo por espacios', async () => {
        const { onSubmit } = setup();

        escribir('Nombre', '   ');
        escribir('Contacto', '   ');
        enviar();

        expect(await screen.findByText('Ingrese el nombre')).toBeInTheDocument();
        expect(screen.getByText('Ingrese el contacto')).toBeInTheDocument();
        expect(onSubmit).not.toHaveBeenCalled();
    });

    it('asocia los errores con sus campos para lectores de pantalla', async () => {
        setup();

        enviar();

        await screen.findByText('Ingrese el nombre');
        const nombre = screen.getByLabelText('Nombre');
        const contacto = screen.getByLabelText('Contacto');

        for (const campo of [nombre, contacto]) {
            expect(campo).toHaveAttribute('aria-invalid', 'true');
            const errorId = campo.getAttribute('aria-describedby');
            expect(errorId).toBeTruthy();
            expect(document.getElementById(errorId as string)).toHaveTextContent(/Ingrese el/);
        }
    });

    it('rechaza un nombre de más de 120 caracteres', async () => {
        const { onSubmit } = setup();

        escribir('Nombre', 'N'.repeat(121));
        escribir('Contacto', 'contacto@proveedor.cl');
        enviar();

        expect(await screen.findByText('Máximo 120 caracteres')).toBeInTheDocument();
        expect(onSubmit).not.toHaveBeenCalled();
    });

    it('rechaza un contacto de más de 200 caracteres', async () => {
        const { onSubmit } = setup();

        escribir('Nombre', 'Proveedor');
        escribir('Contacto', 'C'.repeat(201));
        enviar();

        expect(await screen.findByText('Máximo 200 caracteres')).toBeInTheDocument();
        expect(onSubmit).not.toHaveBeenCalled();
    });

    it('acepta los límites exactos de 120 y 200 caracteres', async () => {
        const { onSubmit } = setup();
        const nombre = 'N'.repeat(120);
        const contacto = 'C'.repeat(200);

        escribir('Nombre', nombre);
        escribir('Contacto', contacto);
        enviar();

        await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
        // handleSubmit entrega los valores como primer argumento y el evento como segundo.
        expect(onSubmit.mock.calls[0][0]).toEqual({
            nombre,
            contacto,
            tipoDistribuidor: 'generico',
        });
    });

    it('recorta los espacios exteriores antes de enviar', async () => {
        const { onSubmit } = setup();

        escribir('Nombre', '  Distribuidora Sur  ');
        escribir('Contacto', '  ventas@sur.cl  ');
        enviar();

        await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
        expect(onSubmit.mock.calls[0][0]).toEqual({
            nombre: 'Distribuidora Sur',
            contacto: 'ventas@sur.cl',
            tipoDistribuidor: 'generico',
        });
    });
});

describe('ProveedorFormDialog: tipo de distribuidor, edición y estado', () => {
    it('envía el tipo de distribuidor elegido', async () => {
        const { onSubmit } = setup();

        escribir('Nombre', 'Proveedor Oficial');
        escribir('Contacto', 'ventas@oficial.cl');
        fireEvent.change(screen.getByLabelText('Tipo'), { target: { value: 'oficial' } });
        enviar();

        await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
        expect(onSubmit.mock.calls[0][0]).toEqual(
            expect.objectContaining({ tipoDistribuidor: 'oficial' })
        );
    });

    it('precarga los datos del proveedor al editar', async () => {
        const { onSubmit } = setup({ initial: PROVEEDOR });

        expect(screen.getByRole('dialog', { name: 'Editar proveedor' })).toBeInTheDocument();
        expect(screen.getByLabelText('Nombre')).toHaveValue('Distribuidora Norte');
        expect(screen.getByLabelText('Contacto')).toHaveValue('contacto@norte.cl');
        expect(screen.getByLabelText('Tipo')).toHaveValue('oficial');

        enviar();

        await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
        expect(onSubmit.mock.calls[0][0]).toEqual({
            nombre: 'Distribuidora Norte',
            contacto: 'contacto@norte.cl',
            tipoDistribuidor: 'oficial',
        });
    });

    it('deshabilita el envío mientras se está guardando', () => {
        setup({ isSubmitting: true });

        expect(screen.getByRole('button', { name: 'Cargando...' })).toBeDisabled();
    });

    it('muestra el error del servidor sin cerrar el formulario', () => {
        setup({ error: 'No se pudo crear el proveedor.' });

        expect(screen.getByText('No se pudo crear el proveedor.')).toBeInTheDocument();
        expect(screen.getByRole('dialog', { name: 'Nuevo proveedor' })).toBeInTheDocument();
    });

    it('cierra el formulario al pulsar Cancelar', () => {
        const { onClose } = setup();

        fireEvent.click(screen.getByRole('button', { name: 'Cancelar' }));

        expect(onClose).toHaveBeenCalledTimes(1);
    });
});
